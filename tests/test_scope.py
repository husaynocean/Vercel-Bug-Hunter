from pathlib import Path

import pytest

from bughunter.contest import Contest, Scope, ScopeError

ROOT = Path(__file__).resolve().parents[1]


def test_scope_contains_project_relative_paths():
    s = Scope(files=["pkg/src/A.sol", "pkg/src/lib/B.sol"], project_dir="pkg")
    assert s.contains("src/A.sol")
    assert s.contains("src/lib/B.sol")
    assert not s.contains("src/C.sol")
    assert not s.contains("lib/openzeppelin/ERC20.sol")
    assert s.project_relative() == ["src/A.sol", "src/lib/B.sol"]


def test_scope_root_project():
    s = Scope(files=["src/A.sol"])
    assert s.contains("src/A.sol") and not s.contains("test/A.t.sol")


def test_empty_scope_refused(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text("id: x\nplatform: c4\nrepo: r\ncommit: c\nscope: {files: []}\n")
    with pytest.raises(ScopeError):
        Contest.load(f)


def _fake_repo(tmp_path, official, present):
    for p in present:
        (tmp_path / p).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / p).write_text("// x")
    (tmp_path / "scope.txt").write_text("\n".join(official))
    return tmp_path


def test_yaml_must_match_official_scope_file(tmp_path):
    repo = _fake_repo(tmp_path, ["src/A.sol", "src/B.sol"], ["src/A.sol", "src/B.sol"])
    c = Contest(id="x", platform="c4", repo="r", commit="c",
                scope=Scope(files=["src/A.sol"]), scope_file="scope.txt")
    with pytest.raises(ScopeError, match="disagrees"):
        c.verify_scope(repo)


def test_missing_scope_file_refused(tmp_path):
    repo = _fake_repo(tmp_path, ["src/A.sol"], [])
    c = Contest(id="x", platform="c4", repo="r", commit="c", scope=Scope(files=["src/A.sol"]))
    with pytest.raises(ScopeError, match="missing"):
        c.verify_scope(repo)


def test_bundled_contests_load():
    for f in (ROOT / "contests").glob("*.yaml"):
        c = Contest.load(f)
        assert c.scope.files and len(c.commit) == 40


def test_multi_part_scope_union_case_insensitive(tmp_path):
    repo = _fake_repo(tmp_path, ["a/src/X.sol", "b/src/Y.sol"], ["A/src/X.sol", "b/src/Y.sol"])
    part = Contest(id="x", platform="c4", repo="r", commit="c", scope=Scope(files=["A/src/X.sol"], project_dir="A"),
                   scope_file="scope.txt", sibling_files=["b/src/Y.sol"])
    part.verify_scope(repo)  # passes: union matches, typo'd case tolerated
    part.sibling_files = []
    with pytest.raises(ScopeError, match="disagrees"):
        part.verify_scope(repo)
