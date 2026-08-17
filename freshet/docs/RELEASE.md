# Producing a release build

```bash
cd freshet/desktop
npm run build:release      # tauri build, then the safety check
```

The first Windows build produced:

| Artifact | Size |
|---|---|
| `freshet-desktop.exe` | 9.7 MB |
| `Freshet_0.1.0_x64_en-US.msi` | 3.7 MB |
| `Freshet_0.1.0_x64-setup.exe` | 2.7 MB |

## The check, and why it has a positive control

`scripts/check-release.py` asserts two things about the artifacts:

1. **The production signing key is compiled in.** A build carrying the zeroed
   placeholder rejects every licence ever issued, and it looks completely
   normal until a customer pays and cannot file.
2. **The development licences are not.** They are signed by a different keypair
   whose public half compiles in only under the `dev-licences` feature.

Claim 2 is the interesting one, and absence proves nothing unless the probe can
find the thing when it *is* there. So the check first runs the same probe
against the debug build and **refuses to pass on a clean release result if no
debug build exists to prove the probe works**. A test that cannot fail is not
evidence.

Measured on the first build:

```
positive control: development seed found in freshet-desktop.exe, as expected

freshet-desktop.exe  (9.7 MB)
  development licences: absent
  signing key: production key present
```

So the two-lock design holds in a real artifact, not just in unit tests.

## What is still missing before this can ship

### Code signing — the blocker

**The installers are unsigned.** On Windows, SmartScreen will warn every user
that the publisher is unknown and bury the install behind "More info → Run
anyway". For tax software asking people to trust it with their SIN, that is
close to fatal at the point of first impression.

Fixing it needs purchases, which are yours to make:

- **Windows:** an OV or EV code-signing certificate from a CA. EV clears
  SmartScreen reputation immediately; OV builds reputation over time and
  downloads. Roughly CAD $300–700 a year, and EV usually ships on a hardware
  token.
- **macOS:** an Apple Developer Program membership (USD $99/year) for a
  Developer ID certificate, plus notarization. Gatekeeper refuses unsigned apps
  outright rather than merely warning.

Tauri signs during `tauri build` when the certificate details are configured, so
this is configuration rather than new code once the certificates exist.

### macOS builds — handled by CI

macOS bundles cannot be cross-compiled from Windows, and CRA lists Windows and
macOS as **separate certifications**, so the macOS build has to exist and pass
its own tests rather than being assumed to work.

`.github/workflows/freshet.yml` builds both. Two jobs:

- **tests** — engine, tax data, licensing and the licence service, on Linux,
  for every push and pull request.
- **desktop** — a matrix of `macos-latest` and `windows-latest` that type-checks
  the frontend, runs the desktop tests both with and without the `dev-licences`
  feature, builds the installers, runs `check-release.py`, and uploads the
  artifacts.

The desktop job is **skipped on pull requests** on purpose. GitHub bills macOS
minutes at ten times the Linux rate on a private repository and this job builds
a full installer twice. Running it on `main` and on demand catches a macOS break
within one merge, which is soon enough, without paying for it on every push to a
branch. If that trade stops being right, delete the `if:` guard.

The job builds a debug binary before the release one, which looks redundant and
is not: `check-release.py` refuses to certify an artifact clean unless it can
first find the development seed in a debug build, so without one the check would
fail rather than pass vacuously.

**No Mac is needed to develop.** The macOS build is only exercised in CI, which
is the point — but it also means a macOS-only failure surfaces on `main` rather
than locally, so it is worth watching the first few runs.

#### What CI does not do

It produces **unsigned** artifacts. Signing needs certificates in repository
secrets, and Tauri reads them from the environment:

| Platform | Secrets |
|---|---|
| macOS | `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID` |
| Windows | the certificate thumbprint, plus the signing tool on the runner |

Adding those is a change to repository settings and involves paid certificates,
so it is deliberately not wired up. Until it is, the artifacts CI uploads are
for testing, not for customers.

### Version number

`0.1.0`. Worth setting deliberately before the first public build, since the
installer embeds it and upgrade behaviour keys off it.
