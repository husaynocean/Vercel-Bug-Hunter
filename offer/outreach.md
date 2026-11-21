# Outreach kit: pre-audit scans

Replace everything in [brackets]. One specific line about *their* project is
what gets a reply, so never send the template unedited.

---

## 1. First DM (X, Discord, Telegram)

Short on purpose. Under 600 characters, so it reads in one screen.

> Hey [Project] team, saw [specific thing: your testnet launch / your ETHGlobal
> win / your v4 hook] and had a look at [repo or contract name].
>
> I run pre-audit scans for Solidity protocols: an AI-assisted review I finish
> by hand, and every bug I report comes with a Foundry test that passes on your
> code today and fails once the fix is in. No proof, no report.
>
> Before your main audit it usually means fewer findings to pay for and fix.
> Fixed price from $500, results in 3–5 days.
>
> Want me to send a sample report? Track record: x.com/xyz_husayn

**If they have no public repo**, swap the first line for:
> Hey [Project] team, saw you're heading to mainnet on [chain] soon.

---

## 2. LinkedIn connection note (300-character limit)

> Hi [Name], saw [Project] is launching on [chain]. I do pre-audit scans for
> Solidity teams: each bug comes with a Foundry test that proves it, plus a fix.
> From $500, 3–5 days. Happy to send a sample report if useful.

---

## 3. Follow-up (once, 4–5 days later, only if no reply)

> Quick follow-up in case this got buried. Here's a real finding from a past
> public contest, so you can see the format: [link to the offer page]. If the
> timing's wrong, no worries, and good luck with the launch.

Then stop. Two messages per project, maximum.

---

## 4. Proposal (send when they reply with interest)

**Pre-audit scan for [Project]**

**What you get**
- A review of the contracts you name, at a pinned commit. Nothing outside that
  list is analysed.
- Slither and Semgrep run first, then every external and public function is
  reviewed for:
  - access control, reentrancy, rounding;
  - oracle manipulation, accounting, external integrations;
  - denial of service, standards compliance.
- For each bug: severity, root cause, impact, a Foundry test that passes on your
  code (proving the bug) and fails once the fix is applied, and the fix as a diff.
- I review every finding by hand before it reaches you. Anything I can't prove
  with a test is left out.
- A free fix check: once you patch, I re-run every test to confirm the fixes hold.

**Track record**
- Tested on 9 past public Code4rena contests.
- Counting only the High-severity bugs the AI could not recite from memory, it
  found and proved 16 of 22 (73%).
- It also missed some, mostly liquidation economics, which is why this is a
  pre-audit and not a replacement for a full audit.

**Price** (fixed, by code size in nSLOC)

| Size | Price | Delivery |
|---|---|---|
| up to 500 | $500 | 3 days |
| up to 1,500 | $1,000 | 4 days |
| up to 3,000 | $2,000 | 5 days |

**What I need from you**
- The repo (a private invite is fine) and the commit hash.
- The list of files in scope.
- Any docs, plus anything you already know is risky.

**Terms**
- Your code and findings stay private. Nothing is published without your written
  permission.
- Payment: 50% upfront, 50% on delivery, in USDC or USDT. Suggested; adjust to
  suit you.

---

## Tips

- **First clients:** consider a discount, or a free scan of one contract, for
  your first 2–3 clients in exchange for a testimonial you can quote. Reviews
  make the next sale much easier.
- **Before you DM a project:** read its README and contracts first. A real
  observation ("your `withdraw` has no slippage check") beats any template.
- **If you find a serious bug before they've agreed to anything:** tell them
  privately and don't put a price tag on it. Never post it publicly.
- **Volume:** 5–10 well-researched messages a day. X free accounts have tight DM
  limits, and mass DMs get flagged as spam.
- **When DMs are closed:** use the project's Discord (a support or partnership
  ticket), or reply to a launch post.
