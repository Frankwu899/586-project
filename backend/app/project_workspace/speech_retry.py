"""Conservative recovery of missing channels without replacing user corrections."""
from __future__ import annotations

import re

from ..providers.base import ProviderError
from ..workflow_errors import WorkflowError
from .models import EvidenceRevision

FAILED = {"failed", "partial", "error", "not_analyzed"}
CHANNELS = {"visual_action": "visual", "visual": "visual", "on_screen_text": "on_screen_text",
            "speech": "speech", "music": "sound", "sfx": "sound"}
_CONFLICT_PREFIX = "Recovery needs review:"

_MESSAGES = {
    "provider_quota": "The provider reports insufficient credit or a billing limit. Check billing for the project that owns this key.",
    "provider_credit_balance_exhausted": "The account has insufficient API credit. Check its API billing balance before retrying.",
    "provider_project_spend_limit": "The API project's spend limit was reached. Check the relevant project limit before retrying.",
    "provider_organization_spend_limit": "The organization's spend limit was reached. Check the relevant organization limit before retrying.",
    "provider_organization_usage_limit": "The organization's usage limit was reached. Check the relevant organization limit before retrying.",
    "provider_authentication": "The service rejected the API key. Check the saved key in Settings.",
    "provider_key_format": "Paste the complete API key in Settings without quotes or a Bearer prefix.",
    "provider_permission": "The key lacks permission for this request. Check model and Audio Transcriptions access.",
    "provider_model_access": "The configured model is unavailable to this key. Check project model access.",
    "provider_temporarily_unavailable": "The service could not accept this request. Wait before retrying; if it persists, check account limits in Settings.",
    "provider_rate_limit": "Requests are temporarily throttled. Wait before retrying.",
    "provider_busy": "The service is temporarily busy. Try again shortly.",
    "provider_timeout": "The service took too long to respond. Check the connection and retry.",
    "provider_network": "The service could not be reached. Check your network, proxy and certificate settings.",
    "provider_invalid_output": "The response could not be read as valid evidence. Retry this operation.",
    "provider_invalid_json": "The response could not be read as valid evidence. Retry this operation.",
    "missing_prepared_audio": "The audio track could not be prepared. Rebuild the media preview and retry transcription.",
    "audio_preparation_invalid": "Prepared audio failed sample or duration validation. Rebuild the media preview and retry transcription.",
    "media_preparation_failed": "Media preparation failed before transcription. Check the original file and FFmpeg, then rebuild the preview.",
    "audio_timestamps_missing": "Transcription returned text without usable timestamps. Retry the affected chunk; saved evidence is retained.",
    "audio_timestamps_invalid": "Some transcription timestamps are invalid. Valid segments are retained; retry missing coverage.",
    "unsupported_model_capability": "The configured transcription engine cannot supply the required timestamps. Check Settings.",
}


def public_failure(error):
    """Only known application prose and sanitized codes leave provider boundaries."""
    code = getattr(error, "code", "processing_failed")
    code = code if isinstance(code, str) and re.fullmatch(r"[a-z_]{1,80}", code) else "processing_failed"
    if isinstance(error, WorkflowError):
        return code, error.message
    if isinstance(error, ProviderError):
        return code, _MESSAGES.get(code, "The service could not complete this request. Check Settings and retry; saved work is retained.")
    return code, "This operation could not finish. Saved work is retained; retry it."


def missing_speech_only(evidence):
    return (evidence is not None and evidence.coverage.get("speech") in FAILED
            and not any(value in {"failed", "partial", "error"}
                        for channel, value in evidence.coverage.items() if channel != "speech"))


def merge_retry(previous: EvidenceRevision, incoming: EvidenceRevision, *, speech_only=False):
    """Keep exact saved event IDs/text/timing; add recovered uncovered intervals.

    Legacy corrections do not identify every edited field, so existing events
    are authoritative. A newly recognized span overlapping retained evidence is
    not allowed to replace it. Historical machine output remains separately saved.
    """
    result = incoming.model_copy(deep=True)
    retried = {"speech"} if speech_only else {
        key for key, value in previous.coverage.items() if value in FAILED and key not in {"music", "sfx"}}
    kinds = {CHANNELS[key] for key in retried if key in CHANNELS}
    kept = [event.model_copy(deep=True) for event in previous.events]
    used_ids = {event.id for event in kept}
    conflicts = {}
    for event in incoming.events:
        if event.kind not in kinds:
            continue
        overlapping = [old for old in previous.events if old.kind == event.kind
                       and old.start_seconds < event.end_seconds and event.start_seconds < old.end_seconds]
        if overlapping:
            # Never split words by proportional timing. A span extending beyond
            # the retained union has unmerged content and cannot mean complete.
            covered_until = event.start_seconds
            for old in sorted(overlapping, key=lambda item: item.start_seconds):
                if old.start_seconds > covered_until + 1e-6:
                    break
                covered_until = max(covered_until, old.end_seconds)
            if covered_until < event.end_seconds - 1e-6:
                conflicts.setdefault(event.kind, []).append(event)
            continue
        recovered = event.model_copy(deep=True)
        if recovered.id in used_ids:
            recovered.id = f"{recovered.id}_retry{previous.revision + 1}"
        used_ids.add(recovered.id)
        kept.append(recovered)
    result.events = sorted(kept, key=lambda event: (event.start_seconds, event.id))
    result.coverage = dict(previous.coverage)
    result.diagnostics = dict(previous.diagnostics)
    for channel in retried:
        if channel in incoming.coverage:
            result.coverage[channel] = incoming.coverage[channel]
            result.diagnostics.pop(channel, None)
        if channel in incoming.diagnostics:
            result.diagnostics[channel] = incoming.diagnostics[channel]
        if CHANNELS.get(channel) in conflicts:
            result.coverage[channel] = "partial"
            result.diagnostics[channel] = "speech_merge_conflict" if channel == "speech" else "evidence_merge_conflict"
    # Resolve old operational errors while retaining truthful source limitations.
    unresolved = [note for note in previous.limitations if not note.startswith(_CONFLICT_PREFIX) and
                  (not speech_only or not any(word in note.lower() for word in
                   ("transcription failed", "audio ", "speech failed", "quota", "credit", "rate limit")))]
    conflict_notes = []
    if conflicts:
        conflict_notes.append(f"{_CONFLICT_PREFIX} New recognition overlaps saved corrections and extends into an uncovered interval. "
                              "Compare the candidate wording and timing below, apply your correction, then retry recognition to check coverage. "
                              "Saved corrections were kept; no words or timestamps were split automatically.")
        for events in conflicts.values():
            for event in events:
                conflict_notes.append(f"{_CONFLICT_PREFIX} Candidate at {event.start_seconds:g}–{event.end_seconds:g}s: {event.text}")
    result.limitations = list(dict.fromkeys([*unresolved, *incoming.limitations,
        "Previously saved observations and corrections were retained; new results fill uncovered intervals.", *conflict_notes]))
    result.reviewed = False
    result.correction_note = previous.correction_note
    return result
