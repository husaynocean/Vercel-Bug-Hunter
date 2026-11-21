# X post (thread). Attach bughunter-1m45s.mp4 to post 1.

## 1/ (the hook)
I gave an AI 9 real smart-contract audit contests.

Then I checked if it was cheating.

On the High-severity bugs it could NOT recite from memory, it still found 73%, and proved every one with a Foundry test.

How 🧵

## 2/
Old audit reports end up in AI training data.

So I asked the model, with no code at all, to list each contest's High bugs from memory.

It could recite 13 of the 35. Those don't count.

On the other 22, it found and proved 16.

## 3/
The other problem with AI bug finders: false alarms.

So mine has one rule: no proof test, no report.

Every bug gets a Foundry test that passes on the buggy code and fails once the fix is in. 7 false alarms died that way.

## 4/
The pipeline:
1. Load only the code in scope
2. Scan with Slither + Semgrep
3. AI reviews every function against a bug checklist
4. Write a test that proves the bug
5. Report only what the test proves

## 5/
A real one it caught that it couldn't have memorised, Canto asD:

(balance * rate) / 1e28 - totalSupply()

cNOTE has 18 decimals, not 8. The math always underflows, so the owner's interest is locked forever.

The fix: 1e28 → 1e18

## 6/
Bugs it couldn't recite, found + proven:
Particle 4/4
AI Arena 4/4
Canto 1/1
Coinbase 1/1
Wildcat 3/5
DYAD 3/7

16/22 = 73%. Counting everything: 28/35.

## 7/
It's not perfect.
It missed 6 of those 22, mostly liquidation economics.
It under-rates severity.

So a human checks every finding.

## 8/ (the offer)
Shipping a Solidity protocol?

I'm doing pre-audit scans: proven bugs, each with a proof test and a fix, before your audit starts.

$500 up to 500 nSLOC
$1,000 up to 1,500
$2,000 up to 3,000

DMs open: @xyz_husayn

---

# Offer tweet (post separately, attach x-offer-1.png to x-offer-4.png)

Launching a Solidity protocol?

I find the bugs before your auditors do, and every finding comes with a Foundry test that proves it.

No proof, no report.

From $500. Fixed quote in 24h.

DM me 👇

## Reply to your own offer tweet (only after you share the page publicly)

Full offer + a sample finding: <paste the shared artifact link here>
