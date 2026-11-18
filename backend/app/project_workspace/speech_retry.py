"""Conservative recovery of missing channels without replacing user corrections."""
from __future__ import annotations

import re
import json
import math

from ..providers.base import ProviderError
from ..workflow_errors import WorkflowError
from .models import EvidenceRevision

FAILED = {"failed", "partial", "error", "not_analyzed"}
CHANNELS = {"visual_action": "visual", "visual": "visual", "on_screen_text": "on_screen_text",
            "speech": "speech", "music": "sound", "sfx": "sound"}
_CONFLICT_PREFIX = "Recovery needs review:"
CORRECTED_IDS = "human_corrected_event_ids"
SPEECH_INTERVALS = "machine_speech_source_intervals"
VISUAL_SAMPLE_SCOPES = "machine_visual_sample_scopes"
OCR_ORIGINS = "machine_ocr_originals"

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
    "audio_transcript_invalid": "Transcription returned no usable text field. Retry the affected audio chunk; saved evidence is retained.",
    "unsupported_model_capability": "This transcription profile is unavailable. Choose whisper-1 for segment timing or gpt-transcribe for whole-chunk text.",
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


def corrected_ids(evidence: EvidenceRevision) -> set[str]:
    """New revisions record exact edited IDs; ambiguous old corrections stay safe."""
    marker = evidence.diagnostics.get(CORRECTED_IDS)
    if marker is not None:
        try:
            values = json.loads(marker)
            if isinstance(values, list) and all(isinstance(value, str) for value in values):
                return set(values)
        except (ValueError, TypeError):
            pass
    return {event.id for event in evidence.events} if evidence.correction_note else set()


