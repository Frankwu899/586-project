"""Lossless import of seconds-based v0.2 task records into the frame contract.

Stored media supplies the frame map; a missing or unrepresentable map retains
the exact legacy intervals. The storage boundary archives the original payload
in the same transaction as its replacement. Storyboard plans remain seconds.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .contract_migration import add_v04_fields
from .media import MediaError, probe_frame_timing
from .models import FrameTiming, TaskState, validate_state
from .timing import seconds_to_frame_range

ROOT = Path(__file__).resolve().parents[2]
_V02_VALIDATOR = Draft202012Validator(
    json.loads((ROOT / "contracts/v0.2.task-state.schema.json").read_text()),
    format_checker=FormatChecker(),
)
def _convert_analysis(analysis: dict, timing: FrameTiming | None) -> dict:
    converted = deepcopy(analysis)
    converted["frame_count"] = timing.frame_count if timing else None
    if timing:
        converted["duration_seconds"] = timing.frame_boundaries_seconds[-1]
    for interval in [*converted["events"], *converted["segments"]]:
        start, end = interval.pop("start_seconds"), interval.pop("end_seconds")
        if timing is None:
            interval.update(start_frame=None, end_frame=None,
                            legacy_seconds={"start_seconds": start, "end_seconds": end})
        else:
            first, stop = seconds_to_frame_range(start, end, timing)
            interval.update(start_frame=first, end_frame=stop, legacy_seconds=None)
    return converted


def _preserves_interval_relationships(analysis: dict) -> bool:
    """Do not lose a citation or merge sections to force subframe data into frames."""
    events = {event["event_id"]: event for event in analysis["events"]}
    previous_end = 0
    for section in analysis["segments"]:
        if section["start_frame"] < previous_end:
            return False
        previous_end = section["end_frame"]
        for event_id in section["evidence_ids"]:
            event = events.get(event_id)
            if event is None:
                # A broken reference is invalid data, not a quantization problem.
                raise ValueError("legacy section has a dangling evidence reference")
            if event["end_frame"] <= section["start_frame"] or event["start_frame"] >= section["end_frame"]:
                return False
    return True


def _archive_unavailable_creative(state: dict) -> None:
    unavailable = {(analysis["analysis_id"], analysis["revision"])
                   for analysis in state["analyses"] if analysis["frame_count"] is None}
    outdated_directions = set()
    for direction in state["directions"]:
        ref = direction["analysis_ref"]
        if (ref["id"], ref["revision"]) in unavailable:
            direction.update(currentness="outdated", approval_status="draft", approved_at=None)
            outdated_directions.add((direction["direction_id"], direction["revision"]))
    for output in [*state["production_briefs"], *state["storyboards"]]:
        ref = output["analysis_ref"]
        if (ref["id"], ref["revision"]) in unavailable:
            output["currentness"] = "outdated"
    for key in ("chosen_direction", "selected_direction"):
        ref = state["task"][key]
        if ref and (ref["id"], ref["revision"]) in outdated_directions:
            state["task"][key] = None
    current = state["task"]["current_analysis"]
    if current and (current["id"], current["revision"]) in unavailable:
        state["task"]["progress"] = "review"


def migrate_v02_task(payload: dict, media_root: Path) -> TaskState:
    """Convert all revisions using one probed map per video; never guess a rate.

    A failed conversion raises before the caller writes anything. The caller
    owns backup/transaction handling. Successful conversion increments the
    optimistic task version once, retaining artifact IDs and revision numbers.
    """
    state = deepcopy(payload)
    # Early v0.2 installations predate the optional persisted draft selection.
    # Its model default was null even though the generated serialization schema
    # requires it. Preserve that default while archiving the exact original JSON.
    state["task"].setdefault("chosen_direction", None)
    _V02_VALIDATOR.validate(state)
    add_v04_fields(state)
    media_root = Path(media_root).resolve()
    for video in state["videos"]:
        video_id = video["video_id"]
        originals = [analysis for analysis in state["analyses"] if analysis["video_id"] == video_id]
        timing = None
        reason = "Source media is unavailable; original seconds are preserved. Upload the source to obtain frame timing."
        if video["storage_id"]:
            path = media_root / video["storage_id"]
            if path.resolve().parent == media_root:
                try:
                    matches_source = True
                    if path.is_file() and video["content_sha256"]:
                        with path.open("rb") as source:
                            matches_source = hashlib.file_digest(source, "sha256").hexdigest() == video["content_sha256"]
                    if matches_source:
                        timing = probe_frame_timing(path)
                    else:
                        reason = ("The saved media does not match the original content hash. Original seconds are preserved; "
                                  "restore the original source or upload and analyze the replacement.")
                except MediaError as error:
                    reason = f"Frame timing unavailable during migration: {error.message} Original seconds are preserved."
                except OSError:
                    reason = "The saved source could not be read during migration. Original seconds are preserved."
        converted = [_convert_analysis(analysis, timing) for analysis in originals]
        if timing and not all(_preserves_interval_relationships(analysis) for analysis in converted):
            timing = None
            reason = ("The old subframe intervals cannot be converted without changing section or evidence links. "
                      "Original seconds are preserved; reanalyze the source to obtain frame timing.")
            converted = [_convert_analysis(analysis, None) for analysis in originals]
        video["frame_timing"] = timing.model_dump(mode="json") if timing else None
        if timing:
            video["duration_seconds"] = timing.frame_boundaries_seconds[-1]
        elif video["intake_status"] == "ready":
            video["intake_status"] = "missing"
            video["error"] = {"code": "legacy_frame_timing_unavailable", "message": reason, "retryable": False}
        replacements = {(analysis["analysis_id"], analysis["revision"]): analysis for analysis in converted}
        state["analyses"] = [replacements.get((analysis["analysis_id"], analysis["revision"]), analysis)
                             for analysis in state["analyses"]]
    _archive_unavailable_creative(state)
    state["task"]["version"] += 1
    return validate_state(TaskState.model_validate(state))
