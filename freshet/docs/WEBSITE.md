# The website

`freshet/site` — a Rust service that sells licences, delivers them, resends
them when lost, and lets support look them up.

It is deliberately **not** a dependency of the desktop app. A customer holding
their licence can file whether or not any of this is running. See
[LICENSING.md](LICENSING.md) for why that is the shape.

## Why Rust, in this repo

The service imports `freshet-license` — the same crate the desktop app verifies
with — and signs through the same `sign()` function. A licence that the app
rejects is therefore a bug in one place, not a disagreement between two
implementations of the same format. A separate Node or Python issuer would have
to re-derive the payload's exact byte layout, and the first field reordering
would break every licence silently.

## Routes

| Route | Purpose |
|---|---|
| `GET /` | Landing page. States plainly that the product cannot yet file. |
| `GET /recover` | "Send me my licence again" form |
| `GET /privacy` | What is held, and how to have it deleted |
| `GET /healthz` | Liveness |
| `POST /api/activate` | **Optional** key → licence exchange |
| `POST /api/recover` | Resend to the registered address |
| `POST /api/webhook/stripe` | Payment → issue → email |
| `GET /admin/licences?q=` | Support lookup, behind IAP |
| `POST /admin/licences/{key}/revoke` | Revoke |
| `POST /admin/customers/{email}/forget` | PIPEDA deletion |

## The four things worth reviewing

### Recovery cannot be turned into a harvester

Three properties, each because the obvious implementation is a vulnerability:

- The licence goes to the **registered address**, never into the response. A
  page that displayed it would be a key-harvesting oracle for anyone who could
  guess customer emails.
- The response is **identical** whether or not the address is on file. A
  different status or wording confirms who is a customer.
- Rate limiting lives **in the database**, not in process memory — Cloud Run
  runs many instances, and a per-instance counter would give an attacker one
  attempt per instance.

Pinned by `recovery_never_puts_a_licence_in_the_response_body` and
`recovery_answers_identically_for_a_stranger_and_a_customer`.

### The webhook cannot be forged, replayed, or double-counted

Signature (constant-time HMAC-SHA256), freshness (5 minutes), idempotency (the
insert *is* the claim, so two concurrent deliveries cannot both win). Rotation
works because multiple `v1=` entries are each tried.

`verify_signature` is pure and separately tested — it is the function between an
anonymous POST and a free licence, so it should be provable without a payment
processor.

### Admin has no password, because it has no passwords

Authentication is Identity-Aware Proxy at the load balancer. The app reads the
email IAP sets and checks it against an allowlist.

**This is only sound because ingress is restricted to the load balancer.** A
header is trivially spoofable by anything that can reach the service directly.
`--ingress internal-and-cloud-load-balancing` in the deploy is what makes the
header meaningful; without it the admin area is public. The allowlist is
defence in depth, not the gate.

Admin is **off** unless `ADMIN_EMAILS` is set, and unauthorised callers get 404
rather than 403 — a 403 confirms there is something there.

### Revocation is honest about what it cannot do

Because verification is offline, revoking stops future activations and recovery
emails. It does not reach a machine that already holds the licence. The admin
page says so on the confirmation screen rather than implying a kill switch.

The mechanism that *does* work offline is **expiry**, which travels inside the
signed payload. `Offer::season` issues licences that expire, which is the real
answer to licence sharing and costs nothing at runtime.

## What is stored

Email address, licence, product, timestamps, order reference, and which
installations activated. That is the whole schema.

No name, no address, no card details, no analytics, and above all no return
data — the desktop product holds none of it and there is no path by which any
could arrive here. PIPEDA applies to what is kept, so the schema is the first
place to say no.

## Running it locally

```bash
cd freshet/site
cargo test          # 47 tests, no database needed
```

The whole suite runs against an in-memory store, so every rule — replay
protection, rate limiting, revocation, device counting, non-disclosure — is
exercised without Postgres anywhere near it.

To run the service itself you need `DATABASE_URL` and a `FRESHET_SIGNING_KEY`
matching the compiled-in public key. Without SMTP credentials it logs licences
instead of sending them, and says so at startup rather than pretending.

## Still to build

- **Stripe checkout page.** The webhook that turns a payment into a licence is
  done and tested; creating the checkout session needs your Stripe account.
- **Download hosting** for the signed installers, once there are signed
  installers to host.
- **Renewal.** Season licences expire, so next year's buyers need a path that
  recognises a returning customer.
