"""Explicit import of v0.1 schema-only fixtures; never creates playable media."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .models import (AnalysisResult, ContentSegment, Correction, Coverage, CreativeTask,
                     EvidenceEvent, Origin, PublicMetrics, ReviewState, TaskState,
                     VersionRef, VideoAsset, validate_state)

ROOT = Path(__file__).resolve().parents[2]


def _event_id(segment_id: str, suffix: str) -> str:
    candidate = f"{segment_id}_{suffix}"
    if len(candidate) <= 64:
        return candidate
    return candidate[:47] + "_" + hashlib.sha256(candidate.encode()).hexdigest()[:16]


def migrate_legacy_analysis(data: dict, original: dict | None = None) -> AnalysisResult:
    """Import supplied v0.1 success shape, preserving synthetic/unknown provenance.

    Legacy checked-absent text remains an empty string in canonical events. These
    events document what the old fixture represented, not new extraction results.
    Missing text stays absent with not_analyzed coverage where none was supplied.
    """
    schema = json.loads((ROOT / "contracts/analysis.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(data)
    if data["status"] != "succeeded":
        raise ValueError("legacy import currently supports completed supplied examples only")
    if data["revision"] > 1 and original is None:
        raise ValueError("revised legacy imports require the preserved original revision")
    if original is not None:
        if (original["analysis_id"], original["project_id"], original["video_id"], original["revision"]) != (data["analysis_id"], data["project_id"], data["video_id"], 1):
            raise ValueError("legacy original must match analysis/project/video at revision 1")
    model_run = data.get("model_run") or {}
    synthetic = "synthetic" in model_run.get("provider", "").lower()
    origin = Origin(kind="sample" if synthetic else "legacy", description=(
        "Imported v0.1 synthetic fixture; schema-only, no media verified. " if synthetic else
        "Imported v0.1 result; extraction and media have not been verified by this application. "
    ) + "Legacy model_run: " + json.dumps(model_run, sort_keys=True))
    events, segments, corrections = [], [], []
    original_segments = {segment["segment_id"]: segment for segment in (original or data)["segments"]}
    for segment in data["segments"]:
        sid = segment["segment_id"]
        if sid not in original_segments:
            raise ValueError("legacy correction must retain original segment IDs")
        baseline = original_segments[sid]
        evidence_ids = []
        for old_field, suffix, kind, lane, field in (
            ("visual_description", "visual", "visual_action", "visual", "description"),
            ("spoken_text", "speech", "speech", "audio", "text"),
            ("on_screen_text", "screen", "on_screen_text", "visual", "text"),
        ):
            value = segment[old_field]
            if value is None:
                continue
            event_id = _event_id(sid, suffix)
            event = EvidenceEvent(event_id=event_id, video_id=data["video_id"],
                                  legacy_seconds={"start_seconds": segment["start_seconds"], "end_seconds": segment["end_seconds"]},
                                  lane=lane, kind=kind, source=f"legacy_segment:{sid}", method="legacy_v0.1_import",
                                  **{field: value})
            events.append(event)
            evidence_ids.append(event_id)
            if value != baseline[old_field]:
                corrections.append(Correction(target_type="event", target_id=event_id, field=field,
                                              before=baseline[old_field], after=value))
        if segment["roles"] != baseline["roles"]:
            corrections.append(Correction(target_type="segment", target_id=sid, field="roles",
                                          before=baseline["roles"], after=segment["roles"]))
        # Retain source interpretation as interpretation, never canonical observation.
        segments.append(ContentSegment(segment_id=sid, video_id=data["video_id"],
                                       legacy_seconds={"start_seconds": segment["start_seconds"], "end_seconds": segment["end_seconds"]},
                                       roles=segment["roles"], evidence_ids=evidence_ids,
                                       interpretation=None if any(segment[field] != baseline[field] for field in ("roles", "visual_description", "spoken_text", "on_screen_text")) else segment["interpretation"]))
    coverage = Coverage(**{kind: "observations" if any(event.kind == kind for event in events) else "not_analyzed"
                           for kind in ("visual_action", "on_screen_text", "speech", "music", "sfx")})
    return AnalysisResult(analysis_id=data["analysis_id"], revision=data["revision"], task_id=data["project_id"],
                          video_id=data["video_id"], duration_seconds=data["video"]["duration_seconds"],
                          status="succeeded", created_at=data["created_at"], updated_at=data["updated_at"],
                          events=events, segments=segments, coverage=coverage, origin=origin,
                          original_revision=data["review"]["original_revision"],
                          review=ReviewState(user_confirmed=data["review"]["user_confirmed"],
                                             confirmed_at=data["review"]["confirmed_at"]),
                          corrections=corrections, empty_result_reason=data["empty_result_reason"])


def migrate_legacy_examples(original: dict, revised: dict) -> TaskState:
    first = migrate_legacy_analysis(original)
    second = migrate_legacy_analysis(revised, original)
    video = VideoAsset(video_id=first.video_id, task_id=first.task_id, input_method="legacy",
                       storage_id=None, original_file_name=original["video"]["original_file_name"],
                       source_url=original["video"]["source_url"], duration_seconds=first.duration_seconds,
                       intake_status="missing", origin=Origin(kind=first.origin.kind, description=
                       "Legacy schema-only source reference; duration copied from fixture, not measured here; no file exists or playback is claimed."),
                       public_metrics=PublicMetrics.model_validate(original["public_metrics"]) if original["public_metrics"] else None,
                       created_at=first.created_at, updated_at=second.updated_at)
    task = CreativeTask(task_id=first.task_id, title="Imported fictional LumaCup v0.1 examples — no media",
                        mode="sample" if first.origin.kind == "sample" else "real", progress="review",
                        current_video_id=first.video_id,
                        current_analysis=VersionRef(id=second.analysis_id, revision=second.revision),
                        created_at=first.created_at, updated_at=second.updated_at)
    return validate_state(TaskState(task=task, videos=[video], analyses=[first, second]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, default=ROOT / "examples/analysis_result.original.json")
    parser.add_argument("--revised", type=Path, default=ROOT / "examples/analysis_result.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = migrate_legacy_examples(json.loads(args.original.read_text()), json.loads(args.revised.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(state.model_dump_json(indent=2) + "\n")
    print(f"Imported legacy examples into {args.output}; media remains missing/unverified")


if __name__ == "__main__":
    main()
