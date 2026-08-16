# Registration: what to do now, and when

Today is **August 2026**. That timing matters, so the short answer first.

> **Register with CRA as a software developer now.** Certification test returns are distributed in **mid-November**. You have roughly three months. The 2026 filing season (tax year 2025) has already closed for new entrants — your realistic target is **tax year 2026, certifying November 2026 to February 2027, filing from late February 2027.** Miss this November and you wait a full year.
>
> **Do not start Québec yet.** It is a second product with its own spec, its own test cycle and its own two-stage approval. Start it after one full federal season.

---

## CRA

### What certification actually requires

CRA's stated criteria for the software itself. Everything else is process around these:

- format electronic records according to CRA's specifications
- calculate the tax-related fields correctly
- pass the error-detection validities built into the system
- process all field codes, including the supporting fields needed for electronic filing

Note what is *not* reviewed: CRA does not check spelling, grammar, or usability. Quality of experience is entirely your problem — which is the space to compete in.

### The sequence

1. **Have the legal entity and business number in place.** Do this first; everything else attaches to it.
2. **Ask CRA to register you as a software developer** for the T1 certification programme, naming the tax year and return types you intend to support. CRA's own wording is that test returns go to "each software developer who has asked to be certified" — asking is the trigger.
   *I could not find a public self-serve registration form.* The entry point is contacting CRA's software-developer/EFILE support directly. Confirm the current channel with them rather than trusting a third-party page.
3. **Sign the confidentiality agreement.** This gates a controlled-access site holding drafts of new and modified forms. You may not show customers draft forms before public release, usually in December.
4. **Build against the draft forms** through the autumn.
5. **Receive the certification test returns in mid-November.** Your engine must be feature-complete before this, not after — the window from mid-November to late February is for fixing what the tests find, not for building.
6. **Transmit your test returns.** CRA evaluates the results.
7. **Receive the confirmation letter.** Only then may you market the product as certified. Do not put "CRA certified" on a website before this letter exists.
8. **NETFILE opens.** For tax year 2025 it opened 23 February 2026 and runs to 29 January 2027; expect a similar shape for 2026.

### Two decisions to make before you contact them

**NETFILE or EFILE, or both.** NETFILE is the individual filing their own return — the consumer product, and what Freshet is built for. EFILE is a professional preparer filing for clients: separate certification, separate applicant screening, and applicants must describe the security methods protecting client information. Start with NETFILE only.

**Which services to seek approval for.** Auto-fill and ReFILE are separately approved but universal in practice — every EFILE-certified product carries both. Blackspark's *Armada* is certified with only those two, which is proof that a minimal service set is viable. Ask for **Auto-fill + ReFILE** and leave T1135, PAD, Business Consent and the rest for later years.

### One thing to design for now

From **February 2026**, each EFILE account is bound to specific certified software products, and returns transmitted with unregistered software are refused. Plan on being registered per product, not per vendor — it affects how you version and name builds.

### If you will ever print returns

Software producing paper records is reviewed by examining the printed forms. Printed returns must be compatible with CRA's processing systems, and many packages print a **2D barcode** on page one that CRA uses to assess the return. If you add the PDF/print feature (and you should — every competitor has it), it is in scope for review.

---

## Revenu Québec

### Why this is a separate product, not a feature

A Québec resident files **two** returns: the federal T1 *and* the provincial TP1. That alone makes Québec a different product, but the process compounds it:

- a different specification — *Requirements for Computer-Generated Forms: Individuals* (**IN-413-V**)
- a different transmission service — **NetFile Québec**, not NETFILE
- a different published list — Revenu Québec's own authorized-software list
- **two** sequential approvals rather than one

So the work is not "add a province". It is a second certification track, against a second regulator, on a second timetable. Treating it as a separate product with its own roadmap and its own launch is the honest framing.

### The two stages

Revenu Québec issues **two** numbers, and the second is gated on the first.

**Stage 1 — Authorization** (permission to reproduce their forms):

1. Register as a partner of Revenu Québec
2. Access **My Account for partners**; add resource people and register the products you intend to develop
3. Develop the product to the **IN-413-V** specification
4. Submit test-case results
5. Adjust the product following their analysis
6. **Provide Revenu Québec with the hardware and documentation** needed to run customized follow-up test cases
7. Carry out supplemental test cases if required

On success they add the product to the authorized-software list and confirm by email.

**Stage 2 — Certification** (permission to transmit online). Only available *once you hold an authorization number*. Same cycle: submit test cases, adjust, supply hardware and documentation, run supplemental cases.

### The one that will surprise you

Step 6 is not a formality. **Revenu Québec expects you to hand over hardware** — a machine with the product installed — so they can run their own follow-up test cases against it. Budget for the device, the imaging, the shipping and the support cycle. Nothing in the CRA process is comparable.

