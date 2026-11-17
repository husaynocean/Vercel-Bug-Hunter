"""Score a scan against a contest's published findings.

Ground truth lives in benchmarks/truth/<id>.yaml and is read ONLY here --
never by the scan or (later) the LLM review, so the benchmark stays blind.

Week-1 metrics: "lead recall" = known Highs whose root function got any
non-noise static lead (only prioritisation -- the LLM reviews every function
anyway); "category recall" = got a lead of the matching bug class. Weeks 3-4 replace this with
"confirmed recall": a Foundry-proven finding matching the known bug."""
from __future__ import annotations

import json
from pathlib import Path

import yaml


def score(scan_dir: Path, truth_file: Path, severities=("high",)) -> dict:
    truth = yaml.safe_load(truth_file.read_text())
    funcs = json.loads((scan_dir / "functions.json").read_text())
    queued = {(f["contract"], f["function"]) for f in funcs if f["leads"]}
    known = {(f["contract"], f["function"]) for f in funcs}
    lead_cats: dict[tuple, set] = {}
    for f in funcs:
        for l in f["leads"]:
            lead_cats.setdefault((f["contract"], f["function"]), set()).add(l["category"])

    rows = []
    for t in truth["findings"]:
        if t["severity"] not in severities:
            continue
        targets = [(t["contract"], fn) for fn in t["functions"]]
        unknown = [x for x in targets if x not in known]
        hit = [x for x in targets if x in queued]
        rule_hits = sorted({l["rule"] for f in funcs for l in f["leads"]
                            if (f["contract"], f["function"]) in targets})
        cats = set().union(*(lead_cats.get(x, set()) for x in targets))
        rows.append({"id": t["id"], "title": t["title"], "functions": t["functions"],
                     "bug_class": t.get("bug_class"),
                     "lead_hit": bool(hit),                       # any lead on the function
                     "category_hit": t.get("bug_class") in cats,  # a lead of the right kind
                     "rules": rule_hits, "lead_categories": sorted(cats),
                     "unmapped_functions": unknown})
    n = len(rows)
    return {"contest": truth["contest"], "severities": list(severities), "known": n,
            "lead_hits": sum(r["lead_hit"] for r in rows),
            "lead_recall": round(sum(r["lead_hit"] for r in rows) / n, 3) if n else None,
            "category_hits": sum(r["category_hit"] for r in rows),
            "category_recall": round(sum(r["category_hit"] for r in rows) / n, 3) if n else None,
            "confirmed_hits": None,  # filled once the proof step exists (week 3)
            "findings": rows}
