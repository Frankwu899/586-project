"""Read-only local usage reporting. No reservations, spending cap or blocking gate."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import json

from .base import ProviderError
from .budget import PRICING_VERIFIED_ON, REJECTED_BEFORE_GENERATION, usage_estimate


def estimate_local_attempt(model, payload, response, *, failure_code=None):
    estimate, basis = None, "provider_usage_unknown"
    try:
        if response is None and failure_code in REJECTED_BEFORE_GENERATION:
            estimate, basis = Decimal(0), "http_auth_rejection_before_generation"
        elif response is not None and 0 <= (date.today() - PRICING_VERIFIED_ON).days <= 30:
            # Actual reported usage replaces the experiment's pre-request bound.
            # An unsupported model/usage or expired prices means unknown cost,
            # never a stopped request or an accounting pause.
            usage = response.get("usage", {})
            tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
            actual = {**payload, "_input_tokens_bound": tokens if type(tokens) is int else 0}
            estimate, basis = usage_estimate(model, actual, response)
        elif response is not None:
            basis = "pricing_needs_review_usage_retained"
    except (ProviderError, ValueError, TypeError, KeyError, OverflowError, InvalidOperation):
        estimate, basis = None, "unrecognized_usage_cost_unknown"
    return {"estimated_cost_usd": str(estimate) if estimate is not None else None,
            "estimate_basis": basis, "provider_billed_cost_usd": None}


def local_usage_summary(cache_dir):
    """Read existing sanitized transport logs without touching the old ledger."""
    attempts, unknown, unreadable = 0, 0, 0
    estimated = Decimal(0)
    available = True
    path = cache_dir / "usage.jsonl" if cache_dir else None
    try:
        if path and path.exists() and not path.is_file():
            available = False
        if path and path.is_file():
            with path.open(encoding="utf-8") as source:
                for line in source:
                    try:
                        record = json.loads(line)
                        count = record.get("attempts", 0)
                        if type(count) is not int or count < 0:
                            raise ValueError("invalid attempt count")
                        if not count:
                            continue
                        cost = record.get("known_estimated_cost_usd", record.get("estimated_cost_usd"))
                        value = Decimal(str(cost)) if cost is not None else Decimal(0)
                        missing = record.get("unknown_attempts", count if cost is None else 0)
                        if not value.is_finite() or value < 0 or type(missing) is not int or not 0 <= missing <= count:
                            raise ValueError("invalid usage totals")
                        attempts += count
                        unknown += missing
                        estimated += value
                    except (ValueError, TypeError, AttributeError, InvalidOperation):
                        unreadable += 1
    except (OSError, UnicodeError):
        available = False
    return {"mode": "usage_only", "enforced": False, "blocked": False,
            "maximum_usd": None, "remaining_usd": None,
            "known_estimated_cost_usd": str(estimated), "unknown_attempts": unknown,
            "attempts": attempts, "usage_records_available": available,
            "unreadable_records": unreadable, "provider_billed_cost_usd": None,
            "explanation": "No client-side spending cap. Recorded estimates are not your OpenAI account balance or invoice."}
