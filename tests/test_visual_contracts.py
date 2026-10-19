"""v0.4 nested observations, immutable correction structure and separate clocks."""
from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError
import pytest

from backend.app.models import (AnalysisResult, Correction, EvidenceEvent, PlaybackRepresentation,
                                TaskState, VideoAsset, VisualDetails, validate_state,
                                validate_visual_details_correction)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def details():
    return json.loads((ROOT / "examples/v0.6.visual-analysis.json").read_text())["events"][0]["visual_details"]


@pytest.fixture
def analysis():
    return json.loads((ROOT / "examples/v0.6.visual-analysis.json").read_text())


def test_synthetic_example_preserves_bilingual_words_and_schema(analysis):
    parsed = AnalysisResult.model_validate(analysis)
    assert parsed.events[1].text == "DemoCup 随行杯 · Shop now"
    assert parsed.events[2].text == "这款 DemoCup，take it anywhere。"
    assert parsed.origin.kind == "sample" and "No media" in parsed.origin.description
    schema = json.loads((ROOT / "contracts/v0.6.analysis.schema.json").read_text())
    Draft202012Validator(schema).validate(analysis)
    current_schema = json.loads((ROOT / "contracts/v0.7.analysis.schema.json").read_text())
    Draft202012Validator(current_schema).validate(parsed.model_dump(mode="json"))
    assert AnalysisResult.model_validate_json(parsed.model_dump_json()) == parsed


@pytest.mark.parametrize("mutation", [
    lambda d: d.pop("subjects"),
    lambda d: d["subjects"]["items"][0].update(kind="null"),
    lambda d: d["subjects"]["items"][0].update(kind="product"),
    lambda d: d["subjects"]["items"][0].update(roles=[]),
    lambda d: d["subjects"]["items"][0].update(roles=[None]),
    lambda d: d["subjects"]["items"][0].update(roles=["presenter", "presenter"]),
    lambda d: d["subjects"]["items"][0].update(roles=["presenter", "other"]),
    lambda d: d["subjects"]["items"][0].update(kind="other", description=None),
    lambda d: d["subjects"]["items"][0].update(roles=["other"], description=None),
    lambda d: d["subjects"]["items"][0].update(label=" \t\n "),
    lambda d: d["subjects"]["items"].append(deepcopy(d["subjects"]["items"][0])),
    lambda d: d["actions"]["items"][0].update(actor_subject_ids=["missing"]),
    lambda d: d["actions"]["items"][0].update(target_subject_ids=["s2", "s2"]),
    lambda d: d["actions"]["items"][0].update(action_type="intent"),
    lambda d: d["actions"]["items"][0].update(description=" \n"),
    lambda d: d["product_presentations"]["items"][0].update(product_subject_ids=[]),
    lambda d: d["product_presentations"]["items"][0].update(product_subject_ids=["s1"]),
    lambda d: d["product_presentations"]["items"][0].update(product_subject_ids=["s2", "s2"]),
    lambda d: d["product_presentations"]["items"][0].update(presentation_type="efficacy"),
    lambda d: d["product_presentations"]["items"][0].update(start_frame=0),
])
def test_invalid_labels_references_and_extra_time_fields_rejected(details, mutation):
    mutation(details)
    with pytest.raises(ValidationError):
        VisualDetails.model_validate(details)


@pytest.mark.parametrize("group", ["subjects", "actions", "product_presentations"])
@pytest.mark.parametrize("status,items,error,valid", [
    ("not_analyzed", [], None, True),
    ("none_found", [], None, True),
    ("observations", [], None, False),
    ("failed", [], None, False),
    ("failed", [], {"code": "extraction_failed", "message": "Retry this extraction."}, True),
    ("none_found", [], {"code": "extraction_failed", "message": "Retry this extraction."}, False),
])
def test_group_status_items_and_errors_agree(details, group, status, items, error, valid):
    # Clear relationships so each group's status can be tested independently.
    for name in details:
        details[name] = {"status": "not_analyzed", "items": [], "error": None}
    details[group] = {"status": status, "items": items, "error": error}
    if valid:
        assert VisualDetails.model_validate(details).model_dump()[group]["status"] == status
    else:
        with pytest.raises(ValidationError):
            VisualDetails.model_validate(details)


def test_unknown_is_null_and_not_a_negative_or_failure(details):
    details["subjects"]["items"][0].update(kind=None, roles=None)
    details["actions"]["items"][0]["action_type"] = None
    details["product_presentations"]["items"][0]["presentation_type"] = None
    parsed = VisualDetails.model_validate(details)
    assert parsed.subjects.items[0].kind is None
    assert parsed.subjects.status == "observations"
    assert not parsed.has_failures()


def test_visual_details_only_on_visual_action(analysis):
    event = deepcopy(analysis["events"][0])
    event.update(kind="on_screen_text")
    with pytest.raises(ValidationError, match="only on visual_action"):
        EvidenceEvent.model_validate(event)


def test_nested_failure_requires_partial_with_successful_parent_coverage(analysis):
    analysis["events"][0]["visual_details"]["actions"] = {
        "status": "failed", "items": [],
        "error": {"code": "classification_failed", "message": "Action classification was unavailable."},
    }
    with pytest.raises(ValidationError, match="partial"):
        AnalysisResult.model_validate(analysis)
    analysis["status"] = "partial"
    parsed = AnalysisResult.model_validate(analysis)
    assert parsed.coverage.visual_action == "observations"
    assert parsed.events[0].visual_details.subjects.items
    analysis["events"][0]["visual_details"]["actions"] = {"status": "not_analyzed", "items": [], "error": None}
    with pytest.raises(ValidationError, match="identify failed"):
        AnalysisResult.model_validate(analysis)


