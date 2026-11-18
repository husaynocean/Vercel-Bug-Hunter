"""Score a scan against a contest's published findings.

Ground truth lives in benchmarks/truth/<id>.yaml and is read ONLY here --
never by the scan or (later) the LLM review, so the benchmark stays blind.

Week-1 metrics: "lead recall" = known Highs whose root function got any
non-noise static lead (only prioritisation -- the LLM reviews every function
anyway); "category recall" = got a lead of the matching bug class.

Week-2 metrics (when review/candidates.json exists): a known High is a
"candidate hit" when the LLM raised a candidate rooted in the same
contract.function; "category hit" additionally needs the same bug class.
Matching is by location, so `matched_titles` is printed for a human to
confirm it is really the same bug. Weeks 3-4 add "confirmed recall": a
Foundry-proven finding matching the known bug."""
from __future__ import annotations

import json
from pathlib import Path

import yaml


def _fn_key(name: str) -> tuple[str | None, str]:
    """'PrizeVault.claimYieldFeeShares(uint256)' -> ('PrizeVault', 'claimYieldFeeShares')"""
    base = name.split("(")[0].strip().strip("`")
    contract, _, fn = base.rpartition(".")
    return (contract or None, fn)


def _targets(t: dict) -> set[tuple[str, str]]:
    """Truth `functions` entries may be 'fn' (in t['contract']) or 'Contract.fn'."""
    out = set()
    for f in t["functions"]:
        c, _, fn = f.rpartition(".")
        out.add((c or t["contract"], fn))
    return out


def score_review(review_dir: Path, truth: dict, severities, only_ids: set | None = None,
                 severity_override: dict | None = None) -> dict | None:
    path = review_dir / "candidates.json"
    if not path.exists():
        return None
    cands = json.loads(path.read_text())
    if only_ids is not None:
        cands = [c for c in cands if c["id"] in only_ids]
    if severity_override:
        cands = [{**c, "severity": severity_override.get(c["id"], c["severity"])} for c in cands]
    rows = []
    for t in truth["findings"]:
        if t["severity"] not in severities:
            continue
        targets = _targets(t)
        names = {fn for _, fn in targets}
        hits = [c for c in cands if any(
            (contract, fn) in targets or (contract is None and fn in names)
            for contract, fn in map(_fn_key, c["functions"] + [c["reviewed_function"]]))]
        cat_hits = [c for c in hits if c["category"] == t.get("bug_class")]
        rows.append({"id": t["id"], "candidate_hit": bool(hits), "category_hit": bool(cat_hits),
                     "severity_match": any(c["severity"] == t["severity"] for c in hits),
                     "matched_titles": [f"[{c['severity']}/{c['category']}] {c['title']}" for c in hits]})
    n = len(rows)
    return {"candidates_total": len(cands),
            "candidates_by_severity": {s: sum(1 for c in cands if c["severity"] == s)
                                       for s in ("high", "medium", "low")},
            "candidate_recall": round(sum(r["candidate_hit"] for r in rows) / n, 3) if n else None,
            "candidate_category_recall": round(sum(r["category_hit"] for r in rows) / n, 3) if n else None,
            "severity_agreement": round(sum(r["severity_match"] for r in rows) / n, 3) if n else None,
            "findings": rows}


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
        targets = sorted(_targets(t))
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
            "findings": rows,
            "review": score_review(scan_dir.parent / "review", truth, severities),
            # week 3: only candidates whose Foundry PoC passed AND failed under the fix
            "confirmed": score_review(scan_dir.parent / "review", truth, severities,
                                      only_ids=_confirmed_ids(scan_dir.parent / "prove")),
            # after the post-proof severity re-check (judge pass), where it has run
            "confirmed_judged": score_review(scan_dir.parent / "review", truth, severities,
                                             only_ids=_confirmed_ids(scan_dir.parent / "prove"),
                                             severity_override=_final_sev(scan_dir.parent / "prove"))}


def _final_sev(prove_dir: Path) -> dict:
    path = prove_dir / "results.json"
    if not path.exists():
        return {}
    return {r["candidate_id"]: r["final_severity"] for r in json.loads(path.read_text()).values()
            if r.get("final_severity")}


def _confirmed_ids(prove_dir: Path) -> set | None:
    path = prove_dir / "results.json"
    if not path.exists():
        return None
    return {r["candidate_id"] for r in json.loads(path.read_text()).values() if r["status"] == "confirmed"}
