"""Week-2 stage: per-function LLM review over the scan's function inventory.

Input:  work/<id>/scan/functions.json (from `bughunter scan`)
Output: work/<id>/review/
          calls/<function>.json   one cached result per function (resumable)
          candidates.json         all suspected findings, ranked -> week-3 proof queue
          review.md               human summary
          manifest.json           model, effort, token usage, estimated cost
The benchmark ground truth is never read here."""
from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from bughunter.contest import Contest
from bughunter.review import prompts
from bughunter.review.schema import FunctionReview

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_SHARED_CONTEXT_CHARS = 400_000     # ~100k tokens; above this, per-file context

# USD per 1M tokens: input, output, cache read, 5-min cache write. Estimates only.
PRICES = {"claude-opus-5-5": (4.00, 20.00, 0.20, 5.00)}

RANK = {"high": 0, "medium": 1, "low": 2}


class ReviewAborted(RuntimeError):
    pass


def select_functions(inventory: list[dict], only: str | None = None) -> list[dict]:
    fns = [f for f in inventory if f["implemented"] and f.get("contract_kind") != "interface"]
    if only:
        fns = [f for f in fns if only.lower() in f["id"].lower()]
    # group by file so consecutive requests share the most cache
    return sorted(fns, key=lambda f: (f["file"], f["lines"][0]))


def build_context(contest: Contest, project: Path, fns: list[dict]) -> dict[str, str]:
    """file -> context string. One shared context when the scope is small enough."""
    files = {p: (project / p).read_text() for p in contest.scope.project_relative()}
    if sum(len(t) for t in files.values()) <= MAX_SHARED_CONTEXT_CHARS:
        shared = prompts.contest_context(contest, files)
        return {f["file"]: shared for f in fns}
    out = {}
    for path, text in files.items():
        parents = {name for clause in re.findall(r"\bis\s+([\w\s,]+?)\s*\{", text)
                   for name in re.findall(r"\w+", clause)}
        related = {p: t for p, t in files.items() if p == path or any(
            re.search(rf"\b(?:contract|interface|library)\s+{re.escape(c)}\b", t) for c in parents)}
        out[path] = prompts.contest_context(contest, related)
    return {f["file"]: out[f["file"]] for f in fns}


