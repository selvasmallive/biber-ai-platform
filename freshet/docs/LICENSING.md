# Licensing

Freshet prepares a complete return for nothing. Filing needs a licence.

## Can the website be built later?

**Yes, and the app is already finished without it.**

Activation sits behind an `Activation` trait — the same seam used for the CRA
transport and the AI providers. `WebActivation` is a stub that fails with a
clear message; when the site exists it becomes one HTTP call and nothing else
in the app changes.

Every path that matters already works with no server at all:

- **Development and CRA-certification licences** are built in and need nothing.
- **A pasted licence** works for anyone who has theirs — from the original
  email, or a backup. This is the normal path, not a fallback.
- **A licence file** can be opened directly from the emailed attachment.
- **Verification** is entirely offline, always, for every licence.

The website is only needed for the optional key exchange, which is opt-in. A
customer who never ticks that box never depends on it existing.

So the ordering is: ship the app, run certification, and build the website when
there is something to sell. Nothing is blocked on it.

## The shape: offline, unless the customer asks otherwise

**Freshet never contacts anything for licensing on its own.** What a customer is
emailed is the signed licence itself, and pasting it is the whole process — the
app checks the signature against a public key compiled into the binary and is
done. No request is made, attempted, or queued.

The one path that can involve a server is a customer who has the short key but
not the licence — a forwarded email, a lost attachment. For them there is a
checkbox, unticked, that offers to exchange the key. It is passed per attempt
rather than stored, so permission given once cannot quietly persist, and the
order of resolution puts it last: a pasted licence and a built-in licence are
both resolved before that branch is reachable at all.

This is enforced by types and pinned by tests, not asserted in prose. A
`Credential::Licence` carries its own proof, so the offline path has no branch
that *could* reach the network. `WebActivation` is a stub that always fails, so
any accidental route to it shows up as a test failure naming the activation
service.

Two things make an unasked-for licence check actively dangerous here:

1. **The product's whole claim is that a return never leaves the machine.** An
   app that phones home to check a licence contradicts that in exactly the way
   this audience notices and tests for.
2. **Filing season is eight weeks.** Everyone files at once, at the end. A
   runtime check puts our uptime between a person and their filing deadline —
   and an outage on 29 April would be unforgivable and unfixable.

Optional activation still buys what online licensing is actually for: for the
customers who use it, you learn how many devices a licence is on and can refuse
a chargeback. It just is not a condition of filing, and it is never the default.

### Delivery follows from this

Because the offline path is the main path, **email the licence, not just the
key**. Put the signed licence in the message body and attach it as a
`.freshet-licence` file — `install_licence_file` opens that directly. The short
key is still worth printing on the receipt: it is what a customer can read over
the phone to support, and what the optional online exchange takes.

## Forgery, and what actually prevents it

The key format carries a checksum, so **typos are caught offline**, before
anything is contacted — "that key has a typo" instead of a support ticket about
the server rejecting a purchase. The alphabet has no `I`, `L`, `O` or `U`, and
the characters people confuse are folded to what they meant.

None of that prevents forgery. A checksum is public arithmetic; anyone can mint
a well-formed key. **The signature is the only thing that matters.** A licence
is an Ed25519-signed payload, and the private half exists solely on the
activation server. Nothing in this repository can mint a retail licence.

## The development licence problem, and how it is solved

Hardcoded bypass keys are a classic way to ship a permanent backdoor. Two
independent locks prevent it here:

1. Development licences are signed by a **different keypair** from production.
2. The development public key is compiled in **only** under the
   `dev-licences` Cargo feature, which is off by default.

So a release build does not merely ignore the development keys — it has never
heard of them. Extracting the development signing key from a debug build yields
licences that no shipped binary will accept.

The app also surfaces `dev_licences_compiled_in` to the UI. If a build ever
ships with them on, it says so on screen.

```bash
npm run dev:app      # development build, built-in licences available
npm run tauri build  # release: no development licences, at all
```

### The built-in licences

| Key | Kind | Purpose |
|---|---|---|
| `FRSH-DEV0-0000-0000-…` | Development | Everyday development and manual testing |
| `FRSH-CERT-0000-0000-…` | Certification | CRA certification test transmissions |

The certification licence is a distinct `LicenceKind`, so a return filed during
CRA testing is distinguishable from a customer's afterwards. During a
three-month certification cycle, making test transmissions wait on a purchase
flow would be absurd — and a licence that expires mid-cycle would be worse.

## What the website has to do

### Activation (optional path only)

```http
POST /api/activate
{ "key": "FRSH-XXXX-XXXX-XXXX-XXXX", "product": "freshet-t1" }

200 { "licence": "<base64 payload>.<base64 signature>" }
404 { "error": "no such key" }
409 { "error": "already activated on the maximum number of devices" }
410 { "error": "this licence was refunded" }
```

Note what the request does **not** carry: no return data, no taxpayer details,
no telemetry. A key and a product name. That is the entire payload, and it
should stay that way — it is a claim the product can make and defend.

### Purchase and delivery

1. Customer buys. Use a payment processor; do not touch card details.
2. Generate a key, sign a licence, store both.
3. Email **the signed licence** to the address on the order, in the body and as
   a `.freshet-licence` attachment, with the key printed alongside it.

### Recovery

Licences get lost — that is normal and it must be self-serve or it becomes your
inbox. "Email me my licence again" takes an email address and **sends to that
address only**. Never display a key on a page in response to an unauthenticated
form: that turns the recovery endpoint into a key-harvesting oracle for anyone
who can guess customer emails.

Rate-limit it, and reply identically whether or not the address is on file.

