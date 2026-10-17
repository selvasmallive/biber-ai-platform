# CRA certification: what it costs and how to sequence it

## The finding that drives the platform decision

CRA does not certify "a product". It certifies **a product on a delivery channel, for one tax year, for one return type**.

On the T1 side, the public certified-software list gives each product a "Software options" column with the values `Online`, `Computer download` and `Mobile app` — and products carry only the options they were certified for. Three of the seventeen products certified for 2025 (GenuTax Standard, FutureTax, myTaxExpress) are listed as **computer download only**, which is the proof that a desktop-only product is a complete, viable certification path.

On the T2 side it is more explicit still. The Corporation Internet Filing certified list contains, as **separate rows**:

- `T2Express (Windows)` and `T2Express (Macintosh)` — same vendor, same product, two listings
- `AuraTax Windows`, `AuraTax Mac OS`, and `AuraTax.ca` — three listings

So Windows and macOS are separately certified even for a single codebase.

### What that means in units of work

| Scope | Certification submissions per tax year |
|---|---|
| Windows desktop only, T1 | 1 |
| Windows + macOS desktop, T1 | 2 |
| Windows + macOS desktop, T1 + T2 | 4 |
| ...plus web | 6 |
| ...plus iOS/Android | 8+ |

Every one of those recurs **annually**. Certification is not a one-time gate.

### Recommendation

Ship **Windows + macOS desktop only**. Beyond the submission count, a web product makes you the *transmitter*: taxpayer returns land on your servers, which pulls in hosting, data residency, retention, breach notification, and a security posture you must defend to CRA. A desktop product keeps the return on the user's disk and transmits from their machine. That is a materially smaller surface for a first certification.

Sequence: **Windows T1 → macOS T1 → Windows T2 → macOS T2**. Add web only once T1 desktop has cleared one full season.

## The process

1. **Register with CRA as a software developer** and apply for the certification programme for the tax year you intend to support.
2. **Sign the confidentiality agreement.** This gates access to draft forms through a controlled-access site. You may not show customers draft forms before CRA's public release, usually in December.
3. **Receive the certification test returns.** CRA distributes these to registered developers in **mid-November** each year. Your software must reproduce CRA's expected results exactly.
4. **Pass and get listed** on the public certified-software page.
5. **Repeat next year.** Forms, rates, thresholds and schemas all change.

Note the T1 calendar: NETFILE for the 2025 tax year opened **23 February 2026** and runs to **29 January 2027**. Test returns arrive in November, roughly three months before that. Your engine must be feature-complete well before November to be testable against them.

### T1: NETFILE vs EFILE

- **NETFILE** — the individual files their own return. This is the consumer product.
- **EFILE** — a professional preparer files on behalf of clients. Separate certification and a separate applicant screening process, and preparers must describe the security methods protecting client information.

There is also a control worth designing for now: from **February 2026**, each EFILE account is bound to specific certified software products, and returns transmitted with unregistered software are refused. Plan on being registered per-product, not per-vendor.

### T2: Corporation Internet Filing

The T2 certified list shows a "Services Available" column. These are **individually approved capabilities**, not a single bundle. Observed across current products:

Corporation Internet Filing · T2 Barcode · Attach-a-doc · T2 Auto-fill Return · Authorization request (formerly RC59) · Pre-validate · T1135 · T1134 · T106 · RC4649 · Submit E-Docs · T2SCH89 · T217 · T2054 · T2057 · T2058 · T2059 · UHT2900 · Attach-a-doc SERs · T1521 · T2123 · T2311 · T5013

Start with the smallest credible set — **Corporation Internet Filing + T2 Barcode** — and add services in later years. Note that CloudTax T2 Basic ships with only three services, which is a viable entry point.

T2 also requires financial statement information coded to **GIFI** (General Index of Financial Information). Budget for GIFI as its own subsystem; it is not a small form.

## What this repository cannot contain

The actual CRA XML schemas, the transmission endpoints, and the certification test vectors are distributed to registered developers under the confidentiality agreement. They are **not public** and must not be committed here until you have signed and confirmed what the agreement permits.

The codebase is therefore built so those slot in behind a boundary:

- `freshet-engine` computes a return with no knowledge of transmission.
- The transmission adapter (not yet written) takes an `Assessment` and emits the CRA payload. That crate is where NDA'd material lands, and it should be a private submodule with its own access control.
- CRA test scenarios become a second, authoritative test suite alongside `crates/freshet-taxdata/tests/`, which currently holds hand-computed vectors.

## The verification gate

Every rate, threshold and dollar amount in `crates/freshet-taxdata/data/` carries a `source` citation and a `verified` flag. The engine refuses to mark a return filable while any parameter behind it is unverified:

```
test shipped_2025_data_is_not_yet_cleared_for_filing ... ok
```

The 2025 values currently shipped were seeded from **secondary sources** and every one is `verified: false`. Before any certification run, a human must check each against the CRA source named in its citation and flip the flag. Wire this gate into the transmit path so it is structurally impossible to file on unverified data.

Two values need particular attention because 2025 is a transition year: Bill C-4 cut the lowest federal rate from 15% to 14% effective 1 July 2025, giving a **blended 14.5%** for the full year. Confirm how CRA directs that rate to be applied to **non-refundable tax credits** for 2025 specifically — the pack currently assumes 14.5% and flags the assumption.

## Connecting to the taxpayer's CRA account

**Yes, this is legitimate and expected — but only through CRA's own service.** It is called **Auto-fill my return (AFR)**, and it is how every major certified product prefills slips today.

There is exactly one disqualifying way to build it: **do not screen-scrape My Account, and never ask for or store the user's CRA credentials.** That would breach CRA's terms, put you outside certification, and make a credential breach your liability. AFR is a proper delegated-authorization flow; use it or do nothing.

### Two flavours, different plumbing

| | Individual (NETFILE) | Preparer (EFILE) |
|---|---|---|
| Who authenticates | The taxpayer, into their own My Account, from inside the software | The representative, via Represent a Client |
| Prerequisite | NETFILE-certified software, approved for AFR | Registered electronic filer; CRA account with Represent a Client; RepID/GroupID/BN; EFILE-certified software |
| Authorization | The taxpayer is the account holder | Client must authorize the RepID — in My Account, by confirming a request, or via notice-of-assessment details |

Freshet is a self-file product, so the **individual flavour is the one to build**. The preparer flavour only matters if you later sell to accountants.

### What AFR delivers

