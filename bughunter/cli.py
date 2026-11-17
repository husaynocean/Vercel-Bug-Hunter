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

    if a.cmd == "bench":
        truth = ROOT / "benchmarks" / "truth" / f"{contest.id}.yaml"
        res = benchmark.score(a.workdir / contest.id / "scan", truth,
                              tuple(a.severity or ["high"]))
        print(json.dumps(res, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
