from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import BiberSettings


@dataclass(frozen=True)
class TestCommandSpec:
    test_id: str
    label: str
    description: str
    cwd: str
    argv: tuple[str, ...]
    timeout_seconds: float | None = None
    xriq_env: bool = False


class TestRunnerConfigurationError(RuntimeError):
    pass


class UnknownTestCommandError(ValueError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[str]]


_TEST_COMMANDS: dict[str, TestCommandSpec] = {
    "python-compileall-api": TestCommandSpec(
        test_id="python-compileall-api",
        label="Python API compileall",
        description="Compile-check app/ and src/ Python modules.",
        cwd="repo",
        argv=(sys.executable, "-m", "compileall", "app", "src"),
        timeout_seconds=120,
    ),
    "pytest-core": TestCommandSpec(
        test_id="pytest-core",
        label="Core API pytest",
        description=(
            "Run focused BIBER API tests for workspace edits, model registry, "
            "GitHub workflows, mentor trigger, repo context, and XRIQ wrappers."
        ),
        cwd="repo",
        argv=(
            sys.executable,
            "-m",
            "pytest",
            "tests/test_agent_capabilities.py",
            "tests/test_agent_session.py",
            "tests/test_biber_agent_client.py",
            "tests/test_workspace_edit.py",
            "tests/test_github_client.py",
            "tests/test_repo_adaptation_eval.py",
            "tests/test_repo_adaptation_failure_review.py",
            "tests/test_repo_adaptation_plan.py",
            "tests/test_test_diagnosis.py",
            "tests/test_model_registry.py",
            "tests/test_openai_mentor_trigger.py",
            "tests/test_repo_context.py",
            "tests/test_test_runner.py",
            "tests/test_xriq_preflight_api.py",
            "-q",
        ),
        timeout_seconds=180,
    ),
    "pytest-test-diagnosis": TestCommandSpec(
        test_id="pytest-test-diagnosis",
        label="Test diagnosis pytest",
        description="Run only BIBER test-failure diagnosis tests.",
        cwd="repo",
        argv=(
            sys.executable,
            "-m",
            "pytest",
            "tests/test_test_diagnosis.py",
            "-q",
        ),
        timeout_seconds=120,
    ),
    "dotnet-test": TestCommandSpec(
        test_id="dotnet-test",
        label=".NET test",
        description="Run `dotnet test --nologo` from the configured repo root.",
        cwd="repo",
        argv=("dotnet", "test", "--nologo"),
        timeout_seconds=300,
    ),
    "maven-test": TestCommandSpec(
        test_id="maven-test",
        label="Maven test",
        description="Run `mvn test` from the configured repo root.",
        cwd="repo",
        argv=("mvn", "test"),
        timeout_seconds=300,
    ),
    "gradle-test": TestCommandSpec(
        test_id="gradle-test",
        label="Gradle test",
        description="Run `gradle test` from the configured repo root.",
        cwd="repo",
        argv=("gradle", "test"),
        timeout_seconds=300,
    ),
    "gradle-wrapper-test": TestCommandSpec(
        test_id="gradle-wrapper-test",
        label="Gradle wrapper test",
        description="Run `./gradlew test` from the configured repo root.",
        cwd="repo",
        argv=("./gradlew", "test"),
        timeout_seconds=300,
    ),
    "xriq-node-fixtures": TestCommandSpec(
        test_id="xriq-node-fixtures",
        label="XRIQ checked fixtures",
        description="Run the checked private-devnet xriq-node JSON fixture tests.",
        cwd="xriq",
        argv=("cargo", "test", "-p", "xriq-node", "checked_fixture", "-j", "1"),
        timeout_seconds=240,
        xriq_env=True,
    ),
    "xriq-private-devnet-smoke": TestCommandSpec(
        test_id="xriq-private-devnet-smoke",
        label="XRIQ private-devnet smoke",
        description=(
            "Run the deterministic private-devnet shell smoke, including "
            "replay-status state-root checks."
        ),
        cwd="repo",
        argv=("bash", "scripts/xriq_private_devnet_smoke.sh"),
        timeout_seconds=240,
        xriq_env=True,
    ),
}