CRA groups it as **tax information slips** and **other tax related information**; representatives additionally get CRA Online Service Registration, unfiled returns, and the **Client Data Enquiry (CDE)**.

Timing is the constraint that shapes the product: CRA receives most third-party data by end of February and has it available **by mid-March**. A user who opens the app in early February and clicks "import" gets a near-empty response. Say so in the UI, or you will be blamed for CRA's calendar.

Crucially, **AFR does not shift responsibility**. CRA is explicit that the filer must confirm every field is true, accurate and complete, and must chase the issuer for missing or wrong slips. Design the UI so imported values are visibly *imported and unconfirmed* until the user reviews them — never silently merged.

### Prior years and amending

- **ReFILE** is the service for amending a T1 electronically. It currently covers **2022–2025**, and it is a separately certified capability.
- Returns can be filed for **2018–2025**, but only with software certified *for that year* — which is why `SUPPORTED_YEARS` is a hard gate in `freshet-taxdata` rather than a loose config value.
- **T2 Auto-fill** is the corporate equivalent and appears as its own entry in the T2 "Services Available" column.

### Registered accounts: what you can and cannot import

This is where the answer gets uneven, and the differences matter for the advisor.

| | On the T1? | Available from CRA? |
|---|---|---|
| **RRSP** deduction limit, unused contributions, contributions to date | Yes | Yes — in My Account, and delivered by AFR |
| **FHSA** | Yes (deduction; T4FHSA slips) | Slips should flow with other slips. Participation-room delivery via AFR **not confirmed — verify** |
| **TFSA** | **No** — contributions are not deductible and never touch the return | Room is visible in My Account for most holders. Delivery via AFR **not confirmed — verify; assume user-entered** |

Two things follow.

First, the **annual dollar limits are not CRA account data at all** — they are published constants (TFSA $7,000 for 2025; RRSP 18% of earned income to an annual cap; FHSA $8,000/year and $40,000 lifetime). Those belong in the parameter packs with citations and `verified` flags, exactly like the tax brackets. Do not hardcode them in advisor prompts, where they cannot be reviewed and will silently rot.

Second — and this is the one that can hurt a user — **CRA's contribution-room figures are as of the last processed information and are routinely stale.** They do not reflect contributions made this year that the issuer has not yet reported. TFSA over-contribution attracts a penalty of **1% per month** on the excess. An advisor that reads "you have $12,000 of TFSA room" off a CRA import and cheerfully recommends contributing it is a liability generator.

The rule to build in: **the advisor may model contributions, but must state the room figure's as-of date and tell the user to confirm it before contributing.** Encode that in the system prompt in `freshet-advisor/src/context.rs`, and carry an `as_of` date on any imported room figure so the UI can show it.

### What AFR changes about the architecture

Today Freshet holds no identity at all. AFR changes that: it needs the taxpayer's SIN and name, and it returns their slips. Two existing boundaries absorb this without redesign, and both must hold:

1. **The vault.** Imported identity goes in the encrypted store with everything else, never in `settings.json`.
2. **The advisor.** Grounding is built from line numbers and amounts only, and the redactor fails closed on SIN and business numbers. Neither may be relaxed to "make the advisor more helpful" — those two rules are precisely what lets the advisor exist at all.

Before building any of this, confirm with CRA what the certification and AFR agreements permit, particularly around retaining imported data and around the AI feature.

## The AI advisor and privacy

This is a compliance surface, not just a feature. Sending taxpayer data to a third-party model provider is a disclosure of personal information under PIPEDA, and provider prompt-retention makes it durable.

The design in `freshet-advisor` addresses this structurally:

- The advisor is grounded on **line numbers and amounts only** — never name, SIN, address, employer or date of birth.
- All free text is passed through a checksum-validated PII redactor before egress, and the check **fails closed**: if a detector still fires after redaction, nothing is sent.
- Remote providers require **explicit, per-provider consent**. Consent granted for a local model does not carry over to OpenAI.
- Keys are bring-your-own and stored in the OS keychain; the serialized config holds only a keychain entry name.
- A local model (Ollama or equivalent) needs no consent because nothing leaves the device — that should be the default offered to privacy-sensitive users.

Confirm with CRA whether the certification agreement imposes any constraint on transmitting return data to third parties. Do this **before** the feature ships, not after.

## Sources

