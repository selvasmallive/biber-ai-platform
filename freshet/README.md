# Freshet

Canadian T1 and T2 tax filing for Windows and macOS, with a grounded AI advisor that works on your actual return.

> **Status: working app, not a filable one.** The calculation engine, the AI egress boundary and the desktop shell are built and tested. The CRA transmission adapter and the T2 return are not yet written. Nothing here is CRA-certified, and the shipped 2025 tax data is explicitly marked unverified — see [docs/CRA-CERTIFICATION.md](docs/CRA-CERTIFICATION.md).

## Why the name

Canadian tax software clusters hard around one suffix: TurboTax, FutureTax, CloudTax, AuraTax, TaxTron, TaxCycle, TaxFreeway, Tax Chopper, AdvTax, myTaxExpress. A mark built on the descriptive word "tax" is weak — hard to register and harder to defend, because every competitor has an equal claim to the word.

The trap on the other side is a name that swallows someone else's mark. An earlier candidate, *Northtally*, was dropped for exactly that: Tally Solutions ships accounting and tax software into Canada, CIPO carries TALLY records, and "North" is a geographic prefix that examiners discount — leaving "tally" as the dominant element in a directly related class.

**Freshet** is an arbitrary mark: a real word (the spring thaw, when a river runs high with meltwater) applied to something it has nothing to do with. Arbitrary marks are the strongest registrable category — the "Apple for computers" pattern — and no software, fintech or tax company surfaced using it. It also happens to describe the season the product is used in.

Before committing: run a CIPO trademark search, check `freshet.ca` and `.com`, and confirm no CRA-certified product is in flight under a similar name.

## Platform decision

**Windows and macOS desktop. No web, no mobile.**

CRA certifies per delivery channel, per tax year, per return type — Windows and macOS are *separate listings* even for the same product. Desktop-only keeps the first season to two submissions instead of six to eight, and avoids becoming the transmitter of record with taxpayer returns on your servers. Full reasoning, with sources, in [docs/CRA-CERTIFICATION.md](docs/CRA-CERTIFICATION.md).

## Architecture

```
crates/
  freshet-engine    calculation engine — pure, decimal, no I/O
  freshet-taxdata   versioned parameter packs + form definitions (JSON)
  freshet-advisor   AI advisor: grounding, PII redaction, consent
  freshet-store     encrypted vault: XChaCha20-Poly1305, key in the OS keychain
  freshet-autofill  CRA Auto-fill: slip mapping, reconciliation, transport seam
  freshet-couple    coupled returns: spousal amount, pooling, transfer optimization
desktop/
  src/              React + TypeScript UI
  src-tauri/        Tauri v2 shell; the only code that touches the network
```

Three decisions worth knowing about:

**Tax rules are data, not code.** A form line is a JSON expression tree, not a Rust function. A new tax year is a data change that a tax professional can review without reading Rust, and the evaluator gets a complete audit trail for free. Lines resolve as a DAG with cycle detection, so a form author never has to topologically sort by hand.

**Exact decimals everywhere.** `f64` cannot represent `0.145`. A return that is off by a cent fails certification, so every amount is a `rust_decimal::Decimal` and rounding is explicitly half-away-from-zero, never banker's rounding.

**Provenance is mandatory.** Every rate and threshold carries a `source` citation and a `verified` flag. The engine refuses to call a return filable while any parameter behind it is unverified. The failure mode that kills tax software is one stale threshold surviving into a new year; making provenance a required field means an unsourced number cannot be added by accident.

**One form, many years.** Tax years 2025 and 2026 are both supported, and they share a single form definition — only the parameter pack differs. That is the payoff from keeping the rules as data: a new tax year is a file, not a fork. It splits into per-year forms the first time a line is actually added or removed.

**Verification is a ledger, not a checkbox.** `crates/freshet-taxdata/tests/verification.rs` pins the exact set of parameters that are still unverified, per pack. Adding a parameter without verifying it fails that test, which forces the omission to be a deliberate line on the list rather than something that drifts into a filed return. Delete a line when its value is verified; the count is the progress bar.

As of the 2026-08-16 pass: **federal 2026 is 30 of 60 verified** (brackets, indexed credit amounts, CWB bands, CPP and EI all confirmed against CRA), **federal 2025 is 24 of 60**, **Ontario 2025 is 23 of 36** (checked line by line against Form ON428 and Worksheet ON428), and **Ontario 2026 is 9 of 36** — Ontario has not published its 2026 package, so its indexed amounts are estimated from the now-verified 2025 figures at Ontario's own 1.9% factor, derived from the confirmed brackets rather than assumed from the federal 2.0%.

The **Ontario health premium** and **Ontario tax reduction**, both found missing during that pass, are now built. Order matters and the form is explicit about it: the reduction applies to tax after the surtax, and the premium is added *after* that rather than netted against it — so it is charged even on a return whose Ontario tax has been reduced to nothing.

