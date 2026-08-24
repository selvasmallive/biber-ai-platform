#!/usr/bin/env python3
"""Offline FastAPI smoke for BIBER API request-size and rate-limit guards."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def check(name: str, condition: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def write_json(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON artifact path.")
    args = parser.parse_args()

    try:
        from fastapi.testclient import TestClient

        import biber_api.main as main_module
        from biber_api.config import BiberSettings
        from biber_api.security import clear_api_request_guard_state
    except Exception as exc:  # pragma: no cover - reported in JSON for ops use.
        payload = {
            "source": "biber_api_request_guard_smoke",
            "ok": False,
            "api_required": False,
            "external_network_required": False,
            "gpu_required": False,
            "mentor_used": False,
            "training_allowed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "checks": [],
        }
        write_json(args.output, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1

    def make_settings(
        workspace: Path,
        *,
        max_request_bytes: int = 1048576,
        rate_limit_requests_per_minute: int = 120,
    ) -> BiberSettings:
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
            api_guard_enabled=True,
            api_max_request_bytes=max_request_bytes,
            api_rate_limit_requests_per_minute=rate_limit_requests_per_minute,
        )

    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="biber-api-guard-smoke-") as tmp:
        workspace = Path(tmp)
        main_module.app.dependency_overrides.clear()

        settings = make_settings(workspace, max_request_bytes=32)
        clear_api_request_guard_state()
        main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
        try:
            oversized = TestClient(main_module.app).post(
                "/v1/tests/diagnose",
                headers={
                    "x-api-key": "test-key",
                    "content-type": "application/json",
                },
                content='{"stdout":"' + ("x" * 80) + '"}',
            )
        finally:
            main_module.app.dependency_overrides.clear()
            clear_api_request_guard_state()
        checks.extend(
            [
                check("oversized_status", oversized.status_code == 413),
                check(
                    "oversized_header",
                    oversized.headers.get("x-biber-max-request-bytes") == "32",
                ),
                check("oversized_no_secret", "test-key" not in oversized.text),
            ]
        )

        settings = make_settings(workspace, rate_limit_requests_per_minute=2)
        clear_api_request_guard_state()
        main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
        try:
            client = TestClient(main_module.app)
            headers = {"Authorization": "Bearer test-key"}
            first = client.get("/v1/agent/capabilities", headers=headers)
            second = client.get("/v1/agent/capabilities", headers=headers)
            third = client.get("/v1/agent/capabilities", headers=headers)
        finally:
            main_module.app.dependency_overrides.clear()
            clear_api_request_guard_state()
        checks.extend(
            [
                check("rate_first_ok", first.status_code == 200),
                check("rate_second_ok", second.status_code == 200),
                check("rate_third_limited", third.status_code == 429),
                check(
                    "rate_limit_header",
                    third.headers.get("x-biber-ratelimit-limit") == "2",
                ),
                check("rate_retry_after", int(third.headers.get("retry-after", "0")) >= 1),
                check("rate_no_secret", "test-key" not in third.text),
            ]
        )

        settings = make_settings(workspace, rate_limit_requests_per_minute=1)
        clear_api_request_guard_state()
        main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
        try:
            client = TestClient(main_module.app)
            health_codes = [client.get("/health").status_code for _ in range(3)]
        finally:
            main_module.app.dependency_overrides.clear()
            clear_api_request_guard_state()
        checks.append(check("health_not_limited", health_codes == [200, 200, 200]))

        settings = make_settings(workspace)
        clear_api_request_guard_state()
        main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
        try:
            capabilities = TestClient(main_module.app).get(
                "/v1/agent/capabilities",
                headers={"x-api-key": "test-key"},
            )
        finally:
            main_module.app.dependency_overrides.clear()
            clear_api_request_guard_state()
        protections = (
            capabilities.json()
            .get("features", {})
            .get("external_agent_api", {})
            .get("server_side_protections", {})
        )
        checks.extend(
            [
                check("capabilities_status", capabilities.status_code == 200),
                check("capabilities_guard_enabled", protections.get("api_guard_enabled") is True),
                check("capabilities_scope", protections.get("scope") == "/v1/*"),
                check(
                    "capabilities_limit",
                    protections.get("rate_limit_requests_per_minute") == 120,
                ),
            ]
        )

    payload = {
        "source": "biber_api_request_guard_smoke",
        "ok": all(item["ok"] for item in checks),
        "api_required": False,
        "external_network_required": False,
        "gpu_required": False,
        "github_request_sent": False,
        "mentor_used": False,
        "training_allowed": False,
        "checks": checks,
        "failed": [item for item in checks if not item["ok"]],
    }
    write_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
