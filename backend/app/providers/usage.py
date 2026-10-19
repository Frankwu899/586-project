"""Comparable per-module diagnostics, with explicit unknowns and no quality score."""
from decimal import Decimal

from .budget import module_name

MODULES = ("m2", "vision", "speech", "creative", "refinement", "production", "structure", "research")


def summarize_usage(records):
    groups = {name: [] for name in MODULES}
    for record in records:
        groups.setdefault(record.get("module") or module_name(record), []).append(record)
    result = {}
    for name, items in groups.items():
        attempts = sum(row.get("attempts", 0) for row in items)
        cached = sum(row.get("cache_status") == "hit" for row in items)
        unknown, estimates = 0, Decimal(0)
        for row in items:
            if row.get("attempts", 0) == 0 and row.get("cache_status") in {"hit", "skipped_no_audio"}:
                continue  # Only a proven no-request result is zero incremental API cost.
            if row.get("attempt_records"):
                for entry in row["attempt_records"]:
                    if entry.get("estimated_cost_usd") is None:
                        unknown += 1
                    else:
                        estimates += Decimal(entry["estimated_cost_usd"])
            else:
                unknown += row.get("attempts", 0)
        def tokens(key):
            values = [row.get("usage", {}).get(key, {}).get("value") for row in items if isinstance(row.get("usage"), dict)]
            return sum(value for value in values if type(value) in (int, float)) if values else None
        result[name] = {"status": "measured" if items else "not_run", "requests": len(items),
            "attempts": attempts, "cache_hits": cached, "unknown_attempts": unknown,
            "input_tokens": tokens("input_tokens"), "output_tokens": tokens("output_tokens"),
            "audio_seconds_submitted": sum(row.get("audio_seconds", 0) * row.get("attempts", 0) for row in items),
            "images_submitted": sum(row.get("prepared_image_count", 0) * row.get("attempts", 0) for row in items),
            "elapsed_ms": sum(row.get("elapsed_ms", 0) or 0 for row in items),
            "known_estimated_cost_usd": str(estimates) if items else None,
            "estimated_cost_usd": str(estimates) if items and not unknown else None,
            "provider_billed_cost_usd": None, "failures": [row["failure_code"] for row in items if row.get("failure_code")],
            "quality_status": "not_human_reviewed", "quality_score": None}
    return result
