#!/usr/bin/env python3
"""Check a release build before it ships.

Run after `npm run tauri build`:

    python scripts/check-release.py

Two things are asserted, and the second is the one that matters:

1. The **production signing key** is compiled in. A build carrying the zeroed
   placeholder rejects every licence ever issued, and it would look completely
   normal until a customer paid and could not file.

2. The **development licences are not**. They are signed by a different keypair
   whose public half is compiled in only under the `dev-licences` feature, so a
   release build should not contain a trace of them.

Claim two is only worth making if the probe can actually detect the thing it
says is absent, so the check runs the same probe against the debug build as a
positive control and refuses to pass on absence alone when no debug build
exists to prove the probe works.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE.parent / "src-tauri" / "target"

# The development seed is ASCII, deliberately: it makes this check greppable
# rather than requiring the binary to be disassembled.
DEV_SEED_TEXT = b"Freshet development licence key"

# Must match PRODUCTION_PUBLIC_KEY in crates/freshet-license/src/sign.rs.
PRODUCTION_KEY = bytes([
    0xb9, 0xfc, 0xe8, 0x1f, 0x45, 0xcc, 0xe5, 0x84,
    0x9a, 0x7d, 0x14, 0x52, 0x12, 0x56, 0x49, 0x89,
    0x41, 0x20, 0x6a, 0x80, 0x7d, 0x80, 0xc4, 0x1e,
    0xfd, 0x42, 0x1b, 0xad, 0xaf, 0x1c, 0x5f, 0xc3,
])

PLACEHOLDER_KEY = bytes(32)


# The compiled application itself, as opposed to an installer wrapping it.
# On Windows that is freshet-desktop.exe; on macOS the same name without a
# suffix, both loose in target/release and again inside the .app bundle.
EXECUTABLE_NAMES = {"freshet-desktop", "freshet-desktop.exe"}


def is_executable(path: pathlib.Path) -> bool:
    return path.name in EXECUTABLE_NAMES


def artifacts():
    release = TARGET / "release"

    found = [release / "freshet-desktop.exe", release / "freshet-desktop"]
    found += sorted((release / "bundle").rglob("*.msi"))
    found += sorted((release / "bundle").rglob("*-setup.exe"))
    found += sorted((release / "bundle").rglob("*.dmg"))
    # The binary inside a macOS .app, which is what actually runs.
    found += sorted((release / "bundle").rglob("*.app/Contents/MacOS/freshet-desktop"))

    return [p for p in found if p.is_file()]


def main() -> int:
    problems = []

    # -- the positive control ------------------------------------------------
    #
    # Absence proves nothing unless the same probe finds the string when it is
    # genuinely there.
    debug = next(
        (p for p in [TARGET / "debug" / "freshet-desktop.exe",
                     TARGET / "debug" / "freshet-desktop"] if p.is_file()),
        None,
    )
    if debug is None:
        problems.append(
            "No debug build to use as a positive control. Run "
            "`npm run dev:app` once so the probe can be shown to work, "
            "otherwise a clean result here means nothing."
        )
    elif DEV_SEED_TEXT not in debug.read_bytes():
        problems.append(
            f"The probe did not find the development seed in {debug.name}, "
            "where it should be. The check itself is broken — do not read a "
            "clean release result as evidence of anything."
        )
    else:
        print(f"positive control: development seed found in {debug.name}, as expected")

    built = artifacts()
    if not built:
        print("No release artifacts found. Run `npm run tauri build` first.", file=sys.stderr)
        return 1

    for path in built:
        blob = path.read_bytes()
        size = len(blob) / 1048576
        print(f"\n{path.name}  ({size:.1f} MB)")

        if DEV_SEED_TEXT in blob:
            problems.append(
                f"{path.name} CONTAINS the development licence key. This build "
                "would accept the built-in development and certification "
                "licences. Do not ship it."
            )
            print("  development licences: PRESENT  <-- do not ship")
        else:
            print("  development licences: absent")

        # Only the executable is expected to carry the key uncompressed; the
        # installers compress their payload, so a miss there is not a finding.
        #
        # Matched by name rather than by suffix: a macOS binary has none, and
        # an earlier version of this check silently skipped the key test on
        # every macOS build because of it.
        if is_executable(path):
            if PLACEHOLDER_KEY in blob and PRODUCTION_KEY not in blob:
                problems.append(
                    f"{path.name} carries the zeroed placeholder signing key. "
                    "It will reject every licence ever issued."
                )
                print("  signing key: PLACEHOLDER  <-- do not ship")
            elif PRODUCTION_KEY in blob:
                print("  signing key: production key present")
            else:
                problems.append(
                    f"{path.name} does not contain the expected production "
                    "signing key. Either sign.rs changed or this binary is not "
                    "what it appears to be."
                )
                print("  signing key: NOT FOUND  <-- do not ship")

    if not any(is_executable(p) for p in built):
        problems.append(
            "No application binary among the artifacts, so the signing key was "
            "never checked. A pass here would mean nothing."
        )

    print()
    if problems:
        print("FAILED:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print("Release build looks shippable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
