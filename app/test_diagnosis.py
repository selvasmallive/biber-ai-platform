from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


SUPPORTED_STACKS = ["dotnet", "java", "rust", "python", "node", "unknown"]

_CATEGORY_PRIORITY = {
    "timeout": 0,
    "compile_error": 10,
    "missing_dependency": 20,
    "configuration_error": 30,
    "assertion_failure": 40,
    "runtime_error": 50,
    "test_failure": 60,
    "unknown": 99,
}


@dataclass(frozen=True)
class _Rule:
    pattern: str
    category: str
    message: str
    stack: str | None = None


_RULES = [
    _Rule(r"\berror\s+cs\d{4}\b", "compile_error", "C# compiler error", "dotnet"),
    _Rule(r"\bcs\d{4}\b", "compile_error", "C# compiler diagnostic", "dotnet"),
    _Rule(r"\bassert\.", "assertion_failure", ".NET assertion failure", "dotnet"),
    _Rule(r"\bfailed\s+.*\s+\[\d+", "test_failure", ".NET test failure", "dotnet"),
    _Rule(r"compilation failure", "compile_error", "Java compilation failure", "java"),
    _Rule(r"compilation error", "compile_error", "Java compilation error", "java"),
    _Rule(r"cannot find symbol", "compile_error", "Java symbol resolution error", "java"),
    _Rule(r"package .* does not exist", "missing_dependency", "Java missing package", "java"),
    _Rule(r"build failed", "test_failure", "Gradle build failed", "java"),
    _Rule(r"\[error\]", "test_failure", "Maven error output", "java"),
    _Rule(r"error\[e\d{4}\]", "compile_error", "Rust compiler error", "rust"),
    _Rule(r"\berror:", "compile_error", "Rust compiler error", "rust"),
    _Rule(r"panicked at", "assertion_failure", "Rust test panic", "rust"),
    _Rule(r"test result: failed", "test_failure", "Rust test failure", "rust"),
    _Rule(r"modulenotfounderror", "missing_dependency", "Python missing module", "python"),
    _Rule(r"importerror", "missing_dependency", "Python import error", "python"),
    _Rule(r"assertionerror", "assertion_failure", "Python assertion failure", "python"),
    _Rule(r"e\s+assert", "assertion_failure", "pytest assertion failure", "python"),
    _Rule(r"traceback \(most recent call last\)", "runtime_error", "Python traceback", "python"),
    _Rule(r"syntaxerror", "compile_error", "Python syntax error", "python"),
    _Rule(r"failed .* in \d", "test_failure", "pytest failure summary", "python"),
    _Rule(r"cannot find module", "missing_dependency", "Node missing module", "node"),
    _Rule(r"module not found", "missing_dependency", "Node missing module", "node"),
    _Rule(r"failed to resolve import", "missing_dependency", "Node import resolution error", "node"),
    _Rule(r"could not resolve", "missing_dependency", "Node import resolution error", "node"),
    _Rule(r"\berror\s+ts\d{4}\b", "compile_error", "TypeScript compiler error", "node"),
    _Rule(r"\bts\d{4}:", "compile_error", "TypeScript compiler diagnostic", "node"),
    _Rule(r"cannot find name", "compile_error", "TypeScript name resolution error", "node"),
    _Rule(r"test suite failed to run", "compile_error", "Jest test-suite setup failure", "node"),
    _Rule(r"failed to parse source", "compile_error", "Vite source parse failure", "node"),
    _Rule(r"failed to transform", "compile_error", "JavaScript transform failure", "node"),
    _Rule(r"expect\(received\)", "assertion_failure", "Jest assertion failure", "node"),
    _Rule(r"unable to find an element", "assertion_failure", "React Testing Library assertion failure", "node"),
    _Rule(r"referenceerror", "runtime_error", "JavaScript reference error", "node"),
    _Rule(r"typeerror", "runtime_error", "JavaScript type error", "node"),
    _Rule(r"syntaxerror", "compile_error", "JavaScript syntax error", "node"),
    _Rule(r"\bfail\b", "test_failure", "JavaScript test failure", "node"),
]


def diagnose_test_failure(
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = None,
    timed_out: bool = False,
    command: list[str] | tuple[str, ...] | None = None,
    test_id: str | None = None,
    max_context_lines: int = 80,
) -> dict[str, Any]:
    command_parts = [str(part) for part in command or ()]
    lines = _split_output(stdout=stdout, stderr=stderr)
    detected_stack = _detect_stack(command_parts, test_id or "", lines)
    signals: list[dict[str, Any]] = []

    if timed_out:
        signals.append(
            {
                "category": "timeout",
                "stack": detected_stack,
                "message": "Test command timed out.",
                "line_number": None,
                "evidence": "",
            }
        )

    for index, line in enumerate(lines):
        match = _match_line(line, detected_stack)
        if match is None:
            continue
        category, stack, message = match
        signals.append(
            {
                "category": category,
                "stack": stack,
                "message": message,
                "line_number": index + 1,
                "evidence": line.strip(),
            }
        )
        if len(signals) >= 12:
            break

    has_failure = bool(signals) or timed_out or (exit_code is not None and exit_code != 0)
    if has_failure and not signals:
        signals.append(
            {
                "category": "unknown",
                "stack": detected_stack,
                "message": "Command failed but no known failure pattern matched.",
                "line_number": None,
                "evidence": "",
            }
        )

    primary_category = _primary_category(signals)
    relevant_output = _relevant_output(lines, signals, max_context_lines=max_context_lines)
    summary = _summary(
        has_failure=has_failure,
        primary_category=primary_category,
        detected_stack=detected_stack,
        signal_count=len(signals),
    )
    return {
        "has_failure": has_failure,
        "primary_category": primary_category,
        "detected_stack": detected_stack,
        "signals": signals,
        "relevant_output": relevant_output,
        "suggested_next_actions": _suggested_next_actions(
            primary_category,
            detected_stack,
        ),
        "summary": summary,
    }


