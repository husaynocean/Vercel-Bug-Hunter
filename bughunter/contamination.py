"""Contamination check: did the model already know the answers?

The benchmark contests are past Code4rena contests whose findings have been
public on GitHub for years, so they are probably in the model's training data.
"Blind" in this repo means the answers were never in the prompt, not that the
model had never seen them. This module measures how much of the benchmark the
model can recite from memory, with no code at all, and re-scores the benchmark
without those findings.

Probes (no source code is ever sent):
  name   contest name, platform, month, URL
  files  the same plus the in-scope file list (a stronger cue, closer to what
         the reviewer sees)
  canary an invented contest in the same format. Any "certain" finding here
         means the model makes things up, so its other answers are less
         trustworthy (the result is marked unreliable).

A known High counts as "memorized" when a recalled finding names one of its
root-cause functions and has a similar title (or a very similar title alone).

Ground truth is read only when scoring (`score` / `clean_bench`), never when
building prompts. Output: work/<id>/memprobe/result.json
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import List, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from bughunter import benchmark
from bughunter.contest import Contest

PROBE_VERSION = 1
PROBES = ("name", "files", "canary")
CANARY_PROJECTS = ["Halcyon Vaults", "Meridian Lend", "Quillstone Swap", "Tidewater Staking",
                   "Orchard Perps", "Basalt Bridge", "Lumen Escrow", "Corvid Options"]

INSTRUCTIONS = """\
You are being tested on what you remember, not on auditing skill.

Below is a smart-contract audit contest. From memory only, list the
High-severity findings from its published report. For each one give the
finding id if you remember it, the title, the contract(s) and function(s)
involved, and the root cause in one sentence.

Rules:
- Do not guess. If you do not remember this contest or its findings, return an
  empty list. An empty list is a perfectly good answer.
- Set confidence to "certain" only for findings you actually remember, and to
  "vague" for half-remembered ones.
- Do not search the web or read any files. No source code is provided on purpose.
"""

MEM_THRESHOLD = 0.25        # title similarity needed together with a function match
TITLE_ONLY_THRESHOLD = 0.5  # title similarity that counts on its own
STOP = set("a an the of to in on for and or by is be can could may with from via when not no its it".split())


class Recalled(BaseModel):
    finding_id: str | None = Field(default=None, description="e.g. H-01, if remembered")
    title: str
    contracts: List[str] = []
    functions: List[str] = Field(default=[], description="Function names, as Contract.function or function")
    root_cause: str = ""
    confidence: Literal["certain", "vague"]


class ProbeAnswer(BaseModel):
    remembers_contest: bool
    findings: List[Recalled]


# ----------------------------------------------------------------- prompts

def _label(contest_file: Path, contest: Contest) -> str:
    first = contest_file.read_text().splitlines()[0]
    m = re.match(r"#\s*([^()]+\([^)]*\))", first)   # "# Code4rena -- Kelp DAO rsETH (Nov 2023). ..."
    return m.group(1).replace("--", "–").strip() if m else contest.id


def _month(contest_id: str) -> str | None:
    m = re.search(r"(\d{4})-(\d{2})", contest_id)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _canary(contest: Contest) -> str:
    i = int(hashlib.sha256(contest.id.encode()).hexdigest(), 16) % len(CANARY_PROJECTS)
    month = _month(contest.id) or "2024-01"
    return f"Code4rena – {CANARY_PROJECTS[i]} ({month})"


def build_prompts(contest_file: Path, contest: Contest) -> dict[str, str]:
    """probe -> user message. Never includes source code or ground truth."""
    label, month = _label(contest_file, contest), _month(contest.id)
    base = f"Contest: {label}\nPlatform: {contest.platform}\nMonth: {month}\n"
    if contest.url:
        base += f"Contest page: {contest.url}\n"
    base += f"Code repository: {contest.repo}\n"
    files = "In-scope files:\n" + "\n".join(f"- {f}" for f in contest.scope.files) + "\n"
    canary = _canary(contest)
    slug = re.sub(r"[^a-z0-9]+", "-", canary.split("–")[1].split("(")[0].strip().lower())
    return {
        "name": base,
        "files": base + files,
        "canary": (f"Contest: {canary}\nPlatform: code4rena\nMonth: {month}\n"
                   f"Contest page: https://code4rena.com/audits/{month}-{slug}\n"),
    }


def _key(model: str, prompt: str) -> str:
    return hashlib.sha256(json.dumps([PROBE_VERSION, model, INSTRUCTIONS, prompt]).encode()).hexdigest()[:16]


# ----------------------------------------------------------------- running

def run(contest_file: Path, workdir: Path, *, client=None, model: str = "claude-opus-5-5",
        effort: str = "high") -> Path:
    contest = Contest.load(contest_file)
    out = workdir / contest.id / "memprobe"
    out.mkdir(parents=True, exist_ok=True)
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    for probe, prompt in build_prompts(contest_file, contest).items():
        path, key = out / f"{probe}.json", _key(model, prompt)
        if path.exists() and json.loads(path.read_text()).get("key") == key:
            continue
        rec = {"probe": probe, "model": model, "key": key}
        try:
            resp = client.beta.messages.parse(
                model=model, max_tokens=4000, output_config={"effort": effort},
                system=INSTRUCTIONS, messages=[{"role": "user", "content": prompt}],
                output_format=ProbeAnswer)
            parsed = getattr(resp, "parsed_output", None)
            rec.update(status="ok", answer=parsed.model_dump()) if parsed else rec.update(
                status="error", error=f"no parsed output ({resp.stop_reason})")
        except Exception as e:  # recorded, not fatal
            rec.update(status="error", error=str(e)[:300])
        path.write_text(json.dumps(rec, indent=1))
    return _finish(contest, out)


PACKET_README = """\
# Memory probe packet

