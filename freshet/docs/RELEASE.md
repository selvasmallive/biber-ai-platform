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

### macOS builds need a Mac

This build produced Windows artifacts only. The `dmg` and `app` bundle targets
were skipped because macOS bundles cannot be cross-compiled from Windows.

That matters for certification scheduling, not just packaging: CRA lists Windows
and macOS as **separate certifications**, so the macOS build has to exist and
pass its own tests. Either a Mac or a macOS CI runner is required, and it is
worth arranging before November rather than during.

### Version number

`0.1.0`. Worth setting deliberately before the first public build, since the
installer embeds it and upgrade behaviour keys off it.
