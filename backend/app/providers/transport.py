"""Bounded OpenAI HTTP transport; no provider payload or credentials in logs."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import threading
from typing import Callable

import httpx

from .base import ProviderError
from .config import ProviderSettings

# Explicitly reviewed model families, not a claim that arbitrary GPT IDs share capabilities.
STRUCTURED_VISION_MODELS = frozenset({"gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini",
                                    "gpt-4.1-2025-04-14", "gpt-4.1-mini-2025-04-14", "gpt-4.1-nano-2025-04-14",
                                    "gpt-4o-2024-08-06", "gpt-4o-mini-2024-07-18"})
TIMESTAMP_MODELS = frozenset({"whisper-1"})
_REQUEST_SLOTS = threading.BoundedSemaphore(2)


def strict_schema(schema: dict) -> dict:
    """Project canonical Pydantic schemas onto OpenAI's supported strict subset.

    Cross-field conditionals/array uniqueness remain in the canonical schema and
    local domain validators. Sending them to OpenAI would reject the entire HTTP
    request; removing them here does not weaken acceptance of provider output.
    Schema property maps are traversed as maps, so legitimate field names such
    as ``default`` or ``contains`` are preserved.
    """
    result = json.loads(json.dumps(schema))
    unsupported = {"default", "allOf", "not", "dependentRequired", "dependentSchemas",
                   "if", "then", "else", "uniqueItems", "contains", "minContains", "maxContains"}

    def visit(value):
        if not isinstance(value, dict):
            return
        for key in unsupported:
            value.pop(key, None)
        if value.get("type") == "object" or "properties" in value:
            value["additionalProperties"] = False
            value["required"] = list(value.get("properties", {}))
        for key, child in value.items():
            if key in ("properties", "$defs", "definitions") and isinstance(child, dict):
                for property_schema in child.values():
                    visit(property_schema)
            elif isinstance(child, dict):
                visit(child)
            elif isinstance(child, list):
                for variant in child:
                    visit(variant)
    visit(result)
    return result


class OpenAITransport:
    def __init__(self, settings: ProviderSettings, *, client=None,
                 before_attempt: Callable[[str, dict], None] | None = None, sleep=time.sleep):
        self.settings = settings
        self.client = client
        self.before_attempt = before_attempt
        self.sleep = sleep
        self.records: list[dict] = []

    def _post(self, client, *args, **kwargs):
        if not _REQUEST_SLOTS.acquire(timeout=self.settings.timeout_seconds):
            raise ProviderError("provider_busy", "Provider request capacity is busy; retry later.", True)
        try:
            return client.post(*args, **kwargs)
        finally:
            _REQUEST_SLOTS.release()

    def _request(self, endpoint: str, model: str, payload: dict, *, metadata: dict | None = None,
                 audio_path: Path | None = None) -> dict:
        if not self.settings.api_key.strip():
            raise ProviderError("provider_not_configured", "Set OPENAI_API_KEY in the backend environment before using real analysis.")
        record = {"provider": "openai", "requested_model": model, "resolved_model": None,
                  "started_at": datetime.now(timezone.utc).isoformat(), "ended_at": None,
                  "elapsed_ms": None, "attempts": 0, "cache_status": "miss", "failure_code": None,
                  "usage": None, "usage_explanation": "Provider usage unavailable; cost is unknown, not zero.",
                  "cost_usd": None, **(metadata or {})}
        self.records.append(record)
        start = time.monotonic()
        owned = self.client is None
        client = self.client or httpx.Client(timeout=self.settings.timeout_seconds, follow_redirects=False)
        try:
            for attempt in range(self.settings.max_retries + 1):
                try:
                    if self.before_attempt:
                        budget_payload = payload if audio_path is None else {
                            "capability": "timestamped_transcription", "model": model,
                            "audio_bytes": audio_path.stat().st_size,
                            "audio_seconds": (metadata or {}).get("audio_seconds"),
                        }
                        self.before_attempt(model, budget_payload)
                    record["attempts"] += 1
                    headers = {"Authorization": f"Bearer {self.settings.api_key}"}
                    if audio_path is None:
                        response = self._post(client, "https://api.openai.com/v1/" + endpoint,
                                               headers=headers, json=payload, timeout=self.settings.timeout_seconds)
                    else:
                        with audio_path.open("rb") as audio:
                            response = self._post(client, "https://api.openai.com/v1/" + endpoint, headers=headers,
                                data=payload, files={"file": ("audio.wav", audio, "audio/wav")},
                                timeout=self.settings.timeout_seconds)
                    if response.status_code >= 400:
                        try:
                            code = response.json().get("error", {}).get("code")
                        except (ValueError, AttributeError):
                            code = None
                        if response.status_code in (401, 403):
                            raise ProviderError("provider_authentication", "Provider authentication failed; check the backend API key and account permissions.")
                        if code in ("insufficient_quota", "billing_hard_limit_reached"):
                            raise ProviderError("provider_quota", "Provider credit or billing quota is exhausted; check the provider account.")
                        transient = response.status_code in (408, 409, 429) or response.status_code >= 500
                        raise ProviderError("provider_temporarily_unavailable" if transient else "provider_request_rejected",
                                            "Provider request failed; retry later." if transient else "Provider rejected the configured model or request; check backend capability settings.", transient)
                    try:
                        data = response.json()
                        if not isinstance(data, dict):
                            raise ValueError("not object")
                    except ValueError as exc:
                        raise ProviderError("provider_invalid_json", "Provider returned malformed JSON; retry the analysis.") from exc
                    record["resolved_model"] = data.get("model")
                    usage = data.get("usage")
                    if isinstance(usage, dict):
                        record["usage"] = {key: {"value": value, "unit": "seconds" if key == "seconds" else "tokens"}
                                           for key, value in usage.items() if type(value) in (int, float)}
                        record["usage_explanation"] = "Usage for the successful response only; unsuccessful-attempt usage and billed cost are unknown."
                    return data
                except httpx.TransportError as exc:
                    error = ProviderError("provider_timeout" if isinstance(exc, httpx.TimeoutException) else "provider_network",
                                          "Provider request timed out or could not connect; retry later.", True)
                except ProviderError as exc:
                    error = exc
                if not error.retryable or attempt >= self.settings.max_retries:
                    record["failure_code"] = error.code
                    raise error
                self.sleep(min(2 ** attempt, 4))
        finally:
            record["ended_at"] = datetime.now(timezone.utc).isoformat()
            record["elapsed_ms"] = round((time.monotonic() - start) * 1000)
            if owned:
                client.close()
        raise AssertionError("bounded retry loop exhausted")

    def json_response(self, model: str, prompt: str, schema: dict, schema_name: str,
                      images=(), *, metadata: dict | None = None) -> dict:
        if model not in STRUCTURED_VISION_MODELS:
            raise ProviderError("unsupported_model_capability", "This model has not been configured for structured text/image responses; select a documented supported model.")
        content = [{"type": "input_text", "text": prompt}]
        for path in images:
            image_bytes = Path(path).read_bytes()
            if len(image_bytes) > 5 * 1024 * 1024:
                raise ProviderError("provider_input_too_large", "A prepared frame exceeds the provider input limit.")
            content.append({"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode(), "detail": "high"})
        payload = {"model": model, "input": [{"role": "user", "content": content}],
                   "max_output_tokens": self.settings.max_output_tokens, "store": False,
                   "text": {"format": {"type": "json_schema", "name": schema_name,
                                        "strict": True, "schema": strict_schema(schema)}}}
        data = self._request("responses", model, payload, metadata=metadata)
        try:
            if data.get("status") != "completed":
                raise ProviderError("provider_incomplete", "Provider response was incomplete; reduce the input or increase the bounded output limit.")
            texts = []
            for output in data.get("output", []):
                for item in output.get("content", []):
                    if item.get("type") == "refusal":
                        raise ProviderError("provider_refusal", "Provider declined this request; review the source material and task.")
                    if item.get("type") == "output_text":
                        texts.append(item.get("text", ""))
            result = json.loads("".join(texts))
            if not isinstance(result, dict):
                raise ValueError("not object")
            return result
        except (ValueError, TypeError, AttributeError) as exc:
            if isinstance(exc, ProviderError):
                self.records[-1]["failure_code"] = exc.code
                raise
            self.records[-1]["failure_code"] = "provider_invalid_json"
            raise ProviderError("provider_invalid_json", "Provider returned malformed structured output; retry the analysis.") from exc

    def transcribe(self, model: str, audio_path: Path, *, prompt: str = "", metadata=None) -> dict:
        if model not in TIMESTAMP_MODELS:
            raise ProviderError("unsupported_model_capability", "Timestamped transcription currently requires whisper-1; other speech models are not assumed to provide segment timing.")
        if audio_path.stat().st_size > 24 * 1024 * 1024:
            raise ProviderError("provider_input_too_large", "Prepared audio exceeds the supported upload limit; use shorter chunks.")
        payload = {"model": model, "response_format": "verbose_json", "timestamp_granularities[]": "segment"}
        if prompt:
            payload["prompt"] = prompt
        return self._request("audio/transcriptions", model, payload, metadata=metadata, audio_path=audio_path)
