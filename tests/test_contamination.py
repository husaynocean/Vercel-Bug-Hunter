"""Offline tests for the contamination check (fake client, no API calls)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from bughunter import contamination as cm
from bughunter.contest import Contest

ROOT = Path(__file__).resolve().parents[1]
KELP = ROOT / "contests" / "c4-2023-11-kelp.yaml"


def test_prompts_have_no_code_or_truth():
    c = Contest.load(KELP)
    ps = cm.build_prompts(KELP, c)
    assert set(ps) == {"name", "files", "canary"}
    assert "Kelp DAO rsETH (Nov 2023)" in ps["name"]
    assert "src/LRTDepositPool.sol" in ps["files"] and "src/LRTDepositPool.sol" not in ps["name"]
    truth = yaml.safe_load((ROOT / "benchmarks/truth/c4-2023-11-kelp.yaml").read_text())
    for p in ps.values():
        assert "function " not in p and "pragma" not in p
        for t in truth["findings"]:
            assert t["title"] not in p
    assert "Kelp" not in ps["canary"]


def test_match_needs_function_and_title_or_strong_title():
    t = {"contract": "LRTOracle", "functions": ["getRSETHPrice"], "title": "The price of rsETH could be manipulated by the first staker"}
    good = {"title": "First depositor can manipulate rsETH price", "functions": ["LRTOracle.getRSETHPrice"], "confidence": "certain"}
    wrong_fn = {"title": "Missing event on config update", "functions": ["LRTOracle.getRSETHPrice"], "confidence": "vague"}
    title_only = {"title": "price of rsETH manipulated by first staker", "functions": [], "confidence": "vague"}
    assert cm.match(t, [good])["function_match"]
    assert cm.match(t, [wrong_fn]) is None
    assert cm.match(t, [title_only]) is not None


class Fake:
    def __init__(self, answers):
        self.answers, self.beta = answers, self
        self.messages, self.prompts = self, []

    def parse(self, **kw):
        msg = kw["messages"][0]["content"]
        self.prompts.append(msg)
        probe = "canary" if "Kelp" not in msg else ("files" if "In-scope files" in msg else "name")
        return SimpleNamespace(parsed_output=cm.ProbeAnswer(**self.answers[probe]), stop_reason="end_turn")


def test_run_and_clean_bench(tmp_path):
    empty = {"remembers_contest": False, "findings": []}
    recalled = {"remembers_contest": True, "findings": [
        {"title": "First depositor can manipulate rsETH price", "functions": ["getRSETHPrice"], "confidence": "certain"}]}
    out = cm.run(KELP, tmp_path, client=Fake({"name": empty, "files": recalled, "canary": empty}))
    r = json.loads((out / "result.json").read_text())
    assert r["memorized"] == 1 and r["highs"] == 3 and r["reliable"] is True
    assert [x["id"] for x in r["findings"] if x["memorized"]] == ["H-03"]

    # no scan in tmp workdir -> reported, not crashed
    res = cm.clean_bench([KELP], tmp_path)
    assert res["contests"][0]["status"] == "no scan or truth"


def test_canary_failure_marks_unreliable(tmp_path):
    empty = {"remembers_contest": False, "findings": []}
    made_up = {"remembers_contest": True, "findings": [{"title": "Reentrancy in withdraw", "confidence": "certain"}]}
    out = cm.run(KELP, tmp_path, client=Fake({"name": empty, "files": empty, "canary": made_up}))
    assert json.loads((out / "result.json").read_text())["reliable"] is False


def test_export_refuses_inside_repo(tmp_path):
    with pytest.raises(ValueError):
        cm.export(KELP, ROOT / "packet")
    d = cm.export(KELP, tmp_path / "packet")
    assert len(list((d / "tasks").glob("*.md"))) == 3


def test_found_by_hand_matches_readme_total():
    hand = yaml.safe_load((ROOT / "benchmarks" / "found_by_hand.yaml").read_text())
    assert sum(len(v or []) for v in hand.values()) == 28
    for cid, ids in hand.items():
        truth = yaml.safe_load((ROOT / "benchmarks" / "truth" / f"{cid}.yaml").read_text())
        highs = {t["id"] for t in truth["findings"] if t["severity"] == "high"}
        assert set(ids or []) <= highs, cid