### Admin

Support needs to look up a customer's key, see activations, and revoke. That is
a normal admin screen with authentication and an audit log of who looked at
what.

**Storing licence keys retrievably is fine** — they are not passwords, and
support genuinely needs them. Two things that are not fine:

- **Never store customer passwords retrievably.** Hash them, or use an identity
  provider and store none.
- **You are holding customer records**, so PIPEDA applies: collect only what the
  sale requires, say what you keep, and be able to delete it on request. The
  desktop product deliberately holds no personal data; do not let the website
  quietly become the place that does.

### Revocation

Because verification is offline, a revoked licence keeps working on a machine
that has already activated. That is the deliberate cost of not phoning home.

If revocation ever needs to be enforceable, the honest mechanism is a licence
that **expires** and is silently renewed at activation — not a runtime check.
Given tax software is sold per year anyway, a licence that expires after its
filing season is a natural fit and needs no new machinery.

## Expiry, and not making people hate it

Expiry is the one licensing mechanism that can hurt someone who paid, so every
rule around it exists to stop that happening at the worst moment. The failure
people actually experience with licensed software is: it works on Tuesday, on
Wednesday a modal says EXPIRED, and their deadline is Thursday. None of that is
necessary.

**Preparing is never gated.** Expiry touches filing and nothing else. A return
opens, edits, recalculates, prints and exports forever, licence or no licence.
Holding someone's own tax data hostage over a renewal would be indefensible,
and `an_ended_licence_never_blocks_preparing_a_return` fails the build if it
ever starts happening.

**The date is shown from day one.** Settings says "Covers filing until 30 April
2027" the moment a licence is installed. A date someone has seen all along
cannot ambush them eleven months later.

**Warnings start when they become useful, not before.** Nothing is said until
60 days out. A countdown running from the day of purchase is nagging, and
nagging is precisely how warnings get tuned out — so the quiet period is a
feature, not an oversight.

**A 30-day grace period, honoured quietly.** Filing keeps working for a month
past the end date. Late returns, amendments prompted by a slip that arrived in
June, deadlines that slip — all normal. A licence that lapsed four days ago is
not the moment to stop someone filing. The anti-sharing property survives
intact: the licence still dies, just not on somebody's deadline.

**A wrong clock is treated as a wrong clock.** A machine set earlier than the
licence's issue date gets a note about the date and keeps filing. That is
almost always a flat CMOS battery or a fresh install, not fraud, and the
signature check does not depend on the clock at all. Small negative skew — time
zones, DST, NTP drift — says nothing.

**The refusal leads with what still works.** When a licence has genuinely
ended: *"Everything else still works: your returns open, recalculate, print and
export as normal, and renewing restores filing."* Not "EXPIRED — buy now".
There is a test asserting no refusal opens with a sales pitch.

Together these are why the offline design costs so little. Expiry travels
inside the signed payload, so it is enforced with no network, no activation
check, and no dependency on us being reachable in April.

## What a licence covers, and how much

Two axes, both inside the signed payload.

**Coverage** is either calendar tax years (T1) or a fiscal period range (T2). A
corporation with a 30 June year-end files something no calendar year can name,
and CRA certifies T2 software by period-end range for the same reason. Modelling
both as a list of years would mean a T2 licence lying about what it covers.

**Allowance** is a fixed number of returns or unlimited. T1 is a household: five
returns, one purchase, covering a spouse, adult children and a parent — that is
what justifies charging when a free web filer exists. T2 buyers split in two: an
owner with one corporation, and an accountant with forty. A single number can
express the first but has to fake the second, and "4,294,967,295 returns left"
is not something to show a professional.

| Tier | Coverage | Allowance |
|---|---|---|
| `Offer::season` | one tax year | 5 returns |
| `Offer::corporate_single` | period-end range | 1 return |
| `Offer::corporate_professional` | period-end range | unlimited |

## Counting returns, and where the count binds

The desktop app keeps a tally per licence key. **It is advisory.** It lives on
the customer's machine, so a reinstall resets it, and nothing local can prevent
that. Its job is to show an honest "2 of 5 used" and to fail before a
transmission that would be refused anyway.

For a counted licence the binding count is claimed at `POST /api/filings/claim`,
**at the moment of transmission**. This is not a contradiction of the offline
design. The argument against phoning home was that our uptime must never sit
between a person and their deadline — and at transmission the network is already
a hard requirement, because the return is going to CRA. If it is down, the filing
cannot happen whatever we do. Counting there adds no dependency that was not
already present.

`Allowance::needs_authoritative_count` is what decides. An unlimited licence
never calls the endpoint: there is nothing to count, so there is nothing to ask,
and no row is written for a firm filing hundreds of returns.

The claim is idempotent on a caller-supplied filing reference. A transmission
that fails *after* we counted it retries with the same reference and does not
consume a second slot — losing a return off your allowance to a dropped
connection would be the most infuriating possible failure.

## Payload versioning

Every change to the signed payload invalidates every licence already issued,
because the signature is over the exact bytes. `PAYLOAD_VERSION` is what makes
the next such change survivable: a licence stamped with a version this build
does not know is refused with *"Update Freshet and it will work — there is
nothing wrong with the licence"*, not with "invalid licence". The difference
decides whether the customer clicks update or emails support.

## Pricing note

Sell per **licence covering several returns**, not per return. The reason a
desktop product can charge anything when Wealthsimple Tax is free is that one
licence covers a household — a person preparing returns for a spouse, parents
and adult children is a different buyer from the one comparing free options.
`max_returns` is on the licence for exactly this.