def list_test_commands(settings: BiberSettings) -> list[dict[str, object]]:
    return [
        {
            "test_id": spec.test_id,
            "label": spec.label,
            "description": spec.description,
            "cwd": _display_cwd(spec, settings),
            "command": list(spec.argv),
            "timeout_seconds": _timeout_seconds(spec, settings),
        }
        for spec in _TEST_COMMANDS.values()
    ]


def run_test_command(
    test_id: str,
    settings: BiberSettings,
    *,
    dry_run: bool = False,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    spec = _spec(test_id)
    cwd = _cwd(spec, settings)
    command = list(spec.argv)
    timeout_seconds = _timeout_seconds(spec, settings)
    env = _subprocess_env(settings) if spec.xriq_env else os.environ.copy()

    response: dict[str, Any] = {
        "test_id": spec.test_id,
        "label": spec.label,
        "description": spec.description,
        "cwd": str(cwd),
        "command": command,
        "timeout_seconds": timeout_seconds,
        "executed": not dry_run,
        "ok": None,
        "exit_code": None,
        "timed_out": False,
        "duration_ms": 0,
        "stdout": "",
        "stderr": "",
        "stdout_truncated": False,
        "stderr_truncated": False,
    }
    if dry_run:
        return response

    started = time.monotonic()
    try:
        completed = runner(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=env,
        )
    except FileNotFoundError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        stderr, stderr_truncated = _truncate(str(exc), settings.test_runner_max_output_bytes)
        return response | {
            "ok": False,
            "exit_code": 127,
            "duration_ms": duration_ms,
            "stderr": stderr,
            "stderr_truncated": stderr_truncated,
        }
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        stdout, stdout_truncated = _truncate(
            _timeout_output(exc.stdout),
            settings.test_runner_max_output_bytes,
        )
        stderr, stderr_truncated = _truncate(
            _timeout_output(exc.stderr),
            settings.test_runner_max_output_bytes,
        )
        return response | {
            "ok": False,
            "timed_out": True,
            "duration_ms": duration_ms,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }

    duration_ms = int((time.monotonic() - started) * 1000)
    stdout, stdout_truncated = _truncate(completed.stdout, settings.test_runner_max_output_bytes)
    stderr, stderr_truncated = _truncate(completed.stderr, settings.test_runner_max_output_bytes)
    return response | {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "duration_ms": duration_ms,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
    }


def _spec(test_id: str) -> TestCommandSpec:
    try:
        return _TEST_COMMANDS[test_id]
    except KeyError as exc:
        raise UnknownTestCommandError(f"Unknown test_id: {test_id}") from exc


def _cwd(spec: TestCommandSpec, settings: BiberSettings) -> Path:
    if spec.cwd == "repo":
        cwd = Path(settings.repo_context_root)
    elif spec.cwd == "xriq":
        cwd = Path(settings.xriq_workspace_dir)
    else:
        raise TestRunnerConfigurationError(f"Unsupported test cwd kind: {spec.cwd}")
    if not cwd.exists() or not cwd.is_dir():
        raise TestRunnerConfigurationError(f"Test command workspace does not exist: {cwd}")
    return cwd


def _display_cwd(spec: TestCommandSpec, settings: BiberSettings) -> str:
    try:
        return str(_cwd(spec, settings))
    except TestRunnerConfigurationError:
        return "unavailable"


def _timeout_seconds(spec: TestCommandSpec, settings: BiberSettings) -> float:
    return spec.timeout_seconds or settings.test_runner_timeout_seconds


def _subprocess_env(settings: BiberSettings) -> dict[str, str]:
    env = os.environ.copy()
    if settings.xriq_rustup_home:
        env["RUSTUP_HOME"] = settings.xriq_rustup_home
    if settings.xriq_cargo_home:
        env["CARGO_HOME"] = settings.xriq_cargo_home
    if settings.xriq_path_prefix:
        env["PATH"] = f"{settings.xriq_path_prefix}{os.pathsep}{env.get('PATH', '')}"
    return env


def _truncate(value: str, max_bytes: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value, False
    truncated = encoded[:max_bytes].decode("utf-8", errors="replace")
    return f"{truncated}\n...<truncated>", True


def _timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
