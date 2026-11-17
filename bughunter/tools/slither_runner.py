"""Compile once with Slither, then (a) run every detector and (b) build the
per-function inventory that the LLM review iterates over. Everything outside
the official scope is dropped here."""
from __future__ import annotations

import inspect
import os
from contextlib import contextmanager
from pathlib import Path

from bughunter import toolchain
from bughunter.contest import Scope
from bughunter.leads import SLITHER_CATEGORY, Lead

IMPACT = {"High": "high", "Medium": "medium", "Low": "low",
          "Informational": "info", "Optimization": "optimization"}


@contextmanager
def _tool_env():
    old = dict(os.environ)
    os.environ.update(toolchain.env())
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old)


def analyse(project: Path, scope: Scope) -> tuple[list[Lead], list[dict], dict]:
    from slither import Slither
    from slither.detectors import all_detectors
    from slither.detectors.abstract_detector import AbstractDetector

    with _tool_env():
        sl = Slither(str(project), filter_paths=["lib/", "node_modules/", "test/", "script/"])
        for _, cls in inspect.getmembers(all_detectors, inspect.isclass):
            if issubclass(cls, AbstractDetector) and cls is not AbstractDetector:
                sl.register_detector(cls)
        raw = [r for batch in sl.run_detectors() for r in (batch or [])]

    leads, dropped = [], 0
    for r in raw:
        lead = _to_lead(r, scope, project)
        if lead is None:
            dropped += 1
        else:
            leads.append(lead)

    inventory = build_inventory(sl, project, scope)
    stats = {"slither_raw": len(raw), "slither_out_of_scope_dropped": dropped,
             "slither_in_scope": len(leads)}
    return leads, inventory, stats


def _rel(project: Path, path: str) -> str:
    """Project-relative POSIX path, independent of the process cwd."""
    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd() / p
    try:
        return p.resolve().relative_to(project.resolve()).as_posix()
    except ValueError:
        return path  # outside the project -> can never match scope


def _to_lead(r: dict, scope: Scope, project: Path) -> Lead | None:
    elems = [e for e in r.get("elements", []) if e.get("source_mapping")]
    for e in elems:
        sm = e["source_mapping"]
        sm["filename_relative"] = _rel(project, sm.get("filename_absolute") or sm.get("filename_relative", ""))
    in_scope = [e for e in elems if scope.contains(e["source_mapping"]["filename_relative"])]
    if not in_scope:
        return None
    primary = in_scope[0]
    sm = primary["source_mapping"]
    contract, function = _owner(primary)
    return Lead(
        tool="slither", rule=r["check"], severity=IMPACT.get(r["impact"], "info"),
        confidence=r["confidence"].lower(), category=SLITHER_CATEGORY.get(r["check"], "other"),
        file=sm["filename_relative"], line=(sm.get("lines") or [0])[0],
        message=r["description"].strip(), contract=contract, function=function,
        extra_locations=[{"file": e["source_mapping"]["filename_relative"],
                          "line": (e["source_mapping"].get("lines") or [0])[0],
                          "name": e.get("name")} for e in in_scope[1:]],
    )


def _owner(elem: dict) -> tuple[str | None, str | None]:
    t = elem.get("type")
    parent = elem.get("type_specific_fields", {}).get("parent", {})
    if t == "function":
        return parent.get("name"), elem.get("name")
    if t == "node":
        fn = parent
        c = fn.get("type_specific_fields", {}).get("parent", {})
        return c.get("name"), fn.get("name")
    if t == "contract":
        return elem.get("name"), None
    if parent.get("type") == "contract":
        return parent.get("name"), None
    if parent.get("type") == "function":
        c = parent.get("type_specific_fields", {}).get("parent", {})
        return c.get("name"), parent.get("name")
    return None, None


def build_inventory(sl, project: Path, scope: Scope) -> list[dict]:
    """One record per in-scope function/modifier: the unit of LLM review."""
    out = []
    src_cache: dict[str, bytes] = {}
    for c in sl.contracts:
        cfile = _rel(project, c.source_mapping.filename.absolute)
        if not scope.contains(cfile):
            continue
        for f in list(c.functions_declared) + list(c.modifiers_declared):
            sm = f.source_mapping
            if _rel(project, sm.filename.absolute) != cfile:
                continue
            data = src_cache.setdefault(cfile, (project / cfile).read_bytes())
            source = data[sm.start: sm.start + sm.length].decode(errors="replace")
            out.append({
                "id": f"{c.name}.{f.full_name}",
                "contract": c.name,
                "contract_kind": c.contract_kind if hasattr(c, "contract_kind") else
                    ("interface" if c.is_interface else "contract"),
                "function": f.name,
                "signature": f.full_name,
                "kind": "modifier" if f in c.modifiers_declared else
                        ("constructor" if f.is_constructor else "function"),
                "visibility": f.visibility,
                "mutability": "pure" if f.pure else "view" if f.view else
                              "payable" if f.payable else "nonpayable",
                "implemented": f.is_implemented,
                "modifiers": [m.name for m in f.modifiers],
                "protected": bool(f.is_protected()) if f.is_implemented else None,
                "state_written": sorted({v.name for v in f.all_state_variables_written()}),
                "state_read": sorted({v.name for v in f.all_state_variables_read()}),
                "external_calls": sorted({_call_str(x) for x in f.all_high_level_calls()}),
                "low_level_calls": len(f.all_low_level_calls()),
                "file": cfile,
                "lines": [sm.lines[0], sm.lines[-1]] if sm.lines else [0, 0],
                "source": source,
                "leads": [],
            })
    return out


def _call_str(x) -> str:
    target, op = x if isinstance(x, tuple) else (getattr(x, "destination", "?"), x)
    fn = getattr(op, "function_name", None) or getattr(getattr(op, "function", None), "name", "?")
    return f"{target}.{fn}"
