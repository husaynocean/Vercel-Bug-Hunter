# Leads for pre-audit scans (researched 21 Nov 2026)

Every lead below has public Solidity/EVM code and no audit by a known firm,
according to its own repo or docs as of 21 Nov 2026. That can change quickly,
so re-check the README before you message. Contacts are the project's own
public channels only. Where the list says "repo only", look for a contact link
on the project's website or in the README first.

Columns:
- **Lines:** rough count of non-test Solidity lines; it sets the price tier.
- **Opener:** the specific line to put at the top of the DM in `outreach.md`.

---

## Tier A: message these first (live with user funds, or blocked on an audit right now)

### 1. AsyncSwap (Uniswap v4 hook, escrowed limit orders)
- **Chain:** Unichain first; now on Unichain Sepolia and Robinhood Chain testnet.
- **Signal:** `MAINNET_READINESS.md` says "Blocked: waiting for audit". The audit
  scope was frozen on 5 Nov 2026 and the last commit was 17 Nov.
- **Past reviews:** individuals and an AI-assisted review, but no major firm.
- **Contact:** X @asyncswap · asyncswap.org · github.com/asyncswap
- **Tier:** probably $1,000. Check the size of the frozen scope first.
- **Opener:** "Saw your audit scope froze on 5 Nov and mainnet is waiting on it.
  A proven pre-audit pass now usually means fewer, cheaper findings in the main one."

### 2. Fulcrum (spot-funded prop trading, USDC LP vault)
- **Chain:** Base mainnet, live (PositionManager and LPVault).
- **Signal:** built at ETHGlobal Mumbai (6–7 Nov). Not audited; the README has
  a "Known gaps before audit" section.
- **Contact:** fulcrum-trade.vercel.app · github.com/Niraj-Kamdar/decentralised-prop-trading
  (look for a contact link on the app)
- **Lines:** about 4,800, so it needs a custom quote (about $2,500), or scope it
  to PositionManager and LPVault for $2,000.
- **Opener:** "Saw Fulcrum is already live on Base with an LP vault, and your
  README lists the known gaps before audit."

### 3. Mamoru (automated USDC savings on Safe accounts)
- **Chain:** Base mainnet with real funds. The per-account cap was raised to
  10k USDC on 7 Nov.
- **Signal:** very active, with commits on 20 Nov. `SECURITY.md` says an earlier
  version was "not deployed and not audited".
- **Contact:** X @entermamoru · mamoru.lol · github.com/ottodevs/mamoru
- **Lines:** the v4-policy contracts are about 630, so scan the new policy for
  $1,000.
- **Opener:** "Saw you raised the per-account cap to 10k USDC. Is the v4 policy
  covered by the earlier review?"

### 4. BELL / belldex (AMM for tokenized stocks, v4 hook)
- **Chain:** Robinhood Chain mainnet, live.
- **Signal:** its own app says "An independent security audit is not complete.
  Treat every BELL contract as unaudited." Last commit 21 Nov.
- **Contact:** X @BELLdexFi · github.com/belldex
- **Opener:** "Saw BELL is live on Robinhood Chain and still labels every
  contract as unaudited."

### 5. Hookr (token launchpad on a shared v4 hook)
- **Chain:** Robinhood Chain mainnet, live.
- **Signal:** the README says "No independent audit has been completed." Last
  commit 17 Nov.
- **Contact:** hookr.fun · github.com/Hookr-fun
- **Opener:** "Saw Hookr is live with vesting and pay-later contracts and no
  independent audit yet."

### 6. Aqua0 (shared-liquidity vaults, v4-hook strategies)
- **Chain:** private mainnet beta on Base, Avalanche, Arbitrum, Celo and Monad.
- **Signal:** the hook repo says "Unaudited. Testnet only" (updated 17 Oct).
  They took part in the Uniswap Foundation acceleration programme and placed
  3rd in the Arbitrum Open House buildathon.
- **Contact:** X @AquaZero0 · aqua0.xyz · github.com/Aqua0-fi
- **Opener:** "Congrats on the Arbitrum Open House result. Saw the base hook is
  still marked unaudited."

### 7. Xochi (private trading; ERC-8262 compliance oracle)
- **Chain:** Base Sepolia, with Base mainnet as the target.
- **Signal:** issue #30 (18 Oct) says "Freeze the audit candidate and commission
  external audit", and the firm is not chosen yet.
