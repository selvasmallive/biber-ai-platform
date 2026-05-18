from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import biber_api.main as main_module


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "examples" / "xriq_private_devnet_dashboard.html"


def test_xriq_dashboard_asset_is_static_and_credential_free() -> None:
    html = DASHBOARD.read_text(encoding="utf-8")

    assert "data-biber-xriq-dashboard" in html
    assert "/v1/xriq/private-devnet/overview" in html
    assert "/v1/xriq/private-devnet/snapshots" in html
    assert "dev-api-key-change-me" not in html
    assert "BIBER_API_KEY" not in html
    assert "http://127.0.0.1:8000" in html
    assert "fetch(" in html


def test_xriq_dashboard_route_serves_html() -> None:
    response = TestClient(main_module.app).get("/xriq/private-devnet/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "XRIQ Private Devnet" in response.text
    assert "data-biber-xriq-dashboard" in response.text
