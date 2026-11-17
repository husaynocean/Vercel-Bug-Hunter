"""Week-1 scan stage: checkout -> scope check -> build -> Slither + Semgrep ->
leads attached to the per-function inventory (the week-2 LLM work queue)."""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from bughunter import toolchain
from bughunter.contest import Contest
from bughunter.leads import SEVERITY_RANK, Lead, dedupe, sort_leads
from bughunter.tools import semgrep_runner, slither_runner

# Pure style/gas detectors: kept in leads.json, hidden from the review queue.
NOISE_RULES = {
    "naming-convention", "solc-version", "pragma", "assembly", "dead-code",
    "too-many-digits", "similar-names", "constable-states", "immutable-states",
    "external-function", "cache-array-length", "unused-state", "unused-import",
    "redundant-statements", "cyclomatic-complexity", "missing-inheritance",
    "custom-errors",
}


def scan(contest: Contest, workdir: Path, commercial: bool = False, build: bool = True) -> Path:
    t0 = time.time()
    tools = toolchain.check(contest.solc)
    repo = contest.checkout(workdir)
    project = contest.project_root(repo)
    out = workdir / contest.id / "scan"
    out.mkdir(parents=True, exist_ok=True)

    if build:
        r = subprocess.run(["forge", "build"], cwd=project, capture_output=True, text=True,
                           env=toolchain.env())
        if r.returncode != 0:
            raise RuntimeError(f"forge build failed:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")

    sl_leads, inventory, sl_stats = slither_runner.analyse(project, contest.scope)
    sg_leads, sg_stats = semgrep_runner.run(project, contest.scope, workdir / "cache", commercial)

    leads = sort_leads(dedupe(sl_leads + sg_leads))
    _attach(leads, inventory)
    queue = [l for l in leads if l.rule not in NOISE_RULES and l.severity != "optimization"]

    manifest = {
        "contest": contest.id, "platform": contest.platform, "repo": contest.repo,
        "commit": contest.commit, "scope": contest.scope.files,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "elapsed_s": round(time.time() - t0, 1), "tools": tools, "commercial_mode": commercial,
        **sl_stats, **sg_stats,
        "leads_total": len(leads), "leads_review_queue": len(queue),
        "functions": len(inventory),
        "functions_with_leads": sum(1 for f in inventory if f["leads"]),
    }
    _dump(out / "manifest.json", manifest)
    _dump(out / "leads.json", [l.to_dict() for l in leads])
    _dump(out / "functions.json", inventory)
    (out / "scan.md").write_text(render_markdown(contest, manifest, queue, inventory))
    return out


def _attach(leads: list[Lead], inventory: list[dict]) -> None:
    """Link each lead to the innermost in-scope function containing it."""
    for l in leads:
        hits = [f for f in inventory
                if f["file"] == l.file and f["lines"][0] <= l.line <= f["lines"][1]]
        if l.function:
            named = [f for f in hits if f["function"] == l.function] or \
                    [f for f in inventory if f["file"] == l.file and f["function"] == l.function
                     and (l.contract is None or f["contract"] == l.contract)]
            hits = named or hits
        if not hits:
            continue
        f = min(hits, key=lambda f: f["lines"][1] - f["lines"][0])
        l.contract, l.function = f["contract"], f["function"]
        if l.rule not in NOISE_RULES:
            f["leads"].append({"tool": l.tool, "rule": l.rule, "severity": l.severity,
                               "category": l.category, "line": l.line})


def render_markdown(contest: Contest, m: dict, queue: list[Lead], inventory: list[dict]) -> str:
    lines = [
        f"# Scan: {contest.id} ({contest.platform})", "",
        f"- Repo: {contest.repo} @ `{contest.commit[:10]}`",
        f"- Scope: {len(contest.scope.files)} files, {m['functions']} functions/modifiers",
        f"- Slither: {m['slither_in_scope']} in-scope results "
        f"({m['slither_out_of_scope_dropped']} out-of-scope dropped)",
        f"- Semgrep: {m['semgrep_in_scope']} results; rulesets: {', '.join(m['semgrep_rulesets'])}",
        f"- Review queue (noise removed): **{m['leads_review_queue']}** leads across "
        f"{m['functions_with_leads']} functions", "",
        "> Leads are unverified pointers for review, not findings.", "",
        "## Leads by severity", "",
        "| Sev | Tool | Rule | Category | Location | Function |",
        "|---|---|---|---|---|---|",
    ]
    for l in sorted(queue, key=lambda l: (SEVERITY_RANK.get(l.severity, 9), l.file, l.line)):
        fn = f"{l.contract}.{l.function}" if l.function else (l.contract or "")
        lines.append(f"| {l.severity} | {l.tool} | `{l.rule}` | {l.category} | "
                     f"{l.file}:{l.line} | {fn} |")
    lines += ["", "## Function review queue", "",
              "Every state-changing, externally reachable function is reviewed in week 2; "
              "leads only set the order.", "",
              "| Function | Vis | Mut | Modifiers | Leads |", "|---|---|---|---|---|"]
    def prio(f):
        return (-len(f["leads"]), f["mutability"] in ("view", "pure"), f["id"])
    for f in sorted([f for f in inventory if f["implemented"]], key=prio):
        lines.append(f"| `{f['id']}` | {f['visibility']} | {f['mutability']} | "
                     f"{', '.join(f['modifiers']) or '-'} | {len(f['leads'])} |")
    return "\n".join(lines) + "\n"


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")
