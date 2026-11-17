"""Offline tests for the LLM review stage (no API calls: a fake client)."""
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from bughunter import benchmark
from bughunter.contest import Contest, Scope
from bughunter.review import prompts, runner
from bughunter.review.schema import FunctionReview

ROOT = Path(__file__).resolve().parents[1]


def _fn(cid, name, kind="contract", src="function f() external {}"):
    return {"id": f"{cid}.{name}()", "contract": cid, "contract_kind": kind, "function": name,
            "signature": f"{name}()", "kind": "function", "visibility": "external",
            "mutability": "nonpayable", "implemented": kind != "interface", "modifiers": [],
            "protected": False, "state_written": [], "state_read": [], "external_calls": [],
            "low_level_calls": 0, "file": "src/A.sol", "lines": [1, 3], "source": src, "leads": []}


@pytest.fixture
def setup(tmp_path):
    proj = tmp_path / "w" / "c1" / "repo"
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "A.sol").write_text("contract A {\n  function f() external {}\n}\n")
    scan = tmp_path / "w" / "c1" / "scan"
    scan.mkdir(parents=True)
    inv = [_fn("A", "claim"), _fn("A", "deposit"), _fn("IA", "claim", kind="interface")]
    (scan / "functions.json").write_text(json.dumps(inv))
    c = Contest(id="c1", platform="code4rena", repo="r", commit="c" * 40,
                scope=Scope(files=["src/A.sol"]), notes="owner is trusted")
    return c, tmp_path / "w"


class FakeClient:
    def __init__(self, refuse=()):
        self.calls, self.refuse, self.lock = [], set(refuse), threading.Lock()
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))

    def parse(self, **kw):
        with self.lock:
            self.calls.append(kw)
        task = kw["messages"][0]["content"]
        fid = task.split("`")[1]
        usage = SimpleNamespace(input_tokens=100, output_tokens=50,
                                cache_read_input_tokens=1000, cache_creation_input_tokens=0)
        if any(r in fid for r in self.refuse):
            return SimpleNamespace(model=kw["model"], stop_reason="refusal", usage=usage,
                                   stop_details=SimpleNamespace(category="cyber"), parsed_output=None)
        findings = []
        if "claim" in fid:
            findings = [{"title": "claim subtracts whole fee balance", "category": "accounting",
                         "severity": "high", "confidence": "medium", "functions": ["A.claim"],
                         "root_cause": "x -= total", "attack_path": ["call claim(1)"],
                         "preconditions": "-", "impact": "fees locked", "poc_plan": "assert"}]
        parsed = FunctionReview.model_validate({"function_id": fid, "summary": "s",
                                                "checklist": [], "findings": findings})
        return SimpleNamespace(model=kw["model"], stop_reason="end_turn", usage=usage,
                               parsed_output=parsed)


def test_reviews_implemented_non_interface_functions(setup):
    c, w = setup
    fake = FakeClient()
    out = runner.run(c, w, client=fake, concurrency=2)
    assert len(fake.calls) == 2  # interface function skipped
    cands = json.loads((out / "candidates.json").read_text())
    assert [x["title"] for x in cands] == ["claim subtracts whole fee balance"]
    m = json.loads((out / "manifest.json").read_text())
    assert m["status"] == {"ok": 2} and m["usd_estimate"] is not None


def test_request_shape_caches_context_and_uses_fallbacks(setup):
    c, w = setup
    fake = FakeClient()
    runner.run(c, w, client=fake, concurrency=1)
    kw = fake.calls[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["fallbacks"] == "default" and runner.FALLBACK_BETA in kw["betas"]
    assert kw["system"][1]["cache_control"] == {"type": "ephemeral"}
    assert "contract A" in kw["system"][1]["text"]          # in-scope source in cached block
    assert kw["system"][0]["text"] == prompts.INSTRUCTIONS   # static, no per-call data
    assert all(k["system"] == kw["system"] for k in fake.calls)  # identical prefix -> cache hits
    assert kw["output_format"] is FunctionReview


def test_resume_skips_done_functions(setup):
    c, w = setup
    runner.run(c, w, client=FakeClient())
    again = FakeClient()
    runner.run(c, w, client=again)
    assert again.calls == []


def test_refusal_recorded_not_fatal(setup):
    c, w = setup
    out = runner.run(c, w, client=FakeClient(refuse={"deposit"}))
    m = json.loads((out / "manifest.json").read_text())
    assert m["status"] == {"ok": 1, "refused": 1}
    assert "refused" in (out / "review.md").read_text()


def test_benchmark_truth_never_reaches_prompts():
    """Blindness: no known-finding text may appear in the prompt templates."""
    for f in (ROOT / "benchmarks" / "truth").glob("*.yaml"):
        for t in yaml.safe_load(f.read_text())["findings"]:
            assert t["title"].strip()[:40] not in prompts.INSTRUCTIONS
    src = (ROOT / "bughunter" / "review" / "runner.py").read_text()
    assert "benchmarks" not in src and "truth" not in src.split('"""', 2)[2]


def test_benchmark_scores_review_candidates(tmp_path):
    review = tmp_path / "review"
    review.mkdir()
    (review / "candidates.json").write_text(json.dumps([
        {"reviewed_function": "PrizeVault.claimYieldFeeShares(uint256)", "functions": [],
         "category": "accounting", "severity": "high", "title": "t"},
        {"reviewed_function": "PrizeVault.deposit(uint256,address)", "functions": ["PrizeVault.deposit"],
         "category": "rounding-precision", "severity": "medium", "title": "u"}]))
    truth = {"contest": "x", "findings": [{"id": "H-01", "severity": "high", "contract": "PrizeVault",
                                           "functions": ["claimYieldFeeShares"], "bug_class": "accounting",
                                           "title": "x"}]}
    r = benchmark.score_review(review, truth, ("high",))
    assert r["candidate_recall"] == 1.0 and r["candidate_category_recall"] == 1.0
    assert r["candidates_by_severity"] == {"high": 1, "medium": 1, "low": 0}