### When

Not now. Sequence it as:

| | Target |
|---|---|
| CRA T1, Windows + macOS | TY2026 — register **now**, certify Nov 2026 – Feb 2027 |
| Ship, run one full season | Feb – Apr 2027 |
| Revenu Québec authorization | begins mid-2027 |
| Revenu Québec certification | after authorization; realistic first TP1 season TY2028 |

The reason to wait is not caution for its own sake. The TP1 shares the taxpayer's income data with the T1 but almost none of its rules, and Québec has provincial credits with no federal analogue. Building that on top of a federal engine that has not yet survived a real filing season means debugging two unproven things at once.

---

## Before you email: set up the identity

Do these first. The registration email is CRA's first impression of a company that wants to handle taxpayer data, and all three of these are things you need anyway.

**Register the domain and email from it.** Not a personal Gmail or Hotmail address. Three practical reasons beyond the obvious one:

- CRA's certified-software lists publish the **company name and telephone number** alongside each product. You are being onboarded as a business, and the T2 list literally has a "Corporation Name & Telephone" column.
- The **code-signing certificate** you will need later — an EV certificate on Windows, an Apple Developer ID on macOS — is issued against a verified legal entity. Domain, company name and product name should agree from the start rather than being reconciled later.
- A personal mailbox is a continuity risk on a multi-year, annually renewed relationship. Use a **role address** such as `certification@` so the thread survives a change of person or provider.

Take `.ca` as well as `.com` if you can — `.ca` requires Canadian presence, which is a small signal in the right direction here. Configure real mailboxes rather than forwarding, and set SPF, DKIM and DMARC so CRA's replies do not land in spam.

**Have the legal entity and business number ready.** Expect to be asked for the company's legal name, business number, address and a telephone number.

**Do the trademark check before you commit the domain** — see the naming note in the README. Registering a domain for a name you then have to abandon is a cheap mistake to avoid.

> **The final, ready-to-send versions are in [CRA-EMAILS.md](CRA-EMAILS.md).**
> The drafts below are kept for the reasoning behind them.

## The registration email

Keep it short, precise, and demonstrate you know the calendar — that last part is what separates a serious applicant from a speculative one.

```text
Subject: Software developer registration — T1 certification, tax year 2026

Hello,

I would like to register as a software developer for CRA T1 certification
for tax year 2026 (the 2027 filing season), and to receive the certification
test returns when they are distributed in November.

About the product
  Company:   <legal name>, <business number>
  Location:  <city, province>
  Product:   Freshet — Canadian T1 preparation software
  Platform:  Desktop, Windows and macOS (separate builds)
  Audience:  Individuals preparing their own returns, so NETFILE rather
             than EFILE. Please confirm this is the correct base
             certification for the two services below.
  Services:  Auto-fill my return, and ReFILE. We are deliberately keeping
             the initial service set minimal and would add others in later
             years.

What I am asking for
  1. Registration in the T1 software developer certification programme for
     tax year 2026.
  2. The confidentiality agreement required for access to draft and
     pre-release forms and specifications, and access to the controlled
     site where those are published.
  3. The T1 certification specifications, test returns and testing
     procedures for tax year 2026.
  4. The requirements to be approved for Auto-fill my return and for
     ReFILE, including anything that must be in place before testing.

Two questions
  - Is there a cut-off for being included in the tax year 2026
    certification cycle, and what is that date?
  - What company, product or technical information do you need from me to
    open the registration?

Please let me know the next step and I will provide whatever is required.

Thank you,
Selva Vadivel
<title>, <company>
<phone>  |  certification@<domain>
```

### The T1-and-T2 version

Use this if you want T2 on CRA's radar now. Note it deliberately keeps T1 as the committed ask and treats T2 as an information request — that costs nothing, gets you their process and timing, and leaves the sequencing decision open. If you intend to certify **both** for the same cycle, change "we expect to follow with" to "we would also like to certify for tax year 2026" and add T2 to the numbered list.

