# Mamoru: notes before the DM (read 23 Nov 2026)

**Repo:** github.com/ottodevs/mamoru (very active; latest commit 23 Nov).
**Contact:** X @entermamoru (the only channel in the README) · mamoru.lol · app.mamoru.lol

## What it is

Automated USDC savings on Base. Passkey-owned Safe accounts, and an engine that
can only act inside on-chain policy contracts. Funds go into Uniswap v3
liquidity and listed vaults.

## What I read

- README, and `contracts/action-policy/SECURITY.md` (their V4 threat model, a
  long, careful document).
- The list of V4 contracts and their sizes.
- I didn't run anything.

## What stands out

1. **Live with real money.** The README's status table says: "Live: Base
   mainnet … Cap of 10,000 USDC per account since 7 Nov 2026." Its Mumbai
   section adds that the cap was "proven on a Base fork up to 60,000".
2. **The next version is unaudited.**
   - The README's "Next" item is "One authorization (V4 policy)".
   - `SECURITY.md` says the V4 scope is "Not deployed and not audited".
3. **V4 can't be fixed after deployment, by design.** It has "no guardian, no
   registry, no admin, no owner, no upgrade, no pause". Their own words: "a
   mistake stays until a new version, so the unit test and the fork deploy test
   … are the gate before T7". An outside review before deployment is the only
   other gate they could add.
4. **Earlier reviews:** a "LeftClaw" review of V2/V3 (findings M-2 to M-6,
   referenced as fixed). I found nothing showing that V4 has been reviewed.
5. **V4 scope size:** about 1,720 non-comment lines.
   - `MamoruActionPolicyV4`: 1,133
   - `MamoruGasPolicyV2`: 147
   - `MamoruRemoteSafe`: 125
   - `MamoruV4Classes`: 112
   - `MamoruV4Chains`: 80
   - `MamoruMigrationCheck`: 47
   - `MamoruV4Lens`: 42
   - `MamoruV4Table`: 32

   That's the **$2,000 tier** (up to 3,000).

## Offer

A proof-based pre-audit of the V4 scope listed in their `SECURITY.md`, before
T7 (deployment). $2,000, 5 days. Each finding comes with a Foundry test, which
suits a team that already pins every invariant to a named test.

## The DM (X, @entermamoru)

> Hey Mamoru team, read through SECURITY.md for the V4 policy. That's one of
> the most careful threat models I've seen on a small team.
>
> One thing stood out: V4 is "not deployed and not audited", and by design it
> has no owner, pause or upgrade, so as you put it, "a mistake stays until a
> new version". That makes the review before T7 the only gate.
>
> I do pre-audit reviews where every finding comes with a Foundry test that
> passes on your code today, proving the bug, and fails once the fix is in. For
> the V4 scope (~1,700 lines: ActionPolicyV4, GasPolicyV2, RemoteSafe, the
> tables) it's $2,000, 5 days, before you deploy.
>
> Want a sample report? [offer page link]

**If their DMs are closed:**
- Look on mamoru.lol and app.mamoru.lol for a contact or Discord link.
- Or reply to one of their posts with a neutral nudge: "Is there a good way to
  reach the team about a V4 security question?" Keep the details private.

## Update: X inbox closed (23 Nov)

The bio says "DMs open", but X shows a closed inbox: probably only accounts
they follow, or verified accounts, can message them. mamoru.lol shows
**hi@mamoru.lol**, so email that instead.

**Subject:** V4 policy: a proof-based review before T7

> Hi Mamoru team,
>
> I read through SECURITY.md for the V4 policy. That's one of the most careful
> threat models I've seen on a small team.
>
> One thing stood out: V4 is "not deployed and not audited", and by design it
> has no owner, pause or upgrade, so as you put it, "a mistake stays until a
> new version". With accounts already live on Base at up to 10,000 USDC, the
> review before T7 is the only gate.
>
> I do pre-audit reviews where every finding comes with a Foundry test that
> passes on your code today, proving the bug, and fails once the fix is in.
> Anything I can't prove is left out. For the V4 scope in SECURITY.md (~1,700
> lines: MamoruActionPolicyV4, GasPolicyV2, RemoteSafe, MigrationCheck and the
> tables), it's $2,000, delivered in 5 days, before you deploy.
>
> Sample finding and track record: [offer page link]
>
> Congrats on the Curator pick, by the way.
>
> [Your name]
> x.com/xyz_husayn

**Optional public nudge** (reply to their 10 Nov "AMA" post; no details):
> Congrats! Sent a note to hi@mamoru.lol about V4. Is that the best way to
> reach the team?
