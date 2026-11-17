"""Structured output the model must return for every reviewed function."""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field

Category = Literal[
    "access-control",
    "reentrancy",
    "rounding-precision",
    "oracle-manipulation",
    "accounting",
    "external-integration",
    "dos",
    "standards-compliance",
]
Verdict = Literal["issue", "no_issue", "not_applicable"]
Level = Literal["high", "medium", "low"]


class ChecklistItem(BaseModel):
    category: Category
    verdict: Verdict
    reasoning: str = Field(description="One or two sentences: what was checked and why it holds or fails.")


class Finding(BaseModel):
    title: str = Field(description="Contest-style title: root cause + impact, under ~15 words.")
    category: Category
    severity: Level = Field(description="Contest severity per the rubric in the instructions.")
    confidence: Level
    functions: List[str] = Field(description="Root-cause function(s), as Contract.function.")
    root_cause: str = Field(description="The exact faulty line(s) / logic and why it is wrong.")
    attack_path: List[str] = Field(description="Concrete numbered steps an unprivileged actor (or normal usage) takes.")
    preconditions: str
    impact: str = Field(description="Who loses what, quantified where possible.")
    poc_plan: str = Field(description="What a Foundry test should set up, call, and assert to prove this.")


class FunctionReview(BaseModel):
    function_id: str
    summary: str = Field(description="What the function does and the invariant it must keep.")
    checklist: List[ChecklistItem]
    findings: List[Finding]
