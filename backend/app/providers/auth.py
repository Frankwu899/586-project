"""Safe credential diagnostics and a non-generating OpenAI connection check.

The models endpoint checks connectivity and credential/model visibility only.
It cannot establish permission to generate Responses or transcribe audio.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

from .base import ProviderError
from .config import ProviderSettings


@dataclass(frozen=True)
class ConnectionCheck:
    status: Literal["verified", "unverified", "rejected"]
    code: str
    message: str
    missing_models: tuple[str, ...] = ()
    endpoint_permissions_verified: bool = False


def normalize_api_key(value: str) -> str:
    """Trim paste whitespace, but never send a masked or malformed credential."""
    key = value.strip()
    if not key:
        raise ProviderError("provider_not_configured", "Add an OpenAI API key in API settings before analyzing a video.")
    if (not key.isascii() or any(char.isspace() or ord(char) < 33 or ord(char) > 126 for char in key)
            or "..." in key or "*" in key or key[:1] in {"\"", "'"} or key[-1:] in {"\"", "'"}):
        raise ProviderError("provider_key_format", "Paste the complete secret key in API settings, without quotes or a Bearer prefix. A masked key from the key list cannot be used.")
    return key


def provider_http_error(response: httpx.Response) -> ProviderError:
    """Map only status and allowlisted codes; never expose a raw provider body."""
    try:
        body = response.json()
        error = body.get("error", {}) if isinstance(body, dict) else {}
        code = error.get("code") if isinstance(error, dict) else None
        code = code if isinstance(code, str) else None
    except ValueError:
        code = None
    status = response.status_code
    if code == "unsupported_country_region_territory":
        return ProviderError("provider_region_restricted", "OpenAI reports that this region is not supported. Check the account's supported region and contact OpenAI support.")
    if code in {"organization_deactivated", "account_deactivated"}:
        return ProviderError("provider_account_disabled", "OpenAI reports that this account or organization is inactive. Check the account or contact OpenAI support.")
    if status == 401:
        return ProviderError("provider_authentication", "OpenAI rejected the API credential (HTTP 401). Replace it in API settings with a complete, active project secret key.")
    if code in {"insufficient_quota", "billing_hard_limit_reached"}:
        return ProviderError("provider_quota", "OpenAI reports insufficient credit or a billing limit. Check billing for the project that owns this API key.")
    if code == "model_not_found":
        return ProviderError("provider_model_access", "OpenAI could not find or allow access to the configured model. Check project model access and the selected model.")
    if status == 403:
        return ProviderError("provider_permission", "OpenAI denied this request (HTTP 403). Check this project's key permissions and model access; video analysis needs Responses and Audio Transcriptions access.")
    if 300 <= status < 400:
        return ProviderError("provider_unexpected_redirect", "The OpenAI connection returned an unexpected redirect. Check the network connection; the credential was not forwarded.")
    transient = status in (408, 409, 429) or status >= 500
    return ProviderError("provider_temporarily_unavailable" if transient else "provider_request_rejected",
                         "OpenAI is temporarily unavailable or rate limited; retry later." if transient
                         else "OpenAI rejected the configured model or request. Check model and API settings.", transient)


def provider_connection_error(error: httpx.TransportError) -> ProviderError:
    if isinstance(error, httpx.TimeoutException):
        return ProviderError("provider_timeout", "The OpenAI connection timed out. Check the network connection and try again.", True)
    return ProviderError("provider_network", "Could not connect securely to OpenAI. Check the network connection, proxy and certificate settings.", True)


def check_openai_connection(settings: ProviderSettings, *, client: httpx.Client | None = None) -> ConnectionCheck:
    """One GET, no media/model inference, no retries and no budget reservation.

    Restricted keys can permit inference but deny Models read. That is an
    unverified check, not evidence that the credential is invalid.
    """
    try:
        key = normalize_api_key(settings.api_key)
    except ProviderError as exc:
        return ConnectionCheck("rejected", exc.code, exc.message)
    owned = client is None
    client = client or httpx.Client(timeout=min(settings.timeout_seconds, 10), follow_redirects=False)
    try:
        try:
            response = client.get("https://api.openai.com/v1/models",
                                  headers={"Authorization": f"Bearer {key}"},
                                  timeout=min(settings.timeout_seconds, 10), follow_redirects=False)
        except httpx.TransportError as exc:
            error = provider_connection_error(exc)
            return ConnectionCheck("unverified", error.code, error.message)
        if response.status_code == 403:
            error = provider_http_error(response)
            if error.code == "provider_permission":
                return ConnectionCheck("unverified", "provider_models_permission",
                    "The Models check was denied (HTTP 403). This does not prove the key is invalid: a restricted key may allow Responses and Audio Transcriptions while denying Models read. Check key/project permissions.")
            return ConnectionCheck("rejected", error.code, error.message)
        if not 200 <= response.status_code < 300:
            error = provider_http_error(response)
            status = "rejected" if response.status_code == 401 else "unverified"
            return ConnectionCheck(status, error.code, error.message)
        try:
            body = response.json()
            entries = body.get("data") if isinstance(body, dict) else None
            if not isinstance(entries, list) or any(not isinstance(entry, dict) or not isinstance(entry.get("id"), str) for entry in entries):
                raise ValueError("invalid models response")
        except ValueError:
            return ConnectionCheck("unverified", "provider_invalid_json", "OpenAI returned an unreadable Models response. Connection permissions could not be checked.")
        visible = {entry["id"] for entry in entries}
        configured = {settings.structure_model, settings.research_model}
        for capability in ("vision", "transcription", "creative", "m2"):
            if getattr(settings, f"{capability}_provider") == "openai":
                configured.add(getattr(settings, f"{capability}_model"))
        missing = tuple(sorted(configured - visible))
        if missing:
            return ConnectionCheck("unverified", "provider_models_unverified",
                "OpenAI accepted the key, but some configured models were not listed. Check project model access. Responses and Audio Transcriptions permissions have not been tested.", missing)
        return ConnectionCheck("verified", "provider_connection_verified",
            "OpenAI accepted the key and listed the configured models. Responses and Audio Transcriptions permissions have not been tested. No analysis was run.")
    finally:
        if owned:
            client.close()
