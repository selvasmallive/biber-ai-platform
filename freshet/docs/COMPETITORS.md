# Where Freshet stands

## The market, factually

Seventeen products were certified for T1 2025. Counting the delivery channels CRA lists against each:

| Channel | Products |
|---|---|
| Online | 12 |
| Computer download | 8 |
| Mobile app | 5 |

Desktop is a real but minority channel, and only three products (GenuTax, FutureTax, myTaxExpress) are download-only. Everyone with a desktop build also runs online — which is worth knowing: **nobody is currently competing on local-first as a position.** The privacy argument is unoccupied.

On the EFILE side, the "Services Available" column shows what each product was separately approved for:

`Auto-fill · ReFILE · T1135 · T1134 · PAD · Submit documents · Business Consent · T217 · T2057 · T2058 · T2059`

All 23 EFILE-certified products carry **Auto-fill and ReFILE**. So while these are formally separate approvals, in practice they are table stakes — a product without Auto-fill is visibly behind. Note also Blackspark's *Armada*, certified with only Auto-fill and ReFILE: proof that a minimal service set is a viable entry.

## The majors

| | Channels | Price | Notable |
|---|---|---|---|
| **Wealthsimple Tax** | Online | Free, optional paid | No upcharge for self-employment, capital gains, rental, FHSA or crypto. Refund optimizer. The price floor. |
| **TurboTax** | Online, download, mobile | Paid tiers | Searches 400+ credits; sells access to human experts. Keeps only the previous year. |
| **UFile** | Online, download | Paid, undercuts TurboTax | Keeps 9 years of returns — matches CRA's 6-year retention advice. |
| **H&R Block** | Online | Paid tiers | Strong self-employed offering; retail fallback. |
| **CloudTax** | Online, mobile | Free + paid | Also ships a T2 Basic product. |
| **StudioTax** | Download, mobile | Paid desktop, free mobile | The established desktop-first option. |

Two things follow. **Free is the floor** — Wealthsimple gives away the complex cases, so Freshet cannot charge for self-employment or capital gains as a tier. And **retention is a feature** — UFile advertises 9 years; TurboTax's single year is a known complaint. Freshet's encrypted local vault keeps everything forever by default, which is a stronger answer than either.

## Where Freshet is genuinely ahead

These are real, built, and hard for the incumbents to copy quickly.

**Local-first with an encrypted vault.** Twelve of seventeen competitors are online-only; your return sits on their servers. Freshet's never leaves the machine, sealed with XChaCha20-Poly1305 under an OS-keychain key. No competitor is positioned here.

**A grounded AI advisor on your own key.** TurboTax sells *human* experts — higher cost, limited hours. Nobody ships a model advisor that sees your actual computed lines, works with your Anthropic/OpenAI/local key, and strips identity before egress. The privacy architecture is what makes it defensible: the advisor sees line numbers and amounts, never a name or SIN, and the redactor fails closed.

**Measured, not estimated.** The marginal rate, the RRSP curve and the capital cost allowance planner are computed by re-running the whole return at each level, so surtaxes, phase-outs and income-tested credits are all included. Competitors quote bracket rates, which are confidently wrong exactly at the decision points.

The CCA planner is the clearest case. Depreciation is optional, and claiming more cuts taxable income but *also* cuts net income — which raises income-tested credits like the Workers Benefit and CARE. Once tax already reaches zero, further depreciation buys no tax saving that year, yet may still raise benefits. The planner reports that crossing point rather than pretending it settles the question, because the real trade-off is against future years and only the filer knows their plans.

**Provenance-gated tax data.** Every rate carries a citation and a `verified` flag, and the engine refuses to file while any is unverified. This is invisible to users and is the strongest quality argument you have with CRA.

## Gaps, ranked

### Cannot launch without these

1. **The remaining twelve provinces and territories.** Ontario is roughly 39% of the country. This is the largest single piece of remaining work and it is mostly data, not code.
2. **The CRA transmission stack** — NETFILE, plus certification. Nothing files today.
3. **The 2025 data verification pass.** Currently every value is `verified: false` and the engine correctly refuses to file.
4. **A printable/PDF copy of the return.** Every competitor has it; people expect a document.

### Cannot compete without these

