# The Freshet squad

Six agents covering the work between here and a certified, saleable product.
They are named `freshet-*` because this repository also holds XRIQ, the Lattice
wallet and the corpus pipeline; the prefix keeps them from being picked up for
unrelated work.

Invoke one with the Agent tool, or ask for it by name.

## The roster

| Agent | Owns | Writes? |
| --- | --- | --- |
| `freshet-tax-data` | Every rate, threshold and CRA code; the verification ledger | yes |
| `freshet-tax-logic` | Form definitions against the Act and CRA guides | yes |
| `freshet-certification` | CRA programme: scope, channels, deadlines, claims | yes |
| `freshet-engine` | Rust across all crates; seams; test quality | yes |
| `freshet-privacy` | PII egress, credentials, vault, keys, PIPEDA | **read-only** |
| `freshet-product` | Pricing, competitors, channel economics | yes |
| `freshet-release` | CI, installers, signing, Google Cloud | yes |

`freshet-privacy` cannot edit on purpose. A reviewer who can patch the code can
paper over their own findings, and these are the invariants a customer has no
way to check.

## Routing

| If the change touches… | Ask |
| --- | --- |
| A number in `crates/freshet-taxdata/data/*.json` | `freshet-tax-data` |
| A rule — an `Expr` tree, a credit, an ordering, a proration | `freshet-tax-logic` |
| Both (a new schedule or jurisdiction) | tax-logic first, then tax-data |
| Rust anywhere | `freshet-engine` |
| The advisor, the store, the licence crate, the site | `freshet-engine`, then `freshet-privacy` |
| What we tell CRA, or what the product claims | `freshet-certification` |
| CI, installers, signing, deployment | `freshet-release` |
| What to build next, or what to charge | `freshet-product` |

## Sequencing a real change

Tax changes are the ones worth being careful about, because a wrong answer is
plausible, well-formatted, and silent.

1. **`freshet-tax-logic`** establishes what the legislation requires.
2. **`freshet-tax-data`** supplies the figures, each with a source it read.
3. **`freshet-engine`** implements, and challenges the tests — particularly
   whether any test was written from the code rather than from the Act.
4. **`freshet-privacy`** audits, if anything touched data handling.
5. **`freshet-certification`** checks the result against what has been
   promised, and that no refusal message now states the wrong reason.

Steps 1 and 2 can run in parallel with 7 and 8 of a release, but never skip 3:
every defect found in this project so far was either a wrong source, or a test
that agreed with the bug.

## What the squad is defending against

These are not hypothetical. Each has happened here.

- **A figure marked verified and wrong.** Four of thirty GIFI codes. One was
  not merely mislabelled: the form *subtracted* machinery as if it were
  accumulated amortization.
- **A test that confirms the bug.** It asserted what the data described, and
  passed for as long as the defect existed.
- **An estimate that was right fifteen times out of sixteen.** The method was
  sound, the indexing factor was correct, and a legislature raised an amount
  instead of indexing it.
- **A seam built early and never exercised**, silently wrong the moment a
  second return type existed.
- **The same decision made in three callers**, all three becoming wrong on the
  same day a province moved a rate to 1 July.
- **A disclosure keyed to a proxy**, which went quiet for exactly the people it
  was written for.

## The standing rule

**Escalate, do not decide**, on anything that: spends money, accepts terms,
goes to CRA or a customer, changes certification scope, touches the signing
key, or could reduce someone's refund. Draft it, state the trade-off, stop.

Every agent repeats this in its own terms. It is the one instruction none of
them may relax.
