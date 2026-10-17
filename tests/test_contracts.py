"""Boundary tests for authoritative v0.6 timing, references and lineage."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from backend.app.migration import migrate_legacy_examples
from backend.app.models import (AnalysisResult, BrandTaskBrief, CreativeDirection, EvidenceReference,
                                Origin, StoryboardRow, TaskState,
                                TextStoryboard, VersionRef, validate_state)

ROOT = Path(__file__).resolve().parents[1]


def imported_state():
    return migrate_legacy_examples(json.loads((ROOT / "examples/analysis_result.original.json").read_text()),
                                   json.loads((ROOT / "examples/analysis_result.json").read_text()))


def frame_state():
    """Synthetic 25-fps metadata for isolated validation, not real media intake."""
    data = json.loads((ROOT / "examples/v0.2.legacy-migrated.json").read_text())
    data["task"]["schema_version"] = "0.6.0"
    for collection in data.values():
        if isinstance(collection, list):
            for record in collection:
                if "schema_version" in record:
                    record["schema_version"] = "0.6.0"
    video = data["videos"][0]
    video["frame_timing"] = {
        "fps_numerator": 25, "fps_denominator": 1, "frame_count": 500,
        "frame_boundaries_seconds": [frame / 25 for frame in range(501)],
        "rate_mode": "constant", "source": "probed",
    }
    for analysis in data["analyses"]:
        analysis["frame_count"] = 500
        for item in [*analysis["events"], *analysis["segments"]]:
            item["start_frame"] = round(item.pop("start_seconds") * 25)
            item["end_frame"] = round(item.pop("end_seconds") * 25)
    return TaskState.model_validate(data)


def creative_state():
    state = frame_state()
    task_id = state.task.task_id
    analysis = state.analyses[-1]
    brief = BrandTaskBrief(brief_id="brief_test", task_id=task_id, brand_company="Fictional LumaCup",
                          product="Fictional cup", selling_points=["Removable lid"],
                          claim_details=[{"claim_id": "claim_test", "statement": "Removable lid", "confirmation_origin": "user_confirmed"}],
                          target_audience="Cup buyers", platform="Team demo", communication_goal="Show the lid",
                          target_duration_seconds=8)
    brief_ref = VersionRef(id=brief.brief_id, revision=1)
    analysis_ref = VersionRef(id=analysis.analysis_id, revision=analysis.revision)
    evidence = EvidenceReference(analysis_id=analysis.analysis_id, analysis_revision=analysis.revision,
                                 video_id=analysis.video_id, event_id=analysis.events[0].event_id,
                                 reason="A fictional product introduction informs this proposed opening.")
    direction = CreativeDirection(direction_id="direction_test", task_id=task_id, brief_ref=brief_ref,
                                  analysis_ref=analysis_ref, core_message="Introduce the lid", hook="Show the cup",
                                  narrative="Reveal the removable lid", cta="Explore the colors",
                                  evidence=[evidence], rationale="A concrete product detail supports the brief.",
                                  hypotheses=["Showing the lid may make the feature easier to understand; test with viewers."],
                                  origin=Origin(kind="sample", description="Schema-only fictional direction"))
    direction.approval_status = "approved"
    direction.approved_at = direction.updated_at
    direction_ref = VersionRef(id=direction.direction_id, revision=1)
    output = TextStoryboard(output_id="storyboard_test", task_id=task_id, direction_ref=direction_ref,
                            brief_ref=brief_ref, analysis_ref=analysis_ref, origin=direction.origin,
                            target_duration_seconds=8,
                            rows=[StoryboardRow(row_id="row_first", start_seconds=0, end_seconds=4,
                                                visual="Show a fictional cup", evidence=[evidence]),
                                  StoryboardRow(row_id="row_second", start_seconds=4, end_seconds=8,
                                                visual="Lift its lid", cta="Explore the colors")])
    state.briefs.append(brief)
    state.task.current_brief = brief_ref
    state.directions.append(direction)
    state.task.selected_direction = direction_ref
    state.storyboards.append(output)
    state.task.current_storyboard = VersionRef(id=output.output_id, revision=1)
    return validate_state(state)


def test_current_contract_and_generated_json_schema_agree():
    state = creative_state()
    schema = json.loads((ROOT / "contracts/v0.6.task-state.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(state.model_dump(mode="json"))
    assert TaskState.model_validate_json(state.model_dump_json()) == state
    result = subprocess.run([sys.executable, "scripts/export_contracts.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_overlapping_visual_audio_events_and_cross_section_event_are_valid():
    analysis = frame_state().analyses[0]
    assert analysis.events[0].start_frame == analysis.events[1].start_frame
    # A canonical event may overlap multiple primary sections.
    analysis.events[0].end_frame = 125
    analysis.segments[1].evidence_ids.append(analysis.events[0].event_id)
    AnalysisResult.model_validate(analysis.model_dump())


@pytest.mark.parametrize("value", [-1, 0, 4.5, True, "100", float("nan"), float("inf"), float("-inf"), 501])
def test_invalid_reference_event_times_are_rejected(value):
    analysis = frame_state().analyses[0].model_dump()
    analysis["events"][0]["end_frame"] = value
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(analysis)


@pytest.mark.parametrize("mutation", [
    lambda data: data["events"][0].update(start_frame=-1),
    lambda data: data["events"][0].update(start_frame=100),
    lambda data: data["segments"][1].update(start_frame=75),
    lambda data: data["segments"][1].update(end_frame=525),
    lambda data: data["segments"][0].update(roles=["hook", "other"]),
    lambda data: data["events"].append(copy.deepcopy(data["events"][0])),
    lambda data: data["segments"].append(copy.deepcopy(data["segments"][0])),
    lambda data: data["segments"][0]["evidence_ids"].append("event_missing"),
    lambda data: data["events"][0].update(video_id="video_wrong"),
    lambda data: data["coverage"].update(speech="none_found"),
    lambda data: data.update(confidence=0.95),
    lambda data: data.update(created_at="2026-10-08T07:00:00"),
])
def test_analysis_structural_and_semantic_boundaries(mutation):
    data = frame_state().analyses[0].model_dump(mode="json")
    mutation(data)
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(data)


@pytest.mark.parametrize("mutation", [
    lambda state: setattr(state.directions[0].evidence[0], "analysis_revision", 1),
    lambda state: setattr(state.directions[0].evidence[0], "event_id", "event_missing"),
    lambda state: setattr(state.directions[0].evidence[0], "video_id", "video_wrong"),
    lambda state: setattr(state.directions[0], "task_id", "task_wrong"),
    lambda state: setattr(state.directions[0].analysis_ref, "revision", 99),
    lambda state: setattr(state.storyboards[0].direction_ref, "revision", 99),
    lambda state: state.briefs.append(state.briefs[0].model_copy(deep=True)),
])
def test_exact_revision_and_task_citations_are_enforced(mutation):
    state = creative_state()
    mutation(state)
    with pytest.raises(ValidationError):
        validate_state(state)


def test_current_creative_records_require_review_and_approval():
    state = creative_state()
    state.analyses[-1].review.user_confirmed = False
    state.analyses[-1].review.confirmed_at = None
    with pytest.raises(ValidationError, match="reviewed successful"):
        validate_state(state)
    state = creative_state()
    state.directions[0].approval_status = "draft"
    state.directions[0].approved_at = None
    with pytest.raises(ValidationError, match="selected approved"):
        validate_state(state)
    # Historical outputs remain readable after upstream changes invalidate approvals.
    state.directions[0].currentness = "outdated"
    state.storyboards[0].currentness = "outdated"
    state.task.selected_direction = None
    validate_state(state)


def test_reference_and_planned_times_use_distinct_clocks():
    state = creative_state()
    assert state.analyses[-1].frame_count == 500
    assert state.analyses[-1].duration_seconds == 20
    assert state.videos[0].frame_timing.fps_numerator == 25
    assert state.storyboards[0].target_duration_seconds == 8
    state.storyboards[0].rows[-1].end_seconds = 9
    with pytest.raises(ValidationError):
        validate_state(state)
    state = creative_state()
    state.storyboards[0].rows[1].start_seconds = 3
    with pytest.raises(ValidationError, match="nonoverlapping"):
        validate_state(state)


@pytest.mark.parametrize("mutation", [
    lambda state: setattr(state.analyses[1].events[0], "end_frame", 99),
    lambda state: setattr(state.analyses[1].events[0], "text", "Unrecorded correction"),
    lambda state: setattr(state.analyses[1].corrections[0], "before", "Invented original"),
    lambda state: setattr(state.analyses[1].corrections[0], "target_id", "event_missing"),
])
def test_corrections_preserve_originals_and_require_replayable_change_log(mutation):
    state = frame_state()
    original = state.analyses[0].model_dump_json()
    mutation(state)
    assert state.analyses[0].model_dump_json() == original
    with pytest.raises(ValidationError):
        validate_state(state)


def test_partial_coverage_is_explicit_and_never_inferred_silence():
    analysis = frame_state().analyses[0]
    assert analysis.coverage.music == "not_analyzed"
    analysis.status = "partial"
    analysis.coverage.music = "failed"
    AnalysisResult.model_validate(analysis.model_dump())
    analysis.status = "succeeded"
    with pytest.raises(ValidationError, match="partial"):
        AnalysisResult.model_validate(analysis.model_dump())


def test_complete_sample_fixture_validates_at_real_runtime_boundary():
    state = TaskState.model_validate_json((ROOT / "examples/v0.6.sample-task.json").read_text())
    assert state.task.mode == "sample"
    assert len(state.directions) >= 3
    assert state.feedback[0].status == "applied"
    assert state.production_briefs and state.storyboards
    assert state.analyses[0].origin.kind == "sample"
    schema = json.loads((ROOT / "contracts/v0.6.task-state.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(state.model_dump(mode="json"))


def test_draft_choice_persists_separately_from_approval_and_resolves_exact_revision():
    state = creative_state()
    chosen = VersionRef(id=state.directions[0].direction_id, revision=1)
    state.task.chosen_direction = chosen
    restored = TaskState.model_validate_json(state.model_dump_json())
    assert restored.task.chosen_direction == chosen
    # A draft choice does not itself establish approval or usable production output.
    restored.storyboards = []
    restored.task.current_storyboard = None
    restored.task.selected_direction = None
    restored.directions[0].approval_status = "draft"
    restored.directions[0].approved_at = None
    validate_state(restored)
    assert restored.task.selected_direction is None
    restored.task.chosen_direction = VersionRef(id=chosen.id, revision=99)
    with pytest.raises(ValidationError, match="wrong-revision"):
        validate_state(restored)
    restored.task.chosen_direction = chosen
    restored.directions[0].currentness = "outdated"
    with pytest.raises(ValidationError, match="chosen direction must be"):
        validate_state(restored)


def test_missing_legacy_media_preserves_original_seconds_without_inventing_frames():
    state = imported_state()
    assert state.videos[0].frame_timing is None
    for analysis in state.analyses:
        assert analysis.frame_count is None
        for interval in [*analysis.events, *analysis.segments]:
            assert interval.start_frame is None and interval.end_frame is None
            assert interval.legacy_seconds is not None
    state.analyses[1].events[0].legacy_seconds.end_seconds = 3.9
    with pytest.raises(ValidationError, match="timing"):
        validate_state(state)


@pytest.mark.parametrize("value", [-1, 0, 2.5, True, "25", float("inf")])
@pytest.mark.parametrize("field", ["fps_numerator", "fps_denominator", "frame_count"])
def test_frame_metadata_requires_positive_integer_rate_and_count(field, value):
    from backend.app.models import FrameTiming

    timing = frame_state().videos[0].frame_timing.model_dump()
    timing[field] = value
    with pytest.raises(ValidationError):
        FrameTiming.model_validate(timing)


@pytest.mark.parametrize("boundaries", [
    [0, 0.04],                         # frame count + 1 required
    [0.01, 0.04, 0.08],               # source clock must begin at zero
    [0, 0.04, 0.04],                  # duplicate presentation boundary
    [0, 0.08, 0.04],                  # reversed boundary
    [0, float("nan"), 0.08],
    [0, 0.04, float("inf")],
])
def test_frame_boundaries_are_complete_finite_and_strictly_increasing(boundaries):
    from backend.app.models import FrameTiming

    with pytest.raises(ValidationError):
        FrameTiming(fps_numerator=25, fps_denominator=1, frame_count=2,
                    frame_boundaries_seconds=boundaries, rate_mode="constant")


@pytest.mark.parametrize("numerator,denominator", [
    (24, 1), (25, 1), (30, 1), (60, 1), (24000, 1001), (30000, 1001), (60000, 1001),
])
def test_integer_and_fractional_frame_rates_preserve_exact_ratio(numerator, denominator):
    from backend.app.models import FrameTiming, VideoAsset

    duration = 2 * denominator / numerator
    timing = FrameTiming(fps_numerator=numerator, fps_denominator=denominator, frame_count=2,
                         frame_boundaries_seconds=[0, denominator / numerator, duration],
                         rate_mode="constant")
    video = frame_state().videos[0].model_dump()
    video.update(duration_seconds=duration, frame_timing=timing.model_dump())
    saved = VideoAsset.model_validate(video)
    assert saved.frame_timing.fps_numerator == numerator
    assert saved.frame_timing.fps_denominator == denominator
    video["duration_seconds"] = duration + 0.1
    with pytest.raises(ValidationError, match="final frame boundary"):
        VideoAsset.model_validate(video)


def test_variable_frame_intervals_and_single_frame_observations_are_valid():
    from backend.app.models import FrameTiming

    timing = FrameTiming(fps_numerator=25, fps_denominator=1, frame_count=3,
                         frame_boundaries_seconds=[0, 0.02, 0.06, 0.1], rate_mode="variable")
    assert timing.frame_boundaries_seconds[2] - timing.frame_boundaries_seconds[1] == pytest.approx(0.04)
    analysis = frame_state().analyses[0].model_dump()
    # A one-frame visual element at the final frame is valid and has an exclusive end.
    event = analysis["events"][0]
    event.update(start_frame=499, end_frame=500)
    analysis.update(events=[event], segments=[], coverage={"visual_action": "observations"})
    saved = AnalysisResult.model_validate(analysis)
    assert saved.events[0].end_frame - saved.events[0].start_frame == 1


@pytest.mark.parametrize("value", [-1, 1.5, 1.0, True, "1"])
def test_start_frame_is_a_strict_nonnegative_integer(value):
    data = frame_state().analyses[0].model_dump()
    data["events"][0]["start_frame"] = value
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(data)


@pytest.mark.parametrize("mutation", [
    lambda data: data.update(frame_count=499),
    lambda data: data.update(frame_count=None),
    lambda data: data["events"][0].update(start_frame=None),
    lambda data: data["events"][0].update(start_frame=None, end_frame=None),
    lambda data: data["events"][0].update(legacy_seconds={"start_seconds": 0, "end_seconds": 4}),
])
def test_analysis_rejects_missing_mixed_or_out_of_bounds_frame_clock(mutation):
    data = frame_state().analyses[0].model_dump()
    mutation(data)
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(data)


def test_task_analysis_frame_count_must_match_the_source_video():
    state = frame_state()
    for analysis in state.analyses:
        analysis.frame_count = 501
    with pytest.raises(ValidationError, match="frame count must match"):
        validate_state(state)


def test_half_open_frame_boundaries_do_not_imply_evidence_overlap():
    analysis = frame_state().analyses[0]
    event = analysis.events[0]
    event.start_frame, event.end_frame = 99, 100
    analysis.segments[1].evidence_ids.append(event.event_id)
    with pytest.raises(ValidationError, match="overlap"):
        AnalysisResult.model_validate(analysis.model_dump())
    event.end_frame = 101
    AnalysisResult.model_validate(analysis.model_dump())


def test_ready_media_requires_probed_frame_timing():
    from backend.app.models import VideoAsset

    video = frame_state().videos[0].model_dump()
    video.update(intake_status="ready", storage_id="0" * 32 + ".mp4", frame_timing=None)
    with pytest.raises(ValidationError, match="frame timing"):
        VideoAsset.model_validate(video)


def test_unavailable_legacy_timing_cannot_power_current_creative_records():
    state = creative_state()
    # Preserve all evidence and review history while making timing unavailable.
    state.videos[0].frame_timing = None
    for analysis in state.analyses:
        analysis.frame_count = None
        for interval in [*analysis.events, *analysis.segments]:
            from backend.app.models import LegacySeconds
            interval.legacy_seconds = LegacySeconds(start_seconds=interval.start_frame / 25,
                                                    end_seconds=interval.end_frame / 25)
            interval.start_frame = interval.end_frame = None
    with pytest.raises(ValidationError, match="available reference frame timing"):
        validate_state(state)
    # Saved historical results can still be opened, without becoming usable again.
    state.directions[0].currentness = "outdated"
    state.storyboards[0].currentness = "outdated"
    state.task.selected_direction = None
    validate_state(state)


@pytest.mark.parametrize("origin", [-1.25, 0, 2.0])
def test_frame_media_origin_is_signed_and_keeps_boundaries_relative(origin):
    from backend.app.models import FrameTiming

    timing = FrameTiming(fps_numerator=25, fps_denominator=1, frame_count=2,
                         media_start_seconds=origin,
                         frame_boundaries_seconds=[0, 0.04, 0.08], rate_mode="constant")
    assert timing.media_start_seconds == origin
    assert timing.frame_boundaries_seconds == [0, 0.04, 0.08]
    data = timing.model_dump(exclude={"media_start_seconds"})
    assert FrameTiming.model_validate(data).media_start_seconds == 0


@pytest.mark.parametrize("origin", [float("nan"), float("inf"), float("-inf")])
def test_frame_media_origin_rejects_nonfinite_values(origin):
    from backend.app.models import FrameTiming

    with pytest.raises(ValidationError):
        FrameTiming(fps_numerator=25, fps_denominator=1, frame_count=2,
                    media_start_seconds=origin,
                    frame_boundaries_seconds=[0, 0.04, 0.08], rate_mode="constant")