def _split_output(*, stdout: str, stderr: str) -> list[str]:
    combined = []
    if stdout:
        combined.extend(stdout.splitlines())
    if stderr:
        combined.extend(stderr.splitlines())
    return combined


def _detect_stack(command: list[str], test_id: str, lines: list[str]) -> str:
    command_text = " ".join([*command, test_id]).lower()
    if "dotnet" in command_text or re.search(r"\bcs\d{4}\b", command_text):
        return "dotnet"
    if any(token in command_text for token in ("mvn", "gradle", "javac", "junit")):
        return "java"
    if any(token in command_text for token in ("cargo", "rustc", "error[e")):
        return "rust"
    if any(
        token in command_text
        for token in ("pytest", "python", "python3", "traceback", "modulenotfounderror")
    ):
        return "python"
    if any(
        token in command_text
        for token in (
            "npm",
            "pnpm",
            "yarn",
            "npx",
            "vitest",
            "jest",
            "node ",
            "tsc",
            "tsx",
            "vite",
            "react-scripts",
            "testing-library",
            ".tsx",
            ".jsx",
        )
    ):
        return "node"

    text = " ".join([command_text, *lines[:80]]).lower()
    if "dotnet" in text or re.search(r"\bcs\d{4}\b", text):
        return "dotnet"
    if any(token in text for token in ("mvn", "gradle", "javac", "junit")):
        return "java"
    if any(token in text for token in ("cargo", "rustc", "error[e")):
        return "rust"
    if any(token in text for token in ("pytest", "traceback", "modulenotfounderror")):
        return "python"
    if any(
        token in text
        for token in (
            "npm",
            "pnpm",
            "yarn",
            "npx",
            "vitest",
            "jest",
            "node ",
            "tsc",
            "tsx",
            "vite",
            "react-scripts",
            "testing-library",
            ".tsx",
            ".jsx",
        )
    ):
        return "node"
    return "unknown"


def _match_line(line: str, detected_stack: str) -> tuple[str, str, str] | None:
    normalized = line.strip().lower()
    if not normalized:
        return None
    for rule in _RULES:
        if rule.stack not in (None, detected_stack) and detected_stack != "unknown":
            continue
        if re.search(rule.pattern, normalized):
            return rule.category, rule.stack or detected_stack, rule.message
    if re.search(r"command not found|no such file or directory", normalized):
        return "configuration_error", detected_stack, "Command or file is unavailable."
    return None


def _primary_category(signals: list[dict[str, Any]]) -> str:
    if not signals:
        return "none"
    return min(
        (str(signal["category"]) for signal in signals),
        key=lambda category: _CATEGORY_PRIORITY.get(category, 999),
    )


def _relevant_output(
    lines: list[str],
    signals: list[dict[str, Any]],
    *,
    max_context_lines: int,
) -> str:
    max_context_lines = max(1, min(max_context_lines, 200))
    selected_indexes: set[int] = set()
    for signal in signals:
        line_number = signal.get("line_number")
        if not isinstance(line_number, int):
            continue
        index = line_number - 1
        selected_indexes.update({index - 1, index, index + 1})

    selected = [
        lines[index]
        for index in sorted(selected_indexes)
        if 0 <= index < len(lines)
    ]
    if not selected:
        selected = lines[:max_context_lines]
    return "\n".join(selected[:max_context_lines])


def _summary(
    *,
    has_failure: bool,
    primary_category: str,
    detected_stack: str,
    signal_count: int,
) -> str:
    if not has_failure:
        return f"No failure detected for {detected_stack} output."
    return (
        f"Detected {primary_category} in {detected_stack} output "
        f"from {signal_count} signal(s)."
    )


def _suggested_next_actions(primary_category: str, detected_stack: str) -> list[str]:
    actions = [
        "Use the repo-context planner with the failing file, related tests, and manifests.",
    ]
    if primary_category == "timeout":
        actions.append("Rerun the narrowest related test with a higher timeout or less setup.")
    elif primary_category == "compile_error":
        actions.append("Fix compiler diagnostics before asking the model to change behavior.")
    elif primary_category == "missing_dependency":
        actions.append("Check dependency manifests, package restore, and import/module names.")
    elif primary_category == "configuration_error":
        actions.append("Verify the test command, working directory, and required toolchain.")
    elif primary_category == "assertion_failure":
        actions.append("Compare expected and actual behavior in the focused failing test.")
    elif primary_category == "runtime_error":
        actions.append("Trace the first runtime exception before editing unrelated files.")
    elif primary_category == "test_failure":
        actions.append("Open the first failing test and its implementation before broader edits.")
    else:
        actions.append("Send the relevant output to the model with a small context budget.")

    if detected_stack == "dotnet":
        actions.append("Include the `.sln`, `.csproj`, changed `.cs`, and matching test file.")
    elif detected_stack == "java":
        actions.append("Include `pom.xml` or Gradle files plus the failing Java test/source.")
    elif detected_stack == "rust":
        actions.append("Include `Cargo.toml`, the failing Rust module, and related test.")
    elif detected_stack == "python":
        actions.append("Include `pyproject.toml` or requirements plus the failing test/module.")
    elif detected_stack == "node":
        actions.append("Include `package.json`, test config, and the failing component/module.")
    return actions