def request_params(model: str, effort: str, context: str, fn: dict) -> dict:
    return dict(
        model=model,
        max_tokens=16000,
        output_config={"effort": effort},
        system=[
            {"type": "text", "text": prompts.INSTRUCTIONS},
            {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": prompts.function_task(fn)}],
    )


def _key(params: dict) -> str:
    blob = json.dumps({"v": prompts.PROMPT_VERSION, **params}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)[:150]


def review_one(client, params: dict, fn: dict) -> dict:
    import anthropic

    t0 = time.time()
    rec = {"function_id": fn["id"], "requested_model": params["model"]}
    try:
        resp = client.beta.messages.parse(
            **params, output_format=FunctionReview,
            betas=[FALLBACK_BETA], fallbacks="default",
        )
    except anthropic.AuthenticationError as e:
        raise ReviewAborted(f"authentication failed: {e.message}") from e
    except anthropic.BadRequestError as e:
        return {**rec, "status": "error", "error": f"bad request: {e.message}"}
    except anthropic.APIStatusError as e:
        return {**rec, "status": "error", "error": f"API {e.status_code}: {e.message}"}
    except anthropic.APIConnectionError as e:
        return {**rec, "status": "error", "error": f"connection: {e}"}

    u = resp.usage
    rec.update({
        "served_model": resp.model, "stop_reason": resp.stop_reason, "elapsed_s": round(time.time() - t0, 1),
        "usage": {"input": u.input_tokens, "output": u.output_tokens,
                  "cache_read": u.cache_read_input_tokens or 0,
                  "cache_write": u.cache_creation_input_tokens or 0},
    })
    if resp.stop_reason == "refusal":
        cat = getattr(getattr(resp, "stop_details", None), "category", None)
        return {**rec, "status": "refused", "error": f"refusal ({cat})"}
    parsed = getattr(resp, "parsed_output", None)
    if parsed is None:
        return {**rec, "status": "error", "error": f"no parsed output (stop_reason={resp.stop_reason})"}
    return {**rec, "status": "ok", "review": parsed.model_dump()}


def run(contest: Contest, workdir: Path, *, client=None, model: str = DEFAULT_MODEL,
        effort: str = "high", only: str | None = None, limit: int | None = None,
        concurrency: int = 4, dry_run: bool = False, force: bool = False) -> Path:
    jobs, out = prepare(contest, workdir, model, effort, only, limit)

    if dry_run:
        chars = sum(len(prompts.INSTRUCTIONS) + len(p["system"][1]["text"]) +
                    len(p["messages"][0]["content"]) for _, p, _, _ in jobs)
        shared = len({p["system"][1]["text"] for _, p, _, _ in jobs})
        (out / "dry_run_example.json").write_text(json.dumps(jobs[0][1], indent=1) if jobs else "{}")
        print(f"dry run: {len(jobs)} functions, {shared} distinct cached context(s), "
              f"~{chars // 4:,} input tokens before caching (chars/4 estimate)")
        return out

    if client is None:
        import anthropic
        client = anthropic.Anthropic()

    todo = []
    for fn, params, path, key in jobs:
        if not force and path.exists():
            old = json.loads(path.read_text())
            if old.get("key") == key and old.get("status") == "ok":
                continue
        todo.append((fn, params, path, key))

    def work(job):
        fn, params, path, key = job
        rec = review_one(client, params, fn)
        rec["key"] = key
        path.write_text(json.dumps(rec, indent=1, default=str))
        return rec

    done = 0
    if todo:
        # warm each distinct cached context with one request before fanning out
        seen, first, rest = set(), [], []
        for j in todo:
            ctx = j[1]["system"][1]["text"]
            (rest if ctx in seen else first).append(j)
            seen.add(ctx)
        for j in first:
            _progress(work(j), done := done + 1, len(todo))
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
            for f in as_completed([ex.submit(work, j) for j in rest]):
                _progress(f.result(), done := done + 1, len(todo))

    records = [json.loads(p.read_text()) for _, _, p, _ in jobs if p.exists()]
    return _write_outputs(contest, out, records, model, effort, len(jobs))


def prepare(contest: Contest, workdir: Path, model: str, effort: str,
            only: str | None = None, limit: int | None = None) -> tuple[list, Path]:
    """Build (fn, request params, result path, cache key) for every selected function."""
    inv_path = workdir / contest.id / "scan" / "functions.json"
    if not inv_path.exists():
        raise FileNotFoundError(f"{inv_path} missing; run `bughunter scan` first")
    inventory = json.loads(inv_path.read_text())
    project = contest.project_root(workdir / contest.id / "repo")
    out = workdir / contest.id / "review"
    calls = out / "calls"
    calls.mkdir(parents=True, exist_ok=True)

    fns = select_functions(inventory, only)[:limit]
    contexts = build_context(contest, project, fns)
    jobs = []
    for fn in fns:
        params = request_params(model, effort, contexts[fn["file"]], fn)
        jobs.append((fn, params, calls / f"{_safe(fn['id'])}.json", _key(params)))
    return jobs, out


def finalize(contest: Contest, out: Path, jobs: list, model: str, effort: str) -> Path:
    records = [json.loads(p.read_text()) for _, _, p, _ in jobs if p.exists()]
    return _write_outputs(contest, out, records, model, effort, len(jobs))


def _progress(rec: dict, i: int, n: int) -> None:
    nf = len(rec.get("review", {}).get("findings", [])) if rec["status"] == "ok" else 0
    print(f"  [{i}/{n}] {rec['function_id']}: {rec['status']}"
          + (f", {nf} finding(s)" if rec["status"] == "ok" else f" ({rec.get('error')})"))


def cost(records: list[dict]) -> dict:
    tot = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    usd, priced = 0.0, True
    for r in records:
        u = r.get("usage")
        if not u:
            continue
        for k in tot:
            tot[k] += u[k]
        p = PRICES.get(r.get("served_model") or r.get("requested_model"))
        if p is None:
            priced = False
            continue
        usd += (u["input"] * p[0] + u["output"] * p[1] + u["cache_read"] * p[2]
                + u["cache_write"] * p[3]) / 1e6
    return {"tokens": tot, "usd_estimate": round(usd, 2) if priced else None}


def candidates_from(records: list[dict]) -> list[dict]:
    cands = []
    for r in records:
        if r.get("status") != "ok":
            continue
        for i, f in enumerate(r["review"]["findings"]):
            cands.append({"id": f"{r['function_id']}#{i}", "reviewed_function": r["function_id"],
                          "served_model": r.get("served_model"), **f})
    return sorted(cands, key=lambda c: (RANK[c["severity"]], RANK[c["confidence"]], c["id"]))


def _write_outputs(contest, out: Path, records: list[dict], model, effort, n_jobs) -> Path:
    cands = candidates_from(records)
    status = {}
    for r in records:
        status[r["status"]] = status.get(r["status"], 0) + 1
    c = cost(records)
    manifest = {
        "contest": contest.id, "prompt_version": prompts.PROMPT_VERSION, "model": model,
        "effort": effort, "functions_selected": n_jobs, "status": status,
        "fallback_served": sorted({r["served_model"] for r in records
                                   if r.get("served_model") and r["served_model"] != r["requested_model"]}),
        "candidates": len(cands),
        "by_severity": {s: sum(1 for x in cands if x["severity"] == s) for s in RANK},
        **c, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "candidates.json").write_text(json.dumps(cands, indent=2) + "\n")
    (out / "review.md").write_text(_markdown(contest, manifest, cands, records))
    return out


def _markdown(contest, m: dict, cands: list[dict], records: list[dict]) -> str:
    lines = [f"# LLM review: {contest.id}", "",
             f"- Model `{m['model']}` (effort {m['effort']}), prompt `{m['prompt_version']}`",
             f"- Functions: {m['functions_selected']} selected; status {m['status']}",
             f"- Candidates: {m['candidates']} ({m['by_severity']})",
             f"- Tokens: {m['tokens']}; estimated cost: "
             + (f"${m['usd_estimate']}" if m["usd_estimate"] is not None else "n/a"), "",
             "> Suspected bugs only. Nothing here is reported until a Foundry test confirms it (week 3).", ""]
    for c in cands:
        lines += [f"## [{c['severity'].upper()}/{c['confidence']}] {c['title']}", "",
                  f"- Category: {c['category']} | Functions: {', '.join(c['functions'])}",
                  f"- Root cause: {c['root_cause']}", f"- Impact: {c['impact']}",
                  "- Attack path:", *[f"  {i}. {s}" for i, s in enumerate(c["attack_path"], 1)],
                  f"- PoC plan: {c['poc_plan']}", ""]
    bad = [r for r in records if r["status"] != "ok"]
    if bad:
        lines += ["## Not reviewed", ""] + [f"- `{r['function_id']}`: {r['status']} {r.get('error', '')}"
                                            for r in bad]
    return "\n".join(lines) + "\n"
