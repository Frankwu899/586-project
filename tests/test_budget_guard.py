"""Mock HTTP and concurrent local accounting only; no paid calls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
from decimal import Decimal
import json

import httpx
import pytest

from backend.app.providers.base import ProviderError
from backend.app.providers.budget import ExperimentBudget, estimate_upper_bound
from backend.app.providers.config import ProviderSettings
from backend.app.providers.transport import OpenAITransport
from backend.app.providers.usage import summarize_usage


def budget(tmp_path, maximum="3"):
    return ExperimentBudget(tmp_path / "shared.sqlite3", maximum, today=date(2026, 10, 19))


def response(**extra):
    return {"status": "completed", "model": "gpt-4.1-mini-2025-04-14",
            "usage": {"input_tokens": 1000, "output_tokens": 100},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"ok":true}'}]}], **extra}


def json_call(transport):
    return transport.json_response("gpt-4.1-mini", "not a secret", {"type": "object"}, "fixture", metadata={"capability": "m2_assistance"})


def test_parallel_reservations_share_cap_and_cannot_reset_it(tmp_path):
    ledger = budget(tmp_path, "0.5")
    def reserve(_):
        try:
            budget(tmp_path).reserve("gpt-4.1-mini", {"max_output_tokens": 1000})
            return True
        except ProviderError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(16))) == 1
    assert ledger.summary()["maximum_usd"] == "0.5"
    assert ledger.summary()["attempts"] == 1
    assert Decimal(ledger.summary()["held_usd"]) <= Decimal("0.5")


def test_retry_reserved_before_each_attempt_unknown_failure_retained(tmp_path):
    ledger = budget(tmp_path)
    seen = []
    def handler(request):
        seen.append(ledger.summary()["attempts"])
        return httpx.Response(503, json={}) if len(seen) == 1 else httpx.Response(200, json=response())
    settings = ProviderSettings(api_key="synthetic-key", budget_path=ledger.path, max_retries=1, max_output_tokens=1000, cache_dir=tmp_path / "cache")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = OpenAITransport(settings, client=client, sleep=lambda _: None)
        assert json_call(transport) == {"ok": True}
    assert seen == [1, 2]
    summary = ledger.summary()
    assert summary["unknown_attempts"] == 1 and summary["attempts"] == 2
    assert summary["known_estimated_cost_usd"] == "0.00056"
    assert Decimal(summary["held_usd"]) == estimate_upper_bound("gpt-4.1-mini", {"max_output_tokens": 1000}) + Decimal("0.00056")
    assert transport.records[0]["estimated_cost_usd"] is None
    persisted = (tmp_path / "cache" / "usage.jsonl").read_text()
    assert "synthetic-key" not in persisted and "not a secret" not in persisted
    assert summarize_usage(transport.records)["m2"]["unknown_attempts"] == 1


def test_exhausted_unknown_model_and_stale_pricing_fail_closed(tmp_path):
    ledger = budget(tmp_path, "0.001")
    calls = []
    settings = ProviderSettings(api_key="synthetic-key", budget_path=ledger.path, max_retries=0)
    with httpx.Client(transport=httpx.MockTransport(lambda request: calls.append(request))) as client:
        with pytest.raises(ProviderError, match="budget"):
            json_call(OpenAITransport(settings, client=client))
        with pytest.raises(ProviderError, match="cost bound"):
            OpenAITransport(settings, client=client).json_response("gpt-4o", "test", {}, "fixture")
    assert calls == []
    with pytest.raises(ProviderError, match="Recheck"):
        ExperimentBudget(tmp_path / "stale", today=date(2027, 1, 1))
    with pytest.raises(ValueError, match="USD 3"):
        budget(tmp_path, "3.01")


def test_unknown_usage_and_different_resolved_model_never_release(tmp_path):
    ledger = budget(tmp_path)
    payload = {"max_output_tokens": 1000}
    for data in (response(usage=None), response(model="unpriced-future-model"), response(usage={"input_tokens": True, "output_tokens": 1})):
        attempt = ledger.reserve("gpt-4.1-mini", payload)
        result = ledger.finish(attempt, "gpt-4.1-mini", payload, data)
        assert result["estimated_cost_usd"] is None
        assert result["held_usd"] == result["reserved_upper_bound_usd"]


def test_audio_duration_is_conservative_estimate_not_reported_usage(tmp_path):
    ledger = budget(tmp_path)
    payload = {"capability": "timestamped_transcription", "audio_seconds": 60.1, "audio_bytes": 100}
    attempt = ledger.reserve("whisper-1", payload, {"capability": "timestamped_transcription"})
    result = ledger.finish(attempt, "whisper-1", payload, {"segments": []})
    assert result["estimated_cost_usd"] == "0.012"
    assert result["provider_billed_cost_usd"] is None
    assert ledger.summary()["modules"]["speech"]["attempts"] == 1


def test_web_search_has_hard_tool_limit_citations_and_accounting(tmp_path):
    ledger = budget(tmp_path)
    requests = []
    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        return httpx.Response(200, json=response(output=[
            {"type": "web_search_call", "action": {"sources": [{"url": "https://example.org/source", "title": "Source"}, {"url": "javascript:bad()"}]}},
            {"type": "message", "content": [{"type": "output_text", "text": "A bounded sourced finding.",
             "annotations": [{"type": "url_citation", "url": "https://example.org/source", "title": "Source", "start_index": 0, "end_index": 10}]}]}]))
    settings = ProviderSettings(api_key="synthetic-key", budget_path=ledger.path, max_retries=0)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = OpenAITransport(settings, client=client).web_search("gpt-4.1-mini", "Test query", max_tool_calls=2, metadata={"capability": "structure", "operation": "research"})
    assert result["sources"] == [{"url": "https://example.org/source", "title": "Source"}]
    assert result["tool_calls"] == 1 and len(result["citations"]) == 1
    assert requests[0]["max_tool_calls"] == 2 and requests[0]["service_tier"] == "default"
    assert requests[0]["include"] == ["web_search_call.action.sources"]
    # Reserve max calls even when response reports only one. Never under-budget hidden search usage.
    assert ledger.summary()["known_estimated_cost_usd"] == "0.02696"
    assert ledger.summary()["modules"]["research"]["attempts"] == 1


def test_unknown_tools_and_unbounded_search_rejected_before_reservation(tmp_path):
    ledger = budget(tmp_path)
    for payload in ({"max_output_tokens": 1000, "tools": [{"type": "code_interpreter"}]},
                    {"max_output_tokens": 1000, "tools": [{"type": "web_search", "search_context_size": "low"}]},
                    {"max_output_tokens": 1000, "service_tier": "priority"}):
        with pytest.raises(ProviderError):
            ledger.reserve("gpt-4.1-mini", payload)
    assert ledger.summary()["attempts"] == 0


def test_cache_is_zero_only_for_no_request_hit_and_missing_modules_not_zero():
    result = summarize_usage([{"capability": "vision", "attempts": 0, "cache_status": "hit", "elapsed_ms": 2},
                              {"capability": "creative", "operation": "directions", "attempts": 1, "cache_status": "miss"}])
    assert result["vision"]["estimated_cost_usd"] == "0"
    assert result["creative"]["estimated_cost_usd"] is None
    assert result["production"]["status"] == "not_run" and result["production"]["estimated_cost_usd"] is None


def test_settings_from_env_uses_one_shared_ledger(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_ANATOMY_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VIDEO_EXPERIMENT_BUDGET_PATH", raising=False)
    assert ProviderSettings.from_env().budget_path == tmp_path / "provider-budget.sqlite3"
    assert replace(ProviderSettings.from_env(), m2_model="gpt-4.1-mini").budget_path == ProviderSettings.from_env().budget_path


def test_injected_non_mock_client_cannot_bypass_shared_cap(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_ANATOMY_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VIDEO_EXPERIMENT_BUDGET_PATH", raising=False)

    class NonNetworkClient:
        def post(self, *_args, **_kwargs):
            pytest.fail("An injected non-mock client bypassed the shared budget")

    settings = ProviderSettings(api_key="synthetic-test-key", experiment_max_usd="0.001", max_retries=0)
    with pytest.raises(ProviderError) as error:
        json_call(OpenAITransport(settings, client=NonNetworkClient()))
    assert error.value.code == "experiment_budget_exhausted"
    ledger = ExperimentBudget(tmp_path / "provider-budget.sqlite3", "3")
    assert ledger.summary()["maximum_usd"] == "0.001"
    assert ledger.summary()["attempts"] == 0
