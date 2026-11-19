"""Regression: Slither reports paths relative to the process cwd, which made
every in-scope result look out of scope when run from the repo root."""
from bughunter.tools.slither_runner import _rel


def test_rel_from_absolute(tmp_path):
    proj = tmp_path / "repo" / "pkg"
    (proj / "src").mkdir(parents=True)
    assert _rel(proj, str(proj / "src" / "A.sol")) == "src/A.sol"


def test_rel_outside_project_never_matches(tmp_path):
    proj = tmp_path / "pkg"
    proj.mkdir()
    out = _rel(proj, str(tmp_path / "other" / "A.sol"))
    assert not out.startswith("src/")
