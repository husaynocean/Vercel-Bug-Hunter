"""Semgrep over in-scope files only (out-of-scope files are never passed as
targets). Rulesets: our own rules/semgrep + optionally Decurity's
smart-contract rules, which are CC BY-NC-SA 4.0 (NON-COMMERCIAL) -- they are
excluded when running in commercial mode."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from bughunter import toolchain
from bughunter.contest import Scope
from bughunter.leads import Lead

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_RULES = REPO_ROOT / "rules" / "semgrep"

RULESETS = {
    "decurity": {
        "repo": "https://github.com/Decurity/semgrep-smart-contracts.git",
        "commit": "2e878a89ac7bba1f8435e8a68e3ecb7700096cd5",
        "subdir": "solidity/security",
        "license": "CC-BY-NC-SA-4.0",
        "commercial_ok": False,
    },
}

SEVERITY = {"ERROR": "medium", "WARNING": "low", "INFO": "info"}

KEYWORD_CATEGORY = [
    ("reentran", "reentrancy"), ("oracle", "oracle-manipulation"), ("price", "oracle-manipulation"),
    ("access", "access-control"), ("unrestricted", "access-control"), ("not-protected", "access-control"),
    ("owner", "access-control"), ("precision", "rounding-precision"), ("rounding", "rounding-precision"),
    ("division", "rounding-precision"), ("underflow", "rounding-precision"),
    ("balance", "accounting"), ("slippage", "oracle-manipulation"),
    ("transfer", "external-call"), ("call", "external-call"), ("loop", "dos"),
]


def fetch_ruleset(name: str, cache: Path) -> Path:
    spec = RULESETS[name]
    dest = cache / f"semgrep-{name}"
    if not (dest / ".git").exists():
        subprocess.run(["git", "clone", "--quiet", spec["repo"], str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "--quiet", spec["commit"]], check=True)
    return dest / spec["subdir"]


def run(project: Path, scope: Scope, cache: Path, commercial: bool = False) -> tuple[list[Lead], dict]:
    configs = [LOCAL_RULES]
    used = ["local"]
    for name, spec in RULESETS.items():
        if commercial and not spec["commercial_ok"]:
            continue
        configs.append(fetch_ruleset(name, cache))
        used.append(f"{name} ({spec['license']})")

    targets = scope.project_relative()
    cmd = ["semgrep", "scan", "--json", "--quiet", "--metrics=off", "--disable-version-check",
           "--no-git-ignore"]
    for c in configs:
        cmd += ["--config", str(c)]
    cmd += targets
    r = subprocess.run(cmd, cwd=project, capture_output=True, text=True, env=toolchain.env())
    if r.returncode not in (0, 1):  # 1 == findings present in some versions
        raise RuntimeError(f"semgrep failed ({r.returncode}): {r.stderr[-2000:]}")
    data = json.loads(r.stdout or "{}")

    leads, dropped = [], 0
    for res in data.get("results", []):
        path = res["path"]
        if not scope.contains(path):
            dropped += 1
            continue
        rule = res["check_id"].split(".")[-1]
        meta = res.get("extra", {}).get("metadata", {}) or {}
        leads.append(Lead(
            tool="semgrep", rule=rule,
            severity=SEVERITY.get(res.get("extra", {}).get("severity", "INFO"), "info"),
            confidence=str(meta.get("confidence", "medium")).lower(),
            category=meta.get("bughunter_category") or _category(rule),
            file=path, line=res["start"]["line"],
            message=res.get("extra", {}).get("message", "").strip(),
        ))
    stats = {"semgrep_rulesets": used, "semgrep_in_scope": len(leads),
             "semgrep_out_of_scope_dropped": dropped,
             "semgrep_errors": len(data.get("errors", []))}
    return leads, stats


def _category(rule: str) -> str:
    for kw, cat in KEYWORD_CATEGORY:
        if kw in rule:
            return cat
    return "other"