The premium's published chart is eleven rows of alternating ramps and plateaus. It is modelled as **five clamped ramps**, from which every plateau falls out of the arithmetic; the tests check both kinds of point against the published figures.

**Computing a year is not permission to file it.** `SUPPORTED_YEARS` and `CERTIFIED_YEARS` are deliberately separate lists, and `CERTIFIED_YEARS` is empty until a certification letter exists. CRA certifies per tax year, so a build that models 2025 while holding only a 2026 certification is fine — one that *offers to file* 2025 on a 2026 certification is not. The return view carries `certified_to_file` independently of whether the return itself is sound, and the app says which of the two is blocking.

**2026 is the certification target**, because CRA distributes test returns in the November before a filing season. The 2026 pack distinguishes CONFIRMED figures (brackets, basic personal amount, the 14% rate — announced by CRA) from ESTIMATED ones (2025 indexed at the confirmed 2.0% factor) and PLACEHOLDER ones (CPP and EI maxima, which are announced separately and are simply wrong until replaced). Every one is `verified: false`, so nothing files either way.

### The AI advisor

Bring-your-own-key: Anthropic, OpenAI, your own Biber gateway, or a local OpenAI-compatible endpoint. Inference is never proxied through our servers.

The advisor sees **line numbers and amounts only** — never name, SIN, address, employer or date of birth. On top of that, everything the user types is passed through a checksum-validated PII redactor, and the check fails closed: if a detector still fires on the redacted text, nothing is sent. Remote providers need explicit per-provider consent, and consent given for a local model does not silently carry over to OpenAI. A local model needs no consent at all, because nothing leaves the device.

It advises; it cannot edit the return. The user makes the change and certifies it.

Crucially, **the webview never talks to a provider**. Every call leaves through a Rust command, and the app grants the webview no HTTP permission at all — so the consent and redaction checks sit on the only path to the network rather than being frontend politeness that a bug could route around.

### Review

Every return is checked against a set of rules written in the same expression language as the form lines, so a tax professional can audit them without reading Rust. One rule governs the rules: **a check that cannot distinguish a mistake from a legitimate case is a warning, never an error.** Two employers legitimately push combined CPP over the annual maximum, and the excess comes back on the return — blocking that would be worse than nagging. Errors are reserved for the internally impossible, and they block filing.

### Coupled returns

A couple files two returns, not one, but several amounts may go on either — and picking wrong costs real money. Freshet computes both returns under every allocation and keeps the lowest **combined** tax.

It does not encode the rules of thumb, because they invert:

- **Medical expenses** are reduced by 3% of the claimant's net income, which argues for the lower earner — until that spouse has no tax to absorb a non-refundable credit, at which point the answer flips.
- **Donations** are credited at a higher rate above the first $200, so pooling beats splitting; but in Ontario the credit lands *before* the surtax, so a dollar of it is worth up to 1.56 on a return that pays surtax.
- **Pension income splitting** (T1032) has the most moving parts. Moving income changes both net incomes, and net income drives the age amount clawback, the spousal amount and the medical threshold. It can also create a *second* $2,000 pension income amount on the receiving return — but only if the sending spouse was old enough for the income to be eligible in the first place. The optimum is rarely 50% and rarely 0%; Freshet sweeps every share in both directions.
- **Schedule 2** moves whatever age, pension and disability amounts a spouse cannot use, plus up to $5,000 of tuition.

The optimizer finds all of this by evaluation against the real engine; the heuristics appear only in the explanation the UI shows.

**Child care is the exception, and the UI says so.** The rules require the spouse with the *lower net income* to claim it — there is nothing to optimize, and a naive optimizer would get it wrong, because a deduction is worth more against the higher earner's marginal rate. It is reported as a decision marked `mandatory`, so the product never takes credit for a choice it did not make. It is also why the two-thirds-of-earned-income cap bites so often: the person required to claim is the one with the least income to measure it against.

Resolving a couple takes four passes, each depending on the one before: incomes before child care (to find the lower earner), net incomes with it applied, unused transferable amounts, then the final returns.

Still missing: carryforward *between* tax years. Unused tuition is computed and reported as a diagnostic so it is not silently lost, but next year's return needs it entered by hand.

### Auto-fill my return

Auto-fill is a CRA service, not a scrape. Freshet never sees, prompts for, or stores CRA credentials.

Mapping, multi-slip aggregation, conflict detection and contribution-room handling are built and tested; only CRA's transport is missing, and it cannot be built from public information — see `CraAutofill` in [freshet-autofill](crates/freshet-autofill/src/source.rs). A fixture source runs the whole path today.

Three rules it holds to: nothing is written to the return without a decision (CRA is explicit that Auto-fill does not move responsibility off the filer); boxes this build cannot place are surfaced rather than dropped; and contribution-room figures always carry their as-of date, because CRA's numbers miss unreported contributions and TFSA over-contribution costs 1% per month.