def test_label_edit_is_atomic_and_preserves_immutable_structure(details):
    after = deepcopy(details)
    after["subjects"]["items"][0].update(kind="graphic", roles=["presenter", "product_user"],
                                         label="示意人物", description="人物的示意图。")
    after["actions"]["items"][0].update(action_type="operate", description="操作杯盖。")
    after["product_presentations"]["items"][0].update(presentation_type="use_case", description="示范开盖。")
    correction = Correction(target_type="event", target_id="event_visual", field="visual_details",
                            before=details, after=after)
    assert correction.before == details
    assert correction.after == after
    assert validate_visual_details_correction(details, after).subjects.items[0].label == "示意人物"


@pytest.mark.parametrize("mutation", [
    lambda d: d["subjects"]["items"].reverse(),
    lambda d: d["product_presentations"]["items"].reverse(),
    lambda d: d["subjects"]["items"][0].update(subject_id="new_subject"),
    lambda d: d["actions"]["items"].append(deepcopy(d["actions"]["items"][0])),
    lambda d: d["actions"]["items"][0].update(actor_subject_ids=[]),
    lambda d: d["actions"]["items"][0].update(target_subject_ids=[]),
    lambda d: d["subjects"]["items"][1].update(roles=["context"]),
    lambda d: d.update(actions={"status": "none_found", "items": [], "error": None}),
    lambda d: d.update(actions={"status": "failed", "items": [], "error": {"code": "failed", "message": "Failed"}}),
])
def test_corrections_reject_structure_and_inconsistent_product_roles(details, mutation):
    after = deepcopy(details)
    mutation(after)
    with pytest.raises(ValueError):
        validate_visual_details_correction(details, after)


def test_missing_or_failed_groups_cannot_be_fabricated_by_correction(details):
    with pytest.raises(ValueError, match="missing extraction"):
        validate_visual_details_correction(None, details)
    with pytest.raises(ValueError, match="missing extraction"):
        validate_visual_details_correction(details, None)
    before = deepcopy(details)
    before["actions"] = {"status": "failed", "items": [], "error": {"code": "failed", "message": "Original failure"}}
    after = deepcopy(before)
    after["actions"]["error"]["message"] = "Rewritten failure"
    with pytest.raises(ValueError, match="errors"):
        validate_visual_details_correction(before, after)


def test_full_state_requires_complete_nested_correction_replay(details):
    data = json.loads((ROOT / "examples/v0.6.sample-task.json").read_text())
    for item in data["analyses"]:
        item["events"][0]["visual_details"] = deepcopy(details)
    revised = data["analyses"][-1]
    revised["events"][0]["visual_details"]["subjects"]["items"][0]["label"] = "修正人物"
    with pytest.raises(ValidationError, match="complete correction log"):
        TaskState.model_validate(data)
    revised["corrections"].append({"target_type": "event", "target_id": revised["events"][0]["event_id"],
                                  "field": "visual_details", "before": details,
                                  "after": deepcopy(revised["events"][0]["visual_details"])})
    state = TaskState.model_validate(data)
    assert state.analyses[0].events[0].visual_details.subjects.items[0].label != "修正人物"
    validate_state(state)
    revised["corrections"][-1]["before"]["subjects"]["items"][0]["label"] = "invented history"
    with pytest.raises(ValidationError, match="before-value"):
        TaskState.model_validate(data)


def test_playback_retains_source_metadata_and_uses_its_own_clock():
    original = json.loads((ROOT / "examples/v0.6.sample-task.json").read_text())["videos"][0]
    source = deepcopy(original)
    proxy_timing = deepcopy(original["frame_timing"])
    proxy_timing["media_start_seconds"] = 1.5
    proxy_timing["frame_boundaries_seconds"][-1] = 10.01
    original["playback"] = {"storage_id": "f" * 32 + ".mp4", "video_codec": "h264", "audio_codec": "aac",
                            "duration_seconds": 10.01, "frame_timing": proxy_timing}
    video = VideoAsset.model_validate(original)
    assert video.frame_timing == VideoAsset.model_validate(source).frame_timing
    assert video.content_sha256 == source["content_sha256"]
    assert video.playback.frame_timing.media_start_seconds == 1.5
    invalid = deepcopy(original["playback"])
    invalid["duration_seconds"] = 10
    with pytest.raises(ValidationError, match="playback final frame"):
        PlaybackRepresentation.model_validate(invalid)
    original["playback"]["frame_timing"]["frame_count"] -= 1
    original["playback"]["frame_timing"]["frame_boundaries_seconds"].pop(-2)
    with pytest.raises(ValidationError, match="one presentation frame"):
        VideoAsset.model_validate(original)


def test_generated_schema_enforces_group_local_status_and_unknown_values(analysis):
    validator = Draft202012Validator(json.loads((ROOT / "contracts/v0.6.analysis.schema.json").read_text()))
    for mutate in (
        lambda d: d["subjects"].update(status="none_found"),
        lambda d: d["actions"].update(error={"code": "failed", "message": "Failed", "retryable": False}),
        lambda d: d["subjects"]["items"][0].update(kind="other", description=None),
        lambda d: d["subjects"]["items"][0].update(roles=["presenter", "presenter"]),
        lambda d: d["subjects"]["items"][0].update(label="  "),
    ):
        invalid = deepcopy(analysis)
        mutate(invalid["events"][0]["visual_details"])
        assert list(validator.iter_errors(invalid))
