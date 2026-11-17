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