- [Find certified tax software — NETFILE (canada.ca)](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/netfile-overview/certified-software-netfile-program.html)
- [Corporation Internet Filing — Software (canada.ca)](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-businesses/corporation-internet-filing/software.html)
- [EFILE certified software for the 2026 EFILE program (canada.ca)](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/efile-electronic-filers/efile-certified-software-efile-program.html)
- [Apply for EFILE (canada.ca)](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/efile-electronic-filers/apply-efile.html)
- [Filing your T2 return electronically using certified software (canada.ca)](https://www.canada.ca/en/revenue-agency/news/newsroom/tax-tips/tax-tips-2022/filing-t2-return-electronically-using-certified-software.html)
- [NETFILE certification, vendor description (UFile)](https://www.ufile.ca/get-started/netfile-certification)

## What was actually applied for

**A T2 developer application was submitted on 2 September 2026**, filed with the
T2 Software Certification team. It changes several things this document
previously assumed, and the assumptions are corrected below rather than quietly
edited away.

The completed questionnaire is deliberately **not** committed: it carries a home
address and personal phone number, and the parts that affect the build are
recorded here instead.

| Declared | |
|---|---|
| Applicant | 16631886 Canada Inc., BN **790623961 RC0001** |
| Products | **Freshet T2 for Windows**, **Freshet T2 for MAC**, **Freshet T2 Online** |
| Website | https://bumi.ca |
| Market | small, medium **and large** businesses |
| Release | 6-12 months from September 2026 |
| Price | $0-$799 |
| Free for nil or inactive accounts | **yes** |
| Available for a Teams interview | yes |

### The T2 is the live application, not the T1

This document sequenced the work **Windows T1 → macOS T1 → Windows T2 → macOS
T2**. The application that actually went in is for the T2, so that ordering is
now wrong: corporate work is on the critical path rather than ahead of it.

### Three declared channels, including web

The recommendation below is desktop-only, on the grounds that a web product
makes you the transmitter. **Freshet T2 Online was declared anyway**, so the
application covers a product that does not exist and whose architecture
contradicts what is built:

- Licensing verifies **offline** against a key compiled into the binary. A
  browser cannot do that.
- The return is held in an **encrypted vault on the user's disk**, which is the
  basis of the claim that it never leaves their machine.
- The AI advisor sends line numbers to a provider the **user** chose with the
  **user's** key. A hosted product would be sending them with yours.

None of that is fatal. It is a different product with a different security story
and a separate certification, and it is worth deciding deliberately whether to
build it or to tell CRA the web channel is deferred. The declaration is not a
commitment to ship all three at once, but it is the scope CRA will expect.

### The free nil-return commitment is now in the code

The application answered **yes** to offering a free product for nil or inactive
accounts. That is a commitment, so the filing gate honours it: a T2 whose total
tax is nil files without a licence, and a test asserts a corporation that owes
tax still needs one. It is scoped to the T2 because that is the form the
commitment was made on.

Worth noting this is the opposite of TaxTron, which requires a purchase for
EFILE and print even at nil or a loss. It is a real differentiator, and now a
real obligation.

## Target year: 2027, not 2026

**CRA's application window for the 2026 T1 closed before this product applied.**
The first tax year Freshet can be certified to file is therefore **2027**, which
is filed in early 2028.

That is recorded in code as `CERTIFICATION_TARGET_YEAR`, kept deliberately
separate from `SUPPORTED_YEARS`. The two disagree right now and should: 2027 has
no parameter pack at all, because its indexed amounts are not published until
late 2026. A test asserts the divergence so that "we are targeting 2027" is
never mistaken for "we can compute 2027".

### What this changes

The engine does not care. A tax year is a parameter pack, and the loader now
takes a list of years rather than two named fields, so adding 2027 is the pack
files plus one entry — not a change to the loader's shape.

What changes is the calendar, and it is worth being honest that the slip is
mostly waiting:

| | 2026 target (lost) | 2027 target |
|---|---|---|
| Indexed amounts published | ~Nov–Dec 2025 | ~Nov–Dec 2026 |
| CRA test returns | Nov 2026 | Nov 2027 |
| Filing season | Feb–Apr 2027 | Feb–Apr 2028 |

So the data that gates everything is over a year away, and there is no T1 work
that can be finished before it arrives. The 468 unverified provincial
parameters are not urgent any more; they are simply waiting for forms that do
not exist.

### Worth confirming before accepting the slip

If the 2026 window closed only recently, it is worth asking CRA directly whether
a late application is possible. Twelve months is a long time to concede on the
strength of a published deadline, and the worst answer is no.

## Jurisdiction scope: Ontario only for the first release

The engine computes the federal return and all thirteen provincial and
territorial forms. The **certification application covers Ontario alone.**

The reason is data, not code. Only the Ontario 2025 pack has every parameter
checked against a published form. The other jurisdictions were built
structure-first: the forms are real and the arithmetic runs, but their numbers
are placeholders, and 468 of them across 24 packs cannot be sourced from what
is publicly reachable today. Applying for thirteen jurisdictions while nine
carry unverified parameters would be asking CRA to certify arithmetic nobody
has checked.

Narrowing costs nothing that matters. `CERTIFICATION_SCOPE` is separate from
`SUPPORTED_PROVINCES`, so the other twelve stay in the product: a taxpayer in
Alberta can prepare, review and print a complete return. They simply cannot
transmit it, and the app says so plainly on the return itself rather than only
at the point of filing.

Widening it later is a data exercise:

1. Source the published form for the jurisdiction and year.
2. Verify its parameters and clear the residual in the verification ledger.
3. Add the code to `CERTIFICATION_SCOPE`.
4. Apply for that jurisdiction in the next certification cycle.

No form definitions change, because they are already written.

### The open question

Whether CRA's test package tracks declared jurisdiction scope, or covers every
province regardless. If it covers everything, narrowing the application saves
nothing technically and the verification work becomes urgent for November. If
it tracks scope, narrowing is exactly right. That question is in the follow-up
email in [CRA-EMAILS.md](CRA-EMAILS.md), and it is worth an answer *before* the
November distribution rather than after.

## T1 data audit, 2026-09-15

Prompted by the GIFI audit, which found four of thirty codes wrong. The
question that raised was whether `verified: true` meant anything, since those
codes had been checked once too.

**The federal 2026 pack held up.** Every high-traffic parameter was re-checked
against CRA and all were correct: the five bracket rates and four thresholds,
the basic personal amount and both phase-out points, CPP (YMPE, exemption,
rate, maximum) and the CPP2 maximum, the EI maximum premium, the RRSP limit,
and ten indexed credit amounts — age, Canada employment, disability, medical
threshold, the four Canada workers benefit figures, and the caregiver amount
and threshold. Two of them corroborate independently: (85,000 − 74,600) × 4%
is exactly the $416.00 CPP2 maximum, and 68,900 × 1.63% is exactly the
$1,123.07 EI maximum.

That is a real difference from GIFI, and the reason is worth naming. The
federal figures were taken from CRA's indexation table, which publishes them as
a list. The GIFI codes were taken from an understanding of what the codes meant.

**Ontario 2026 had one wrong figure out of sixteen.** Those sixteen were
estimates: the verified 2025 amounts indexed forward, because Ontario had not
published 2026 amounts when the pack was written. Five can now be checked, and
four were exactly right — the basic personal amount, both surtax thresholds,
and the tax reduction basic amount. Ontario's 2026 indexing factor is 1.9%,
which is precisely what the estimates assumed.

The fifth was wrong. The tax reduction **per dependant** is $575, where
indexing 2025's $544 gives $554. Ontario raised it by 5.7% rather than indexing
it. A family with two children claiming the reduction was being credited $42
less than they were entitled to.

This is the argument for the `verified` flag in a single example. The method was
sound, the arithmetic was right, and the answer was still wrong, because a
legislature is under no obligation to index anything. The remaining eleven
Ontario estimates stay `verified: false` for exactly that reason, even though
every one of them that could be checked proved correct.

**The 2025 Ontario figures could not be checked directly** — those payroll
tables are archived and the tax package does not reproduce the charts. They are
corroborated rather than verified: reverse-indexing the confirmed 2026 figures
by 1.9% lands on 12,747.8, 5,709.5, 7,307.2 and 294.4 against stored values of
12,747, 5,710, 7,307 and 294. Notably $575 reverse-indexes to $564 and not to
$544, which is consistent with a discretionary increase rather than an error in
the 2025 figure.

Residual: 463 unverified, down from 468. All but eleven are the structure-first
provinces, which are outside the Ontario-only certification scope.

## Reconciliation: the application against the build, 2026-10-17

Thirty days before CRA distributes certification test returns. This section is
the audit of what was declared on the 2 September 2026 T2 developer application
against what the repository does today. Everything below was checked against the
code, not against the prose above.

### What is true in code right now

```
SUPPORTED_YEARS            [2025, 2026]
CERTIFICATION_TARGET_YEAR  2027
CERTIFIED_YEARS            []
CERTIFICATION_SCOPE        ["on"]
CERTIFIED_PROVINCES        []
T2_PROVINCES               ["on"]
```

Measured behaviour of the engine, not inferred:

| Return | Unverified parameters | `is_filable()` |
|---|---|---|
| T2 ON 2025 | 0 | true |
| T2 ON 2026 | 0 | true |
| T1 ON 2025 | 0 | true |
| T1 ON 2026 | 11 | false |
| T1 AB 2025 / 2026 | 21 each | false |

So the provenance gate is silent on **every corporate return the product can
compute**, and on the Ontario 2025 personal return as well. Certification is the
only gate still closed on those, which is the shift this document predicted.

### Channels

| Declared | Built | What it still cannot do |
|---|---|---|
| Freshet T2 for Windows | **Yes.** `Corporate` tab, `compute_t2`, `t2_filing_gate`, print via `shared/return-document`, `save_t2` into the vault. Installer builds in CI. | Installer is **unsigned**; SmartScreen warns on every install. No transmission. |
| Freshet T2 for MAC | **Code yes, product no.** Same source; `.github/workflows/freshet.yml` builds a `macos-latest` matrix leg and uploads a bundle. | **Unsigned and un-notarized**, so Gatekeeper refuses it outright rather than warning. There is no macOS build a customer can install. No Apple Developer ID purchased. |
| Freshet T2 Online | **Partly.** `crates/freshet-wasm` computes in the page, `web/` is a complete T2 interview with print and encrypted local backup, `/api/web/file` is registered and recomputes server-side. | **Nothing serves it.** `site::router()` has no static-file layer, so neither `web/dist` nor `/engine/freshet_wasm.js` is reachable from any deployment; `web/public/engine/` and `web/dist/` are gitignored build output. `docs/DEPLOY.md` has no web channel. The channel exists only under `npm run dev`. It also has **no free nil path**, and no account or session. |

### Commitments

| Declared | State |
|---|---|
| Free for nil or inactive accounts | **Desktop only.** `evaluate_gate` sets `nil_return` when the return is a T2 and `summary.total_tax` is zero, opens the licence lock, and four tests in `commands.rs` pin it (dormant, loss year, tax-owing, and a T1 excluded). Reachable through the `t2_filing_gate` command. **Absent from the web channel**: `site/src/routes/web.rs::file` demands a key unconditionally, with no nil exemption. Latent today only because the certification refusal fires first. |
| A full commercial product, not a limited subset | **No.** The federal T2 is 22 computed lines plus a 9-line Schedule 1. See the form gap below. |
| Small, medium **and large** businesses | **No.** GIFI is GIFI-Short's 69 items, which is CRA's subset for corporations under $1M revenue and assets. There is no Schedule 5 provincial allocation, so anything operating outside Ontario cannot be represented. |
| Price $0 to $799 | **Not sellable.** `Offer::corporate_single` and `Offer::corporate_professional` exist and are tested, but the Stripe webhook issues `Offer::season(state.sale_year)` unconditionally, product `freshet-t1`. A T2 buyer would receive a T1 licence and `check()` would answer `WrongProduct`. `sale_year` also defaults to 2027, a year the engine has no pack for. |
| Website https://bumi.ca | **Wrong product.** bumi.ca serves a client-rendered SPA for a web-accessibility scanning tool; its bundle contains WCAG and batch-scan copy and no mention of Freshet or tax. `freshettax.ca`, the domain in every piece of CRA correspondence and in the product's own privacy text, is a **parked Namecheap page** with no TLS on the apex. The site in `site/src/routes/pages.rs` is deployed nowhere. |

### Form gap on the T2 itself

The whole federal return is `t2.sch1.*` (nine lines), `t2.300`, `t2.311`,
`t2.360`, `t2.active_business_income`, `t2.business_limit`, `t2.430`, `t2.550`,
`t2.608`, `t2.638`, `t2.700` and three `summary.*` lines. Ontario adds five.
Absent, and each of these is ordinary CCPC arithmetic that a test return is
likely to touch:

- **Capital gains**: no line anywhere on the T2 (Schedule 6).
- **Part IV tax** on taxable dividends received, and the dividend refund
  (Schedule 3). Common for any corporation holding shares.
- **Aggregate investment income**, the additional refundable tax, and
  RDTOH/ERDTOH (Schedule 7).
- ~~**Business-limit reductions**~~ — **done 2026-10-17.** Both ITA 125(5.1)(a)
  and (b) are implemented, parallel with the greater taken, each figure cited.
  The same pass found ITA 125(5) itself wrong: the build prorated the limit for
  every short period, where the Act gates it on the year being *less than 51
  weeks*. Ontario is deliberately left unreduced and says so on the return —
  see the escalation below.
- **Associated-corporation allocation** of the business limit (Schedules 23/49).
- **Loss continuity** (Schedule 4). Taxable income floors at nil but nothing
  carries forward or back.
- **Schedule 5** provincial allocation, **Schedule 50** shareholders,
  **Schedule 53** GRIP, **Schedule 141** notes checklist.
- The **full Schedules 100/125** GIFI code set, as opposed to GIFI-Short's
  subset.
- The **T2 bar code return**, and the Corporation Internet Filing adapter. The
  latter is correctly absent, being NDA'd material behind the boundary this
  document describes, but it is still absent.
- Ontario credits are one entered figure, `prov.refundable_credits`.

### Refusal messages: what a user actually sees

Checked against the code paths rather than against the comments.

**T2 Ontario 2025, web.** Warnings are empty, so the provenance branch does not
fire; `is_certified(2025, "on")` is false and `in_certification_scope("on")` is
true, so the message is "Freshet is not yet certified by the CRA to transmit a
2025 ON return." The gate is the binding one. **The wording is not.** 2025 can
never be certified: the first year that can enter `CERTIFIED_YEARS` is
`CERTIFICATION_TARGET_YEAR`, 2027. "Not yet" is the wrong half of the
distinction this product was careful to draw for provinces, and it is drawn
nowhere for years. Both years in `SUPPORTED_YEARS` are in the "not ever, in this
release" bucket, so **every return a user can prepare today gets the wrong one
of the two messages.** `refuse()` needs a `year < CERTIFICATION_TARGET_YEAR`
branch to match the `in_certification_scope` branch beside it.

**T2 Ontario 2026, web.** Identical, and identically mis-worded.

**T1 in a structure-first province (Alberta), desktop.** `blocked_by` carries
both locks and the UI lists all of them, so the user sees the 21 unverified
parameters first and the out-of-scope line second. The out-of-scope line is the
binding one; the unverified line reads as the fixable one and is printed above
it. Not wrong, but the order inverts which objection is permanent.

**The more serious finding is about Ontario.** For a 2025 Ontario T1 the
warnings are empty, so the only substantive lock is certification, and
`Summary.tsx` renders it as "CRA certified for 2025" with the help text "CRA
issues the confirmation letter after the certification tests pass." There is no
T1 application in flight. The live application is T2 only, the T1 target is
2027, and the 2026 T1 window closed. That string tells an Ontario user a
confirmation letter is pending for a year nothing was ever applied for.

### Three places where `is_certified` has the wrong shape

1. **No return type.** `is_certified(year, province)` takes two of the three
   dimensions CRA certifies on. CRA certifies a product on a channel, for a tax
   year, for a **return type**, which is this document's own opening sentence. A
   T2 Ontario 2027 letter, recorded as `CERTIFIED_YEARS = [2027]` and
   `CERTIFIED_PROVINCES = ["on"]`, would open T1 Ontario 2027 filing in the same
   commit. This is precisely the failure the year-and-province split was made to
   prevent, one axis along.
2. **No channel.** Windows, macOS and web are separately certified, which the
   `T2Express (Windows)` and `T2Express (Macintosh)` rows are the evidence for,
   and nothing in the code knows which channel it is running in.
3. **`CERTIFICATION_SCOPE` does not know what it scopes.** It is consulted by
   both the T1 and the T2 gate and reads as a T1 jurisdiction scope above, while
   the live application is a T2. The declared T2 tax year is recorded nowhere;
   `CERTIFICATION_TARGET_YEAR`'s own doc comment explains itself in terms of the
   2026 **T1** window.

### Claims we are not entitled to make

Nothing is certified. `CERTIFIED_YEARS` and `CERTIFIED_PROVINCES` are both
empty. Against that, in descending order of seriousness:

1. **`desktop/src/components/Summary.tsx:191`**: "This release **is certified**
   for Ontario only. Returns for other provinces can be prepared, checked and
   printed, but not filed." A flat assertion of a certification that does not
   exist, shown to every user outside Ontario. This is the one to fix first.
2. **`site/src/routes/pages.rs`**: "Certification for the **2026 tax year** is
   in progress." False twice over, since the 2026 window closed before this
   product applied and the target is 2027. The same page sells a **T1** product
   ("Freshet prepares your Canadian T1 return") when the only live application
   is the T2, and never mentions Ontario-only scope or the free nil tier.
3. **`desktop/src/components/Summary.tsx:190`**: "CRA issues the confirmation
   letter after the certification tests pass," attached to a 2025 or 2026 tax
   year that will never be tested.
4. **"Not yet certified ... a 2025 ON return"** in `web.rs::refuse` and
   `commands.rs::evaluate_gate`, per the section above. "Not yet" is a claim
   about the future that is false for every year the build supports.
5. **`site/src/routes/pages.rs` and `docs/WEBSITE.md`**: "Not in our cloud,
   because there isn't one", "none of that is ever sent to us, because the
   software has nowhere to send it", and "no return data, and there is no path
   by which any could arrive here." `/api/web/file` takes the taxpayer's
   complete fact set by POST. `docs/WEB.md` states the limit correctly ("At
   transmission, the return does leave"); the privacy copy and `WEBSITE.md` were
   written before the web channel and now contradict it. The `WEBSITE.md` route
   table omits `/api/web/file` entirely.
6. **`web/src/components/Transmit.tsx:122`**: "Disabled because this build has
   not been certified for the period entered." `blockedHere` is
   `!result.filable`, and `filable` no longer tracks certification, so for
   Ontario it is true, the button is enabled, and this text never renders. The
   pre-warning the component's own doc comment describes, "what stops a user
   filling in a whole return before discovering it cannot be sent", has
   silently lapsed. `compute_t2` returns `filable: a.is_filable()` while
   `compute_return` returns `a.is_filable() && certified`; the asymmetry is the
   cause.

Nothing published on the live web makes a certification claim, for the simple
reason that nothing about Freshet is published on the live web at all.

### Stale documentation found during this pass

- `site/src/routes/web.rs`, the `refuse()` doc comment: "today every T2
  parameter pack still carries unverified figures, so the unverified check below
  always fires first and the certification check underneath it is unreachable."
  Both halves are now false. `docs/WEB.md` records the shift correctly; the code
  comment does not.
- `web.rs`'s module-level refusal list has five entries and omits the province
  check that `file()` performs first. `docs/WEB.md` lists six. The six are
  right.
- `docs/CRA-EMAILS.md` and `docs/outbox/cra-jurisdiction-scope.txt` are both
  written for a **2026 T1** application. The application that actually went in
  was the T2, on 2 September 2026, and neither its text nor any reply or
  acknowledgement is recorded anywhere in this repository.

### The gap to mid-November, ordered by what blocks a submission

Today is 2026-10-17. Test returns are distributed in mid-November, roughly four
weeks away.

**Blocks a submission outright**

1. **Confirm we are in the November 2026 T2 distribution at all.** The single
   unresolved fact. Question 3 of email 2 in `docs/CRA-EMAILS.md` asks the T2
   schedule and has no recorded answer, and nothing in the repository records a
   CRA reply to the 2 September application. If the answer is that the T2 cycle
   for 2026 closed too, every engineering item below moves out a year and the
   real deadline is November 2027. **Nothing else should be sequenced before
   knowing this.** Escalated, not drafted.
2. **The confidentiality agreement, and access to the controlled site.** Test
   returns go only to developers who have signed. No record exists that this has
   happened. It cannot be compressed and it gates item 3.
3. **The Corporation Internet Filing adapter.** Does not exist, by design, since
   schemas and endpoints arrive under the agreement. Zero days of work are
   possible on it until item 2 completes, and it is the difference between
   computing a return and submitting one.
4. **The missing T2 arithmetic.** Capital gains, Part IV tax and the dividend
   refund, aggregate investment income and the refundable tax, both
   business-limit grinds, loss continuity, Schedule 5. CRA's criterion is
   "calculate the tax-related fields correctly" across the fields the test
   returns exercise, and a 22-line return will not reproduce a test return that
   holds portfolio dividends or an associated corporation. **This is the largest
   body of work and the one that must be feature-complete, not started, by
   mid-November.**
5. **Record the declared T2 tax year.** Not written down anywhere, and it
   determines which pack the certification gate is measured against.

**Does not block a submission, but blocks shipping or honesty**

6. **The false certification claim in `Summary.tsx:191`**, and the "2026 in
   progress" claim on the landing page. One-line fixes, and the only items here
   that are purely a liability rather than a cost. Do them this week.
7. **A `year < CERTIFICATION_TARGET_YEAR` branch in both refusal paths**, so the
   "not yet" versus "not ever" distinction holds on years as it already does on
   provinces. Half a day, including tests.
8. **`is_certified` needs the return-type dimension**, and preferably the
   channel. Cheap now while both certified lists are empty; a latent mis-filing
   the day a letter arrives.
9. **Decide the web channel.** Either serve it, which means a static-file layer
   on `site::router()`, the engine build in the deploy pipeline, and a hosting
   entry in `DEPLOY.md`, or tell CRA that Freshet T2 Online is deferred. It was
   declared as one of three products and today it is a dev server. This is a
   scope decision and belongs upstream. **Escalated, not decided.**
10. **The free nil path in the web channel.** The commitment was made for the
    product, not for one channel. Fix before certification, because the day the
    letter arrives the web channel starts breaking a declaration.
11. **Code signing.** A Windows OV or EV certificate, and an Apple Developer ID
    plus notarization. Until these are bought there is no macOS product at all,
    because Gatekeeper refuses rather than warns, and macOS is a separately
    certified channel that was declared. Costs money; **escalated, not
    decided.**
12. **Wire the T2 offers to checkout.** The webhook issues a `freshet-t1`
    licence for every payment. A T2 purchase today produces a licence the
    product rejects.
13. **A public web presence for the declared products.** bumi.ca, the website
    given to CRA, serves an unrelated accessibility tool. freshettax.ca is
    parked. `pages.rs` is deployed nowhere.
14. **Reconcile the privacy copy** on `pages.rs` and in `WEBSITE.md` with the
    existence of the web channel, and add `/api/web/file` to the route table.

**Genuinely at risk**

Item 4 is the one that cannot be bought, delegated or compressed. Four weeks for
capital gains, Part IV, investment income, both SBD grinds, loss continuity and
Schedule 5, each with cited parameters and a verified flag, under the discipline
that found four wrong GIFI codes in thirty, is not a four-week job at the
quality this repository has been held to. If item 1 answers "yes, November
2026", the honest position is that the engine will meet the test returns
incomplete.

Items 1 and 2 are not at risk for engineering reasons. They are at risk because
they are waiting on CRA and nothing in the repository shows either has moved
since 2 September. They are also the two that make items 3 and 4 either urgent
or irrelevant.

## The real calendar, established 2026-10-17

Everything above dated the programme from a single remembered fact — "CRA
distributes certification test returns in mid-November" — and applied it to both
return types. That fact is real, it is published, and **it is published about the
T1 EFILE programme only.** Nothing CRA publishes attaches it to the T2.

This section is the calendar as CRA actually states it, separated from what is
inferred. Dates marked **firm** are quoted from a CRA page or taken from a
CRA-controlled file. Dates marked **extrapolated** are pattern-fitted, and the
pattern is carried with them so the fit can be re-checked later.

### T1 / NETFILE: an annual cycle, keyed to a tax year

**Firm.** From [EFILE certified software for the 2026 EFILE program](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/efile-electronic-filers/efile-certified-software-efile-program.html),
which is the only CRA page that describes the developer side of certification at
all:

> The CRA performs a limited annual review of commercially developed tax
> preparation software packages.

> In mid-November of each year, the CRA provides the certification test returns
> to each software developer who has asked to be certified for EFILE. The
> developer uses these returns to test their software.

> The CRA allows software developers to view drafts of new or modified forms
> through a controlled-access Web site. Before having this opportunity,
> developers must sign a confidentiality agreement with the CRA. The agreement
> states that developers cannot show their customers these new forms until they
> are printed and released to the public, usually in December of each year.

> Once a software developer has completed their product, they can transmit their
> test returns to the CRA. The CRA evaluates the results and, if the software
> meets the certification test criteria, issues a confirmation letter to the
> developer. Only when a developer has received this confirmation letter can the
> product be marketed as software that is EFILE-certified.

Three things in that are worth naming. The review is **annual**. The test returns
go to developers "who has asked to be certified" — the asking precedes
mid-November, and CRA publishes no date for it. And the confirmation letter is
what licenses the marketing claim, which is the external authority for the rule
this repository already enforces through `CERTIFIED_YEARS`.

**Firm filing-window dates**, each quoted from CRA at the time:

| Tax year | NETFILE / EFILE opens | Closes |
|---|---|---|
| 2023 | Monday 19 February 2024 | — |
| 2024 | Monday 24 February 2025 | — |
| 2025 | Monday 23 February 2026, 06:00 ET (NETFILE) / 08:30 ET (EFILE) | Friday 29 January 2027 |

**Extrapolated, tax year 2027** — the T1 target year:

| | Date | Basis |
|---|---|---|
| Developer application | ~mid-July 2027 | The only evidence is a 2016 developer mailing-list thread describing a "July 15th application deadline" as "critical to the whole 2016 Certification Cycle". Secondary, informal, ten years old. **This is the weakest date on this page and the one most worth confirming.** |
| Indexed amounts for 2027 published | ~Nov–Dec 2026 | CRA indexation-table pattern |
| Confidentiality agreement and controlled-site access | before the November distribution | it gates the draft forms the test returns exercise |
| Certification test returns | mid-November 2027 | "mid-November of each year" |
| Forms released publicly | December 2027 | "usually in December of each year" |
| NETFILE opens for 2027 returns | Monday 21 February 2028 | The three firm dates are 19, 24 and 23 February, always a Monday. The Monday inside 19–24 February 2028 is the 21st. If CRA is instead following "fourth Monday", it is 28 February 2028. |
| NETFILE closes | late January 2029 | one week short of a full year, per the 2026→2027 window |

Nothing about tax year 2027 is published yet, and that is expected rather than
alarming: as of today CRA's own NETFILE page, modified 2026-04-07, still lists
2025 as the current certified year.

### T2 / Corporation Internet Filing: not an annual cycle at all

This is the finding that changes the shape of the question. **The T2 does not
follow the T1 calendar, and CRA publishes no developer-facing T2 calendar of any
kind.** What it publishes instead describes a service with no season and a
certified list with no year.

**Firm, from CRA:**

1. **There is no T2 filing season.** [Hours of service](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-businesses/corporation-internet-filing/hours-service.html):
   Corporation Internet Filing "is available 21 hours a day, Monday to Saturday,
   and 20 hours on Sunday" — year round. The EFILE news page says it directly
   when announcing the T1 close: Corporation Internet Filing remains available
   after 30 January. There is no T2 equivalent of "opens 23 February".
2. **The T2 certified list carries no tax year.** [Software](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-businesses/corporation-internet-filing/software.html)
   has the columns Product / Corporation Name & Telephone / Services Available
   and **no year anywhere on the page** — the only four-digit year in its text is
   the page-modified date, 2026-09-04. The T1 list, by contrast, is headed
   "Certified tax software for 2025" and carries an explicit "Certified tax
   years" column. The two lists are built on different ideas.
3. **The T2 return is revised mid-year, more than once a year.** CRA's own
   [T2 form page](https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t2.html)
   lists revisions by month-year rather than by year: the current one is
   `t2-fill-10-26e.pdf`, and 2024 appears twice, as `t2-fill-24e.pdf` and
   `t2-fill-11-24e.pdf`. Last-modified dates on CRA's own CDN:

   | Revision | Published |
   |---|---|
   | `t2-23e` | 2023-03-23 |
   | `t2-24e` | 2024-06-21 |
   | `t2-11-24e` | 2025-01-27 |
   | `t2-25e` | 2025-05-29 |
   | `t2-26e` | 2026-05-04 |
   | `t2-10-26e` | **2026-10-15** |

   Roughly two revisions a year: one in late spring, one in autumn or the
   following January. A new one landed two days before this section was written.
   These are CDN last-modified dates, so they record publication or re-posting,
   not necessarily first drafting.
4. **Tax-year coverage runs back to 2002.** [Restrictions](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-businesses/corporation-internet-filing/restrictions.html):
   you cannot file "a return for any year prior to the 2002 tax year". There is
   no per-tax-year software gate of the kind the T1 has.
5. **T2 transmission does sit inside the EFILER system**, and so is interrupted by
   the same annual conversion: services down from 22:00 ET on Friday 16 October
   2026, "Prior to the opening of the upcoming EFILE program", with T1 and T3
   transmission back Sunday 18 October at 06:00 ET and T2 transmission back
   19 October at 06:00 ET — the notice's own text is internally inconsistent
   about that last day. Then: "On October 19, 2026, you will receive a message
   inviting you to renew your participation for the 2027 EFILE program." The 2025
   equivalent ran 17–20 October 2025. So the **EFILE programme year turns over on
   the third weekend of October** — but that is the transmitter's programme year,
   not a software certification year.

**Strongly evidenced, from certified vendors rather than from CRA.** T2
certification is granted against a **range of corporate tax year ends**, and
extended in increments of about five months. TaxCycle publishes the boundary with
each certified release:

| TaxCycle certified release | Dated | Certified to tax year ends |
|---|---|---|
| 14.0 | ~Nov 2024 | 31 May 2025 |
| 14.2 | 2025-05-22 | 31 October 2025 |
| 15.0 | 2025-11-26 | 31 May 2026 |
| 15.2 | 2026-06-04 | 31 October 2026 |

> "This certified release of TaxCycle T2 and AT1 extends the supported corporate
> tax year ends up to October 31, 2026." — [TaxCycle 15.2.62988.0](https://www.taxcycle.com/news/taxcycle-152629880/)

Those four dates line up with the CRA form revisions above: a spring revision
certified in May–June covering year ends to 31 October, and an autumn revision
certified in November covering year ends to 31 May. **Two T2 certification rounds
per year, in roughly May–June and October–November.**

[FutureTax](https://www.futuretax.ca/t2/) states the same structure explicitly,
and publishes its version numbering as calendar-year `.1` for the spring round
and `.2` for the autumn round, each with its certified year-end window:

| FutureTax version | Certified tax-year-end window | Availability as published |
|---|---|---|
| 2025.1 | 2023-01-01 to **2025-10-31** | "week of 12 - 16 May" (2025) |
| 2025.2 | 2023-01-01 to **2026-05-31** | "week of October 21st" (2025) |
| 2026.1 | 2024-01-01 to **2026-10-31** | "available on May 12, 2026"; "FutureTax T2 2026.1 certified version was released on May 11, 2026" |
| 2026.2 | 2024-01-01 to **2027-05-31** | "expected to be available by the end of October" (2026) |

Two independent vendors therefore agree on the same boundaries — 31 October and
31 May — and on the same two release months. That is as close to a published T2
certification calendar as exists.

**Empirically, new T2 products join the list at various points in the year, not
in one annual intake.** From Internet Archive captures of CRA's T2 certified
list:

- `Tax Chopper T2`, and the separate `AuraTax Windows` / `AuraTax Mac OS` rows,
  first appear between 2025-06-19 and 2025-09-06.
- `CloudTax T2 Basic` first appears between 2025-09-06 and 2026-03-12.
- `DataClub Tax` is on the live page but absent from the 2026-07-06 capture, so
  it was added within the last three months; the page's own modified date is
  2026-09-04.

And the page's modified dates across captures — 2023-07-06, 2023-09-20,
2024-09-20, 2025-03-10, 2025-08-14, 2026-09-04 — are scattered through the
calendar rather than clustered in February.

### Does "T2 mid-2027" map onto anything CRA offers

**Yes.** It is the better-mapped of the two tracks, and a closer fit than the
November date it replaces.

Mid-2027 lands on the **spring T2 certification round**: a T2 return revision
published around **May 2027** (successor to `t2-26e` of 2026-05-04 and `t2-25e`
of 2025-05-29), certified in **May–June 2027**, covering **corporate tax year
ends up to 31 October 2027**.

The nearest thing to a date is **mid-May 2027**. FutureTax's 2026.1, the
equivalent round one year earlier, was certified on 11 May 2026 and shipped on
12 May; its 2025.1 shipped in the week of 12–16 May 2025. The round immediately
before the one in question — the autumn 2026 round, covering year ends to
31 May 2027 — is being released as this is written, "by the end of October"
2026. So the sequence is legible and the next two stops are known.

Stated carefully: **the slot is real, the month is well-evidenced, and the date
is not published by CRA.** It rests on two vendors' release records and six CRA
form revisions, which is a two-year-deep consistent rhythm rather than a
commitment. Freshet would be entering a round that exists, not inventing one.

Two consequences follow from the facts rather than from preference:

- **A T2 certification is not a tax year.** It is a product version certified for
  a window of corporate tax year ends. `CERTIFICATION_TARGET_YEAR` is a
  T1-shaped concept and does not describe what a T2 letter would grant. Nothing
  in `freshet-taxdata` records a tax-year-end window today.
- **T2 has no November data dependency.** The T1 is gated on indexed amounts CRA
  publishes in November–December. The T2 figures that matter — the $500,000
  business limit, the taxable-capital and adjusted-aggregate-investment-income
  grind thresholds, the Part IV and additional refundable tax rates — are
  statutory, not indexed annually. The forms and schedules for the missing
  arithmetic are published **today**, including the revision posted 2026-10-15.
  There is no CRA-side release that work is waiting for.

### The confidentiality agreement and controlled-site access

**Firm as to what it gates:** signing precedes viewing drafts of new or modified
forms on the controlled-access site, and the embargo runs until those forms are
public, "usually in December of each year".

**Firm as to where in the cycle it falls:** before the mid-November test-return
distribution, because the draft forms it releases are the forms the test returns
exercise.

**Not published: whether it is signed once or per year.** The only evidence either
way is that developers refer to it by year — the 2016 thread cites "the 2016
NETFILE Certification Agreement" — which implies a year-stamped instrument
re-executed each cycle. Treat as unconfirmed.

**Not published at all: the T2 equivalent.** Every sentence CRA publishes about
confidentiality agreements and controlled-access sites appears on the EFILE page
and concerns EFILE. Whether the T2 has its own agreement, shares the EFILE one,
or distributes its specifications by some other route is not discoverable from
public material.

### The 2 September 2026 application: lapse, carry forward, or re-submit

**Unknown, and not knowable from published sources.** CRA publishes nothing about
deferring, withdrawing or carrying forward a software developer application, for
either return type. Its EFILE, NETFILE, Corporation Internet Filing and T2 guide
pages contain no mention of application status, deferral or re-application.

What the structure of the programme suggests, and it is only a suggestion:

- There is no published T2 "cycle" for an application to be inside or outside, no
  programme year on the T2 certified list, and no annual T2 intake. On that
  reading there is nothing for the application to lapse *against*.
- The annual-renewal mechanism that does exist — the October invitation to renew
  for the next EFILE programme year — is addressed to **electronic filers**, that
  is, transmitters holding an EFILE number, not to software developers.
- Against that, the T1 side is explicitly annual and its agreement appears to be
  year-stamped, so an application left unanswered across a cycle boundary
  plausibly needs restating.

This is a question for CRA, and the answer materially affects the plan. Nothing
is drafted here.

### Dates that could make a plan unworkable

1. **The T1 developer application deadline.** If it is genuinely mid-July, the
   tax year 2027 T1 application falls due around **July 2027** — the same quarter
   as the extrapolated mid-2027 T2 certification round. The two tracks collide at
   a single point in the calendar, and that collision rests on the
   weakest-sourced date on this page. Worth pinning before anything is sequenced
   around it.
2. **The spring 2027 T2 form revision is not published yet.** On the pattern it
   appears around May 2027 — the same month as the certification round it feeds.
   Building against `t2-10-26e` is the only option available, and it carries the
   risk that the May revision moves something. The mitigation is that T2
   revisions are incremental rather than re-indexed annually.
3. **A T2 certification round is in progress right now and Freshet is not in
   it.** The autumn 2026 round — CRA revision `t2-10-26e` of 2026-10-15, covering
   corporate tax year ends to 31 May 2027 — is being released by certified
   vendors this month. Deferring to mid-2027 means skipping it, which is a
   deliberate choice rather than a missed deadline, but it also means the
   mid-2027 round will be the **second** one Freshet has stood outside. Nothing
   in the published material suggests a round can only be entered at a
   particular point; the empirical evidence is that new products join the list
   at scattered times of year.
4. **An unanswered application has now been open for six weeks.** Both the
   confidentiality agreement and controlled-site access — and therefore every day
   of work on the Corporation Internet Filing adapter — sit behind a reply that
   has not arrived. Moving the target to mid-2027 buys engineering time; it does
   not move this, and nothing in the repository shows it has moved since
   2 September 2026.
5. **Not a risk, and worth stating plainly:** nothing in the November 2026 window
   now binds. The T2 has no November deadline of its own, and the T1 2027 cycle's
   November is a year away.

### Sources added in this pass

- [EFILE certified software for the 2026 EFILE program](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/efile-electronic-filers/efile-certified-software-efile-program.html) — the certification-testing description: annual review, mid-November test returns, confidentiality agreement, December form release, confirmation letter
- [EFILE news and program updates](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/efile-electronic-filers/efile-news-program-updates.html) — T1/T3 open and close dates, annual conversion, T2 stays open after 30 January
- [Corporation Internet Filing — Hours of service](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-businesses/corporation-internet-filing/hours-service.html) — no T2 season
- [Corporation Internet Filing — Restrictions](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-businesses/corporation-internet-filing/restrictions.html) — 2002 onwards
- [Corporation Internet Filing — About the service](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-businesses/corporation-internet-filing/about-corporation-internet-filing-service.html) — mandatory electronic filing for tax years starting after 2023
- [T2 Corporation Income Tax Return, form page](https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t2.html) — the month-year revision series
- [TaxCycle 15.2.62988.0](https://www.taxcycle.com/news/taxcycle-152629880/), [15.0.58923.0](https://www.taxcycle.com/news/taxcycle-150589230/) and [14.2.56699.0](https://www.taxcycle.com/news/taxcycle-142566990/) — certified tax-year-end boundaries, with dates
- [CRA interruption of services for annual conversion, 16–19 October 2026](https://www.taxcycle.com/news/cra-interruption-of-services-for-annual-conversion/) — the 2027 EFILE programme turnover
- [FutureTax T2](https://www.futuretax.ca/t2/) — a second vendor's version numbering, certified year-end windows and spring/autumn release months, including "FutureTax T2 2026.1 certified version was released on May 11, 2026"
- [libreplanet-ca-on, August 2016](https://lists.gnu.org/archive/html/libreplanet-ca-on/2016-08/msg00000.html) — the only sighting anywhere of a developer application deadline, and of a year-stamped certification agreement. Secondary and old; cited because nothing better exists.
