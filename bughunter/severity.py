"""Post-proof severity re-check ("judge pass").

The review guesses severity before anything is proven; on the first five
benchmark contests it under-rated 4 of 11 found Highs. After the proof we
know the concrete, demonstrated impact, so a separate judge re-rates every
confirmed finding against the contest's severity rules. The final severity
drives the report draft; the original rating is kept for comparison.

No-API mode like the review/proof steps: export a packet, a context-free
agent writes answers/<cid>.json, import validates and records them.
The benchmark answer key is never part of the packet."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from bughunter import prove
from bughunter.contest import Contest

JUDGE_VERSION = "judge-v1"

RUBRIC = """\
Severity rules (Code4rena):
- High: assets can be stolen, lost or compromised directly, or indirectly if there is a valid attack path
  that does not rely on hand-wavy hypotheticals. This includes funds that become PERMANENTLY frozen or
  unrecoverable (for users, the protocol, or a role's legitimate entitlement), and breaking a core
  protocol invariant in a way that loses value.
- Medium: assets are not at direct risk, but the function or availability of the protocol could be
  impacted, or value can leak, with a hypothetical attack path under stated assumptions / external
  requirements. Temporary freezing or DoS that resolves (or that the victim can work around) is usually
  Medium; DoS that an attacker can sustain indefinitely at negligible cost, blocking users' funds, is
  usually High.
- Low / QA: real but minor: state handling, spec deviations without loss, issues that need a trusted
  admin to make a mistake, or self-inflicted user errors.
Other judging conventions:
- Trusted roles are trusted: an issue that requires an admin to act maliciously is invalid; an admin
  making a reasonable, documented action that unexpectedly breaks the system can still be valid.
- Rate by the impact the PoC actually demonstrates under realistic conditions, considering likelihood:
  high impact + realistic likelihood = High; high impact + unlikely preconditions = Medium.
- Issues already listed as known issues in the contest notes are invalid.
"""

README = f"""\
# Severity re-check packet

You are acting as an experienced audit-contest judge. Each file in `findings/`
is a finding that has already been PROVEN: its Foundry test passes on the
audited code and fails once the proposed fix is applied. The finding's
validity is not in question; your job is to assign the severity a strict
contest judge would give it.

Read `contest.md` (contest notes, roles, known issues) and, for each finding,
its file in `findings/` (claim, root-cause source, the proving test and the fix).

{RUBRIC}
For each finding write `answers/<cid>.json`:
`{{"cid": "<cid>", "severity": "high" | "medium" | "low", "rationale": "<2-4 sentences: impact shown, likelihood, which rule applies>"}}`

Be independent: the finding's own proposed severity may be wrong in either
direction. Use only files in this packet; do not search the web.
"""


class Verdict(BaseModel):
    cid: str
    severity: Literal["high", "medium", "low"]
    rationale: str = Field(min_length=10)


def export(contest: Contest, workdir: Path, dest: Path) -> dict:
    dest = dest.resolve()
    root = Path(__file__).resolve().parents[1]
    if dest == root or root in dest.parents:
        raise ValueError("export outside the repository (it contains benchmark answers)")
    funcs = json.loads((workdir / contest.id / "scan" / "functions.json").read_text())
    pdir = workdir / contest.id / "prove"
    items = [c for c in prove.confirmed(workdir, contest) if not c.get("duplicate_of")]
    (dest / "findings").mkdir(parents=True, exist_ok=True)
    (dest / "answers").mkdir(exist_ok=True)
    for c in items:
        src = _root_cause_source(funcs, c)
        test = (pdir / "pocs" / f"{c['cid']}.t.sol").read_text()
        patch = (pdir / "pocs" / f"{c['cid']}.patch").read_text()
        claim = {k: c[k] for k in ("title", "category", "severity", "functions", "root_cause",
                                   "attack_path", "preconditions", "impact")}
        claim["proposed_severity"] = claim.pop("severity")
        (dest / "findings" / f"{c['cid']}.md").write_text(
            f"# {c['cid']}: {c['title']}\n\n## Claim\n```json\n{json.dumps(claim, indent=1)}\n```\n\n"
            f"## Root-cause source\n```solidity\n{src}\n```\n\n"
            f"## Proving test (passes on audited code)\n```solidity\n{test}\n```\n\n"
            f"## Fix (test fails once applied)\n```diff\n{patch}\n```\n")
    (dest / "contest.md").write_text(
        f"# {contest.id}\n\nNotes: {contest.notes}\n\nOut of scope:\n"
        + "\n".join(f"- {x}" for x in contest.out_of_scope) + "\n")
    (dest / "README.md").write_text(README)
    (dest / ".index.json").write_text(json.dumps(
        {"contest": contest.id, "judge": JUDGE_VERSION, "cids": [c["cid"] for c in items]}, indent=1))
    return {"dest": str(dest), "findings": [c["cid"] for c in items]}


def _root_cause_source(funcs: list[dict], c: dict) -> str:
    names = c["functions"] or [c["reviewed_function"]]
    out = []
    for n in names:
        base = n.split("(")[0]
        contract, _, fn = base.rpartition(".")
        for f in funcs:
            if f["function"] == fn and (not contract or f["contract"] == contract):
                out.append(f"// {f['id']}  ({f['file']}:{f['lines'][0]})\n{f['source']}")
                break
    return "\n\n".join(out) or "(see claim)"


def import_verdicts(contest: Contest, workdir: Path, src: Path) -> dict:
    path = workdir / contest.id / "prove" / "results.json"
    results = json.loads(path.read_text())
    index = json.loads((src / ".index.json").read_text())
    counts = {"imported": 0, "invalid": 0, "missing": 0}
    for cid in index["cids"]:
        ans = src / "answers" / f"{cid}.json"
        if not ans.exists():
            counts["missing"] += 1
            continue
        try:
            v = Verdict.model_validate_json(ans.read_text())
            if v.cid != cid:
                raise ValueError(f"cid mismatch {v.cid} != {cid}")
        except (ValidationError, ValueError) as e:
            counts["invalid"] += 1
            print(f"  {cid}: invalid verdict: {str(e)[:200]}")
            continue
        results[cid].update(final_severity=v.severity, severity_rationale=v.rationale,
                            judge=index.get("judge", JUDGE_VERSION))
        counts["imported"] += 1
    path.write_text(json.dumps(results, indent=1) + "\n")
    return counts


def final_severities(workdir: Path, contest: Contest) -> dict[str, str]:
    """candidate id -> final severity, for confirmed findings that have been judged."""
    path = workdir / contest.id / "prove" / "results.json"
    if not path.exists():
        return {}
    return {r["candidate_id"]: r["final_severity"] for r in json.loads(path.read_text()).values()
            if r.get("status") == "confirmed" and r.get("final_severity")}
