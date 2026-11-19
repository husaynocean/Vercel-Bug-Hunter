"""No-API review mode: export the exact review prompts as files, have an
agent with no prior context (e.g. a fresh Claude Code subagent) answer them,
then import and validate the answers. Produces the same candidates.json /
review.md as the API mode, so `bughunter bench` works unchanged.

Blindness: export to a directory OUTSIDE the repo (the repo contains
benchmarks/truth/), and give the reviewing agent only that directory."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from bughunter.contest import Contest
from bughunter.review import runner
from bughunter.review.schema import FunctionReview

MANUAL_MODEL = "claude-code-manual"
MANUAL_EFFORT = "n/a"

REVIEWER_README = """\
# Review packet

You are reviewing smart-contract functions for an audit contest.

For each file in `tasks/`:
1. Read `{context}` (instructions, checklist, severity rubric and the full in-scope source).
2. Read the task file. It names one function to review.
3. Write your answer as JSON to `answers/<same name as the task, with .json>`.
   It must validate against `schema.json` (no extra keys). `function_id` must be the id in the task.

Use only the files in this packet. Do not search the web or read other files.
"""


def export(contest: Contest, workdir: Path, dest: Path, only: str | None = None,
           limit: int | None = None) -> dict:
    jobs, _ = runner.prepare(contest, workdir, MANUAL_MODEL, MANUAL_EFFORT, only, limit)
    repo = (workdir / contest.id / "repo").resolve()
    dest = dest.resolve()
    if dest == repo or repo in dest.parents or Path(__file__).resolve().parents[2] in dest.parents:
        raise ValueError("export outside the repository so the reviewer cannot see benchmark truth")
    (dest / "tasks").mkdir(parents=True, exist_ok=True)
    (dest / "answers").mkdir(exist_ok=True)

    contexts: dict[str, str] = {}
    index = {}
    for fn, params, path, key in jobs:
        ctx = params["system"][0]["text"] + "\n\n" + params["system"][1]["text"]
        name = contexts.setdefault(ctx, f"context-{len(contexts) + 1}.md")
        task_name = path.stem
        (dest / "tasks" / f"{task_name}.md").write_text(
            f"Context file: {name}\n\n" + params["messages"][0]["content"] + "\n")
        index[task_name] = {"function_id": fn["id"], "key": key, "context": name}
    for ctx, name in contexts.items():
        (dest / name).write_text(ctx)
    (dest / "schema.json").write_text(json.dumps(FunctionReview.model_json_schema(), indent=1))
    (dest / "README.md").write_text(REVIEWER_README.format(context=" / ".join(contexts.values())))
    (dest / ".index.json").write_text(json.dumps(index, indent=1))
    return {"dest": str(dest), "tasks": len(index), "contexts": len(contexts)}


def import_answers(contest: Contest, workdir: Path, src: Path, only: str | None = None,
                   limit: int | None = None) -> tuple[Path, dict]:
    jobs, out = runner.prepare(contest, workdir, MANUAL_MODEL, MANUAL_EFFORT, only, limit)
    index = json.loads((src / ".index.json").read_text())
    counts = {"imported": 0, "invalid": 0, "missing": 0, "stale": 0}
    for fn, params, path, key in jobs:
        entry = index.get(path.stem)
        ans = src / "answers" / f"{path.stem}.json"
        if entry is None or not ans.exists():
            counts["missing"] += 1
            continue
        if entry["key"] != key:  # prompt changed since export
            counts["stale"] += 1
            continue
        rec = {"function_id": fn["id"], "requested_model": MANUAL_MODEL,
               "served_model": MANUAL_MODEL, "key": key}
        try:
            review = FunctionReview.model_validate_json(ans.read_text())
            if review.function_id != fn["id"]:
                raise ValueError(f"function_id {review.function_id!r} != {fn['id']!r}")
            rec.update(status="ok", review=review.model_dump())
            counts["imported"] += 1
        except (ValidationError, ValueError) as e:
            rec.update(status="error", error=f"invalid answer: {str(e)[:300]}")
            counts["invalid"] += 1
        path.write_text(json.dumps(rec, indent=1))
    return runner.finalize(contest, out, jobs, MANUAL_MODEL, MANUAL_EFFORT), counts
