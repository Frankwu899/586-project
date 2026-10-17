"""The deliberately limited legacy import preserves fixtures and uncertainty."""
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from backend.app.migration import migrate_legacy_analysis, migrate_legacy_examples
from backend.app.models import TaskState

ROOT = Path(__file__).resolve().parents[1]
LEGACY_HASHES = {
    "contracts/analysis.schema.json": "801045a9d2980889cd85506fe2f0badea90c7a148d5731c4208ebea2679078f8",
    "examples/analysis_result.original.json": "32b67e7ded06dedbfd8728ab9652aad3cedab2cf306de24c97b81404fb7a5b1d",
    "examples/analysis_result.json": "bacc106164c335ee33984f9ea71bee3c2eb570fe660aa8dd8a7e972c83502d59",
    "contracts/v0.2.analysis.schema.json": "ddc12af3674392b62d79426923466a2ec65c79285ef693579d2af885f32815e4",
    "contracts/v0.2.task-state.schema.json": "6a6b536ad5bf50d0424f55a214cd4d3ce472b36fc631f58fe028c3b6d21ed9bd",
    "examples/v0.2.sample-task.json": "9c0ee5cd7726d5cd356b73b025d2be179699efe9e4ea21a21df5034980aba121",
    "examples/v0.2.legacy-migrated.json": "0ea9654d6624cfb37ba8b56bd2d291b84ec1f62601d29af7eb7290788a1f9c7f",
    "contracts/v0.3.analysis.schema.json": "b9f49a0203038d9c8839c7caad155f2b115554a7609653bbdab0649c8c1c186e",
    "contracts/v0.3.task-state.schema.json": "c6708d93634c696578098527dd9451233416e6c15bc18229699dccf8daa9c51b",
    "examples/v0.3.sample-task.json": "e2020a6b362d9a7a336d6b1bd4482cdfbcef6c3f98946e519dcb932973b679f3",
    "examples/v0.3.legacy-migrated.json": "cdf0419b0a2d1a339ba4cabf1abb98846fbcd412c6291f4c35da97ec7f40174d",
}


def legacy():
    return (json.loads((ROOT / "examples/analysis_result.original.json").read_text()),
            json.loads((ROOT / "examples/analysis_result.json").read_text()))


def test_legacy_bytes_preserved_and_both_supplied_examples_validate():
    for path, digest in LEGACY_HASHES.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    schema = json.loads((ROOT / "contracts/analysis.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for example in legacy():
        validator.validate(example)


def test_migration_keeps_synthetic_origin_unknown_metrics_and_missing_media():
    original, revised = legacy()
    state = migrate_legacy_examples(original, revised)
    assert state == TaskState.model_validate_json((ROOT / "examples/v0.4.legacy-migrated.json").read_text())
    assert state.task.task_id == original["project_id"]
    assert state.task.mode == "sample"
    video = state.videos[0]
    assert video.frame_timing is None
    assert video.intake_status == "missing" and video.storage_id is None
    assert video.original_file_name == "SYNTHETIC_LumaCup_demo_NO_MEDIA.mp4"
    assert video.public_metrics.views is None
    assert video.public_metrics.likes is None
    assert video.public_metrics.comments is None
    assert video.source_url == original["video"]["source_url"]
    for analysis in state.analyses:
        assert analysis.frame_count is None
        assert all(event.start_frame is None and event.end_frame is None for event in analysis.events)
        assert all(event.legacy_seconds is not None for event in analysis.events)
        assert analysis.origin.kind == "sample"
        assert "synthetic_fixture_not_an_api_run" in analysis.origin.description
        assert all(event.method == "legacy_v0.1_import" for event in analysis.events)
        assert analysis.coverage.music == "not_analyzed"
        assert analysis.coverage.sfx == "not_analyzed"
        assert any(event.kind == "speech" and event.text == "Meet LumaCup." for event in analysis.events)
    assert state.analyses[0].segments[1].interpretation is not None
    assert state.analyses[1].segments[1].interpretation is None
    assert len(state.analyses[1].corrections) == 2
    assert state.analyses[1].review.user_confirmed
    assert {event.event_id for event in state.analyses[0].events} == {event.event_id for event in state.analyses[1].events}


def test_revised_import_requires_matching_preserved_original():
    original, revised = legacy()
    with pytest.raises(ValueError, match="preserved original"):
        migrate_legacy_analysis(revised)
    original["project_id"] = "task_other"
    with pytest.raises(ValueError, match="match analysis/project/video"):
        migrate_legacy_analysis(revised, original)


def test_unknown_speech_does_not_become_a_checked_silent_source():
    original, _ = legacy()
    for segment in original["segments"]:
        segment["spoken_text"] = None
    analysis = migrate_legacy_analysis(original)
    assert analysis.coverage.speech == "not_analyzed"
    assert not any(event.kind == "speech" for event in analysis.events)


def test_empty_text_and_missing_text_remain_distinct():
    original, _ = legacy()
    original["segments"][0]["spoken_text"] = ""
    original["segments"][1]["spoken_text"] = None
    analysis = migrate_legacy_analysis(original)
    speech = [event for event in analysis.events if event.kind == "speech"]
    assert speech[0].text == ""
    assert len(speech) == 2
