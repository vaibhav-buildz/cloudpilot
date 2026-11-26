"""Regression coverage for the production smoke-test request and output contract."""

from __future__ import annotations

import json
import sys
import uuid
from importlib import import_module
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
smoke = import_module("scripts.smoke_test")


@pytest.mark.parametrize(
    ("cap_detail", "html_proxy"),
    [
        ("exceeds SIM_MAX_SERVICES limit", False),
        ("invalid n_steps", False),
        ("exceeds SIM_MAX_SERVICES limit", True),
    ],
)
def test_smoke_checks_real_cap_and_uses_valid_workloads(
    monkeypatch, capsys, cap_detail, html_proxy
):
    monkeypatch.setenv("BACKEND_URL", "https://backend.example")
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.example")
    monkeypatch.setenv("CLOUDPILOT_API_KEY", "synthetic-test-key")
    monkeypatch.delenv("ALLOWED_ORIGIN", raising=False)
    client_type = httpx.Client
    direct_visitor = None
    run_id = str(uuid.uuid4())

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal direct_visitor
        path = request.url.path
        if path in ("/health", "/ready"):
            return httpx.Response(200)
        if request.method == "OPTIONS":
            origin = request.headers["origin"]
            if origin == "https://evil.example":
                return httpx.Response(400)
            return httpx.Response(200, headers={"Access-Control-Allow-Origin": origin})
        if path == "/api/limits":
            if "X-API-Key" not in request.headers:
                return httpx.Response(401)
            assert request.headers["X-API-Key"] == "synthetic-test-key"
            direct_visitor = request.headers["X-Visitor-Id"]
            assert uuid.UUID(direct_visitor).version == 4
            return httpx.Response(200, json={"max_services": 20})
        if path == "/api/simulate":
            payload = json.loads(request.content)
            assert payload["n_steps"] == 600
            if request.url.host == "backend.example":
                assert request.headers["X-API-Key"] == "synthetic-test-key"
                assert request.headers["X-Visitor-Id"] == direct_visitor
                assert payload["n_services"] > 20
                return httpx.Response(422, json={"detail": cap_detail})
            assert payload["n_services"] == 4
            assert "X-API-Key" not in request.headers
            if html_proxy:
                return httpx.Response(200, text="<html>Wrong upstream</html>")
            return httpx.Response(
                200,
                json={"saved": True, "run_id": run_id},
                headers={"Set-Cookie": "cp_vid=smoke-visitor; Secure; Path=/"},
            )
        assert path == f"/api/runs/{run_id}"
        assert request.headers["cookie"] == "cp_vid=smoke-visitor"
        return httpx.Response(200, json={"id": run_id})

    monkeypatch.setattr(
        smoke.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs),
    )
    expected = "SIM_MAX_SERVICES" in cap_detail
    assert smoke.main() == (0 if expected and not html_proxy else 1)
    captured = capsys.readouterr().out
    if html_proxy:
        assert "FAIL proxy_simulate_and_readback: POST HTTP 200" in captured
        assert "Wrong upstream" in captured
    else:
        assert "PASS proxy_simulate_and_readback" in captured
    if expected:
        assert "PASS simulation_caps" in captured
    else:
        assert "FAIL simulation_caps" in captured
        assert cap_detail in captured


def test_response_detail_redacts_credentials_and_keeps_diagnostic():
    known = 'test"credential'
    response = httpx.Response(
        500,
        json={
            "detail": f"FUNCTION_INVOCATION_FAILED {known} sb_secret_fake123",
            "Authorization": "Bearer some-other-fixture",
            "CLOUDPILOT_API_KEY": "test-fixture",
        },
    )
    detail = smoke._response_detail(response, known)
    assert "HTTP 500" in detail
    assert "FUNCTION_INVOCATION_FAILED" in detail
    assert "[REDACTED]" in detail
    for value in ('test\\"credential', "sb_secret_fake123", "some-other-fixture", "test-fixture"):
        assert value not in detail
