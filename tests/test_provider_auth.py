"""Offline provider connection checks; no real key or external requests."""
from dataclasses import asdict
import json

import httpx
import pytest

from backend.app.providers.auth import check_openai_connection, normalize_api_key, provider_http_error
from backend.app.providers.base import ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.providers.transport import OpenAITransport


def test_connection_check_is_one_bounded_read_without_media_budget_or_persisted_secret(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        assert str(request.url) == "https://api.openai.com/v1/models"
        assert request.headers["Authorization"] == "Bearer sk-offline-fixture"
        assert not request.content
        assert request.extensions["timeout"]["read"] == 10
        return httpx.Response(200, json={"data": [{"id": "gpt-6.1-sol"}, {"id": "gpt-6-luna"}, {"id": "whisper-1"}]})

    settings = ProviderSettings(api_key=" \tsk-offline-fixture\r\n", budget_path=tmp_path / "ledger.sqlite3", cache_dir=tmp_path / "cache")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = check_openai_connection(settings, client=client)
        assert not client.is_closed  # Only the creator closes an injected client.
    assert result.status == "verified" and result.endpoint_permissions_verified is False
    assert result.missing_models == ()
    assert "sk-offline-fixture" not in json.dumps(asdict(result))
    assert len(requests) == 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("key", ["", "sk-...abcd", "sk-••••abcd", "sk-***abcd", "Bearer sk-test", "'sk-test'", '"sk-test"', "sk-test\nextra", "sk-test\x00extra"])
def test_invalid_or_masked_key_is_rejected_before_network_or_budget(key, tmp_path):
    settings = ProviderSettings(api_key=key, budget_path=tmp_path / "ledger.sqlite3")
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected HTTP request"))) as client:
        result = check_openai_connection(settings, client=client)
        assert result.status == "rejected"
        assert result.code in {"provider_not_configured", "provider_key_format"}
        with pytest.raises(ProviderError):
            OpenAITransport(settings, client=client).json_response("gpt-4.1-mini", "text", {}, "test")
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("status,code,expected_status,expected_code", [
    (401, "invalid_api_key", "rejected", "provider_authentication"),
    (403, "insufficient_permissions", "unverified", "provider_models_permission"),
    (403, "unsupported_country_region_territory", "rejected", "provider_region_restricted"),
    (403, "organization_deactivated", "rejected", "provider_account_disabled"),
    (429, "insufficient_quota", "unverified", "provider_quota"),
    (429, "rate_limit_exceeded", "unverified", "provider_temporarily_unavailable"),
    (503, None, "unverified", "provider_temporarily_unavailable"),
])
def test_check_distinguishes_invalid_key_permission_quota_and_service_failure_without_raw_body(status, code, expected_status, expected_code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"code": code, "message": "sk-offline-private-body"}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = check_openai_connection(ProviderSettings(api_key="sk-offline-key"), client=client)
    assert (result.status, result.code) == (expected_status, expected_code)
    assert result.endpoint_permissions_verified is False
    assert "sk-offline" not in json.dumps(asdict(result))
    assert len(calls) == 1


def test_missing_model_is_warning_not_assertion_of_inference_permission():
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": [{"id": "gpt-6.1-sol"}, {"id": "gpt-6-luna"}]}))) as client:
        result = check_openai_connection(ProviderSettings(api_key="sk-fixture"), client=client)
    assert result.status == "unverified"
    assert result.code == "provider_models_unverified"
    assert result.missing_models == ("whisper-1",)
    assert result.endpoint_permissions_verified is False


@pytest.mark.parametrize("body", [[], {}, {"data": None}, {"data": ["wrong"]}, {"data": [{"id": 42}]}])
def test_models_response_shape_is_checked(body):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))) as client:
        result = check_openai_connection(ProviderSettings(api_key="sk-fixture"), client=client)
    assert result.status == "unverified" and result.code == "provider_invalid_json"


@pytest.mark.parametrize("exception,code", [(httpx.ReadTimeout, "provider_timeout"), (httpx.ConnectError, "provider_network")])
def test_connection_check_network_failure_is_safe_and_not_retried(exception, code):
    calls = []

    def handler(request):
        calls.append(request)
        raise exception("sk-private-network-detail", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = check_openai_connection(ProviderSettings(api_key="sk-fixture"), client=client)
    assert result.status == "unverified" and result.code == code
    assert len(calls) == 1 and "sk-private" not in result.message


def test_redirect_does_not_forward_credential_even_with_injected_redirecting_client():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "https://example.invalid/steal"})

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        result = check_openai_connection(ProviderSettings(api_key="sk-fixture"), client=client)
    assert result.code == "provider_unexpected_redirect"
    assert len(calls) == 1


def test_actual_generation_uses_normalized_key_and_differentiates_permission_failure():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer sk-fixture"
        return httpx.Response(403, json={"error": {"message": "raw private denied body"}})

    settings = ProviderSettings(api_key="\n sk-fixture \n", max_retries=3)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = OpenAITransport(settings, client=client)
        with pytest.raises(ProviderError) as exc:
            transport.json_response("gpt-4.1-mini", "text", {}, "test")
    assert exc.value.code == "provider_permission"
    assert "raw private" not in exc.value.message
    assert len(calls) == 1
    assert transport.records[0]["failure_code"] == "provider_permission"


@pytest.mark.parametrize("body", [[], {"error": []}, {"error": {"code": {"unexpected": "secret"}}}])
def test_malformed_error_body_never_leaks_or_breaks_safe_http_classification(body):
    error = provider_http_error(httpx.Response(401, json=body))
    assert error.code == "provider_authentication"
    assert "secret" not in error.message.replace("secret key", "credential")


def test_normalization_does_not_rewrite_the_key():
    assert normalize_api_key("  sk-test-with_hyphens123 \n") == "sk-test-with_hyphens123"
