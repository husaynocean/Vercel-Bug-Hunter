# Vercel-Bug-Hunter

An AI-assisted bug hunter for smart-contract audit contests (Code4rena, Sherlock,
Cantina, Immunefi). It only analyses the code that a contest or bounty officially
publishes as in scope.

```
contest.yaml ─► checkout @ pinned commit ─► scope check ─► forge build
            ─► Slither + Semgrep (in-scope only) ─► leads + function inventory   [wk1 ✅]
            ─► LLM review per function × checklist                              [wk2 ✅]                         
            ─► Foundry PoC per suspected bug; keep only test-confirmed           [wk3 ✅]
            ─► contest-format report draft → human review → submit              [wk3 ✅]
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

## LLM review (week 2)

```bash
export ANTHROPIC_API_KEY=...        # or set it on the cloud environment (see below)
bughunter review contests/c4-2024-03-pooltogether.yaml --dry-run          # prompts + size, no calls
bughunter review contests/c4-2024-03-pooltogether.yaml --only claimYieldFeeShares   # 1-call smoke test
bughunter review contests/c4-2024-03-pooltogether.yaml                    # all functions
bughunter bench  contests/c4-2024-03-pooltogether.yaml                    # adds review recall
```

- **Unit of work.** Every implemented, non-interface function and modifier in
  `functions.json` gets one call, whether or not it has static leads (61 on
  PoolTogether). Its static leads go in as unverified hints.
- **Checklist.** The model must give a verdict for each category: access
  control, reentrancy, rounding/precision, oracle manipulation, accounting,
  external integration, DoS, standards compliance (`review/prompts.py`). Then
  it reports findings in a strict schema (`review/schema.py`): title,
  severity, confidence, root cause, attack path, impact, and a **PoC plan**
  that the week-3 proof step will turn into a Foundry test.
- **Context.** The cached prefix is the static instructions plus all in-scope
  source with line numbers, the contest notes and the out-of-scope list. On
  PoolTogether that's one ~18k-token prefix shared by every call. Only
  in-scope code is sent; external contracts are described as trusted per the
  README. Above ~100k tokens it switches to per-file context.
- **API.** `claude-opus-5-5` at effort `high`, structured output via
  `client.beta.messages.parse`, prompt caching on the context block, and
  server-side refusal fallbacks (`fallbacks="default"`), since security work
  can trip safety classifiers. Refusals and errors are recorded per function,
  not fatal. Results are cached per function, so re-runs only redo what
  changed (`--force` redoes everything).
- **Outputs** in `work/<id>/review/`: `candidates.json` (ranked suspected
  bugs, the week-3 queue), `review.md`, `manifest.json` (token usage,
  estimated USD), `calls/*.json`.
- **Benchmark.** `bench` reports *candidate recall* (a candidate rooted in
  the known High's function) and *candidate category recall* (same bug class
  too), plus `matched_titles` for a human to confirm it's really the same bug.
  It also reports total candidates by severity, as a noise measure.

**No-API mode (no credits needed).** Export the exact same prompts as files
to a folder **outside the repo** (the repo holds the benchmark answers). Have
a fresh agent with no prior context answer them, e.g. a Claude Code subagent
told to read only that folder. Then import; answers are schema-validated:

```bash
bughunter review contests/<id>.yaml --export /tmp/packet [--only fn] [--limit N]
# agent reads /tmp/packet/README.md, writes /tmp/packet/answers/*.json
bughunter review contests/<id>.yaml --import /tmp/packet
```

First blind result (PoolTogether, `claimYieldFeeShares` only): a fresh subagent
reported H-01 exactly. It gave the right line, high severity, the accounting
category, and a usable PoC plan. Caveat: that function was chosen because it
holds the known bug, so this shows the review *can* catch it. Recall and noise
need the full 61-function run.

### Week 2 result: PoolTogether, full blind run (61 functions, no-API mode)

Six fresh subagents of about 10 functions each, plus the H-01 smoke test.
All 61 answers validated. 6 candidates (1 high, 3 medium, 2 low).

| known finding | auto match | human check of the matched candidate |
|---|---|---|
| **H-01** fee claim loses unclaimed fees | hit | **same bug** (exact line, high, accounting) |
| M-06 funds locked, missing transfer check | hit | **same root cause** (raw `transfer` in `_withdraw`) |
| M-03 maxDeposit vs yieldVault.mint | hit (location) | different cause (yield-buffer `LossyDeposit`), same ERC4626 class: **not counted** |
| M-07 maxDeposit ignores fees | hit (location) | different cause: **not counted** |
| M-01, M-02, M-04, M-05, M-08 | miss | M-02 and M-05 were seen but dismissed as out of scope / unrealistic |

- **High recall: 1/1.** Medium recall: 1/8 confirmed (4/8 by location only;
  `bench` matches on location, so always read `matched_titles`).
- **Candidates:** 2 of 6 match published bugs. The other 4 are USDT-style
  raw `approve`/`transferFrom` notes, a `maxDeposit` edge case, and a
  fee-recipient handover: plausible, but not awarded. Week 3's Foundry
  proofs decide which survive.
- **Usage:** about 0.9M subagent tokens (each helper re-reads the ~19k-token
  context). This came from the Claude plan, not an API key.

## Proof step + report drafts (week 3)

```bash
bughunter prove  contests/<id>.yaml                       # list candidates (c00, c01, ...)
bughunter prove  contests/<id>.yaml --export /tmp/poc-A --cids c00,c05
# an agent writes project/test/bughunter/<cid>.t.sol + answers/<cid>.patch/.json
bughunter prove  contests/<id>.yaml --run /tmp/poc-A      # independent verification
bughunter report contests/<id>.yaml                       # drafts for confirmed, non-known findings
```

- **Confirmed** means the PoC passes on the audited commit **and** fails once
  the proposed in-scope fix is applied. Both are re-run by `prove --run` in the
  clean contest checkout. It copies only the test file and never trusts the
  writer's claims. A test that passes regardless of the code is caught (status
  `unverified_fix_does_not_break_test`).
- **Known-issue filter:** contests publish automated reports (bot report,
  4naly3er) before they start, and issues listed there aren't paid. A
  confirmed finding whose fix touches lines those reports cite (H/M/L
  sections, not gas/NC) is listed in `report/known-issues.md` instead of
  being drafted. Configure via `known_issues:` in the contest YAML.
- **Drafts** in `work/<id>/report/` follow Code4rena's layout: lines of code
  (GitHub links at the audited commit), details, impact, PoC steps, the test,
  the mitigation diff and the assessed type. They're drafts for you to review.
  Nothing is ever submitted automatically.
- **Fork tests:** PoolTogether's PoCs are unit tests on the contest's own
  mocks. Contests whose bugs need live protocol state will need an RPC URL
  (a network host plus usually a key) for `forge test --fork-url`. Not
  wired up yet.

### Week 3 result: PoolTogether

| cid | candidate | proof | known issue? | drafted |
|---|---|---|---|---|
| c00 | **H-01** partial fee claim wipes unclaimed fees | **confirmed** | no | **yes (High)** |
| c01 | raw `approve` breaks USDT-like deposits | confirmed | bot M-04 | no |
| c02 | raw `transfer` in `_withdraw` locks funds | confirmed | bot M-02/M-03 | no (published M-06 extended this) |
| c03 | raw `transferFrom` in `deployVault` | confirmed | bot M-02/M-03 | no |
| c04 | `maxDeposit` over-reports when buffer is empty | confirmed | no | yes (Low) |
| c05 | fee-recipient change hands over unclaimed fees | **rejected**: trusted owner, no loss | n/a | no |

**Confirmed High recall: 1/1**, and the only drafted High is the real one.
All PoCs were written by context-free subagents (about 320k tokens of plan
usage).

## Benchmark scoreboard (week 4, running)

Blind review by context-free subagents, then a Foundry proof re-run by the
pipeline. "Found" was checked by hand against the published finding (same
root cause), not just a location match.

| contest | prompt | published Highs | High found + proven | severity agreed | Mediums found + proven | drafts (H/M/L) | known-issue filtered | plan tokens (approx.) |
|---|---|---|---|---|---|---|---|---|
| PoolTogether 2024-03 | v1 | 1 | **1/1** | 1/1 | 1/8 (M-06 twin, filtered as bot-known) | 1/0/1 | 3 | ~1.2M |
| Canto 2023-11 | v1 | 1 | **1/1** | 0/1 (rated Medium) | 1/2 | 0/3/0 | 0 | ~0.4M |
| Kelp 2023-11 | v2 | 3 | **2/3** (H-02, H-03; missed H-01) | 2/2 | 2/2 | 2/4/0 | 1 | ~0.7M |
| DYAD 2024-04 | v2 | 10 | **6/10** (H-01,03,05,06,08,09) | 4/6 (H-03, H-08 rated Medium) | 0/9 | 4/2/0 (+1 duplicate) | 0 | ~0.6M |
| **total so far** | | **15** | **10/15** | **7/10** | **4/21** | | | **~2.9M** |

Notes:
- Canto H-01 needs outside knowledge (cNOTE's exchange rate is scaled 1e18
  on Canto). The reviewer knew it without web access. Its proof relies on a
  cNOTE mock with that scaling, so a submission should cite the deployed
  contract.
- The review underrates severity (Canto H-01 came back Medium). Worth a
  prompt tweak: "permanently locked protocol/creator funds = High".
- Kelp: 7 of 7 candidates were confirmed by PoC. Two drafted Mediums (DoS
  until a newly added asset's oracle or strategy is configured) were not
  awarded; they hinge on trusted-admin sequencing. The miss, H-01 (arbitrage
  from Chainlink deviation thresholds), needs feed-parameter knowledge the
  review did not use.
- DYAD: all 7 candidates confirmed by PoC; 0 false positives drafted. The
  deploy-script bug (H-01) was proven without a mainnet fork by etching the
  real out-of-scope contracts at the script's hard-coded addresses and running
  the unmodified `DeployV2.run()`. Misses: H-02/H-07/H-10 and most Mediums are
  liquidation-economics issues (partial liquidation, incentives, bonus math);
  H-04 needs an unlicensed fake vault. The review still underrates DoS-style
  "funds locked" Highs (H-03, H-08 came back Medium). Candidate for prompt v3.
- Duplicates: `bughunter prove --duplicate c01:c00` keeps a confirmed
  duplicate out of the drafts (listed in `report/duplicates.md`).
- Known-issue filter v2: matching on lines alone wrongly hid two awarded Kelp
  findings (H-02, M-01) that sit next to unrelated bot notes. It now requires
  the bot issue to be about the same bug class; regression-checked on all
  contests so far.
- Misses so far are mostly Mediums that need off-repo context or that the
  prompt's "no speculation" rule dismissed (PoolTogether M-02, M-05).

**API key in cloud sessions:** add `ANTHROPIC_API_KEY` as an environment
variable on the `vercel-bug-hunter` cloud environment (environment menu →
Edit). New sessions pick it up.

## Adding a contest

1. Copy `contests/c4-2024-03-pooltogether.yaml`. Set `repo`, the full 40-char
   `commit`, `solc`, `scope.project_dir`, and the `scope.files` list from the
   contest page.
2. For benchmark contests, add `benchmarks/truth/<id>.yaml` with each High
   finding's contract, root function(s) and bug class.