For each file in `tasks/`: read `instructions.md` and the task, then answer
from memory only. Write JSON to `answers/<task name>.json` matching `schema.json`.

Do not search the web, open links or read any other files. If you do not
remember a contest, answer {"remembers_contest": false, "findings": []}.
"""


def export(contest_file: Path, dest: Path) -> Path:
    """No-API mode: write the probes for a fresh agent with no web access."""
    contest = Contest.load(contest_file)
    dest = dest.resolve()
    repo_root = Path(__file__).resolve().parents[1]
    if dest == repo_root or repo_root in dest.parents:
        raise ValueError("export outside the repository (it holds the benchmark answers)")
    (dest / "tasks").mkdir(parents=True, exist_ok=True)
    (dest / "answers").mkdir(exist_ok=True)
    (dest / "instructions.md").write_text(INSTRUCTIONS)
    (dest / "schema.json").write_text(json.dumps(ProbeAnswer.model_json_schema(), indent=1))
    (dest / "README.md").write_text(PACKET_README)
    for probe, prompt in build_prompts(contest_file, contest).items():
        (dest / "tasks" / f"{contest.id}--{probe}.md").write_text(prompt)
    return dest


def import_answers(contest_file: Path, workdir: Path, src: Path) -> Path:
    contest = Contest.load(contest_file)
    out = workdir / contest.id / "memprobe"
    out.mkdir(parents=True, exist_ok=True)
    for probe, prompt in build_prompts(contest_file, contest).items():
        ans = src / "answers" / f"{contest.id}--{probe}.json"
        rec = {"probe": probe, "model": "claude-code-manual", "key": _key("manual", prompt)}
        if not ans.exists():
            rec.update(status="missing")
        else:
            try:
                rec.update(status="ok", answer=ProbeAnswer.model_validate_json(ans.read_text()).model_dump())
            except ValidationError as e:
                rec.update(status="error", error=f"invalid answer: {str(e)[:300]}")
        (out / f"{probe}.json").write_text(json.dumps(rec, indent=1))
    return _finish(contest, out)


# ----------------------------------------------------------------- scoring

def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", s).lower())
            if w not in STOP and len(w) > 1}


def similarity(a: str, b: str) -> float:
    x, y = _tokens(a), _tokens(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def _fn_names(names: list[str]) -> set[str]:
    return {benchmark._fn_key(n)[1].lower() for n in names if n}


def match(truth_finding: dict, recalled: list[dict]) -> dict | None:
    """The best recalled finding that matches a known one, or None."""
    target_fns = {fn.lower() for _, fn in benchmark._targets(truth_finding)}
    best = None
    for r in recalled:
        sim = max(similarity(truth_finding["title"], r["title"]),
                  similarity(truth_finding["title"], r.get("root_cause", "")))
        fn_hit = bool(target_fns & _fn_names(r.get("functions", [])))
        if (fn_hit and sim >= MEM_THRESHOLD) or sim >= TITLE_ONLY_THRESHOLD:
            if best is None or sim > best[0]:
                best = (sim, r, fn_hit)
    if best is None:
        return None
    sim, r, fn_hit = best
    return {"recalled_title": r["title"], "similarity": round(sim, 2),
            "function_match": fn_hit, "confidence": r["confidence"]}


def score(contest: Contest, probes: dict[str, dict], truth: dict) -> dict:
    highs = [t for t in truth["findings"] if t["severity"] == "high"]
    rows = []
    for t in highs:
        hits = {p: match(t, probes[p]["answer"]["findings"])
                for p in ("name", "files") if probes.get(p, {}).get("status") == "ok"}
        hits = {p: h for p, h in hits.items() if h}
        rows.append({"id": t["id"], "title": t["title"], "memorized": bool(hits), "evidence": hits})
    canary = probes.get("canary", {})
    canary_certain = sum(1 for f in canary.get("answer", {}).get("findings", [])
                         if f["confidence"] == "certain") if canary.get("status") == "ok" else None
    n = len(rows)
    mem = sum(r["memorized"] for r in rows)
    return {
        "contest": contest.id, "highs": n, "memorized": mem,
        "memorized_share": round(mem / n, 2) if n else None,
        "remembers_contest": any(probes.get(p, {}).get("answer", {}).get("remembers_contest")
                                 for p in ("name", "files")),
        "canary_certain_findings": canary_certain,
        "reliable": canary_certain == 0 if canary_certain is not None else None,
        "findings": rows,
    }


def _finish(contest: Contest, out: Path) -> Path:
    probes = {p: json.loads((out / f"{p}.json").read_text()) for p in PROBES if (out / f"{p}.json").exists()}
    truth_file = Path(__file__).resolve().parents[1] / "benchmarks" / "truth" / f"{contest.id}.yaml"
    res = score(contest, probes, yaml.safe_load(truth_file.read_text()))
    (out / "result.json").write_text(json.dumps(res, indent=1))
    return out


def clean_bench(contest_files: list[Path], workdir: Path, cutoff: str | None = None) -> dict:
    """Benchmark recall with and without memorized Highs, per contest and in total.

    A contest from after `cutoff` (YYYY-MM, the model's training cutoff) is
    clean by date and needs no probe."""
    rows, tot = [], {"highs": 0, "found": 0, "clean_highs": 0, "clean_found": 0}
    for cf in contest_files:
        contest = Contest.load(cf)
        truth_file = Path(__file__).resolve().parents[1] / "benchmarks" / "truth" / f"{contest.id}.yaml"
        scan = workdir / contest.id / "scan"
        if not truth_file.exists() or not (scan / "functions.json").exists():
            rows.append({"contest": contest.id, "status": "no scan or truth"})
            continue
        b = benchmark.score(scan, truth_file)
        conf = b.get("confirmed_judged") or b.get("confirmed")
        found = {r["id"] for r in (conf or {}).get("findings", []) if r["candidate_hit"]}
        month = _month(contest.id)
        post = bool(cutoff and month and month > cutoff)
        mp = workdir / contest.id / "memprobe" / "result.json"
        if post:
            mem, status = set(), "after cutoff: clean by date"
        elif mp.exists():
            r = json.loads(mp.read_text())
            mem = {x["id"] for x in r["findings"] if x["memorized"]}
            status = "probed" + ("" if r["reliable"] is not False else " (canary failed: unreliable)")
        else:
            rows.append({"contest": contest.id, "status": "not probed: run `bughunter memprobe`"})
            continue
        highs = {x["id"] for x in b["findings"]}
        clean = highs - mem
        row = {"contest": contest.id, "status": status, "highs": len(highs), "found": len(found & highs),
               "memorized": sorted(mem), "clean_highs": len(clean), "clean_found": len(found & clean)}
        rows.append(row)
        for k in tot:
            tot[k] += row[k]
    pct = lambda a, b: f"{a}/{b} ({round(100 * a / b)}%)" if b else "n/a"
    return {"contests": rows,
            "recall_all": pct(tot["found"], tot["highs"]),
            "recall_excluding_memorized": pct(tot["clean_found"], tot["clean_highs"])}
