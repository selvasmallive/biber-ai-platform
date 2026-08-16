# CRA correspondence, ready to send

Two emails, deliberately sequenced. The first exists to get the company
registered and into the November test-return distribution — that is the only
time-critical thing. The second is the T2 technical questionnaire, which gets
better answers once a named person at CRA has already onboarded you.

Send the second one immediately after if you prefer; nothing breaks. But do not
let it delay the first.

> **Before sending, fill the Business Number.** CRA identifies a business by its
> 9-digit BN (formatted `123456789 RC0001` for corporate income tax), not by the
> Corporations Canada corporation number. A federally incorporated company
> normally receives one at incorporation. "What is your BN?" is otherwise the
> most likely first reply, and it costs a round trip.

---

## Email 1 — registration (send now)

```text
Subject: Software developer registration — 16631886 Canada Inc., T1
         certification for tax year 2026

Hello,

I would like to register 16631886 Canada Inc. as a CRA software developer and
enter the tax year 2026 T1 certification cycle, in time to receive the
certification test returns when they are distributed in November. Our first
product is a T1 personal income tax application. We are also developing a T2
corporation product on the same calculation platform, and I have a few
scheduling questions about that below; the detailed T2 technical questions can
follow separately.

Company
  Legal name:         16631886 Canada Inc.
  Corporation number: 1663188-6
  Business Number:    <9-digit BN>
  Jurisdiction:       Federal — Canada Business Corporations Act
  Province:           Ontario
  Contact:            Selva Kumaran Vadivel Murugan
  Phone:              +1 647-376-5493
  Email:              selva@freshettax.ca

Product 1 — T1 personal income tax (the immediate request)
  Product name:  Freshet
  Purpose:       Canadian T1 personal income tax preparation and filing
  Delivery:      Computer download, with separate Windows and macOS builds
  Target users:  Individuals preparing and filing their own returns

  On that basis we expect NETFILE to be the applicable base certification —
  please confirm. Within it, the services we intend to support in the first
  release are Auto-fill my return and ReFILE. We are keeping the initial
  service set deliberately small.

Product 2 — T2 corporation income tax (planned)
  A T2 corporation preparation and electronic filing product built on the same
  calculation platform, also delivered as a computer download for Windows and
  macOS. Our intention is a full commercial product covering the core return,
  applicable schedules, GIFI financial statement information and Corporation
  Internet Filing, rather than a permanently limited subset. I would like to
  design it against CRA's requirements from the outset, so I will follow up
  with detailed technical questions separately.

What I am requesting now
  1. Registration of 16631886 Canada Inc. as a software developer for T1
     certification for tax year 2026.
  2. The confidentiality agreement required for access to draft and
     pre-release forms, specifications and other controlled material.
  3. Access to the controlled site or repository through which CRA distributes
     certification specifications, draft forms and related technical material.
  4. The T1 certification specifications, test returns and testing procedures
     for tax year 2026, when they become available.
  5. The technical and certification requirements for NETFILE, Auto-fill my
     return and ReFILE, including any prerequisites that must be completed
     before testing can begin.

Questions
  1. Is there a registration cut-off for a new software developer to
     participate in the tax year 2026 T1 certification cycle and receive the
     test returns when they are distributed? If so, what is that date?

  2. Is T2 certification a separate software developer registration, or can
     both products be registered under the same developer account?

  3. What is the certification schedule for tax year 2026 T2 software? Does it
     follow the same November-to-February period as T1?

  4. Can a new developer reasonably pursue both T1 and T2 certification in the
     same cycle, assuming sufficient development resources, or are there CRA
     dependencies that would require them to be completed sequentially?

  5. Our calculation engine is being designed to support prior tax years as
     well as the current one. Can a new developer obtain certification for a
     previous tax year after that year's certification cycle has closed, or is
     certification available only for the current cycle?

  6. Once the confidentiality requirements are complete, will we receive the
     schemas, transmission specifications, validation rules, error codes and
     test cases needed to implement NETFILE?

  7. What additional company, product, security or technical information do
     you require from us to open the developer registration?

Our immediate priority is entering the tax year 2026 T1 certification cycle and
receiving the certification materials and test returns when they are
distributed. Please let me know the next steps and any forms or agreements I
should complete.

Thank you,

Selva Kumaran Vadivel Murugan
16631886 Canada Inc.
+1 647-376-5493  |  selva@freshettax.ca
```

---

## Email 2 — T2 technical questionnaire (send after the first reply)

