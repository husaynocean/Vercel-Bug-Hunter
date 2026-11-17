from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bughunter import benchmark, toolchain
from bughunter.contest import Contest
from bughunter.pipeline import scan

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bughunter")
    p.add_argument("--workdir", type=Path, default=ROOT / "work")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="clone contest, verify scope, run Slither + Semgrep")
    s.add_argument("contest", type=Path, help="contests/<id>.yaml")
    s.add_argument("--commercial", action="store_true",
                   help="exclude non-commercially licensed rulesets (use for paid scans)")
    s.add_argument("--no-build", action="store_true")

    b = sub.add_parser("bench", help="score an existing scan against published findings")
    b.add_argument("contest", type=Path)
    b.add_argument("--severity", action="append", default=None,
                   help="severity to score (repeatable; default: high)")

    r = sub.add_parser("review", help="LLM review of every in-scope function (needs a scan)")
    r.add_argument("contest", type=Path)
    r.add_argument("--model", default=None, help="default: claude-opus-5-5")
    r.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    r.add_argument("--only", help="review only functions whose id contains this text")
    r.add_argument("--limit", type=int)
    r.add_argument("--concurrency", type=int, default=4)
    r.add_argument("--dry-run", action="store_true", help="build prompts, estimate size, no API calls")
    r.add_argument("--force", action="store_true", help="ignore cached per-function results")
    r.add_argument("--export", type=Path, metavar="DIR",
                   help="no-API mode: write review prompts to DIR (outside the repo) for an agent to answer")
    r.add_argument("--import", dest="import_dir", type=Path, metavar="DIR",
                   help="no-API mode: validate answers in DIR/answers and build candidates")

    pv = sub.add_parser("prove", help="Foundry PoC per candidate; keep only confirmed bugs")
    pv.add_argument("contest", type=Path)
    pv.add_argument("--export", type=Path, metavar="DIR", help="write a PoC packet (outside the repo)")
    pv.add_argument("--cids", help="comma-separated candidate ids for --export (default: all)")
    pv.add_argument("--run", type=Path, metavar="DIR", help="verify PoCs + fixes from DIR in the clean repo")

    rp = sub.add_parser("report", help="draft contest write-ups for confirmed findings")
    rp.add_argument("contest", type=Path)

    sub.add_parser("doctor", help="check toolchain")

    a = p.parse_args(argv)
    if a.cmd == "doctor":
        for k, v in toolchain.check().items():
            print(f"{k:10} {v}")
        return 0

    contest = Contest.load(a.contest)
    if a.cmd == "scan":
        out = scan(contest, a.workdir, commercial=a.commercial, build=not a.no_build)
        m = json.loads((out / "manifest.json").read_text())
        print(f"scan written to {out}")
        print(f"  {m['functions']} functions, {m['leads_review_queue']} leads in review queue "
              f"({m['leads_total']} total), {m['elapsed_s']}s")
        return 0

    if a.cmd == "review" and (a.export or a.import_dir):
        from bughunter.review import manual
        if a.export:
            info = manual.export(contest, a.workdir, a.export, a.only, a.limit)
            print(f"exported {info['tasks']} task(s), {info['contexts']} context file(s) to {info['dest']}")
        else:
            out, counts = manual.import_answers(contest, a.workdir, a.import_dir, a.only, a.limit)
            m = json.loads((out / "manifest.json").read_text())
            print(f"imported {counts}; {m['candidates']} candidates {m['by_severity']} -> {out}")
        return 0

    if a.cmd == "review":
        from bughunter.review import runner
        try:
            out = runner.run(contest, a.workdir, model=a.model or runner.DEFAULT_MODEL,
                             effort=a.effort, only=a.only, limit=a.limit,
                             concurrency=a.concurrency, dry_run=a.dry_run, force=a.force)
        except runner.ReviewAborted as e:
            print(f"review aborted: {e}. Set ANTHROPIC_API_KEY (see README#llm-review).", file=sys.stderr)
            return 2
        if not a.dry_run:
            m = json.loads((out / "manifest.json").read_text())
            print(f"review written to {out}")
            print(f"  status {m['status']}, {m['candidates']} candidates {m['by_severity']}, "
                  f"est. ${m['usd_estimate']}")
        return 0

    if a.cmd == "prove":
        from bughunter import prove
        if a.export:
            info = prove.export(contest, a.workdir, a.export, a.cids.split(",") if a.cids else None)
            print(f"exported {len(info['candidates'])} candidate(s) {info['candidates']} to {info['dest']}")
        elif a.run:
            out, counts = prove.run(contest, a.workdir, a.run)
            print(f"proof results {counts} -> {out}")
        else:
            for c in prove.load_candidates(a.workdir, contest):
                print(f"{c['cid']} [{c['severity']}] {c['title']}")
        return 0

    if a.cmd == "report":
        from bughunter import report
        out = report.draft(contest, a.workdir)
        n = len([f for f in out.glob("*.md") if f.name != "known-issues.md"])
        known_note = " + known-issues.md" if (out / "known-issues.md").exists() else ""
        print(f"{n} draft(s){known_note} in {out} (confirmed, not-known findings only; review before submitting)")
        return 0

    if a.cmd == "bench":
        truth = ROOT / "benchmarks" / "truth" / f"{contest.id}.yaml"
        res = benchmark.score(a.workdir / contest.id / "scan", truth,
                              tuple(a.severity or ["high"]))
        print(json.dumps(res, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
