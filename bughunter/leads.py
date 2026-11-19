"""Normalised static-analysis lead. A lead is NOT a finding: it is a pointer
for the LLM review (week 2) and the Foundry proof step (week 3)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

# Checklist categories the LLM review will walk through. Static leads are
# tagged with one so the reviewer can prioritise per function.
CATEGORIES = (
    "access-control",
    "reentrancy",
    "rounding-precision",
    "oracle-manipulation",
    "accounting",          # balance/state bookkeeping, share math, fee accounting
    "external-call",       # unchecked returns, arbitrary calls, token quirks
    "dos",
    "other",
)

SLITHER_CATEGORY = {
    "arbitrary-send-eth": "access-control", "arbitrary-send-erc20": "access-control",
    "arbitrary-send-erc20-permit": "access-control", "suicidal": "access-control",
    "unprotected-upgrade": "access-control", "protected-vars": "access-control",
    "tx-origin": "access-control", "missing-zero-check": "access-control",
    "events-access": "access-control",
    "reentrancy-eth": "reentrancy", "reentrancy-no-eth": "reentrancy",
    "reentrancy-benign": "reentrancy", "reentrancy-events": "reentrancy",
    "reentrancy-unlimited-gas": "reentrancy", "reentrancy-balance": "reentrancy",
    "divide-before-multiply": "rounding-precision", "incorrect-exp": "rounding-precision",
    "tautology": "rounding-precision",
    "weak-prng": "oracle-manipulation", "timestamp": "oracle-manipulation",
    "incorrect-equality": "accounting", "uninitialized-state": "accounting",
    "uninitialized-local": "accounting", "write-after-write": "accounting",
    "unused-return": "external-call", "unchecked-transfer": "external-call",
    "unchecked-lowlevel": "external-call", "unchecked-send": "external-call",
    "controlled-delegatecall": "external-call", "low-level-calls": "external-call",
    "calls-loop": "dos", "costly-loop": "dos", "msg-value-loop": "dos",
}

SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2, "info": 3, "optimization": 4}


@dataclass
class Lead:
    tool: str                 # slither | semgrep
    rule: str
    severity: str             # high|medium|low|info|optimization (tool's own rating)
    confidence: str
    category: str
    file: str                 # project-relative
    line: int
    message: str
    contract: str | None = None
    function: str | None = None
    extra_locations: list[dict] = field(default_factory=list)

    @property
    def key(self) -> tuple:
        return (self.tool, self.rule, self.file, self.line, self.function)

    def to_dict(self) -> dict:
        return asdict(self)


def dedupe(leads: list[Lead]) -> list[Lead]:
    seen, out = set(), []
    for l in leads:
        if l.key not in seen:
            seen.add(l.key)
            out.append(l)
    return out


def sort_leads(leads: list[Lead]) -> list[Lead]:
    return sorted(leads, key=lambda l: (SEVERITY_RANK.get(l.severity, 9), l.file, l.line))
