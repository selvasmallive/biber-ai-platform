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
