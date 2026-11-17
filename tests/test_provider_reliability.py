"""Injected HTTP failures only: no live provider access or recognition claims."""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
import time

import httpx
import pytest

from backend.app.providers.auth import provider_http_error, retry_after
from backend.app.providers.base import ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.providers.transport import OpenAITransport


def response_body(text='{"reply":"Private result"}'):
    return {"status": "completed", "output": [{"content": [{"type": "output_text", "text": text}]}]}


def make_transport(tmp_path, handler, *, retries=2, timeout=45, sleep=lambda _: None):
    return OpenAITransport(ProviderSettings(api_key="sk-offline-fixture", max_retries=retries,
        experiment_budget_enabled=False, cache_dir=tmp_path, timeout_seconds=timeout),
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleep)


def call(transport, **metadata):
    return transport.json_response("gpt-6.1-sol", "Private prompt", {}, "test", metadata=metadata)


@pytest.mark.parametrize("code,expected,action", [
    ("credit_balance_exhausted", "provider_credit_balance_exhausted", "billing"),
    ("project_spend_limit_exceeded", "provider_project_spend_limit", "project"),
    ("organization_spend_limit_exceeded", "provider_organization_spend_limit", "organization"),
    ("organization_usage_limit_exceeded", "provider_organization_usage_limit", "usage"),
])
@pytest.mark.parametrize("operation", ["chat", "transcription"])
def test_billing_failures_are_actionable_and_never_automatically_retried(tmp_path, code, expected, action, operation):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"x-request-id": "req_billing", "Retry-After": "1"},
            json={"error": {"code": code, "type": "insufficient_quota", "message": "Private billing text"}})
    transport = make_transport(tmp_path, handler)
    with pytest.raises(ProviderError) as exc:
        if operation == "chat":
            call(transport)
        else:
            path = tmp_path / "fixture.wav"
            path.write_bytes(b"injected transport fixture, not prepared media")
            transport.transcribe("whisper-1", path)
    assert exc.value.code == expected and action in exc.value.message
    assert len(calls) == 1 and not exc.value.retryable
    assert exc.value.diagnostics["provider_code"] == code
    assert exc.value.diagnostics["provider_request_id"] == "req_billing"
    assert exc.value.diagnostics["attempts"] == 1
    assert "elapsed_ms" in exc.value.diagnostics
    assert "Private billing" not in json.dumps(exc.value.diagnostics)


@pytest.mark.parametrize("body,expected,retryable", [
    (None, "provider_temporarily_unavailable", True),
    ({"error": []}, "provider_temporarily_unavailable", True),
    ({"error": {"code": {"private": "secret"}, "type": []}}, "provider_temporarily_unavailable", True),
    ({"error": {"type": "insufficient_quota"}}, "provider_quota", False),
    ({"error": {"code": "unknown_private_code", "type": "rate_limit_error"}}, "provider_rate_limit", True),
])
def test_429_requires_safe_fields_to_distinguish_cause(body, expected, retryable):
    result = provider_http_error(httpx.Response(429, json=body, headers={"x-request-id": "sk-private-secret"}))
    assert (result.code, result.retryable) == (expected, retryable)
    assert "private" not in json.dumps(result.diagnostics)


def test_retry_after_is_respected_and_long_delay_is_deferred(tmp_path):
    calls, sleeps = [], []
    def handler(_):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "7.5"}, json={"error": {"code": "slow_down"}})
        return httpx.Response(200, json=response_body())
    # The per-request timeout does not shorten a server-mandated retry delay.
    transport = make_transport(tmp_path, handler, sleep=sleeps.append, timeout=1)
    call(transport)
    assert len(calls) == 2 and sleeps == [7.5]
    long_wait = make_transport(tmp_path, lambda _: httpx.Response(503, headers={"Retry-After": "120"}), sleep=sleeps.append)
    with pytest.raises(ProviderError) as exc:
        call(long_wait)
    assert long_wait.records[-1]["attempts"] == 1 and sleeps == [7.5]
    assert exc.value.diagnostics["retry_after_seconds"] == 120


def test_retry_after_does_not_retry_early_when_run_deadline_is_short(tmp_path):
    transport = make_transport(tmp_path, lambda _: httpx.Response(429, headers={"Retry-After": "20"}),
                               sleep=lambda _: pytest.fail("must not sleep then retry early"))
    with pytest.raises(ProviderError):
        call(transport, _deadline=time.monotonic() + 5)
    assert transport.records[-1]["attempts"] == 1


def test_retry_after_accepts_http_date_and_ignores_malformed_values():
    future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=30), usegmt=True)
    assert 28 <= retry_after(httpx.Response(503, headers={"Retry-After": future})) <= 30
    for value in ("nan", "inf", "-1", "private secret", "x" * 200):
        assert retry_after(httpx.Response(503, headers={"Retry-After": value})) is None


@pytest.mark.parametrize("body,code", [
    (response_body("not JSON private text"), "provider_invalid_json"),
    ({"status": "incomplete", "output": []}, "provider_incomplete"),
    ({"status": "completed", "output": [{"content": [{"type": "refusal", "refusal": "Private refusal"}]}]}, "provider_refusal"),
    ({"status": "completed", "output": [None]}, "provider_invalid_json"),
])
def test_final_output_validation_is_persisted_after_successful_http(tmp_path, body, code):
    transport = make_transport(tmp_path, lambda _: httpx.Response(200, json=body, headers={"x-request-id": "req_output"}))
    with pytest.raises(ProviderError) as exc:
        call(transport, project_id="project_fixture", conversation_turn_id="message_fixture", prompt="Private metadata")
    record = json.loads((tmp_path / "validation.jsonl").read_text().splitlines()[-1])
    assert record["failure_code"] == code and record["validation_outcome"] == "rejected"
    assert record["http_status"] == 200 and record["provider_request_id"] == "req_output"
    assert record["project_id"] == "project_fixture" and record["conversation_turn_id"] == "message_fixture"
    assert record["application_version"] == "1.8.3" and len(record["source_commit"]) == 40
    assert exc.value.diagnostics == record
    assert "Private" not in (tmp_path / "validation.jsonl").read_text()
    assert "Private" not in (tmp_path / "usage.jsonl").read_text()
    assert len((tmp_path / "usage.jsonl").read_text().splitlines()) == 1


def test_domain_validation_hook_preserves_failure_rule_without_double_counting_usage(tmp_path):
    transport = make_transport(tmp_path, lambda _: httpx.Response(200, json=response_body()))
    call(transport)
    transport.validation_result("partial", code="conversation_grounding", rule="source_excerpt", field="proposals[1].excerpt")
    record = json.loads((tmp_path / "validation.jsonl").read_text().splitlines()[-1])
    assert record["validation_rule"] == "source_excerpt"
    assert record["validation_field"] == "proposals[1].excerpt"
    assert record["validation_outcome"] == "partial"
    assert len((tmp_path / "usage.jsonl").read_text().splitlines()) == 1