5. ~~**Coupled (spousal) returns with transfer optimization.**~~ **Built** — spousal amount, medical and donation pooling, pension income splitting swept in both directions, and Schedule 2 transfers of unused age, pension, disability and tuition amounts.
6. ~~**Dependants and child care expenses.**~~ **Built** — child care (T778) with per-child limits and the two-thirds earned-income cap, the amount for an eligible dependant, and the caregiver amount for infirm minors. Refundable credits now exist as a concept: CPP and EI overpayment recovery, and Ontario's refundable **CARE** credit (Schedule ON479-A) with its step-rate schedule. The **Canada Workers Benefit** (Schedule 6, line 45300) is built, including the disability supplement and the switch to family bands, as are the caregiver amounts for infirm dependants 18 and over (federal line 30450, Ontario line 58185). Still not modelled: the CWB disability supplement where *both* spouses are eligible (reduced at 7.5% each rather than 15% once), multiple infirm adult dependants, and self-employment income in the working-income and earned-income bases.
7. ~~**Tuition (T2202)**~~ **Built** for the current year, including the transfer. Carryforward *between years* is not — it is reported as a diagnostic so it is not lost, but must be re-entered.
8. ~~**Medical, donations, pension income and pension splitting.**~~ **Built.**
9. ~~**Self-employment (T2125).**~~ **Built** — net business income, and CPP on it at both the employee and employer halves with one half deducted and the other credited. It also feeds the two bases that were previously understating for the self-employed: the child care earned-income cap and the Workers Benefit working income. Capital cost allowance (classes 8, 10, 12 and 50, with the half-year rule) and the business-use-of-home calculation are also built, including the rule that home office cannot create or deepen a loss. Recapture, terminal losses, class 10.1 passenger vehicles (with the cost cap and the rule that neither recapture nor a terminal loss ever arises), and claiming less than the maximum CCA are all built — the last with a planner that sweeps every claim level through the full return. Not modelled: the separate professional, farming and fishing lines, and the Accelerated Investment Incentive, whose first-year factor is a parameter awaiting confirmation.
10. **Capital gains (Schedule 3)**, including the recent inclusion-rate changes.
11. **Multi-year support with carryforward** between years — and note that filing a prior year requires certification *for that year*.

### Expected, not blocking

12. **Express NOA** — the assessment arrives seconds after filing. Requires My Account and online mail.
13. **ReFILE** — amending 2022–2025. Universal among certified products.
14. **T1135** foreign property, once anyone with foreign holdings uses this.
15. **Prior-year import** from a competitor's file format — removes the switching cost.
16. **Direct deposit and pre-authorized debit (PAD).**

### A separate product, not a gap

**Québec (TP1).** Roughly 22% of the population, and it is a second product rather than a thirteenth province: Québec residents file both a federal T1 *and* a provincial TP1, against a different specification (IN-413-V), a different transmission service (NetFile Québec), and a two-stage Revenu Québec approval — authorization to reproduce forms, then certification to transmit. Revenu Québec also expects you to ship them hardware for follow-up test cases. Sequencing and process in [REGISTRATION.md](REGISTRATION.md); the target is a first TP1 season in 2028, after the federal product has survived one real filing season.

## What was added this session, and why

**Review diagnostics.** Every major competitor has an "audit check" or "review" step; Freshet had none. The rules are written in the same expression language as the form lines, so a tax professional can audit them without reading Rust, and they carry plain-language help rather than error codes.

The design rule that matters: **a rule that cannot distinguish a mistake from a legitimate case is a warning, never an error.** Two employers legitimately push combined CPP over the annual maximum and the excess is recovered on the return — blocking that correct return would be worse than nagging about a suspicious one. Errors are reserved for the internally impossible (contributions exceeding the income they came from) and they block filing.

**Auto-fill my return.** Mapping, multi-slip aggregation, reconciliation with conflict detection, and contribution-room handling are complete and tested end to end against a fixture source. Only CRA's transport is missing, and it cannot be built from public information.

Three decisions inside it are worth defending:

- **Nothing is written without a decision.** CRA is explicit that Auto-fill does not move responsibility off the filer, so the importer produces proposals. Conflicts start unticked — overwriting something a person typed is their call, not ours.
- **Unmapped boxes are surfaced, never dropped.** The fixture deliberately includes a T4A box this build cannot place. Silently discarding income CRA already knows about is the worst thing an importer can do: CRA reassesses and the user has no idea why.
- **Room figures always carry their as-of date.** CRA's numbers miss unreported contributions, and TFSA over-contribution costs 1% per month. The advisory is attached to the figure in the model, so it cannot be shown without it.

**RRSP planner.** The "refund optimizer" competitors advertise, done properly: it re-runs the return at twenty contribution levels, finds the last dollar still earning the top rate, and binary-searches the contribution that clears a balance owing. It pairs with Auto-fill — once the real transport lands, CRA's reported deduction limit becomes the planner's ceiling instead of an estimate from this year's income.

## Sources

- [Find certified tax software — NETFILE](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/netfile-overview/certified-software-netfile-program.html)
- [EFILE certified software for the 2026 EFILE program](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/efile-electronic-filers/efile-certified-software-efile-program.html)
- [Auto-fill my return](https://www.canada.ca/en/revenue-agency/services/e-services/about-auto-fill-return.html)
- [Express NOA](https://www.canada.ca/en/revenue-agency/services/e-services/about-express-noa)
- [Best tax software in Canada 2026 (moneyGenius)](https://moneygenius.ca/personal-finance/tax-software)
- [Best free tax software Canada 2026 (LoonieLabs)](https://www.loonielabs.ca/blog/best-free-tax-software-canada-2026)
