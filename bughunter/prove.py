"""Week-3 proof step: every review candidate needs a Foundry PoC.

A candidate is CONFIRMED only if, run by this module in a clean checkout:
  1. its PoC test passes against the unmodified in-scope code, and
  2. the same test FAILS once the proposed fix patch is applied.
Check 2 stops tests that "pass" without exercising the bug. Only confirmed
candidates reach the report draft.

PoCs are written by an agent from an exported packet (no-API mode, like the
review): `export` copies the contest project (with deps) plus one brief per
candidate; the agent writes project/test/bughunter/<cid>.t.sol and
answers/<cid>.patch / <cid>.json. `run` never trusts the agent's claims: it
copies only the test file into the clean contest repo and re-runs everything."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from bughunter import toolchain
from bughunter.contest import Contest

POC_DIR = "test/bughunter"

README = """\
# Proof-of-concept packet

`project/` is a full copy of the contest's Foundry project, dependencies
included. Run `forge test --offline --match-path test/bughunter/<cid>.t.sol -vvv`
inside it. Foundry is at /root/.foundry/bin/forge.

For each brief in `candidates/` (cid = file name without .md):

1. **Reproduce.** Write `project/test/bughunter/<cid>.t.sol` with a contract named
   `PoC_<cid>` and one or more functions named `test_poc...`. The test must
   PASS when the bug is present, and its assertions must show the impact
   (e.g. funds lost or locked, wrong balance, unexpected revert), not merely
   that code runs. Reuse the project's existing test setup and mocks under
   `project/test/` where they exist and fit; otherwise write minimal mocks in the
   test file. Use the real in-scope contracts from `project/src/`.
   Mocks are fine only for out-of-scope dependencies, and only behaving as the
   contest README allows (see `contest.md`). Never edit files in `project/src/`.
2. **Fix.** Write `answers/<cid>.patch`: a minimal unified diff
   (`--- a/src/...` / `+++ b/src/...`, paths relative to `project/`) that fixes
   the root cause. With the fix applied, your test must still COMPILE and must
   FAIL (an assertion or expected-revert failure, not a compile error). If the
   natural fix changes a signature (e.g. adds a slippage parameter), keep the old
   signature working (e.g. add an overload) so the test compiles. Check this by
   applying it (`git apply` or `patch -p1` inside `project/`), running the test,
   then reverting `project/src/` exactly.
3. **Report.** Write `answers/<cid>.json`:
   `{"cid": "<cid>", "status": "reproduced" | "not_reproduced", "notes": "<one paragraph>"}`.
   If the bug is not real, or cannot be shown under the contest's rules, say
   `not_reproduced` and explain. That is a useful result, not a failure.

