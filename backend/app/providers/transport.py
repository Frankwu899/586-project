"""Bounded OpenAI HTTP transport; no provider payload or credentials in logs."""
from __future__ import annotations

import base64
from decimal import Decimal
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import threading
import fcntl
import sqlite3
from urllib.parse import urlsplit
from typing import Callable

import httpx

from .base import ProviderError
from .auth import normalize_api_key, provider_connection_error, provider_http_error
from .config import ProviderSettings
from .budget import ExperimentBudget, TEXT_MODELS, module_name

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
        self.budget = None
        self._thread_record = threading.local()

    def _experiment_budget(self):
        path = self.settings.budget_path
        is_mock_http = isinstance(getattr(self.client, "_transport", None), httpx.MockTransport)
        if path is None and not is_mock_http:
            # Directly constructed real transports still share the experiment
            # guard, including injected real/custom clients. Only an explicit
            # offline MockTransport may omit persistent accounting in unit tests.
            path = ProviderSettings.from_env().budget_path
        if self.budget is None and path is not None:
            self.budget = ExperimentBudget(path, self.settings.experiment_max_usd)
        return self.budget

    def _persist_usage(self, record):
        if self.settings.cache_dir is None:
            return
        try:
            self.settings.cache_dir.mkdir(parents=True, exist_ok=True)
            with (self.settings.cache_dir / "usage.jsonl").open("a", encoding="utf-8") as output:
                fcntl.flock(output.fileno(), fcntl.LOCK_EX)
                output.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                output.flush()
                fcntl.flock(output.fileno(), fcntl.LOCK_UN)
        except (OSError, ValueError):
            record["diagnostics_error"] = "usage_write_failed"

    def _post(self, client, *args, **kwargs):
        if not _REQUEST_SLOTS.acquire(timeout=self.settings.timeout_seconds):
            raise ProviderError("provider_busy", "Provider request capacity is busy; retry later.", True)
        try:
            return client.post(*args, **kwargs)
        finally:
            _REQUEST_SLOTS.release()

    def _request(self, endpoint: str, model: str, payload: dict, *, metadata: dict | None = None,
                 audio_path: Path | None = None) -> dict:
        api_key = normalize_api_key(self.settings.api_key)
        record = {"provider": "openai", "requested_model": model, "resolved_model": None,
                  "started_at": datetime.now(timezone.utc).isoformat(), "ended_at": None,
                  "elapsed_ms": None, "attempts": 0, "cache_status": "miss", "failure_code": None,
                  "usage": None, "usage_explanation": "Provider usage unavailable; cost is unknown, not zero.",
                  "cost_usd": None, "provider_billed_cost_usd": None,
                  "module": module_name(metadata), "attempt_records": [], **(metadata or {})}
        record["prepared_image_count"] = sum(item.get("type") == "input_image"
            for entry in payload.get("input", []) if isinstance(entry, dict)
            for item in entry.get("content", []) if isinstance(item, dict))
        self.records.append(record)
        self._thread_record.value = record
        start = time.monotonic()
        owned = self.client is None
        client = self.client or httpx.Client(timeout=self.settings.timeout_seconds, follow_redirects=False)
        try:
            for attempt in range(self.settings.max_retries + 1):
                attempt_started = time.monotonic()
                reservation_id = None
                attempt_response = None
                attempt_error = None
                error = None
                budget = None
                budget_payload = payload if audio_path is None else {
                    "capability": "timestamped_transcription", "model": model,
                    "audio_bytes": audio_path.stat().st_size,
                    "audio_seconds": (metadata or {}).get("audio_seconds"),
                }
                try:
                    if self.before_attempt:
                        self.before_attempt(model, budget_payload)
                    try:
                        budget = self._experiment_budget()
                        if budget is not None:
                            reservation_id = budget.reserve(model, budget_payload, metadata)
                    except (OSError, sqlite3.Error) as exc:
                        raise ProviderError("experiment_budget_unavailable", "The shared experiment ledger is unavailable; no paid request was sent.") from exc
                    record["attempts"] += 1
                    headers = {"Authorization": f"Bearer {api_key}"}
                    if audio_path is None:
                        response = self._post(client, "https://api.openai.com/v1/" + endpoint,
                                               headers=headers, json=payload, timeout=self.settings.timeout_seconds, follow_redirects=False)
                    else:
                        with audio_path.open("rb") as audio:
                            response = self._post(client, "https://api.openai.com/v1/" + endpoint, headers=headers,
                                data=payload, files={"file": ("audio.wav", audio, "audio/wav")},
                                timeout=self.settings.timeout_seconds, follow_redirects=False)
                    if response.status_code >= 300:
                        raise provider_http_error(response)
                    try:
                        data = response.json()
                        if not isinstance(data, dict):
                            raise ValueError("not object")
                    except ValueError as exc:
                        raise ProviderError("provider_invalid_json", "Provider returned malformed JSON; retry the analysis.") from exc
                    attempt_response = data
                    record["resolved_model"] = data.get("model")
                    usage = data.get("usage")
                    if isinstance(usage, dict):
                        record["usage"] = {key: {"value": value, "unit": "seconds" if key == "seconds" else "tokens"}
                                           for key, value in usage.items() if type(value) in (int, float)}
                        record["usage_explanation"] = "Usage for the successful response only; unsuccessful-attempt usage and billed cost are unknown."
                    return data
                except httpx.TransportError as exc:
                    error = provider_connection_error(exc)
                except ProviderError as exc:
                    error = exc
                finally:
                    attempt_error = error if attempt_response is None else None
                    if reservation_id is not None:
                        try:
                            settled = budget.finish(reservation_id, model, budget_payload, attempt_response,
                                elapsed_ms=round((time.monotonic() - attempt_started) * 1000),
                                failure_code=attempt_error.code if attempt_error else None)
                            record["attempt_records"].append(settled)
                            record["estimated_cost_usd"] = settled["estimated_cost_usd"]
                            record["estimate_basis"] = settled["estimate_basis"]
                        except (OSError, sqlite3.Error, ValueError):
                            # The already committed reservation stays held. Never
                            # send another request after a failed accounting write.
                            raise ProviderError("experiment_budget_unavailable", "The experiment reservation remains held; accounting could not be finalized.") from None
                if not error.retryable or attempt >= self.settings.max_retries:
                    record["failure_code"] = error.code
                    raise error
                self.sleep(min(2 ** attempt, 4))
        finally:
            record["ended_at"] = datetime.now(timezone.utc).isoformat()
            record["elapsed_ms"] = round((time.monotonic() - start) * 1000)
            settlements = record["attempt_records"]
            if settlements:
                record["known_estimated_cost_usd"] = str(sum((Decimal(item["estimated_cost_usd"]) for item in settlements
                    if item["estimated_cost_usd"] is not None), Decimal(0)))
                record["unknown_attempts"] = sum(item["estimated_cost_usd"] is None for item in settlements)
                record["estimated_cost_usd"] = record["known_estimated_cost_usd"] if not record["unknown_attempts"] else None
            self._persist_usage(record)
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
                   "max_output_tokens": self.settings.max_output_tokens, "store": False, "service_tier": "default",
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
                self._thread_record.value["failure_code"] = exc.code
                raise
            self._thread_record.value["failure_code"] = "provider_invalid_json"
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

    def web_search(self, model: str, prompt: str, *, max_tool_calls=2, metadata=None) -> dict:
        """Bounded hosted search. Returned URLs are provenance, never fetched locally."""
        if model not in TEXT_MODELS or type(max_tool_calls) is not int or not 1 <= max_tool_calls <= 3:
            raise ProviderError("unsupported_research_configuration", "Select the reviewed research model and a bounded search-call count.")
        if len(prompt.encode("utf-8")) > 100_000:
            raise ProviderError("provider_input_too_large", "Research context exceeds the bounded input limit.")
        payload = {"model": model, "input": prompt, "store": False, "service_tier": "default",
                   "max_output_tokens": min(self.settings.max_output_tokens, 4000),
                   "tools": [{"type": "web_search", "search_context_size": "low"}],
                   "max_tool_calls": max_tool_calls, "tool_choice": "required",
                   "include": ["web_search_call.action.sources"]}
        data = self._request("responses", model, payload, metadata=metadata or {"capability": "research"})
        if data.get("status") != "completed":
            raise ProviderError("provider_incomplete", "Background research ended before a complete response was available.")
        texts, sources, citations = [], {}, []
        calls = 0

        def valid_url(value):
            if not isinstance(value, str) or len(value) > 4096:
                return False
            try:
                parts = urlsplit(value)
                return parts.scheme in {"https", "http"} and bool(parts.hostname) and not parts.username and not parts.password
            except ValueError:
                return False

        for item in data.get("output", []):
            if item.get("type") == "web_search_call":
                calls += 1
                for source in item.get("action", {}).get("sources", []):
                    url = source.get("url")
                    if valid_url(url):
                        sources[url] = {"url": url, "title": str(source.get("title", ""))[:1000]}
            for content in item.get("content", []):
                if content.get("type") == "refusal":
                    raise ProviderError("provider_refusal", "The provider declined background research.")
                if content.get("type") == "output_text":
                    texts.append(str(content.get("text", "")))
                    for annotation in content.get("annotations", []):
                        if annotation.get("type") == "url_citation" and valid_url(annotation.get("url")):
                            citation = {key: annotation.get(key) for key in ("url", "title", "start_index", "end_index")}
                            citations.append(citation)
                            sources.setdefault(citation["url"], {"url": citation["url"], "title": str(citation.get("title") or "")[:1000]})
        if calls > max_tool_calls:
            raise ProviderError("provider_tool_limit", "Research exceeded the requested tool limit; no further research was started.")
        if not texts or not sources:
            raise ProviderError("research_no_sources", "No usable cited background was returned; the video-only analysis is retained.")
        return {"text": "\n".join(texts), "sources": list(sources.values()), "citations": citations, "tool_calls": calls}