### Storage

Returns are held in one sealed file that the app rewrites atomically, keeping the previous version as `.bak`. XChaCha20-Poly1305 with a random nonce per save; the 50-byte header is passed as associated data, so the key-source byte and salt cannot be rewritten without the tag failing. The 32-byte key lives in the OS keychain — Windows Credential Manager or macOS Keychain — and never appears in the file or in a `Debug` line.

Returns save themselves as you type. Only the *inputs* are stored, never the computed result: the engine is deterministic, so recomputing on load is cheaper than storing and immune to a stale figure surviving a rule change.

There is no escrow and no recovery. Lose the keychain entry and the vault is gone — the correct trade for tax data, and the UI says so plainly.

Passphrase-protected vaults (Argon2id) are implemented and tested in the crate; the app currently opens keychain-backed vaults only, and the file format already carries the key-source byte needed to switch.

## Run it

```bash
cargo test
```

36 tests: engine arithmetic and guardrails, hand-computed T1 golden vectors, and the AI egress boundary. The desktop app is excluded from this workspace, so the engine loop stays a two-second cycle.

```bash
cd desktop && npm install && npm run tauri dev
```

To produce installers (`.msi`/`.exe` on Windows, `.dmg`/`.app` on macOS):

```bash
cd desktop && npm run tauri build
```

## What is next

1. **Code signing and notarization** — an unsigned tax app will be refused by SmartScreen and Gatekeeper. Needs an EV cert on Windows and an Apple Developer ID.

**Licensing — free to prepare, licensed to file.** The intended model: the download prepares a complete return for nothing, and a validated licence key is required to transmit. Two design constraints follow from what this product already is:

- **Validation must work offline.** The whole pitch is local-first, and a licence check that phones home contradicts it in exactly the way the audience notices. Use signed licence files verified against a public key compiled into the binary — no call home, no telemetry, works on a disconnected machine.
- **It slots in beside `CERTIFIED_YEARS`.** Transmission already has one gate that is independent of whether the return is sound; the licence is a second one at the same point, and should surface the same way — the app saying *which* gate is closed rather than a generic refusal.

Worth pricing per licence with several returns rather than per return: that is where a desktop product genuinely beats the free online tools, and it sells to families rather than competing head-on with free.
2. **CRA developer registration** — the gating item, and time-sensitive. Test returns land mid-November. See [docs/REGISTRATION.md](docs/REGISTRATION.md).
3. **Verification pass on 2025 data** — check every value against its citation, flip the flags.
4. **The remaining twelve provinces and territories** — mostly data, not code, and the largest single piece of work left.
5. **Transmission** — NETFILE, plus the CRA Auto-fill transport. Both behind the NDA boundary; both slot in against interfaces that already exist.
6. **T2** — a separate product on the same engine. See below.

## T2 is not a feature, it is the next product

Freshet is **T1 only** today, deliberately. T2 is worth building on the same engine, but not in the same certification cycle as a first T1, and it is worth knowing why before committing.

**What carries over:** the calculation engine, the expression language, decimal arithmetic, the provenance gate, the diagnostics framework, the encrypted store, the advisor, and the desktop shell. That is most of the hard infrastructure.

**What does not:**

- **A separate certification.** Corporation Internet Filing has its own approved-software list, its own test cycle, and — as with T1 — Windows and macOS are listed separately. Roughly doubles the annual submission count again.
- **GIFI.** Every T2 carries financial statement information coded to the General Index of Financial Information: a balance sheet and income statement mapped onto several hundred codes (schedules 100, 125 and 141). It is a subsystem in its own right, not a form.
- **A much larger schedule surface** — the Schedule 1 accounting-to-tax reconciliation, capital cost allowance, the small business deduction, shareholder information, and so on.
- **A different year model, and this one bites.** A corporation's tax year is its *fiscal period*, which can end in any month and need not be twelve. The engine currently keys everything on `tax_year: u16` and the T1 form asks for "province of residence on December 31". Both assumptions are wrong for T2, so the year model needs generalising before any T2 form is written.

**Encouraging precedent:** CloudTax T2 Basic is certified with only three services, so a minimal T2 entry is viable — you do not need the full professional feature set to be listed.

**Québec (TP1) is a separate product, not a feature.** A Québec resident files both a federal T1 and a provincial TP1, against a different specification (IN-413-V), a different transmission service (NetFile Québec), and a two-stage approval with Revenu Québec — one for reproducing forms, one for transmitting. It gets its own roadmap and its own launch; see [docs/REGISTRATION.md](docs/REGISTRATION.md).

A ranked gap analysis against TurboTax, Wealthsimple Tax, UFile and the rest is in [docs/COMPETITORS.md](docs/COMPETITORS.md).

Item 3 is the gate on everything downstream. Nothing should transmit until it is done.