def _completed_speech_intervals(incoming, protected):
    """Only validated input chunks authorize replacing speech across silence."""
    suppressed = [event for event in incoming.events if event.kind == "speech" and any(
        old.start_seconds < event.end_seconds and event.start_seconds < old.end_seconds for old in protected)]
    intervals = []
    for detail in incoming.support_details:
        if (detail.get("stage") != "transcription_chunk"
                or detail.get("validation_outcome") != "accepted" or detail.get("failure_code")):
            continue
        try:
            start, end = float(detail["chunk_start_seconds"]), float(detail["chunk_end_seconds"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end:
            continue
        # A candidate spanning a correction may be suppressed in full below,
        # including source-frame rounding beyond its measured input chunk.
        # Keep the other saved wording in that chunk until the conflict clears.
        if any(old.start_seconds < end and start < old.end_seconds for old in [*protected, *suppressed]):
            continue
        intervals.append((start, end))
    completed = []
    for start, end in sorted(intervals):
        if completed and start <= completed[-1][1]:
            completed[-1] = (completed[-1][0], max(completed[-1][1], end))
        else:
            completed.append((start, end))
    return completed


def source_speech_intervals(evidence):
    """Native machine spans are separate from frame-quantized display timing."""
    try:
        values = json.loads(evidence.diagnostics.get(SPEECH_INTERVALS, "{}"))
    except (TypeError, ValueError):
        return {}
    if not isinstance(values, dict):
        return {}
    return {event.id: tuple(values[event.id]) for event in evidence.events if event.kind == "speech"
            and isinstance(values.get(event.id), list) and len(values[event.id]) == 2
            and all(type(value) in (int, float) and math.isfinite(value) for value in values[event.id])
            and 0 <= values[event.id][0] < values[event.id][1]}


def _replacement_interval(event, native):
    if event.id in native:
        return native[event.id]
    if event.start_frame is not None or event.end_frame is not None:
        return None  # Older frame spans cannot establish which audio chunk supplied their words.
    return event.start_seconds, event.end_seconds


def _within_speech_scope(event, scopes, native):
    bounds = _replacement_interval(event, native)
    return bounds is not None and any(start <= bounds[0] and bounds[1] <= end for start, end in scopes)


def _visual_replacement_scopes(incoming):
    """Accepted complete samples own all their OCR lines, including empty sets.

    Historical attempts lack the sample marker. Only their actual visual/OCR
    event intervals establish a replacement range; channel status alone does not.
    """
    marker = incoming.diagnostics.get(VISUAL_SAMPLE_SCOPES)
    if marker is None:
        return [(event.start_seconds, event.end_seconds) for event in incoming.events
                if event.kind in {"visual", "on_screen_text"}]
    try:
        scopes = json.loads(marker)
    except (TypeError, ValueError):
        return []
    if not isinstance(scopes, dict):
        return []
    return [tuple(bounds) for bounds in scopes.values()
            if isinstance(bounds, list) and len(bounds) == 2
            and all(type(value) in (int, float) and math.isfinite(value) for value in bounds)
            and 0 <= bounds[0] < bounds[1]]


def _same_observation(left, right):
    return left.model_dump(exclude={"id"}) == right.model_dump(exclude={"id"})


def source_ocr_originals(evidence):
    """Read host-recorded machine wording; never infer a historical original."""
    try:
        origins = json.loads(evidence.diagnostics.get(OCR_ORIGINS, "{}"))
    except (TypeError, ValueError):
        return {}
    if not isinstance(origins, dict):
        return {}
    result = {}
    for event in evidence.events:
        value = origins.get(event.id)
        if (event.kind == "on_screen_text" and isinstance(value, dict)
                and isinstance(value.get("text"), str)
                and all(type(value.get(key)) in (int, float) and math.isfinite(value[key]) for key in ("start", "end"))
                and 0 <= value["start"] < value["end"]):
            result[event.id] = {key: value[key] for key in ("start", "end", "text")}
    return result


def _protected_ocr_matches(event, previous, protected, origins):
    corrections = [old for old in previous.events if old.id in protected and old.kind == "on_screen_text"]
    # The user can move the corrected interval. Its known machine original
    # still belongs to that correction at the original time and provider ID.
    original_matches = [old for old in corrections if old.id in origins
                        and origins[old.id]["text"] == event.text
                        and origins[old.id]["start"] < event.end_seconds
                        and event.start_seconds < origins[old.id]["end"]]
    if original_matches:
        complete = any(origins[old.id]["start"] <= event.start_seconds
                       and event.end_seconds <= origins[old.id]["end"] for old in original_matches)
        return original_matches, not complete, complete
    overlapping = [old for old in corrections if old.id == event.id
                   or old.start_seconds < event.end_seconds and event.start_seconds < old.end_seconds]
    matched = [old for old in overlapping if old.id == event.id or old.text == event.text]
    if matched:
        return matched, False, False
    # Older corrected text without its machine original cannot establish which
    # changed provider identity belongs to the correction. Keep known separate
    # lines, but expose unknown candidates for review rather than restoring them.
    unknown = [old for old in overlapping if old.id not in origins]
    distinct = any(old.kind == "on_screen_text" and old.id not in protected
                   and old.start_seconds == event.start_seconds and old.end_seconds == event.end_seconds
                   and (old.id == event.id or old.text == event.text) for old in previous.events)
    return (unknown, True, False) if unknown and not distinct else ([], False, False)


def merge_retry(previous: EvidenceRevision, incoming: EvidenceRevision, *, speech_only=False):
    """Replace recoverable machine output, preserving exact human corrections/history."""
    result = incoming.model_copy(deep=True)
    retried = {"speech"} if speech_only else {
        key for key, value in previous.coverage.items() if value in FAILED and key not in {"music", "sfx"}}
    kinds = {CHANNELS[key] for key in retried if key in CHANNELS}
    protected = corrected_ids(previous)
    previous_intervals, incoming_intervals = source_speech_intervals(previous), source_speech_intervals(incoming)
    native_intervals = previous_intervals.copy()
    previous_ocr, incoming_ocr = source_ocr_originals(previous), source_ocr_originals(incoming)
    ocr_origins = previous_ocr.copy()
    # Channel status alone cannot authorize deleting speech retained elsewhere.
    # Successful measured chunks do, including silent gaps and empty transcripts.
    completed = _completed_speech_intervals(incoming, [event for event in previous.events
        if event.id in protected and event.kind == "speech"]) if "speech" in kinds else []
    visual_scopes = _visual_replacement_scopes(incoming)
    kept = [event.model_copy(deep=True) for event in previous.events
            if event.id in protected or not (
                event.kind == "speech" and _within_speech_scope(event, completed, previous_intervals)
                or event.kind in kinds & {"visual", "on_screen_text"}
                and any(start <= event.start_seconds and event.end_seconds <= end for start, end in visual_scopes))]
    used_ids = {event.id for event in previous.events}
    conflicts = {}
    admitted = []
    for event in incoming.events:
        if event.kind not in kinds:
            continue
        ambiguous_ocr = False
        if event.kind == "on_screen_text":
            overlapping, ambiguous_ocr, known_original = _protected_ocr_matches(event, previous, protected, previous_ocr)
            if known_original:
                continue
        else:
            overlapping = [old for old in previous.events if old.id in protected and old.kind == event.kind
                           and old.start_seconds < event.end_seconds and event.start_seconds < old.end_seconds]
        if overlapping:
            # Never split words by proportional timing. A span extending beyond
            # the retained union has unmerged content and cannot mean complete.
            covered_until = event.start_seconds
            for old in sorted(overlapping, key=lambda item: item.start_seconds):
                if old.start_seconds > covered_until + 1e-6:
                    break
                covered_until = max(covered_until, old.end_seconds)
            if ambiguous_ocr or covered_until < event.end_seconds - 1e-6:
                conflicts.setdefault(event.kind, []).append(event)
            continue
        candidate_bounds = incoming_intervals.get(event.id, (event.start_seconds, event.end_seconds))
        if event.kind == "speech":
            kept = [old for old in kept if old.id in protected or old.kind != "speech"
                    or not _within_speech_scope(old, [candidate_bounds], native_intervals)]
        if any(old.kind == event.kind and old.start_seconds == event.start_seconds
               and old.end_seconds == event.end_seconds and old.text == event.text for old in [*kept, *admitted]):
            continue
        recovered = event.model_copy(deep=True)
        matching = next((old for old in previous.events if old.id not in protected
                         and _same_observation(old, event)), None)
        if matching is not None:
            recovered.id = matching.id
        elif recovered.id in used_ids:
            recovered.id = f"{recovered.id}_retry{previous.revision + 1}"
        used_ids.add(recovered.id)
        admitted.append(recovered)
        if event.id in incoming_intervals:
            native_intervals[recovered.id] = incoming_intervals[event.id]
        if event.id in incoming_ocr:
            ocr_origins[recovered.id] = incoming_ocr[event.id]
    result.events = sorted([*kept, *admitted], key=lambda event: (event.start_seconds, event.id))
    result.coverage = dict(previous.coverage)
    result.diagnostics = dict(previous.diagnostics)
    result.diagnostics.update({key: value for key, value in incoming.diagnostics.items()
                               if key not in CHANNELS and key not in {CORRECTED_IDS, SPEECH_INTERVALS, OCR_ORIGINS}})
    native_intervals = {event.id: native_intervals[event.id] for event in result.events if event.id in native_intervals}
    if native_intervals or SPEECH_INTERVALS in result.diagnostics:
        result.diagnostics[SPEECH_INTERVALS] = json.dumps(native_intervals, sort_keys=True)
    ocr_origins = {event.id: ocr_origins[event.id] for event in result.events if event.id in ocr_origins}
    if ocr_origins or OCR_ORIGINS in result.diagnostics:
        result.diagnostics[OCR_ORIGINS] = json.dumps(ocr_origins, sort_keys=True)
    if protected or CORRECTED_IDS in previous.diagnostics:
        result.diagnostics[CORRECTED_IDS] = json.dumps(sorted(protected))
    for channel in retried:
        if channel in incoming.coverage:
            result.coverage[channel] = incoming.coverage[channel]
            result.diagnostics.pop(channel, None)
        if channel in incoming.diagnostics:
            result.diagnostics[channel] = incoming.diagnostics[channel]
        if CHANNELS.get(channel) in conflicts:
            result.coverage[channel] = "partial"
            result.diagnostics[channel] = "speech_merge_conflict" if channel == "speech" else "evidence_merge_conflict"
    ambiguous = any(old.kind == "speech" and old.id not in protected
        and _replacement_interval(old, previous_intervals) is None and old in kept and (
            any(event.kind == "speech" and old.start_seconds < event.end_seconds
                and event.start_seconds < old.end_seconds for event in admitted)
            or (incoming.coverage.get("speech") == "none_found"
                and any(old.start_seconds < end and start < old.end_seconds for start, end in completed)))
        for old in previous.events)
    if ambiguous:
        result.coverage["speech"] = "partial"
        result.diagnostics["speech"] = "speech_merge_provenance_missing"
    # Resolve old operational errors while retaining truthful source limitations.
    unresolved = [note for note in previous.limitations if not note.startswith(_CONFLICT_PREFIX) and
                  (not speech_only or not any(word in note.lower() for word in
                   ("transcription failed", "audio ", "speech failed", "quota", "credit", "rate limit")))]
    conflict_notes = []
    if conflicts:
        conflict_notes.append(f"{_CONFLICT_PREFIX} New recognition overlaps saved corrections with ambiguous identity or extends into an uncovered interval. "
                              "Compare the candidate wording and timing below, apply your correction, then retry recognition to check coverage. "
                              "Saved corrections were kept; no words or timestamps were split automatically.")
        for events in conflicts.values():
            for event in events:
                conflict_notes.append(f"{_CONFLICT_PREFIX} Candidate at {event.start_seconds:g}–{event.end_seconds:g}s: {event.text}")
    if ambiguous:
        conflict_notes.append(f"{_CONFLICT_PREFIX} Older frame-aligned speech has no native audio interval provenance. "
                              "Its wording was retained alongside the new attempt; compare and correct the overlapping transcript before treating coverage as complete.")
    result.limitations = list(dict.fromkeys([*unresolved, *incoming.limitations,
        "Previously saved observations and corrections were retained; new results fill uncovered intervals.", *conflict_notes]))
    result.reviewed = False
    result.correction_note = previous.correction_note
    return result
