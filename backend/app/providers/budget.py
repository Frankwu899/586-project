"""Shared pre-request experiment budget. No provider invoice is inferred.

Prices and model limits were checked against official OpenAI pages on 2026-10-19.
Unknown attempts keep their reservation; known usage settles at undiscounted rates.
SQLite BEGIN IMMEDIATE serializes reservations across threads and processes.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .base import ProviderError
from .catalog import GPT6_MODELS, GPT6_PRICES

PRICING_VERIFIED_ON = date(2026, 10, 19)
PRICING_SOURCES = [
    "https://developers.openai.com/api/docs/models/gpt-4.1-mini",
    "https://developers.openai.com/api/docs/models/whisper-1",
    "https://developers.openai.com/api/docs/pricing",
    "https://developers.openai.com/api/docs/models/gpt-6.1-sol",
    "https://developers.openai.com/api/docs/models/gpt-6-luna",
    "https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count",
]
TEXT_MODELS = frozenset({"gpt-4.1-mini", "gpt-4.1-mini-2025-04-14"}) | GPT6_MODELS
CONTEXT_TOKENS = 1_047_576
INPUT_RATE = Decimal("0.40") / 1_000_000
OUTPUT_RATE = Decimal("1.60") / 1_000_000
AUDIO_MINUTE_RATE = Decimal("0.006")
SEARCH_CALL_RATE = Decimal("0.01")
SEARCH_CONTENT_TOKENS = 8000
MAXIMUM_USD = Decimal("3")
UNITS_PER_USD = Decimal(1_000_000_000)  # exact integer accounting, never binary floats
REJECTED_BEFORE_GENERATION = frozenset({"provider_authentication", "provider_permission"})


def _number(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Budget values must be finite positive decimals") from None
    if not result.is_finite() or result <= 0:
        raise ValueError("Budget values must be finite positive decimals")
    return result


def _units(value):
    return int((value * UNITS_PER_USD).to_integral_value(rounding=ROUND_CEILING))


def _usd(units):
    return str(Decimal(units) / UNITS_PER_USD)


def module_name(metadata):
    capability = (metadata or {}).get("capability", "unknown")
    operation = (metadata or {}).get("operation", "")
    if capability == "creative":
        return {"directions": "creative", "refine": "refinement", "production": "production"}.get(operation, operation or "creative")
    if capability == "structure" and operation == "research":
        return "research"
    return {"timestamped_transcription": "speech", "m2_assistance": "m2"}.get(capability, capability)


def estimate_upper_bound(model, payload):
    if model == "whisper-1" and payload.get("capability") == "timestamped_transcription":
        duration = _number(payload.get("audio_seconds"))
        size = payload.get("audio_bytes")
        if duration > 120 or type(size) is not int or not 0 < size <= 24 * 1024 * 1024:
            raise ProviderError("experiment_input_limit", "Audio exceeds the reviewed experiment limits.")
        return (duration / 60).to_integral_value(rounding=ROUND_CEILING) * AUDIO_MINUTE_RATE
    if model not in TEXT_MODELS:
        raise ProviderError("experiment_cost_bound_missing", "This model has no reviewed experiment cost bound.")
    output = payload.get("max_output_tokens")
    if type(output) is not int or not 1 <= output <= 16000:
        raise ProviderError("experiment_output_limit", "Every paid experiment request needs a bounded output limit.")
    tools = payload.get("tools", [])
    calls = 0
    if tools:
        if tools != [{"type": "web_search", "search_context_size": "low"}]:
            raise ProviderError("experiment_cost_bound_missing", "This tool configuration has no reviewed cost bound.")
        calls = payload.get("max_tool_calls")
        if type(calls) is not int or not 1 <= calls <= 3:
            raise ProviderError("experiment_tool_limit", "Research needs a bounded maximum of one to three search calls.")
    if payload.get("service_tier", "default") != "default":
        raise ProviderError("experiment_cost_bound_missing", "Only standard service pricing is reviewed.")
    if model in GPT6_MODELS:
        price = GPT6_PRICES[model]
        if calls:
            # Hosted search has no documented hard retrieved-token limit.
            # Reserve each possible full context, including cache-write and long
            # context premiums; the smaller retrieval model keeps this affordable.
            tokens = price.context_tokens * (calls + 1)
            return (tokens * price.cache_write_per_million * 2 + output * price.output_per_million * Decimal("1.5")) / 1_000_000 + calls * SEARCH_CALL_RATE
        tokens = payload.get("_input_tokens_bound")
        if type(tokens) is not int or not 0 < tokens <= price.long_context_threshold:
            raise ProviderError("experiment_input_limit", "The request needs a verified input token count within the reviewed short-context limit; no generation was sent.")
        return (tokens * price.cache_write_per_million + output * price.output_per_million) / 1_000_000
    # Reserve one whole context per possible tool/model turn. This covers images,
    # all prompt/schema bytes, and hidden retrieved context without a tokenizer guess.
    # Additional fixed search content blocks deliberately over-reserve potential overlap.
    return (CONTEXT_TOKENS * (calls + 1) + SEARCH_CONTENT_TOKENS * calls) * INPUT_RATE + output * OUTPUT_RATE + calls * SEARCH_CALL_RATE


def usage_estimate(model, payload, response):
    """Undiscounted estimate; None means keep the entire reservation."""
    resolved = response.get("model", model)
    if model == "whisper-1":
        # Duration of the submitted audio is measured locally; verbose_json often
        # has no usage object. Never call this provider-reported token usage.
        return estimate_upper_bound(model, payload), "measured_audio_rounded_up_to_minutes"
    if model not in TEXT_MODELS or resolved not in TEXT_MODELS:
        return None, "unknown_model_or_usage"
    if response.get("service_tier", "default") != "default":
        return None, "unexpected_service_tier"
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None, "unknown_usage"
    input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
    if any(type(value) is not int or value < 0 for value in (input_tokens, output_tokens)):
        return None, "unknown_usage"
    calls = payload.get("max_tool_calls", 0) if payload.get("tools") else 0
    if sum(item.get("type") == "web_search_call" for item in response.get("output", []) if isinstance(item, dict)) > calls:
        return None, "provider_tool_limit"
    if model in GPT6_MODELS:
        if resolved != model:
            return None, "unknown_model_or_usage"
        price = GPT6_PRICES[model]
        bound = price.context_tokens * (calls + 1) if calls else payload.get("_input_tokens_bound", 0)
        if input_tokens > bound or output_tokens > payload["max_output_tokens"]:
            return None, "usage_exceeds_reviewed_bound"
        # Count cache writes at the documented premium. Missing cache details
        # conservatively use that premium for every input token, never a discount.
        details = usage.get("input_tokens_details")
        writes = details.get("cache_write_tokens") if isinstance(details, dict) else None
        writes = writes if type(writes) is int and 0 <= writes <= input_tokens else input_tokens
        input_cost = (input_tokens - writes) * price.input_per_million + writes * price.cache_write_per_million
        long_context = bool(calls) or input_tokens > price.long_context_threshold
        cost = (input_cost * (2 if long_context else 1) + output_tokens * price.output_per_million * (Decimal("1.5") if long_context else 1)) / 1_000_000
        return cost + calls * SEARCH_CALL_RATE, "provider_tokens_with_cache_write_and_maximum_search_bound"
    if input_tokens > CONTEXT_TOKENS * (calls + 1) or output_tokens > payload["max_output_tokens"]:
        return None, "usage_exceeds_reviewed_bound"
    # No prompt-cache discount and no assumption that a missing search event was free.
    estimate = (input_tokens + SEARCH_CONTENT_TOKENS * calls) * INPUT_RATE + output_tokens * OUTPUT_RATE + calls * SEARCH_CALL_RATE
    return estimate, "provider_tokens_full_input_rate_plus_maximum_search_cost"


class ExperimentBudget:
    def __init__(self, path: Path, maximum="3", *, today=None):
        maximum = _number(maximum)
        if maximum > MAXIMUM_USD:
            raise ValueError("The authorized experiment budget cannot exceed USD 3")
        current = today or date.today()
        if not 0 <= (current - PRICING_VERIFIED_ON).days <= 30:
            raise ProviderError("experiment_pricing_stale", "Recheck official model and search pricing before further paid experiments.")
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.maximum = _units(maximum)
        with self._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY CHECK(id=1), maximum INTEGER NOT NULL, blocked INTEGER NOT NULL DEFAULT 0)")
            db.execute("INSERT OR IGNORE INTO budget(id, maximum) VALUES(1, ?)", (self.maximum,))
            # A new process may tighten, but never silently enlarge, an existing cap.
            db.execute("UPDATE budget SET maximum=min(maximum, ?) WHERE id=1", (self.maximum,))
            db.execute("""CREATE TABLE IF NOT EXISTS attempts (
                id TEXT PRIMARY KEY, module TEXT NOT NULL, model TEXT NOT NULL,
                reserved INTEGER NOT NULL, held INTEGER NOT NULL, estimated INTEGER,
                status TEXT NOT NULL, basis TEXT, usage TEXT, elapsed_ms INTEGER,
                failure_code TEXT, created_at TEXT NOT NULL)""")

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=20, isolation_level=None)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def reserve(self, model, payload, metadata=None):
        amount = _units(estimate_upper_bound(model, payload))
        request_id = uuid4().hex
        with self._transaction() as db:
            limit = db.execute("SELECT maximum, blocked FROM budget WHERE id=1").fetchone()
            held = db.execute("SELECT coalesce(sum(held),0) FROM attempts").fetchone()[0]
            if limit["blocked"] or held + amount > limit["maximum"]:
                raise ProviderError("experiment_budget_exhausted", "The local API budget cannot cover this request. Open API settings to see estimated usage and unresolved reservations. Saved work is retained; this is not your OpenAI account balance.")
            db.execute("INSERT INTO attempts(id,module,model,reserved,held,status,created_at) VALUES(?,?,?,?,?,'reserved',?)",
                       (request_id, module_name(metadata), model, amount, amount, datetime.now(timezone.utc).isoformat()))
        return request_id

    def finish(self, request_id, model, payload, response=None, *, elapsed_ms=0, failure_code=None, request_sent=True):
        estimate, basis = usage_estimate(model, payload, response) if response is not None else (None, "unknown_attempt_usage_reservation_retained")
        if response is None and failure_code in REJECTED_BEFORE_GENERATION:
            estimate, basis = Decimal(0), "http_auth_rejection_before_generation"
        if not request_sent and response is None:
            estimate, basis = Decimal(0), "generation_request_not_sent"
        with self._transaction() as db:
            row = db.execute("SELECT * FROM attempts WHERE id=?", (request_id,)).fetchone()
            if row is None or row["status"] != "reserved":
                raise ValueError("Unknown or already finalized budget reservation")
            estimated = _units(estimate) if estimate is not None else None
            held = estimated if estimated is not None and estimated <= row["reserved"] else row["reserved"]
            if basis in {"usage_exceeds_reviewed_bound", "unexpected_service_tier", "provider_tool_limit"}:
                db.execute("UPDATE budget SET blocked=1 WHERE id=1")
            if estimated is not None and estimated > row["reserved"]:
                db.execute("UPDATE budget SET blocked=1 WHERE id=1")
                held = estimated  # retain the anomaly, never hide it behind the cap
            usage = response.get("usage") if response is not None else None
            db.execute("UPDATE attempts SET held=?,estimated=?,status=?,basis=?,usage=?,elapsed_ms=?,failure_code=? WHERE id=?",
                       (held, estimated, "estimated" if estimated is not None else "unknown", basis,
                        json.dumps(usage) if isinstance(usage, dict) else None, elapsed_ms, failure_code, request_id))
        return {"reservation_id": request_id, "reserved_upper_bound_usd": _usd(row["reserved"]),
                "held_usd": _usd(held), "estimated_cost_usd": _usd(estimated) if estimated is not None else None,
                "estimate_basis": basis, "provider_billed_cost_usd": None}

    def reconcile_rejected_attempts(self):
        """Release only old explicit HTTP 401/403 refusals, never unknown failures.

        Keep the original reservation and failure code for audit. The caller can
        offer this as a recovery action; this never resets or enlarges the cap.
        """
        with self._transaction() as db:
            rows = db.execute("SELECT id, held FROM attempts WHERE status='unknown' AND failure_code IN (?, ?)",
                              tuple(sorted(REJECTED_BEFORE_GENERATION))).fetchall()
            for row in rows:
                db.execute("UPDATE attempts SET held=0,estimated=0,status='estimated',basis='http_auth_rejection_before_generation' WHERE id=?", (row["id"],))
        return {"reconciled_attempts": len(rows), "released_usd": _usd(sum(row["held"] for row in rows))}

    def summary(self):
        with self._transaction() as db:
            limit = db.execute("SELECT maximum, blocked FROM budget WHERE id=1").fetchone()
            rows = db.execute("SELECT * FROM attempts ORDER BY created_at, id").fetchall()
        modules = {}
        for row in rows:
            module = modules.setdefault(row["module"], {"attempts": 0, "unknown_attempts": 0, "held_units": 0, "estimated_units": 0, "elapsed_ms": 0})
            module["attempts"] += 1
            module["unknown_attempts"] += row["estimated"] is None
            module["held_units"] += row["held"]
            module["estimated_units"] += row["estimated"] or 0
            module["elapsed_ms"] += row["elapsed_ms"] or 0
        for module in modules.values():
            module["held_usd"] = _usd(module.pop("held_units"))
            module["known_estimated_cost_usd"] = _usd(module.pop("estimated_units"))
        held = sum(row["held"] for row in rows)
        return {"maximum_usd": _usd(limit["maximum"]), "held_usd": _usd(held),
                "remaining_usd": _usd(max(0, limit["maximum"] - held)),
                "reserved_upper_bound_usd": _usd(sum(row["reserved"] for row in rows)),
                "known_estimated_cost_usd": _usd(sum(row["estimated"] or 0 for row in rows)),
                "unknown_attempts": sum(row["estimated"] is None for row in rows), "attempts": len(rows),
                "recoverable_rejected_attempts": sum(row["status"] == "unknown" and row["failure_code"] in REJECTED_BEFORE_GENERATION for row in rows),
                "unresolved_reserved_usd": _usd(sum(row["held"] for row in rows if row["estimated"] is None)),
                "blocked": bool(limit["blocked"]), "modules": modules, "provider_billed_cost_usd": None,
                "pricing_verified_on": PRICING_VERIFIED_ON.isoformat(), "pricing_sources": PRICING_SOURCES,
                "explanation": "One shared USD 3 application experiment cap. Held includes estimated undiscounted usage and unresolved reservations; cumulative reservations are not spend. Provider invoice and activity outside this ledger are unknown."}
