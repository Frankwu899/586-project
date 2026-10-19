"""Preserve exact v0.3 originals and every historical review/citation on upgrade."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from backend.app.contract_migration import migrate_v03_task
from backend.app.storage import TaskStore, WorkflowError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def legacy():
    return json.loads((ROOT / "examples/v0.3.sample-task.json").read_text())


def install(root, payload):
    raw = json.dumps(payload, indent=3, ensure_ascii=False) + "\n"
    with sqlite3.connect(root / "tasks.sqlite3") as db:
        db.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL)")
        db.execute("INSERT INTO tasks VALUES (?, ?, ?)", (payload["task"]["task_id"], payload["task"]["version"], raw))
    return raw


def test_v03_upgrade_preserves_all_content_review_history_and_citations(legacy):
    untouched = deepcopy(legacy)
    state = migrate_v03_task(legacy)
    assert legacy == untouched
    converted = state.model_dump(mode="json")
    assert converted["task"]["version"] == legacy["task"]["version"] + 1
    converted["task"]["version"] -= 1
    for record in [converted["task"], *(r for values in converted.values() if isinstance(values, list) for r in values)]:
        assert record["schema_version"] == "0.6.0"
        record["schema_version"] = "0.3.0"
    for brief in converted["briefs"]:
        details = brief.pop("claim_details")
        assert [claim["statement"] for claim in details] == brief["selling_points"]
        assert all(claim["confirmation_origin"] == "legacy_unrecorded" for claim in details)
    assert converted["task"].pop("generation_language") is None
    for direction in converted["directions"]:
        assert direction.pop("auxiliary_status") == "current"
        assert direction.pop("structure_handoff_id") is None
    for output in [*converted["production_briefs"], *converted["storyboards"]]:
        assert output.pop("bundle_id") is None
    for video in converted["videos"]:
        assert video.pop("deleted_at") is None
        assert video.pop("playback") is None
    for analysis in converted["analyses"]:
        assert analysis.pop("extraction_failures") == {}
        assert analysis.pop("output_language") is None
        for event in analysis["events"]:
            assert event.pop("visual_details") is None
    assert converted == untouched


def test_storage_archives_unchanged_payload_once_and_rejects_old_task_version(tmp_path, legacy):
    raw = install(tmp_path, legacy)
    store = TaskStore(tmp_path)
    state = store.get(legacy["task"]["task_id"])
    assert TaskStore(tmp_path).get(state.task.task_id) == state
    with sqlite3.connect(store.path) as db:
        rows = db.execute("SELECT source_schema_version, target_schema_version, original_payload, original_sha256 FROM task_migration_archive").fetchall()
    assert rows == [("0.3.0", "0.6.0", raw, hashlib.sha256(raw.encode()).hexdigest())]
    with pytest.raises(WorkflowError, match="changed"):
        store.update(state.task.task_id, legacy["task"]["version"], lambda state: None)


def test_invalid_historical_replay_rolls_back_entire_migration(tmp_path, legacy):
    legacy["analyses"][-1]["corrections"][0]["before"] = "Not the preserved original"
    raw = install(tmp_path, legacy)
    with pytest.raises(ValueError, match="before-value"):
        TaskStore(tmp_path)
    with sqlite3.connect(tmp_path / "tasks.sqlite3") as db:
        assert db.execute("SELECT payload FROM tasks").fetchone()[0] == raw
        assert db.execute("SELECT COUNT(*) FROM task_migration_archive").fetchone()[0] == 0


def test_missing_timing_legacy_nulls_are_preserved():
    old = json.loads((ROOT / "examples/v0.3.legacy-migrated.json").read_text())
    state = migrate_v03_task(old)
    assert state.videos[0].playback is None and state.videos[0].frame_timing is None
    assert state.videos[0].public_metrics.views is None
    assert state.analyses[-1].review.model_dump(mode="json") == old["analyses"][-1]["review"]
    for analysis in state.analyses:
        assert all(event.visual_details is None and event.legacy_seconds is not None for event in analysis.events)
