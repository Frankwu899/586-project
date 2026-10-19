"""Offline GPT-6 capability, preflight and budget-recovery regressions."""
from decimal import Decimal
import json
import sqlite3

import httpx
import pytest

from backend.app.providers.base import ProviderError
from backend.app.providers.budget import ExperimentBudget, estimate_upper_bound, usage_estimate
from backend.app.providers.config import ProviderSettings
from backend.app.providers.transport import OpenAITransport


MODEL = "gpt-6.1-sol"


def test_new_profiles_and_legacy_environment_defaults_use_reviewed_gpt6_models(monkeypatch):
    monkeypatch.delenv("OPENAI_TRANSCRIPTION_MODEL", raising=False)
    for capability in ("VISION", "CREATIVE", "M2", "STRUCTURE", "RESEARCH"):
        monkeypatch.setenv(f"OPENAI_{capability}_MODEL", "gpt-4.1-mini")
    settings = ProviderSettings.from_env()
    assert settings.vision_model == settings.creative_model == settings.m2_model == settings.structure_model == MODEL
    assert settings.research_model == "gpt-6-luna"
    assert settings.transcription_model == "disabled"


def test_preflight_counts_images_and_reserves_only_bounded_request_before_generation(tmp_path):
    ledger = ExperimentBudget(tmp_path / "ledger.sqlite3", "0.10")
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"synthetic image; no decoding in mocked HTTP")
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(request.url.path)
        assert payload["model"] == MODEL
        if request.url.path.endswith("input_tokens"):
            assert ledger.summary()["attempts"] == 0
            assert payload["input"][0]["content"][1]["type"] == "input_image"
            return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 2000})
        assert ledger.summary()["attempts"] == 1
        assert Decimal(ledger.summary()["held_usd"]) < Decimal("0.10")
        assert "_input_tokens_bound" not in payload
        assert payload["reasoning"] == {"effort": "low"}
        return httpx.Response(200, json={"status": "completed", "model": MODEL,
            "usage": {"input_tokens": 2000, "output_tokens": 100, "input_tokens_details": {"cache_write_tokens": 1000}},
            "output": [{"content": [{"type": "output_text", "text": '{"value":"ok"}'}]}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = OpenAITransport(ProviderSettings(api_key="synthetic-key", budget_path=ledger.path, max_retries=0), client=client)
        assert transport.json_response(MODEL, "synthetic prompt", {"type": "object"}, "fixture", [image]) == {"value": "ok"}
    assert calls == ["/v1/responses/input_tokens", "/v1/responses"]
    assert ledger.summary()["known_estimated_cost_usd"] == "0.0055"


@pytest.mark.parametrize("body", [{}, {"object": "response.input_tokens", "input_tokens": True},
    {"object": "response.input_tokens", "input_tokens": 300000}])
def test_unverified_or_oversized_count_never_generates_or_reserves(tmp_path, body):
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json=body)
    ledger = ExperimentBudget(tmp_path / "ledger.sqlite3")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = OpenAITransport(ProviderSettings(api_key="synthetic-key", budget_path=ledger.path, max_retries=0), client=client)
        with pytest.raises(ProviderError):
            transport.json_response(MODEL, "synthetic prompt", {}, "fixture")
    assert calls == ["/v1/responses/input_tokens"]
    assert ledger.summary()["attempts"] == 0


def test_luna_research_reserves_full_hidden_context_with_long_context_premiums():
    payload = {"max_output_tokens": 4000, "tools": [{"type": "web_search", "search_context_size": "low"}], "max_tool_calls": 2}
    # 3 context turns, 2x cache-write input rate, 1.5x output rate, two search calls.
    assert estimate_upper_bound("gpt-6-luna", payload) == Decimal("0.8105")
    assert estimate_upper_bound(MODEL, payload) > Decimal("3")


def test_missing_cache_breakdown_uses_premium_not_discount_and_unknown_usage_is_held():
    payload = {"max_output_tokens": 8000, "_input_tokens_bound": 2000}
    result = usage_estimate(MODEL, payload, {"model": MODEL, "usage": {"input_tokens": 1000, "output_tokens": 100}})
    assert result[0] == Decimal("0.0035")
    assert usage_estimate(MODEL, payload, {"model": "gpt-future", "usage": {"input_tokens": 1000, "output_tokens": 100}})[0] is None


def test_reconciliation_releases_only_explicit_old_auth_failures_and_preserves_audit(tmp_path):
    ledger = ExperimentBudget(tmp_path / "ledger.sqlite3")
    payload = {"max_output_tokens": 1000, "_input_tokens_bound": 2000}
    auth = ledger.reserve(MODEL, payload)
    timeout = ledger.reserve(MODEL, payload)
    with sqlite3.connect(ledger.path) as db:
        db.execute("UPDATE attempts SET status='unknown',failure_code='provider_authentication' WHERE id=?", (auth,))
        db.execute("UPDATE attempts SET status='unknown',failure_code='provider_timeout' WHERE id=?", (timeout,))
    assert ledger.summary()["recoverable_rejected_attempts"] == 1
    assert ledger.reconcile_rejected_attempts() == {"reconciled_attempts": 1, "released_usd": "0.015"}
    summary = ledger.summary()
    assert summary["maximum_usd"] == "3" and summary["unknown_attempts"] == 1
    assert summary["held_usd"] == "0.015" and summary["reserved_upper_bound_usd"] == "0.03"
    assert ledger.reconcile_rejected_attempts()["reconciled_attempts"] == 0
    with sqlite3.connect(ledger.path) as db:
        assert db.execute("SELECT failure_code,basis FROM attempts WHERE id=?", (auth,)).fetchone() == ("provider_authentication", "http_auth_rejection_before_generation")


@pytest.mark.parametrize("failure", ["provider_authentication", "provider_permission"])
def test_new_explicit_http_auth_refusal_is_zero_generation_cost(tmp_path, failure):
    ledger = ExperimentBudget(tmp_path / "ledger.sqlite3")
    payload = {"max_output_tokens": 1000, "_input_tokens_bound": 2000}
    reservation = ledger.reserve(MODEL, payload)
    result = ledger.finish(reservation, MODEL, payload, failure_code=failure)
    assert result["held_usd"] == "0" and result["estimated_cost_usd"] == "0"
    assert ledger.summary()["remaining_usd"] == "3"


def test_expired_deadline_after_token_count_sends_no_generation_and_holds_no_budget(tmp_path, monkeypatch):
    now = [0.0]
    monkeypatch.setattr("backend.app.providers.transport.time.monotonic", lambda: now[0])
    ledger = ExperimentBudget(tmp_path / "ledger.sqlite3")
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.extensions["timeout"]["read"] == 10
        now[0] = 11
        return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 1000})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = OpenAITransport(ProviderSettings(api_key="synthetic", budget_path=ledger.path, max_retries=0), client=client)
        with pytest.raises(ProviderError) as error:
            transport.json_response(MODEL, "test", {}, "fixture", metadata={"_deadline": 10.0, "capability": "structure"})
    assert error.value.code == "structure_time_limit"
    assert calls == ["/v1/responses/input_tokens"]
    assert ledger.summary()["attempts"] == 0 and ledger.summary()["held_usd"] == "0"
    assert transport.records[0]["attempts"] == 0 and "_deadline" not in transport.records[0]


