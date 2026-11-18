import json
from pathlib import Path

import pytest

from bughunter import prove
from bughunter.contest import Contest, Scope

ROOT = Path(__file__).resolve().parents[1]


def test_patch_files_parses_targets():
    patch = "--- a/src/A.sol\n+++ b/src/A.sol\n@@ -1 +1 @@\n-x\n+y\n--- a/src/B.sol\n+++ b/src/B.sol\n"
    assert prove._patch_files(patch) == ["src/A.sol", "src/B.sol"]


def test_export_refuses_repo_paths(tmp_path):
    c = Contest(id="c1", platform="c4", repo="r", commit="c" * 40, scope=Scope(files=["src/A.sol"]))
    rev = tmp_path / "c1" / "review"
    rev.mkdir(parents=True)
    (rev / "candidates.json").write_text("[]")
    with pytest.raises(ValueError):
        prove.export(c, tmp_path, ROOT / "packet")


def test_confirmed_filters_on_status(tmp_path):
    c = Contest(id="c1", platform="c4", repo="r", commit="c" * 40, scope=Scope(files=["src/A.sol"]))
    (tmp_path / "c1" / "review").mkdir(parents=True)
    (tmp_path / "c1" / "prove").mkdir(parents=True)
    (tmp_path / "c1" / "review" / "candidates.json").write_text(json.dumps([{"id": "x#0"}, {"id": "y#0"}]))
    (tmp_path / "c1" / "prove" / "results.json").write_text(json.dumps({
        "c00": {"status": "confirmed", "candidate_id": "x#0"},
        "c01": {"status": "unverified_fix_does_not_break_test", "candidate_id": "y#0"}}))
    assert [x["id"] for x in prove.confirmed(tmp_path, c)] == ["x#0"]


def test_known_issue_matching():
    from bughunter import known
    report = """### [M-02]<a name="m-02"></a> ERC-20: transfer() return values should be checked
```solidity
File: pkg/src/V.sol

     |  // @audit-issue Check return value
 939 |  _asset.transfer(_receiver, _assets);
```
### [GAS-1] something
File: src/V.sol
617: yieldFeeBalance -= x;
"""
    refs = known.parse_report(report)
    assert refs == {("pkg/src/V.sol", 939): ["M-02 ERC-20: transfer() return values should be checked"]}
    patch = "--- a/src/V.sol\n+++ b/src/V.sol\n@@ -937,4 +937,4 @@\n a\n b\n-        _asset.transfer(r, x);\n+        _asset.safeTransfer(r, x);\n c\n"
    assert known.changed_lines(patch)[0] == ("src/V.sol", 939)
    assert known.match({("src/V.sol", 939): ["bot: M-02"]}, patch) == ["bot: M-02"]
    # same lines, different kind of bug -> not "known"
    refs2 = {("src/V.sol", 939): ["bot: M-02 ERC-20: transfer() return values should be checked"]}
    assert known.match(refs2, patch, "accounting") == []
    assert known.match(refs2, patch, "external-integration") == ["bot: M-02 ERC-20: transfer() return values should be checked"]
    assert known.match({("src/V.sol", 939): ["bot: L-11 Lack of two-step update"]}, patch, "accounting") == []
    gas_only = "--- a/src/V.sol\n+++ b/src/V.sol\n@@ -617 +617 @@\n-x\n+y\n"
    assert known.match({("src/V.sol", 939): ["bot: M-02"]}, gas_only) == []


def test_severity_verdict_import(tmp_path):
    from bughunter import severity
    c = Contest(id="c1", platform="c4", repo="r", commit="c" * 40, scope=Scope(files=["src/A.sol"]))
    pdir = tmp_path / "w" / "c1" / "prove"
    pdir.mkdir(parents=True)
    (pdir / "results.json").write_text(json.dumps({
        "c00": {"status": "confirmed", "candidate_id": "x#0"},
        "c01": {"status": "confirmed", "candidate_id": "y#0"}}))
    pkt = tmp_path / "pkt"
    (pkt / "answers").mkdir(parents=True)
    (pkt / ".index.json").write_text(json.dumps({"cids": ["c00", "c01"]}))
    (pkt / "answers" / "c00.json").write_text(json.dumps(
        {"cid": "c00", "severity": "high", "rationale": "Permanent freeze of user funds shown by the PoC."}))
    (pkt / "answers" / "c01.json").write_text(json.dumps({"cid": "c01", "severity": "critical", "rationale": "x" * 20}))
    counts = severity.import_verdicts(c, tmp_path / "w", pkt)
    assert counts == {"imported": 1, "invalid": 1, "missing": 0}
    assert severity.final_severities(tmp_path / "w", c) == {"x#0": "high"}