```text
Subject: T2 certification requirements — 16631886 Canada Inc. (follow-up)

Hello,

Further to my registration request for T1 certification for tax year 2026, this
is the detail on our planned T2 corporation product. We would like to design it
against CRA's requirements from the start rather than retrofit, so the
questions below are about scope and sequencing rather than any immediate
request.

Product — T2 corporation income tax
  Delivery:  Computer download, separate Windows and macOS builds
  Intent:    A full commercial product — the core return, applicable schedules
             and forms, GIFI financial statement information, and Corporation
             Internet Filing — rather than a permanently limited subset.

  Beyond that we would expect a competitive product to support, where
  applicable: the T2 bar code return, T2 Auto-fill, Attach-a-doc, electronic
  authorization requests, electronic submission of supporting documents,
  amended corporation returns, and the T1135, T1134 and T106 information
  returns.

Questions

  1. Core scope. What functionality, forms and schedules constitute the
     minimum core T2 certification for a commercial preparation product?

  2. GIFI. What is required for GIFI financial statement information, and is
     it tested as part of core T2 certification or separately?

  3. Corporation Internet Filing. What additional technical requirements, test
     cases or approvals apply?

  4. Bar code return. Is certification for the T2 bar code return required for
     a product supporting Corporation Internet Filing, or can a product be
     certified for electronic filing without it?

  5. Additional services. What are the certification or testing requirements
     for T2 Auto-fill, Attach-a-doc, authorization requests and electronic
     document submission? Which of these require separate approval rather than
     forming part of the core certification?

  6. Information returns. Are T1135, T1134 and T106 included within T2
     certification, or does each require its own specifications, testing and
     approval?

  7. Amended returns. What functionality and certification requirements apply
     if our software allows a corporation to prepare and electronically submit
     an amended T2 return?

  8. Sequencing. Which of the above can be added to an already-certified
     product in a later cycle, and which must be in place at first
     certification?

  9. Specifications. Once the confidentiality requirements are complete, will
     the T2 schemas, transmission specifications, validation rules, error codes
     and test cases be provided through the same channel as the T1 material?

Thank you,

Selva Kumaran Vadivel Murugan
16631886 Canada Inc.
+1 647-376-5493  |  selva@freshettax.ca
```

---

## What changed from the single long draft

- **The request leads.** The original opened with two product descriptions and
  reached "what I am requesting" after roughly six hundred words.
- **Business Number added.** CRA works from the BN; the Corporations Canada
  number alone will not open a registration.
- **Phone and email filled.** Both were blank. The phone is not cosmetic — CRA
  publishes a company telephone number against each certified product.
- **NETFILE repositioned.** It is the base certification, not a service
  alongside Auto-fill and ReFILE.
- **Split in two.** Fourteen questions in a first-contact email invites a short
  generic reply. Question 8 of the second email — what can be added later
  versus what must be present at first certification — is new, and is the one
  most likely to change the build order.
- **Dropped the competitive framing.** CRA is a regulator. The specificity of
  the questions demonstrates seriousness better than a claim about competing
  with established software.

---

## Follow-up: narrowing the first release to Ontario

Send this if the original email has already gone. It corrects a scope point
that email did not state either way, so it reads as a clarification rather than
a change of plan.

> Subject: Freshet — jurisdiction scope for our 2026 T1 certification
>
> Further to my earlier email about certifying Freshet for the 2026 T1, I want
> to state our jurisdiction scope explicitly, since I did not cover it.
>
> **For the first release we are seeking certification for Ontario returns
> only.**
>
> The software computes the federal return and all thirteen provincial and
> territorial forms, and we intend to certify the rest over subsequent seasons.
> We are limiting the first application because our tax parameters for the
> other jurisdictions have not yet been checked against their published forms,
> and we would rather narrow the scope than submit calculations we cannot
> stand behind. Returns for other jurisdictions can be prepared and printed in
> the product but the software refuses to transmit them, and says so on screen.
>
> Two questions:
>
> 1. Is jurisdiction scope declared as part of the certification application,
>    or is it simply a matter of which test returns we are required to
>    reproduce?
> 2. Do the 2026 T1 certification test returns cover every province and
>    territory, or only those a developer has declared support for? This
>    determines whether an Ontario-only application still has to reproduce
>    results for other jurisdictions.
>
> If narrowing the scope changes anything about the timeline or the test
> package, I would be grateful to know before the November distribution.

### Why the second question matters

If CRA's test package covers every jurisdiction regardless of declared scope,
then narrowing the application saves nothing technically — the software would
still have to reproduce results everywhere, and the placeholder data would fail.
If the package tracks declared scope, narrowing is exactly the right move.

The answer decides whether the remaining verification work is urgent for
November or can wait for a later season, so it is worth asking before the test
returns arrive rather than after.
