# Vercel-Bug-Hunter

An AI-assisted bug hunter for smart-contract audit contests (Code4rena, Sherlock,
Cantina, Immunefi). It only analyses the code that a contest or bounty officially
publishes as in scope.

```
contest.yaml ─► checkout @ pinned commit ─► scope check ─► forge build
            ─► Slither + Semgrep (in-scope only) ─► leads + function inventory   [wk1 ✅]
            ─► LLM review per function × checklist                              [wk2]
            ─► Foundry PoC per suspected bug, local fork; keep only passing      [wk3]
            ─► contest-format report draft → human review → submit              [wk3/4]
            ─► benchmark: 10 past contests, % known Highs caught                [wk4]
```

## Scope rules (enforced in code)

- `contests/<id>.yaml` holds the scope list, copied verbatim from the contest page.
  The pipeline refuses to run if that list is empty, if any listed file is missing
  at the pinned commit, or if the list disagrees with the repo's official
  `scope.txt` (`scope.scope_file`).
- Semgrep is only given in-scope files as targets. Slither compiles the whole
  project, because it needs the dependencies, but every result and inventory
  entry outside the scope list is dropped. The counts are recorded in
  `manifest.json`.
- Ground truth for the benchmark (`benchmarks/truth/`) is read only by
  `bughunter bench`, never by the scan or the review stages.

## Usage

```bash
pip install -e '.[dev]'
bughunter doctor                                     # forge / slither / semgrep present?
bughunter scan contests/c4-2024-03-pooltogether.yaml # → work/<id>/scan/
bughunter bench contests/c4-2024-03-pooltogether.yaml
pytest -q
```

Scan outputs in `work/<id>/scan/`:

| file | contents |
|---|---|
| `manifest.json` | commit, scope, tool paths, rulesets, in/out-of-scope counts, timing |
| `leads.json` | every normalised Slither/Semgrep result (tool, rule, severity, checklist category, file:line, contract.function) |
| `functions.json` | one record per in-scope function and modifier: source, visibility, modifiers, state read/written, external calls, attached leads. **This is the week-2 LLM work queue.** |
| `scan.md` | human summary: leads by severity plus the function queue ordered by lead count |

Leads are pointers, not findings. Style and gas detectors (`naming-convention`,
`solc-version`, …) stay in `leads.json` but are left out of the review queue.

### Semgrep rulesets and licensing

- `rules/semgrep/checklist.yaml`: our own generic rules, aligned with the
  checklist. Do **not** add rules derived from a benchmark contest's known
  findings. That would inflate the benchmark.
- Decurity `semgrep-smart-contracts`, pinned and fetched at runtime, is
  **CC BY-NC-SA 4.0 (non-commercial)**. Use `bughunter scan --commercial` for
  paid pre-audit scans; that excludes it.

## Setup notes

- Foundry: if `foundry.paradigm.xyz` is unreachable, unpack the GitHub release
  tarball into `~/.foundry/bin` (`foundry-rs/foundry/releases/.../foundry_stable_linux_amd64.tar.gz`).
- solc: `toolchain.ensure_solc` drops the GitHub-release static binary into
  `~/.svm/<v>/` when `binaries.soliditylang.org` is unreachable, so `forge`
  never needs to download it.
- `semgrep --validate` needs semgrep.dev, but scanning with `--metrics=off` does not.

## Week 1 result: Code4rena 2024-03 PoolTogether

6 in-scope files (648 SLOC). Published findings: 1 High, 8 Medium.

| metric | value |
|---|---|
| in-scope functions/modifiers inventoried | 66 |
| Slither results (in scope) / Semgrep results | 73 / 17 |
| review-queue leads (noise removed) | 34 across 19 functions |
| re-scan time (already built) | ~9 s |
| **H-01 lead recall** (any lead on `claimYieldFeeShares`) | 1/1 |
| **H-01 category recall** (lead of the right bug class) | **0/1** |

H-01 (`yieldFeeBalance -= _yieldFeeBalance` instead of `-= _shares`) is a pure
logic/accounting bug. The only static lead on that function is an unrelated
`reentrancy-events`. This is the expected baseline: static tools set the order
of review, and the LLM pass has to catch this class of bug. Note that the LLM
reviews *every* externally reachable state-changing function, not only those
with leads.

## Adding a contest

1. Copy `contests/c4-2024-03-pooltogether.yaml`. Set `repo`, the full 40-char
   `commit`, `solc`, `scope.project_dir`, and the `scope.files` list from the
   contest page.
2. For benchmark contests, add `benchmarks/truth/<id>.yaml` with each High
   finding's contract, root function(s) and bug class.
