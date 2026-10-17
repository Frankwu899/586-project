"""Upgrade saved edits without inventing timing or destroying the original JSON."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess

import pytest

from backend.app.frame_migration import migrate_v02_task
from backend.app.models import TaskState
from backend.app.storage import TaskStore, WorkflowError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def legacy_payload():
    return json.loads((ROOT / "examples/v0.2.sample-task.json").read_text())


@pytest.fixture(scope="module")
def source_clip(tmp_path_factory):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg and ffprobe are required")
    path = tmp_path_factory.mktemp("migration-media") / "source.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "color=c=blue:s=64x64:r=20:d=10", "-c:v", "libx264", "-pix_fmt",
                    "yuv420p", str(path)], check=True)
    return path


def install_media(root, payload, source_clip):
    directory = root / "media"
    directory.mkdir(parents=True)
    shutil.copyfile(source_clip, directory / payload["videos"][0]["storage_id"])
    payload["videos"][0]["content_sha256"] = hashlib.sha256(source_clip.read_bytes()).hexdigest()
    return directory


def put_legacy(root, payload):
    root.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, indent=3) + "\n"
    with sqlite3.connect(root / "tasks.sqlite3") as db:
        db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL)")
        db.execute("INSERT INTO tasks VALUES (?, ?, ?)",
                   (payload["task"]["task_id"], payload["task"]["version"], raw))
    return raw


def test_readable_media_preserves_edits_approval_refs_and_storyboard_seconds(tmp_path, legacy_payload, source_clip):
    media_root = install_media(tmp_path, legacy_payload, source_clip)
    original = deepcopy(legacy_payload)
    state = migrate_v02_task(legacy_payload, media_root)
    assert legacy_payload == original  # Conversion cannot mutate the source backup.
    assert state.task.schema_version == "0.4.0"
    assert state.task.version == legacy_payload["task"]["version"] + 1
    assert state.videos[0].frame_timing.frame_count == 200
    assert state.videos[0].frame_timing.fps_numerator == 20
    assert state.task.selected_direction.model_dump() == original["task"]["selected_direction"]
    converted = state.model_dump(mode="json")
    for collection in ("briefs", "directions", "feedback", "production_briefs", "storyboards", "jobs"):
        for before, after in zip(original[collection], converted[collection], strict=True):
            assert after == {**before, "schema_version": "0.4.0"}
    for before, after in zip(original["analyses"], converted["analyses"], strict=True):
        assert after["review"] == before["review"]
        assert after["corrections"] == before["corrections"]
        assert after["frame_count"] == 200
        for collection in ("events", "segments"):
            for old_interval, new_interval in zip(before[collection], after[collection], strict=True):
                old = dict(old_interval)
                if collection == "events":
                    old["visual_details"] = None
                start, end = old.pop("start_seconds"), old.pop("end_seconds")
                assert new_interval == {**old, "start_frame": round(start * 20),
                                        "end_frame": round(end * 20), "legacy_seconds": None}


def test_startup_migration_archives_exact_original_once(tmp_path, legacy_payload, source_clip):
    install_media(tmp_path, legacy_payload, source_clip)
    original_raw = put_legacy(tmp_path, legacy_payload)
    task_id = legacy_payload["task"]["task_id"]
    state = TaskStore(tmp_path).get(task_id)
    reopened = TaskStore(tmp_path)
    assert reopened.get(task_id) == state
    assert reopened.list() == [state]
    with sqlite3.connect(tmp_path / "tasks.sqlite3") as db:
        rows = db.execute("SELECT original_payload, original_sha256, original_task_version, migrated_task_version FROM task_migration_archive").fetchall()
    assert rows == [(original_raw, hashlib.sha256(original_raw.encode()).hexdigest(),
                     legacy_payload["task"]["version"], state.task.version)]
    with pytest.raises(WorkflowError, match="changed"):
        reopened.update(task_id, legacy_payload["task"]["version"], lambda task: None)
    assert reopened.get(task_id) == state


def test_rows_added_after_startup_migrate_on_load(tmp_path, legacy_payload):
    store = TaskStore(tmp_path)
    original_raw = put_legacy(tmp_path, legacy_payload)
    state = store.list()[0]
    assert state.task.schema_version == "0.4.0"
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT original_payload FROM task_migration_archive").fetchone()[0] == original_raw


def test_early_v02_rows_without_optional_draft_selection_still_migrate(tmp_path, legacy_payload, source_clip):
    install_media(tmp_path, legacy_payload, source_clip)
    legacy_payload["task"].pop("chosen_direction")
    original_raw = put_legacy(tmp_path, legacy_payload)
    state = TaskStore(tmp_path).get(legacy_payload["task"]["task_id"])
    assert state.task.chosen_direction is None
    assert state.task.selected_direction.model_dump() == legacy_payload["task"]["selected_direction"]
    with sqlite3.connect(tmp_path / "tasks.sqlite3") as db:
        assert db.execute("SELECT original_payload FROM task_migration_archive").fetchone()[0] == original_raw


def test_replaced_media_does_not_supply_a_false_frame_map(tmp_path, legacy_payload, source_clip):
    original_digest = legacy_payload["videos"][0]["content_sha256"]
    media_root = install_media(tmp_path, legacy_payload, source_clip)
    legacy_payload["videos"][0]["content_sha256"] = original_digest
    state = migrate_v02_task(legacy_payload, media_root)
    assert state.videos[0].frame_timing is None
    assert "original content hash" in state.videos[0].error.message
    assert state.analyses[-1].review.model_dump(mode="json") == legacy_payload["analyses"][-1]["review"]
    assert all(interval.legacy_seconds is not None for interval in state.analyses[0].events)


def test_missing_media_keeps_seconds_and_user_content_without_inventing_rate(tmp_path, legacy_payload):
    state = migrate_v02_task(legacy_payload, tmp_path)
    assert state.videos[0].frame_timing is None
    assert state.videos[0].intake_status == "missing"
    assert state.videos[0].error.code == "legacy_frame_timing_unavailable"
    assert state.task.selected_direction is None
    assert state.task.chosen_direction is None
    assert state.task.progress == "review"
    assert all(output.currentness == "outdated" for output in state.storyboards + state.production_briefs)
    assert all(direction.approval_status == "draft" for direction in state.directions)
    for old, analysis in zip(legacy_payload["analyses"], state.analyses, strict=True):
        assert analysis.frame_count is None
        assert analysis.review.model_dump(mode="json") == old["review"]
        assert [item.model_dump() for item in analysis.corrections] == old["corrections"]
        for collection in ("events", "segments"):
            for before, after in zip(old[collection], getattr(analysis, collection), strict=True):
                assert after.start_frame is None and after.end_frame is None
                assert after.legacy_seconds.model_dump() == {key: before[key] for key in ("start_seconds", "end_seconds")}
    for old, storyboard in zip(legacy_payload["storyboards"], state.storyboards, strict=True):
        assert [row.model_dump() for row in storyboard.rows] == old["rows"]


def test_unrepresentable_subframe_sections_preserve_all_links_as_archived_seconds(tmp_path, legacy_payload, source_clip):
    media_root = install_media(tmp_path, legacy_payload, source_clip)
    for analysis in legacy_payload["analyses"]:
        analysis["segments"][0].update(start_seconds=0, end_seconds=.01, evidence_ids=[])
        analysis["segments"][1].update(start_seconds=.01, end_seconds=.02, evidence_ids=[])
        analysis["segments"][2].update(start_seconds=.02, end_seconds=10, evidence_ids=[])
    state = migrate_v02_task(legacy_payload, media_root)
    assert state.videos[0].frame_timing is None
    assert "cannot be converted" in state.videos[0].error.message
    assert state.analyses[0].segments[1].legacy_seconds.end_seconds == .02
    assert state.analyses[-1].corrections


def test_failed_migration_is_atomic_and_keeps_unmodified_original(tmp_path, legacy_payload, source_clip):
    install_media(tmp_path, legacy_payload, source_clip)
    # JSON Schema permits this string, but the cumulative correction replay must reject it.
    legacy_payload["analyses"][-1]["corrections"][0]["before"] = "Broken original value"
    raw = put_legacy(tmp_path, legacy_payload)
    with pytest.raises(ValueError, match="before-value"):
        TaskStore(tmp_path)
    with sqlite3.connect(tmp_path / "tasks.sqlite3") as db:
        assert db.execute("SELECT payload FROM tasks").fetchone()[0] == raw
        assert db.execute("SELECT COUNT(*) FROM task_migration_archive").fetchone()[0] == 0


def test_new_fixture_validates_and_old_sample_remains_seconds():
    state = TaskState.model_validate_json((ROOT / "examples/v0.4.sample-task.json").read_text())
    assert state.videos[0].frame_timing.frame_count == 200
    old = json.loads((ROOT / "examples/v0.2.sample-task.json").read_text())
    assert old["task"]["schema_version"] == "0.2.0"
    assert "start_seconds" in old["analyses"][0]["events"][0]
