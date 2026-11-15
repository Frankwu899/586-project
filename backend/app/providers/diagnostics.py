"""Allowlisted operational metadata. Never retain provider messages or content."""
from __future__ import annotations

import math
import re

SAFE_CODES = frozenset({
    "unsupported_country_region_territory", "organization_deactivated", "account_deactivated",
    "invalid_api_key", "insufficient_permissions", "insufficient_quota", "billing_hard_limit_reached",
    "credit_balance_exhausted", "project_spend_limit_exceeded", "organization_spend_limit_exceeded",
    "organization_usage_limit_exceeded", "model_not_found", "rate_limit_exceeded", "slow_down",
    "server_is_overloaded", "invalid_request", "invalid_request_error", "server_error",
})
SAFE_TYPES = frozenset({"insufficient_quota", "invalid_request_error", "authentication_error",
    "permission_error", "rate_limit_error", "service_unavailable_error", "server_error"})
TEXT_FIELDS = frozenset({"application_version", "source_commit", "requested_model", "resolved_model",
    "provider", "capability", "operation", "stage", "project_id", "resource_id", "job_id", "task_id",
    "conversation_turn_id", "message_id", "analysis_id", "prompt_version", "schema_version", "preparation_version",
    "cache_status", "failure_code", "validation_outcome", "validation_rule", "validation_field",
    "started_at", "ended_at", "chunk_id", "source_sha256", "content_region_digest"})
NUMBER_FIELDS = frozenset({"http_status", "attempts", "elapsed_ms", "audio_seconds", "chunk_index",
    "chunk_start_seconds", "chunk_end_seconds", "chunk_start", "chunk_end", "retry_after_seconds",
    "completed_chunks", "total_chunks", "invalid_segments", "analysis_revision"})


def safe_diagnostics(values: dict | None) -> dict:
    """Only named scalars, bounded identifiers and known provider enums may leave."""
    result = {}
    for key, value in (values or {}).items():
        if key == "validation_rule" and isinstance(value, str) and re.fullmatch(r"[a-z0-9_,]{1,160}", value):
            result[key] = value
        elif key in TEXT_FIELDS and isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:/+\-\[\]]{1,160}", value) and not value.startswith("sk-"):
            result[key] = value
        elif key in NUMBER_FIELDS and type(value) in (int, float) and math.isfinite(value):
            result[key] = value
        elif key == "provider_code" and isinstance(value, str) and value in SAFE_CODES:
            result[key] = value
        elif key == "provider_type" and isinstance(value, str) and value in SAFE_TYPES:
            result[key] = value
        elif key == "provider_request_id" and isinstance(value, str) and re.fullmatch(r"req_[A-Za-z0-9_-]{1,120}", value):
            result[key] = value
    return result