```text
Subject: Software developer registration — T1 certification for tax year 2026,
         and T2 enquiry

Hello,

I would like to register as a software developer for CRA T1 certification for
tax year 2026 (the 2027 filing season), and to receive the certification test
returns when they are distributed in November. We expect to follow with a T2
product, and I have some questions about that below.

About the company
  Company:   <legal name>, <business number>
  Location:  <city, province>
  Contact:   <phone>  |  certification@<domain>

Product 1 — T1 (the immediate request)
  Product:   Freshet — Canadian T1 preparation software
  Delivery:  Computer download, Windows and macOS (separate builds)
  Audience:  Individuals preparing their own returns, so NETFILE rather than
             EFILE. Please confirm this is the correct base certification for
             the two services below.
  Services:  Auto-fill my return, and ReFILE. We are deliberately keeping the
             initial service set minimal.

Product 2 — T2 (planned, not yet requested)
  Product:   A T2 corporation return product on the same calculation engine.
  Delivery:  Computer download, Windows and macOS.
  Services:  We would expect to start with Corporation Internet Filing and the
             T2 barcode only, adding others in later years.

What I am asking for now
  1. Registration in the T1 software developer certification programme for
     tax year 2026.
  2. The confidentiality agreement required for access to draft and
     pre-release forms and specifications, and access to the controlled site
     where those are published.
  3. The T1 certification specifications, test returns and testing procedures
     for tax year 2026.
  4. The requirements to be approved for Auto-fill my return and for ReFILE,
     including anything that must be in place before testing.

Questions
  - Is there a cut-off for being included in the tax year 2026 T1
    certification cycle, and what is that date?
  - Is T2 certification a separate registration and a separate test cycle from
    T1, and does it run on the same November-to-February calendar? Can a
    developer reasonably pursue both in one cycle, or do you recommend
    sequencing them?
  - What does T2 certification require in respect of GIFI financial statement
    information, and is that tested separately?
  - Our engine can also compute prior tax years. Can certification for a
    previous year be requested by a new developer after that year's test cycle
    has closed, or is certification only available for the current cycle?
  - What company, product or technical information do you need from me to open
    the registration?

Please let me know the next step and I will provide whatever is required.

Thank you,
Selva Vadivel
<title>, <company>
<phone>  |  certification@<domain>
```

Why it is shaped this way: **the questions are the valuable part.** You do not currently know whether the T2 cycle runs on the same calendar, whether both are feasible together, or whether a prior year can still be certified. Each answer changes the roadmap, and asking costs one email. Committing to T2 before you know the answers does not.

### Two refinements worth making

**Use CRA's own vocabulary for the platform.** Their certified-software lists categorise products as `Online`, `Computer download` and `Mobile app`. Saying "computer download for Windows and macOS" maps onto the column they will file you under; "desktop" makes them translate.

**Ask about prior years explicitly.** Certifying only for 2026 is the right first ask, but the product will want to file prior years eventually, and it is unclear whether a new developer can obtain certification for a year whose test cycle has closed. Add:

> Separately: our engine can also compute prior tax years. Can certification for a
> previous year be requested by a new developer after that year's test cycle has
> closed, or is certification only available for the current cycle?

The answer shapes the roadmap. If prior years are only available in their own cycle, then every year you skip is permanently lost to the product.

### Three deliberate changes from a first draft worth keeping:

- **Name the tax year and the filing season.** "The upcoming tax year" is ambiguous in August; "tax year 2026, the 2027 filing season" cannot be misread, and referencing the November distribution shows you know when the real deadline is.
- **State NETFILE up front, then ask for confirmation.** Asking only at the end invites a generic answer. Stating your intent lets them correct you if it is wrong.
- **Describe the draft-forms site by function, not by acronym.** Internal system names change and getting one wrong reads worse than not using it.

## Answering the two questions directly

**What registration do I need to do with CRA now?**
Ask CRA to add you to the software developer certification programme for T1, sign the confidentiality agreement, and state that you want Auto-fill and ReFILE. Do it in the next few weeks — test returns land in mid-November and the engine has to be finished by then, not started.

**How and when do I submit for Québec?**
Register as a Revenu Québec *partner*, then run their two-stage process: authorization for form reproduction first, certification for online transmission second, each with its own test-case cycle and each requiring you to supply hardware. Do not begin until the federal product has completed one filing season — realistically mid-2027, for a first TP1 season in 2028.

---

## Sources

- [EFILE certified software for the 2026 EFILE program — certification testing](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/efile-electronic-filers/efile-certified-software-efile-program.html)
- [Find certified tax software — NETFILE](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/netfile-overview/certified-software-netfile-program.html)
- [Apply for EFILE](https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/efile-electronic-filers/apply-efile.html)
- [Auto-fill my return](https://www.canada.ca/en/revenue-agency/services/e-services/about-auto-fill-return.html)
- [Revenu Québec — Authorization and Certification, Personal Income Tax](https://www.revenuquebec.ca/en/partners/product-developers/fields-of-activity/income-tax-product-developers/personal-income-tax/authorization-and-certification-personal-income-tax/)
- [Revenu Québec — Registering as a Partner](https://www.revenuquebec.ca/en/partners/registering-as-a-partner/)
- [Revenu Québec — Authorized software](https://www.revenuquebec.ca/en/partners/authorized-products/authorized-software/)
