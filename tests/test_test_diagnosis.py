from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import biber_api.main as main_module
from biber_api.config import BiberSettings
from biber_api.test_diagnosis import diagnose_test_failure


def make_settings(workspace: Path) -> BiberSettings:
    return BiberSettings(
        env="test",
        api_keys=("test-key",),
        priority_passcodes={},
        local_model_base_url="http://local-model/v1",
        local_model_name="biber-dev-core",
        local_model_timeout_seconds=1,
        mentor_enabled=False,
        openai_base_url="https://api.openai.com/v1",
        openai_api_key=None,
        openai_model=None,
        github_token=None,
        github_default_owner=None,
        github_default_repo=None,
        azure_storage_connection_string=None,
        azure_blob_container="biber-backups",
        repo_context_root=str(workspace),
    )


def test_diagnose_dotnet_compile_error() -> None:
    diagnosis = diagnose_test_failure(
        command=["dotnet", "test"],
        exit_code=1,
        stdout=(
            "Program.cs(10,13): error CS0103: "
            "The name 'missing' does not exist in the current context\n"
        ),
    )

    assert diagnosis["has_failure"] is True
    assert diagnosis["detected_stack"] == "dotnet"
    assert diagnosis["primary_category"] == "compile_error"
    assert diagnosis["signals"][0]["category"] == "compile_error"
    assert "CS0103" in diagnosis["relevant_output"]


def test_diagnose_java_missing_symbol() -> None:
    diagnosis = diagnose_test_failure(
        command=["mvn", "test"],
        exit_code=1,
        stderr="[ERROR] cannot find symbol\n  symbol: class WalletService\n",
    )

    assert diagnosis["detected_stack"] == "java"
    assert diagnosis["primary_category"] == "compile_error"
    assert "cannot find symbol" in diagnosis["relevant_output"]


def test_diagnose_rust_test_panic() -> None:
    diagnosis = diagnose_test_failure(
        command=["cargo", "test"],
        exit_code=101,
        stdout=(
            "thread 'ledger::tests::rejects_bad_nonce' panicked at "
            "src/ledger.rs:44:9\n"
            "test result: FAILED. 0 passed; 1 failed\n"
        ),
    )

    assert diagnosis["detected_stack"] == "rust"
    assert diagnosis["primary_category"] == "assertion_failure"
    assert "panicked at" in diagnosis["relevant_output"]


def test_diagnose_pytest_failure_with_embedded_rust_fixture() -> None:
    diagnosis = diagnose_test_failure(
        command=["python", "-m", "pytest"],
        test_id="pytest-core",
        exit_code=1,
        stdout=(
            "____ test_diagnose_rust_test_panic ____\n"
            "            stdout=(\n"
            "                \"thread 'ledger::tests::rejects_bad_nonce' panicked at \"\n"
            "                \"src/ledger.rs:44:9\\n\"\n"
            "                \"test result: FAILED. 0 passed; 1 failed\\n\"\n"
            "            ),\n"
            ">       assert diagnosis[\"primary_category\"] == \"assertion_failure\"\n"
            "E       AssertionError: assert 'test_failure' == 'assertion_failure'\n"
            "E         - assertion_failure\n"
            "E         + test_failure\n"
        ),
    )

    assert diagnosis["detected_stack"] == "python"
    assert diagnosis["primary_category"] == "assertion_failure"
    assert "assert 'test_failure' == 'assertion_failure'" in diagnosis["relevant_output"]


def test_diagnose_python_missing_dependency() -> None:
    diagnosis = diagnose_test_failure(
        command=["python", "-m", "pytest"],
        exit_code=1,
        stderr="ModuleNotFoundError: No module named 'fastapi'\n",
    )

    assert diagnosis["detected_stack"] == "python"
    assert diagnosis["primary_category"] == "missing_dependency"
    assert "requirements" in " ".join(diagnosis["suggested_next_actions"])


def test_diagnose_typescript_compile_error() -> None:
    diagnosis = diagnose_test_failure(
        command=["pnpm", "exec", "tsc", "--noEmit"],
        exit_code=2,
        stdout="src/App.tsx(8,12): error TS2304: Cannot find name 'ButtonProps'.\n",
    )

    assert diagnosis["detected_stack"] == "node"
    assert diagnosis["primary_category"] == "compile_error"
    assert diagnosis["signals"][0]["message"] == "TypeScript compiler error"
    assert "package.json" in " ".join(diagnosis["suggested_next_actions"])


def test_diagnose_react_testing_library_assertion() -> None:
    diagnosis = diagnose_test_failure(
        command=["npm", "test", "--", "Button.test.tsx"],
        exit_code=1,
        stderr=(
            "TestingLibraryElementError: Unable to find an element with the text: Save\n"
            "Ignored nodes: comments, script, style\n"
        ),
    )

    assert diagnosis["detected_stack"] == "node"
    assert diagnosis["primary_category"] == "assertion_failure"
    assert "Unable to find an element" in diagnosis["relevant_output"]


def test_diagnose_vite_import_resolution_failure() -> None:
    diagnosis = diagnose_test_failure(
        command=["yarn", "vite", "build"],
        exit_code=1,
        stderr="[vite]: Rollup failed to resolve import \"@/widgets/Card\" from src/App.tsx.\n",
    )

    assert diagnosis["detected_stack"] == "node"
    assert diagnosis["primary_category"] == "missing_dependency"
    assert diagnosis["signals"][0]["message"] == "Node import resolution error"


def test_diagnose_endpoint_returns_structured_failure(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).post(
            "/v1/tests/diagnose",
            headers={"x-api-key": "test-key"},
            json={
                "command": ["dotnet", "test"],
                "exit_code": 1,
                "stdout": "Example.cs(7,1): error CS1002: ; expected\n",
            },
        )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["has_failure"] is True
    assert body["detected_stack"] == "dotnet"
    assert body["primary_category"] == "compile_error"
    assert body["signals"][0]["evidence"].endswith("; expected")


def test_diagnose_endpoint_requires_api_key(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).post("/v1/tests/diagnose", json={})
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 401
