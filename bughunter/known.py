"""Known-issue filter. Contests publish automated reports (Code4rena bot
report, 4naly3er) before they start; anything they list is a known issue and
not paid. A confirmed finding is flagged as possibly known when the lines its
fix patch changes are cited by a non-gas, non-NC issue in those reports.

The flag is for a human to judge: a known issue can still be worth reporting
when the submission shows a new, more severe impact (on PoolTogether the
awarded M-06 built on the bot's 'unchecked transfer' line)."""
from __future__ import annotations

import re
from pathlib import Path

from bughunter.contest import Contest

SECTION = re.compile(r"^###\s+(?:<a[^>]*>\s*)?\[?\[?([A-Z]+-\d+)\]?[^\n]*?\]?\s*(.*)$")
FILE = re.compile(r"^File:\s*(\S+)")
LINE = re.compile(r"^\s*(\d+)\s*[|:]")
COUNTED = ("H", "M", "L")  # skip GAS / NC / informational

# A bot issue only makes a finding "known" if it is about the same kind of bug, not merely
# the same lines: on Kelp, the awarded H-02 sits next to a transferFrom the bot flagged for
# token compatibility. Issue titles map to review categories by keyword; generic hygiene
# notes (events, two-step ownership, zero-address checks, ...) map to nothing and never match.
ISSUE_CATEGORY = [
    (("reentran",), "reentrancy"),
    (("chainlink", "oracle", "stale", "price feed", "latestanswer", "sequencer", "twap", "slippage"),
     "oracle-manipulation"),
    (("transfer", "approve", "allowance", "fee-on-transfer", "erc20", "ierc20", "return value",
      "safeerc20", "rebasing", "decimals"), "external-integration"),
    (("rounding", "precision", "division", "divide", "truncat", "overflow", "underflow", "downcast"),
     "rounding-precision"),
    (("access control", "onlyowner", "unprotected", "permission", "authoriz", "tx.origin"),
     "access-control"),
    (("loop", "gas limit", "denial of service", "dos", "unbounded"), "dos"),
    (("erc4626", "eip-4626", "erc-4626", "erc1155", "eip-"), "standards-compliance"),
    (("first deposit", "inflation", "donation", "share price", "accounting"), "accounting"),
]


def issue_categories(title: str) -> set[str]:
    t = title.lower()
    return {cat for kws, cat in ISSUE_CATEGORY if any(k in t for k in kws)}


def parse_report(text: str) -> dict[tuple[str, int], list[str]]:
    """(file, line) -> ['M-02 ERC-20: transfer() return values should be checked', ...]"""
    refs: dict[tuple[str, int], list[str]] = {}
    issue, cur_file = None, None
    for raw in text.splitlines():
        m = SECTION.match(raw)
        if m:
            iid, title = m.group(1), re.sub(r"<[^>]+>|\[|\]|\(#[^)]*\)", "", m.group(2)).strip()
            issue = f"{iid} {title}" if iid.split("-")[0] in COUNTED else None
            cur_file = None
            continue
        if issue is None:
            continue
        f = FILE.match(raw)
        if f:
            cur_file = f.group(1)
            continue
        ln = LINE.match(raw)
        if cur_file and ln:
            refs.setdefault((cur_file, int(ln.group(1))), [])
            if issue not in refs[(cur_file, int(ln.group(1)))]:
                refs[(cur_file, int(ln.group(1)))].append(issue)
    return refs


def changed_lines(patch: str) -> list[tuple[str, int]]:
    """Original-file (path, line) pairs a unified diff removes or modifies."""
    out, path, old = [], None, 0
    for line in patch.splitlines():
        if line.startswith("--- "):
            path = re.sub(r"^a/", "", line[4:].split("\t")[0].strip())
        elif line.startswith("@@"):
            old = int(re.match(r"@@ -(\d+)", line).group(1))
        elif path and line.startswith("-") and not line.startswith("---"):
            out.append((path, old))
            old += 1
        elif path and line.startswith("+") and not line.startswith("+++"):
            out.append((path, old))  # insertion point
        elif path and not line.startswith("\\"):
            old += 1
    return out


def load(contest: Contest, repo: Path) -> dict[tuple[str, int], list[str]]:
    """Merge all known-issue reports, keyed by project-relative path."""
    prefix = "" if contest.scope.project_dir in (".", "") else contest.scope.project_dir.rstrip("/") + "/"
    refs: dict[tuple[str, int], list[str]] = {}
    for rel in contest.known_issues:
        p = repo / rel
        if not p.is_file():
            continue
        for (f, ln), issues in parse_report(p.read_text()).items():
            f = f[len(prefix):] if prefix and f.startswith(prefix) else f
            for i in issues:
                refs.setdefault((f, ln), [])
                tagged = f"{Path(rel).stem}: {i}"
                if tagged not in refs[(f, ln)]:
                    refs[(f, ln)].append(tagged)
    return refs


def match(refs: dict, patch: str, category: str | None = None, slack: int = 1) -> list[str]:
    """Known issues on the fix's lines; with `category`, only issues about that bug class."""
    hits: list[str] = []
    for f, ln in changed_lines(patch):
        for d in range(-slack, slack + 1):
            for i in refs.get((f, ln + d), []):
                if category is not None and category not in issue_categories(i):
                    continue
                if i not in hits:
                    hits.append(i)
    return hits