Use only files in this packet. Do not search the web or read other paths.
"""


def _cid(i: int) -> str:
    return f"c{i:02d}"


def load_candidates(workdir: Path, contest: Contest) -> list[dict]:
    path = workdir / contest.id / "review" / "candidates.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run the review first")
    cands = json.loads(path.read_text())
    for i, c in enumerate(cands):
        c["cid"] = _cid(i)
    return cands


def export(contest: Contest, workdir: Path, dest: Path, cids: list[str] | None = None) -> dict:
    project = contest.project_root(workdir / contest.id / "repo")
    dest = dest.resolve()
    root = Path(__file__).resolve().parents[1]
    if dest == root or root in dest.parents:
        raise ValueError("export outside the repository (it contains benchmark answers)")
    cands = [c for c in load_candidates(workdir, contest) if not cids or c["cid"] in cids]
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "candidates").mkdir(parents=True)
    (dest / "answers").mkdir()
    shutil.copytree(project, dest / "project", symlinks=True,
                    ignore=shutil.ignore_patterns(".git", "out", "cache", "broadcast"))
    (dest / "project" / POC_DIR).mkdir(parents=True, exist_ok=True)
    for c in cands:
        brief = {k: c[k] for k in ("cid", "title", "category", "severity", "functions", "root_cause",
                                   "attack_path", "preconditions", "impact", "poc_plan")}
        (dest / "candidates" / f"{c['cid']}.md").write_text(
            f"# {c['cid']}: {c['title']}\n\n```json\n{json.dumps(brief, indent=1)}\n```\n")
    (dest / "contest.md").write_text(
        f"# {contest.id}\n\nIn scope:\n" + "\n".join(f"- {f}" for f in contest.scope.project_relative())
        + f"\n\nNotes: {contest.notes}\n\nOut of scope:\n"
        + "\n".join(f"- {x}" for x in contest.out_of_scope) + "\n")
    (dest / "README.md").write_text(README)
    (dest / ".index.json").write_text(json.dumps({c["cid"]: c["id"] for c in cands}, indent=1))
    return {"dest": str(dest), "candidates": [c["cid"] for c in cands]}


# ---------------------------------------------------------------- verification
def _forge_test(project: Path, rel_test: str) -> tuple[bool, str]:
    r = subprocess.run(["forge", "test", "--offline", "--match-path", rel_test, "-vvv"],
                       cwd=project, capture_output=True, text=True, env=toolchain.env(), timeout=900)
    out = (r.stdout + r.stderr)[-12000:]
    ran_poc = re.search(r"\[PASS\][^\n]*test_poc|\[FAIL[^\n]*test_poc", out) is not None
    passed = r.returncode == 0 and re.search(r"\[PASS\][^\n]*test_poc", out) is not None
    if not ran_poc:
        return False, "NO_POC_TEST_RAN\n" + out
    return passed, out


def _patch_files(patch: str) -> list[str]:
    return sorted({m.group(1) for m in re.finditer(r"^\+\+\+ b/(\S+)", patch, re.M)})


def verify(contest: Contest, workdir: Path, cid: str, test_src: str, patch: str | None) -> dict:
    repo = workdir / contest.id / "repo"
    project = contest.project_root(repo)
    rel_test = f"{POC_DIR}/{cid}.t.sol"
    poc_dir = project / POC_DIR
    if poc_dir.exists():
        shutil.rmtree(poc_dir)  # exactly one PoC compiled at a time
    poc_dir.mkdir(parents=True)
    (project / rel_test).write_text(test_src)
    res: dict = {"cid": cid}
    try:
        ok, log = _forge_test(project, rel_test)
        res["log_original"] = log
        if "NO_POC_TEST_RAN" in log:
            res["status"] = "compile_error" if "Error" in log else "no_poc_test"
            return res
        if not ok:
            res["status"] = "test_fails_on_original"
            return res
        if not patch:
            res["status"] = "unverified_no_fix"
            return res
        files = _patch_files(patch)
        in_scope = set(contest.scope.project_relative())
        # The fix must change in-scope code; it may also touch the project's own supporting
        # sources (e.g. an interface whose signature changes), never deps, tests or scripts.
        extra = [f for f in files if f not in in_scope]
        bad = [f for f in extra if f.startswith(("lib/", "node_modules/", "test/", "script/"))
               or "/lib/" in f or ".." in f]
        if not files or not (set(files) & in_scope) or bad:
            res.update(status="unverified_bad_fix", fix_files=files)
            return res
        if extra:
            res["fix_touches_outside_scope"] = extra
        prefix = contest.scope.project_dir
        apply = ["git", "-C", str(repo), "apply"] + ([f"--directory={prefix}"] if prefix not in (".", "") else [])
        chk = subprocess.run(apply + ["--check", "-"], input=patch, capture_output=True, text=True)
        if chk.returncode != 0:
            res.update(status="unverified_bad_fix", fix_error=chk.stderr[-500:])
            return res
        subprocess.run(apply + ["-"], input=patch, capture_output=True, text=True, check=True)
        try:
            ok_fixed, log_fixed = _forge_test(project, rel_test)
        finally:
            subprocess.run(["git", "-C", str(repo), "checkout", "--"]
                           + [str(Path(prefix) / f) for f in files], check=True)
        res["log_fixed"] = log_fixed
        res["status"] = "confirmed" if not ok_fixed and "NO_POC_TEST_RAN" not in log_fixed \
            else "unverified_fix_does_not_break_test"
        return res
    finally:
        shutil.rmtree(poc_dir, ignore_errors=True)


def run(contest: Contest, workdir: Path, src: Path) -> tuple[Path, dict]:
    cands = {c["cid"]: c for c in load_candidates(workdir, contest)}
    out = workdir / contest.id / "prove"
    (out / "pocs").mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)
    results = json.loads((out / "results.json").read_text()) if (out / "results.json").exists() else {}
    for cid, cand in cands.items():
        ans_path = src / "answers" / f"{cid}.json"
        test_path = src / "project" / POC_DIR / f"{cid}.t.sol"
        if not ans_path.exists() and not test_path.exists():
            continue
        ans = json.loads(ans_path.read_text()) if ans_path.exists() else {}
        rec = {"cid": cid, "candidate_id": cand["id"], "title": cand["title"],
               "writer_status": ans.get("status"), "writer_notes": ans.get("notes", "")}
        if not test_path.exists():
            rec["status"] = "not_reproduced" if ans.get("status") == "not_reproduced" else "no_poc_test"
        else:
            test_src = test_path.read_text()
            patch_path = src / "answers" / f"{cid}.patch"
            patch = patch_path.read_text() if patch_path.exists() else None
            (out / "pocs" / f"{cid}.t.sol").write_text(test_src)
            if patch:
                (out / "pocs" / f"{cid}.patch").write_text(patch)
            v = verify(contest, workdir, cid, test_src, patch)
            (out / "logs" / f"{cid}.txt").write_text(
                "== original ==\n" + v.pop("log_original", "") + "\n== with fix ==\n" + v.pop("log_fixed", ""))
            rec.update(v)
        results[cid] = rec
        print(f"  {cid} {rec['status']:<34} {cand['title'][:70]}")
    (out / "results.json").write_text(json.dumps(results, indent=1) + "\n")
    annotate_known(contest, workdir)
    results = json.loads((out / "results.json").read_text())
    counts: dict[str, int] = {}
    for r in results.values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    (out / "summary.json").write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "counts": counts},
        indent=1) + "\n")
    return out, counts


def annotate_known(contest: Contest, workdir: Path) -> None:
    """Flag confirmed results whose fix touches lines a known-issue report cites."""
    from bughunter import known
    out = workdir / contest.id / "prove"
    path = out / "results.json"
    if not path.exists():
        return
    refs = known.load(contest, workdir / contest.id / "repo")
    cats = {c["cid"]: c["category"] for c in load_candidates(workdir, contest)}
    results = json.loads(path.read_text())
    for cid, r in results.items():
        patch_path = out / "pocs" / f"{cid}.patch"
        if r.get("status") == "confirmed" and patch_path.exists():
            r["known_issue"] = known.match(refs, patch_path.read_text(), cats.get(cid))
    path.write_text(json.dumps(results, indent=1) + "\n")


def mark_duplicate(contest: Contest, workdir: Path, cid: str, of: str) -> None:
    path = workdir / contest.id / "prove" / "results.json"
    res = json.loads(path.read_text())
    if cid not in res or of not in res:
        raise KeyError(f"unknown candidate {cid} or {of}")
    res[cid]["duplicate_of"] = of
    path.write_text(json.dumps(res, indent=1) + "\n")


def confirmed(workdir: Path, contest: Contest) -> list[dict]:
    path = workdir / contest.id / "prove" / "results.json"
    if not path.exists():
        return []
    res = json.loads(path.read_text())
    out = []
    for c in load_candidates(workdir, contest):
        r = res.get(c["cid"], {})
        if r.get("status") == "confirmed":
            out.append({**c, "known_issue": r.get("known_issue", []),
                        "duplicate_of": r.get("duplicate_of")})
    return out
