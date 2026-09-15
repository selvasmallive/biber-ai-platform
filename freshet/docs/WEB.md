# The web channel

Freshet T2 Online — the third channel declared on the CRA questionnaire,
alongside the Windows and macOS desktop builds.

## Why this needed a decision rather than a framework

The desktop product's central claim is that a tax return never leaves the
machine it was prepared on. That is not marketing: it is why the vault has no
escrow, why the AI advisor sees line numbers and amounts but never a name or a
SIN, and why the webview has no HTTP permission at all.

A hosted product cannot make that claim the same way. The usual web tax product
posts every keystroke to a server that does the arithmetic, and by the time a
corporation has finished entering its financial statements the vendor holds a
complete copy of them.

Freshet does not do that, because it does not have to. The engine is Rust with
no operating-system dependencies in its calculation path, so it compiles to
WebAssembly. **The calculation runs in the browser.** A corporation entering its
statements is computing on its own device, exactly as on the desktop.

The compiled engine is about 950 KB, 166 KB over the wire. That is the cost of
the whole arrangement, paid once per visit.

## What it does not buy

Stating this plainly is the point of the document.

- **Licensing cannot be verified offline here.** The desktop build checks an
  Ed25519 signature against a key compiled into the binary. A browser tab cannot
  be trusted to do that — anyone can edit the JavaScript. Entitlement for the
  web product is decided server-side, at transmission.
- **The user still trusts the served code.** A desktop binary is signed and
  changes only when someone installs an update. A page is whatever the server
  sent this morning. That is inherent to the channel and cannot be engineered
  away; it can only be stated.
- **At transmission, the return does leave.** It has to: it is going to the CRA
  through us. The claim is about preparation, not about filing, and it should
  never be written as though it covered both.

## The parts

| Piece | Where | What it is |
| --- | --- | --- |
| `freshet-wasm` | `crates/freshet-wasm` | The engine's browser binding. Computes; does nothing else. |
| `scripts/build-web.sh` | `scripts/` | Builds the module and the JavaScript that loads it. |
| The page | `web/` | React, Vite, no runtime dependencies beyond React. |
| The questions | `shared/t2-interview.ts` | The T2 interview, shared with the desktop app. |
| `/api/web/file` | `site/src/routes/web.rs` | The transmission gate. |

`freshet-wasm` deliberately excludes `freshet-store` and `freshet-license`. The
store depends on the OS keychain and has no business in a browser; the licence
crate verifies offline, which is exactly what a browser cannot do meaningfully.
Leaving them out is the design, not an omission.

## The transmission gate

The browser computed the return, so the figures arriving at the server were
produced by code the user controls. Anyone who wanted to file a return showing
no tax payable could do it from the developer console.

So the server does not believe them. `/api/web/file` receives the **facts**,
runs the same engine over them, and compares its own result against what the
browser reported.

Recomputing and quietly filing the server's answer would be simpler and wrong:
if the two disagree, one of them has a bug, and the user is about to file a
return that does not match what they reviewed on screen. Overwriting hides that.
Refusing surfaces it, and shows which lines differ.

The refusals, in order — most fundamental first, so a user hears the real
reason:

1. The province is not one we file.
2. The period is not one a corporation can have.
3. The two calculations disagree.
4. A parameter behind the calculation is unverified.
5. This build is not certified for that year and province.
6. The licence has no filing left.

Only the last costs the customer anything, and it is last on purpose: taking a
filing off someone's allowance and *then* telling them the return could not be
sent would be the worst version of this. Counting reuses the desktop's
`claim_filing` path, with a reference derived from the return so a retry after a
dropped connection does not consume a second slot.

Which of these actually fires has moved once already, and the movement is the
point. When this endpoint was written, 4 always fired first — every corporate
parameter was a placeholder — and 5 was unreachable. The corporate rates are
now cited, so 4 is silent and **5 is what refuses**: Freshet is not certified,
and that is the honest reason a customer hears.

That is why the gate is split into `refuse()` and unit-tested directly rather
than only through the endpoint. The branch that could not be reached is now the
branch that runs, and it had to be right on the day it started running.

## Storage

`web/src/crypto.ts` encrypts a return with AES-GCM under a key derived from a
passphrase by PBKDF2-SHA-256 at 600,000 iterations. The passphrase never leaves
the browser.

Today it backs the **Save a copy** panel: a single encrypted `.freshet` file the
user downloads and keeps. A web product holding the only copy of a return has
quietly made itself impossible to leave, and a corporation cannot accept that
for a filing it must keep for six years.

As on the desktop, **there is no recovery**. A forgotten passphrase is a lost
return. Escrowing a key would quietly undo the whole arrangement, because then
we could read everything after all.

`crypto.test.ts` checks the round trip and, more usefully, the things a round
trip cannot see: that the envelope does not carry the plaintext beside the
ciphertext, that altered ciphertext fails rather than decrypting to a changed
amount, and that the salt and nonce are fresh on every save.

## The interview

`shared/t2-interview.ts` declares the questions, and is shared with the
desktop app rather than copied into it. The labels and hints are presentation
and could reasonably differ between channels; the fact keys cannot. They are
the join between a text box and a line on the return, and a wrong key is the
worst kind of defect this product can have. Nothing errors: the engine finds no
fact under `gifi.800`, reads zero, and computes a return that is internally
consistent, professionally formatted, and wrong.

`crates/freshet-taxdata/tests/t2_interview.rs` therefore reads the TypeScript
from Rust and checks the join in both directions. A second copy for the desktop
would sit outside that check and be free to drift, which is how the nine got
missed in the first place. It found nine missing fields
the first time it ran, including three CCA disposition amounts and every
terminal-loss flag. It also caught a field labelled as an amount that the form
reads as a flag, which would have turned "claim 50,000 of CCA" into "claim
something" and then claimed nothing.

## Running it

```bash
cd freshet && bash scripts/build-web.sh
cd web && npm install && npm run dev
```

The dev server proxies `/api` to the licence service on port 8080. Everything
else — the whole calculation — happens in the page and never reaches it.

## Not built yet

- No account or session. Entitlement is proven by presenting a licence key at
  transmission, the same key the desktop uses. A signed-in experience with saved
  returns needs an auth story that does not exist yet.
- No transmission to the CRA. Nothing is certified, so `/api/web/file` currently
  ends at "ready to transmit" rather than transmitting.
- Server-side storage of sealed returns. The encryption is used for the local
  backup file, so it is exercised rather than sitting as an unused seam, but
  nothing is stored for a user between visits. That needs the account story
  above.
