# AsyncSwap: notes before the DM (read 21 Nov 2026)

**Repo:** github.com/asyncswap/contracts, head `b7ab5da` (17 Nov, "Deploy to Base mainnet").
**Contact:** X @asyncswap · asyncswap.org

## What I read

- README, `MAINNET_READINESS.md`, `audit/AUDIT_SCOPE_11_05_26.md`, and the
  `deployments/8453` registry.
- Three of the money-moving contracts in full: `FeeVault`, `TokenClaims` and
  `NativeClaims`. No issue found in them: each `unlockCallback` only accepts the
  PoolManager, and the PoolManager only calls back the contract that started
  the unlock.
- I did not run their tests. `foundry.toml` sets `ffi = true`, which lets tests
  run shell commands, so their test suite should only run in a throwaway
  machine.

## What stands out

1. **The code moved after the audit freeze.**
   - `MAINNET_READINESS.md` and `docs/deployments.md` say the source is frozen at
     `c9372ff` (5 Nov), and to "re-freeze in a new dated scope" if `src/` changes.
   - Since then, 15 files in `src/` have changed: +1,233 / −143 lines. New
     files: `IncomingMatching` (345 lines), `MultiAsset` (188),
     `RouterFlashFills` (185), `DutchAuction` (98), `TokenTransfers` (74) and
     `periphery/AsyncSwapFlashFiller` (84). `AsyncSwap.sol`, `Router.sol`,
     `AsyncFiller` and `AsyncMatching` also changed.
   - No new dated scope exists yet. `audit/` holds only the 11-03 and 11-05 scopes.
2. **The Base mainnet registry includes the new code.**
   - `deployments/8453/8453.json` (17 Nov) lists `IncomingMatching`,
     `MultiAsset` and `DutchAuction`, which are not in the frozen scope.
   - It also lists the hook, the Router, `FeeVault` and four stock/USDC pools
     (AAPLc, NVDAc, TSLAc and others).
   - I did not check on-chain whether those pools hold funds.
3. **They already use AI scanners.**
   - Previous reviews include Nethermind AuditAgent (twice), Pashov's
     `solidity-auditor`, a "Formal Mind" swarm and an earlier AI-assisted review.
   - So "AI pre-audit scan" alone is nothing new to them. The difference to
     pitch is proof: a Foundry test for every finding.
4. **There's an open question they want answered.** The scope says: "The 29
   leads in the Pashov review … are unconfirmed trails … confirming or ruling
   out any of them is in scope." Turning unconfirmed leads into a test that
   passes, or a clear "not a bug", is exactly what this pipeline does.

## Offer to make

- A pre-audit pass on the **post-freeze delta** (about 1,100 new lines plus the
  changed functions), in the **$1,000 tier**, delivered in 4 days.
- **Optional add-on:** confirm or rule out the 29 unconfirmed Pashov leads, each
  with a test or a short written reason. Quote it after looking at the leads.
- **Full scope** is 2,824 nSLOC at the freeze plus the delta, which is over the
  $2,000 tier. Only quote it if they ask.

## The DM (X, @asyncswap)

> Hey AsyncSwap team, went through the contracts repo. That's a serious review
> trail already (LSP, Pashov, AuditAgent, Formal Mind).
>
> One thing I noticed: MAINNET_READINESS freezes the audit scope at c9372ff
> (5 Nov), but src/ has gained ~1,100 lines since (IncomingMatching, MultiAsset,
> DutchAuction, flash fills), and deployments/8453 already lists those new
> libraries on Base. So the code on Base isn't fully the code your auditor will see.
>
> I can do a pre-audit pass on exactly that delta: every finding comes with a
> Foundry test that passes on your code today and fails once fixed. $1,000,
> 4 days. I can also confirm or rule out the 29 open Pashov leads the same way.
> Want a sample report?

**Before you send:**
- Open the repo once more and check whether a new dated scope has appeared in
  `audit/`. If it has, drop the "code your auditor will see" line.
- Have the offer-page link ready to send as the sample.
