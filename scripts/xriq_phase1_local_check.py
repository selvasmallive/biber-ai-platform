from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
XRIQ_MANIFEST = ROOT / "xriq" / "Cargo.toml"


class CheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the local CPU-only XRIQ Phase 1 validation set. "
            "This does not use Vast, vLLM, BIBER API, or model training."
        )
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=None,
        help="Directory for smoke artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument(
        "--skip-smokes",
        action="store_true",
        help="Skip transfer and HTTP smoke scripts after Rust checks.",
    )
    parser.add_argument(
        "--skip-clippy",
        action="store_true",
        help="Skip cargo clippy. Use only for quick local iteration.",
    )
    return parser.parse_args(argv)


def default_artifact_root() -> Path:
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return ROOT / "xriq" / "target" / f"xriq-phase1-local-check-{stamp}"


def run_step(
    name: str,
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> None:
    print(f"==> {name}")
    print("$ " + " ".join(command))
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(command, cwd=cwd, env=merged_env)
    if result.returncode != 0:
        raise CheckError(f"{name} failed with exit code {result.returncode}")


def cargo_env(target_dir: str) -> dict[str, str]:
    return {"CARGO_TARGET_DIR": target_dir}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_root = (args.artifact_root or default_artifact_root()).resolve()
    artifact_root.mkdir(parents=True, exist_ok=False)

    completed: list[str] = []
    skipped: list[str] = []

    steps: list[tuple[str, list[str], dict[str, str] | None]] = [
        (
            "cargo fmt check",
            [
                "cargo",
                "fmt",
                "--all",
                "--manifest-path",
                str(XRIQ_MANIFEST),
                "--",
                "--check",
            ],
            None,
        ),
        (
            "python smoke syntax check",
            [
                sys.executable,
                "-m",
                "py_compile",
                str(ROOT / "scripts" / "xriq_private_devnet_transfer_smoke.py"),
                str(ROOT / "scripts" / "xriq_private_devnet_http_smoke.py"),
            ],
            None,
        ),
        (
            "cargo test workspace",
            [
                "cargo",
                "test",
                "--workspace",
                "--manifest-path",
                str(XRIQ_MANIFEST),
                "-j",
                "1",
            ],
            cargo_env("target-codex-xriq-phase1-test"),
        ),
    ]

    if args.skip_clippy:
        skipped.append("cargo clippy workspace")
    else:
        steps.append(
            (
                "cargo clippy workspace",
                [
                    "cargo",
                    "clippy",
                    "--workspace",
                    "--manifest-path",
                    str(XRIQ_MANIFEST),
                    "--",
                    "-D",
                    "warnings",
                ],
                cargo_env("target-codex-xriq-phase1-clippy"),
            )
        )

    for name, command, env in steps:
        run_step(name, command, env=env)
        completed.append(name)

    if args.skip_smokes:
        skipped.extend(["transfer smoke", "http smoke"])
    else:
        transfer_dir = artifact_root / "transfer-smoke"
        http_dir = artifact_root / "http-smoke"
        run_step(
            "transfer smoke",
            [
                sys.executable,
                str(ROOT / "scripts" / "xriq_private_devnet_transfer_smoke.py"),
                "--artifact-dir",
                str(transfer_dir),
            ],
            env=cargo_env("target-codex-xriq-phase1-transfer-smoke"),
        )
        completed.append("transfer smoke")
        run_step(
            "http smoke",
            [
                sys.executable,
                str(ROOT / "scripts" / "xriq_private_devnet_http_smoke.py"),
                "--artifact-dir",
                str(http_dir),
            ],
            env=cargo_env("target-codex-xriq-phase1-http-smoke"),
        )
        completed.append("http smoke")

    summary = {
        "ok": "xriq-phase1-local-check",
        "artifact_root": str(artifact_root),
        "completed": completed,
        "skipped": skipped,
    }
    summary_path = artifact_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