- **Contact:** X @xochi_fi · xochi.fi · github.com/xochi-fi
- **Scope:** the Solidity oracle, pause and rotation logic. The ZK verifiers
  are out of scope for this tool.
- **Opener:** "Saw you're picking an audit firm for the ERC-8262 oracle."

### 8. imdUSD / INFER (stablecoin vault)
- **Chain:** Ethereum mainnet, live since 11 Oct.
- **Signal:** the README says its pre-launch reviews were "not third-party audit
  firms".
- **Contact:** x.com/imdusd · imdusd.com · github.com/imdusd/infer-protocol
- **Caution:** parts of the project look AI-agent-run. Check that there's a
  human who can pay before you put time in.

---

## Tier B: pre-launch and small (good for the $500 tier, or a free first scan for a testimonial)

| Project | What it does | Chain | Size | Signal | Contact |
|---|---|---|---|---|---|
| Earlyout | ERC-4626 vault buying redemption claims | Arc testnet | ~1.2k | ETHGlobal Mumbai; "grant-readiness" PR on 20 Nov; no audit | earlyout.vercel.app · github.com/ETH-Global-Mumbai-2026/earlyout |
| Vaipakam | P2P lending and NFT rental (Diamond proxy) | Base / Arbitrum Sepolia | Foundry | README: "third-party security audit is required before any mainnet launch" | vaipakam.com · github.com/vaipakam/vaipakam |
| Zenith | Uniswap v4 curated-liquidity hook | Unichain Sepolia | ~390 | Uniswap hookathon (UHI11) now; Atrium lists demo day as 11 Dec | github.com/Dydex/zenith (repo only) |
| Dob Protocol | RWA DEX on v4 hooks | Unichain Sepolia | Foundry | UHI8 Unichain prize; testnet; no audit; commit 20 Nov | dobprotocol.com · github.com/Dobprotocol |
| DeltaMon | Delta-neutral USDC vault | **Monad mainnet** | ~2.5k | README: "new and unaudited; deposit caps apply" | github.com/tima-t/deltamon (repo only) |
| Floorline | Fully backed MON put options | Monad mainnet vault | ~1.1k | Monad Metropolis; no audit; quiet since 16 Oct | floorline-app.vercel.app · github.com/jenzylove/floorline |
| Tremor | v4-hook volatility cover for LPs | Sepolia | ~2.1k | ETHGlobal Mumbai; no audit | tremor-mumbai.vercel.app |
| CRSHMARKET | 60-second livestream prediction markets | Monad (live) | ? | Raised a $3.5M seed (reported 3 Nov); audit unknown | @crshmarket |
| 0xterm | DeFi terminal + dead-man-switch contract | testnets | Foundry | "Mainnet is disabled until an independent audit is attached" | 0xterm.xyz |
| BaseYield | Aerodrome LP automation | Base Sepolia | Foundry | "NOT YET AUDITED … audit scheduled prior to mainnet" | github.com/altrudev/baseyield-contracts |
| TAOP | On-chain reputation oracle for AI agents | Base Sepolia | Foundry | "not yet audited … Not ready for mainnet" | github.com/lexagor/TAOP-protocol |

---

## Where to find more buyers

- **Callisto audit-request board:** github.com/CallistoSecurity/Smart-contract-auditing/issues
  - Projects post public requests for audit quotes there every few weeks, and
    freelancers bid in the thread.
  - Bids run from $40 to $1,200, so compete on proof (the Foundry tests), not on
    price.
- **Uniswap Hook Incubator (UHI11):** the hookathon runs to 3 Dec, with demo day
  on 11 Dec. Small v4-hook projects are a perfect fit for this tool.
- **Base Batches 004:** the cohort just held its demo day (17–18 Nov). Watch for
  teams announcing mainnet, e.g. Tribeca, Conta, LEDiG.
- **Audit-subsidy rejects:** the Arbitrum Audit Program approved only about 4%
  of applicants, so teams announcing they "applied for an audit grant" are
  likely buyers.

## What I could not check

- **X, Reddit and LinkedIn posts:** the research tools couldn't search them
  directly, so most leads come from public GitHub repos, hackathon pages and
  accelerator announcements.
- **Hackathon results:** ethglobal.com, devfolio.co and monad.xyz were
  unreachable, so prize results are unconfirmed.
- **Current state:** live TVL and whether a team has booked an auditor in the
  last few days were not checked.