def test_generation_timeout_uses_only_time_remaining_after_preflight(tmp_path, monkeypatch):
    now = [0.0]
    monkeypatch.setattr("backend.app.providers.transport.time.monotonic", lambda: now[0])
    timeouts = []

    def handler(request):
        timeouts.append(request.extensions["timeout"]["read"])
        if request.url.path.endswith("input_tokens"):
            now[0] = 3
            return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 1000})
        return httpx.Response(200, json={"status": "completed", "model": MODEL,
            "usage": {"input_tokens": 1000, "output_tokens": 100},
            "output": [{"content": [{"type": "output_text", "text": '{"ok":true}'}]}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = OpenAITransport(ProviderSettings(api_key="synthetic", budget_path=tmp_path / "ledger.sqlite3", max_retries=0), client=client)
        assert transport.json_response(MODEL, "test", {}, "fixture", metadata={"_deadline": 10.0}) == {"ok": True}
    assert timeouts == [10, 7]


def test_deadline_exhausted_while_waiting_for_slot_releases_only_unsent_reservation(tmp_path, monkeypatch):
    now = [0.0]
    monkeypatch.setattr("backend.app.providers.transport.time.monotonic", lambda: now[0])
    class Slots:
        acquisitions = 0
        releases = 0
        def acquire(self, *, timeout):
            assert timeout == 10
            self.acquisitions += 1
            if self.acquisitions == 2:
                now[0] = 11
            return True
        def release(self):
            self.releases += 1
    slots = Slots()
    monkeypatch.setattr("backend.app.providers.transport._REQUEST_SLOTS", slots)
    ledger = ExperimentBudget(tmp_path / "ledger.sqlite3")
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 1000})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = OpenAITransport(ProviderSettings(api_key="synthetic", budget_path=ledger.path, max_retries=0), client=client)
        with pytest.raises(ProviderError) as error:
            transport.json_response(MODEL, "test", {}, "fixture", metadata={"_deadline": 10.0})
    assert error.value.code == "structure_time_limit" and calls == ["/v1/responses/input_tokens"]
    assert slots.releases == 2
    assert ledger.summary()["attempts"] == 1 and ledger.summary()["held_usd"] == "0"
    assert transport.records[0]["attempts"] == 0
    assert transport.records[0]["attempt_records"][0]["estimate_basis"] == "generation_request_not_sent"
