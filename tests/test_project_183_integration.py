"""Cross-module compatibility and exact-snapshot checks with paid calls forbidden."""
from copy import deepcopy
import csv
import hashlib
import io
from pathlib import Path
import runpy

from fastapi.testclient import TestClient
import pytest

from backend.app.api import create_app
from backend.app.project_workspace.store import ProjectStore
from backend.app.providers.transport import OpenAITransport
from backend.app.workflow_errors import WorkflowError


_SEED = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                            "frontend/e2e/project-release-183-fixtures.py"))["seed_legacy_project"]


@pytest.fixture
def integrated(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("RUN_LIVE_MODEL_TESTS", "0")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Cross-module persistence checks must not call a paid provider")

    monkeypatch.setattr(OpenAITransport, "_request", forbidden)
    receipt = _SEED(tmp_path)
    app = create_app(tmp_path)
    with TestClient(app) as client:
        yield client, app.state.project_workspace, receipt, tmp_path


def _base(receipt):
    return "/api/projects/" + receipt["project"]["id"]


def _change(client, base, path, values=None, method="POST"):
    project = client.get(base).json()
    response = client.request(method, base + path,
                              json={"expected_version": project["version"], **(values or {})})
    assert response.status_code == 200, response.text
    return response.json()


def _old_fields(project):
    """Project a new record onto the original fixture's 1.8.2 fields."""
    result = deepcopy(project)
    result.pop("resource_folders", None)
    result.pop("topic_suggestions", None)
    for resource in result["resources"]:
        resource.pop("folder_id", None)
        resource.pop("trashed_at", None)
        for revision in resource["evidence"]:
            for event in revision["events"]:
                event.pop("precision", None)
    for message in result["messages"]:
        message.pop("attempt_id", None)
    for analysis in result["analyses"]:
        analysis.pop("key_insights", None)
    for pack in result["packs"]:
        pack.pop("sheet_format", None)
    return result


def test_old_project_adds_only_defaults_and_retains_all_saved_artifact_bytes(integrated):
    client, runtime, receipt, root = integrated
    loaded = client.get(_base(receipt)).json()
    assert _old_fields(loaded) == receipt["project"]
    assert {folder["id"] for folder in loaded["resource_folders"]} == {
        "folder_inbox", "folder_references", "folder_documents", "folder_production_assets"}
    resources = {resource["id"]: resource for resource in loaded["resources"]}
    assert resources["resource_legacy_reference"]["folder_id"] == "folder_references"
    assert resources["resource_legacy_document"]["folder_id"] == "folder_documents"
    assert loaded["packs"][0]["sheet_format"] == "legacy_documents"
    assert loaded["packs"][0]["shots"] == []
    assert loaded["active_content_id"] == "content_active_video"
    original = runtime.resources.path(loaded["id"], "resource_legacy_reference")
    assert hashlib.sha256(original.read_bytes()).hexdigest() == receipt["media_sha256"]
    assert ProjectStore(root).get(loaded["id"]).model_dump(mode="json") == loaded


def test_folder_and_file_lifecycle_preserve_exact_history_and_gate_new_work(integrated):
    client, runtime, receipt, _ = integrated
    base = _base(receipt)
    initial = client.get(base).json()
    rid = "resource_legacy_reference"
    source = next(resource for resource in initial["resources"] if resource["id"] == rid)
    with_folder = _change(client, base, "/folders", {"name": "A movable source folder"})
    folder_id = next(folder["id"] for folder in with_folder["resource_folders"]
                     if folder["name"] == "A movable source folder")
    moved = _change(client, base, "/resources/move", {"resource_ids": [rid], "folder_id": folder_id})
    renamed = _change(client, base, f"/resources/{rid}", {"name": "Renamed source.mp4"}, "PATCH")
    actual = next(resource for resource in renamed["resources"] if resource["id"] == rid)
    assert {key: value for key, value in actual.items() if key not in {"name", "folder_id"}} == {
        key: value for key, value in source.items() if key not in {"name", "folder_id"}}
    assert moved["selection"] == initial["selection"]
    assert renamed["analyses"] == initial["analyses"]
    assert renamed["contents"] == initial["contents"]
    assert renamed["packs"] == initial["packs"]
    response = client.get(base + f"/resources/{rid}/file")
    assert response.status_code == 200
    assert hashlib.sha256(response.content).hexdigest() == receipt["media_sha256"]

    trashed = _change(client, base, f"/resources/{rid}/trash")
    own_trash = next(resource for resource in trashed["resources"] if resource["id"] == rid)["trashed_at"]
    _change(client, base, f"/folders/{folder_id}/trash")
    restored_parent = _change(client, base, f"/folders/{folder_id}/restore")
    assert next(resource for resource in restored_parent["resources"] if resource["id"] == rid)["trashed_at"] == own_trash
    assert client.get(base + f"/resources/{rid}/file").status_code == 410
    with pytest.raises(WorkflowError) as error:
        runtime.planning.preflight_generation(initial["id"], "content_active_video")
    assert error.value.code == "reference_unavailable"
    with pytest.raises(WorkflowError):
        runtime.analysis.analyze(initial["id"], [rid])
    unavailable = client.get(base).json()
    assert unavailable["analyses"] == initial["analyses"]
    assert unavailable["active_content_id"] == initial["active_content_id"]
    _change(client, base, f"/resources/{rid}/restore")
    restored = client.get(base).json()
    assert restored["analyses"][0]["sources"][0] == receipt["old_source"]
    assert [event["text"] for revision in restored["resources"][0]["evidence"]
            for event in revision["events"]] == [
                "Original observation at one second.", "Human-corrected observation at three seconds."]
    assert hashlib.sha256(client.get(base + f"/resources/{rid}/file").content).hexdigest() == receipt["media_sha256"]


def test_new_original_video_does_not_inherit_project_references_or_require_their_analysis(integrated):
    client, _, receipt, _ = integrated
    base = _base(receipt)
    created = _change(client, base, "/contents", {"title": "An original standalone Video"})
    item = created["contents"][-1]
    assert item["series_id"] is None
    assert item["selection"]["resource_ids"] == []
    assert created["selection"]["resource_ids"] == ["resource_legacy_reference"]
    saved = _change(client, base, f"/contents/{item['id']}/directions", {
        "title": "A user-authored original direction", "concept": "A simple new introduction.",
        "hook": "", "narrative": "A handwritten creative approach.", "cta": ""})
    direction = saved["contents"][-1]["directions"][-1]
    _change(client, base, f"/contents/{item['id']}/directions/{direction['id']}/approve", {
        "revision": direction["revision"]})
    ready = _change(client, base, f"/contents/{item['id']}/production/manual")
    assert ready["packs"][-1]["content_id"] == item["id"]
    assert ready["packs"][-1]["inputs"]["resource_ids"] == []
    assert ready["jobs"] == []


def test_structured_sheet_save_reopen_and_csv_pin_the_same_revision_without_rewriting_legacy(integrated):
    client, _, receipt, root = integrated
    base = _base(receipt)
    legacy_csv = client.get(base + "/packs/pack_legacy_text/export?revision=1&format=csv")
    assert legacy_csv.status_code == 200
    assert "Hand-edited free-text storyboard" in legacy_csv.text
    assert "no synchronized structured shots" in legacy_csv.text
    assert "Framing / Camera" not in legacy_csv.text
    saved = _change(client, base, "/contents/content_active_video/directions", {
        "title": "Explicit new sheet direction", "concept": "A six-second commuter introduction.",
        "hook": "A simple opening", "narrative": "An authored plan", "cta": ""})
    direction = saved["contents"][0]["directions"][-1]
    _change(client, base, f"/contents/content_active_video/directions/{direction['id']}/approve", {
        "revision": direction["revision"]})
    created = _change(client, base, "/contents/content_active_video/production/manual")
    new_pack = created["packs"][-1]
    assert new_pack["content_id"] == "content_active_video"
    assert new_pack["sheet_format"] == "storyboard_sheet"
    shots = [{"id": "shot_first", "start_seconds": 0, "end_seconds": 3,
              "framing_camera": "Medium shot / locked-off", "visual": "Camera moves, then pauses.",
              "dialogue": "你好，commuters.\nA second line.", "on_screen_text": "Introduction",
              "sound": "Ambient", "notes": "Source timing stays separate.", "sources": [receipt["latest_source"]]},
             {"id": "shot_second", "start_seconds": 3, "end_seconds": 6,
              "framing_camera": "Close-up", "visual": "Hold the final frame.",
              "dialogue": "End.", "on_screen_text": "", "sound": "", "notes": ""}]
    values = {"revision": new_pack["revision"], "production_brief": "The short sheet brief.", "shots": shots}
    saved = _change(client, base, f"/packs/{new_pack['id']}", values)
    latest = saved["packs"][-1]
    assert latest["revision"] == 2
    assert [{key: shot[key] for key in shots[index] if key != "sources"}
            for index, shot in enumerate(latest["shots"])] == [
                {key: value for key, value in shot.items() if key != "sources"} for shot in shots]
    linked = latest["shots"][0]["sources"][0]
    assert (linked["resource_id"], linked["evidence_revision"], linked["event_id"],
            linked["start_seconds"], linked["end_seconds"]) == (
                "resource_legacy_reference", 2, "visual_corrected", 3, 3)
    wrong_time = deepcopy(shots)
    wrong_time[0]["sources"][0]["start_seconds"] = 5
    wrong_time[0]["sources"][0]["end_seconds"] = 5
    rejected = client.post(base + f"/packs/{new_pack['id']}", json={
        "expected_version": saved["version"], "revision": 2, "shots": wrong_time})
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "invalid_generation_citation"
    assert client.get(base).json()["packs"][-1] == latest
    reopened = ProjectStore(root).get(saved["id"])
    assert reopened.packs[-1].model_dump(mode="json") == latest
    exported = client.get(base + f"/packs/{new_pack['id']}/export?revision=2&format=csv")
    assert exported.status_code == 200
    rows = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert rows[0] == ["Shot", "Start", "End", "Framing / Camera", "Visual / Action", "Dialogue / VO",
                       "On-screen Text", "Music / SFX", "Production Notes"]
    assert len(rows) == 3
    assert rows[1] == ["01", "0.0", "3.0", *[shots[0][key] for key in (
        "framing_camera", "visual", "dialogue", "on_screen_text", "sound", "notes")]]
    assert not any("Input manifest" in cell or "Supporting reference" in cell for row in rows for cell in row)
    unchanged = _change(client, base, f"/packs/{new_pack['id']}", {**values, "revision": 2})
    assert unchanged["packs"][-1]["revision"] == 2
    edited_shots = deepcopy(shots)
    edited_shots[0]["dialogue"] = "A later human edit."
    revised = _change(client, base, f"/packs/{new_pack['id']}", {"revision": 2, "shots": edited_shots})
    assert revised["packs"][-1]["revision"] == 3
    assert client.get(base + f"/packs/{new_pack['id']}/export?revision=2&format=csv").content == exported.content
    current_csv = client.get(base + f"/packs/{new_pack['id']}/export?revision=3&format=csv")
    assert "A later human edit." in current_csv.text
    legacy_after = client.get(base + "/packs/pack_legacy_text/export?revision=1&format=csv")
    # A new approved direction legitimately marks the old pack as needing review.
    # Its status metadata may change; saved document rows and provenance may not.
    assert list(csv.reader(io.StringIO(legacy_after.content.decode("utf-8-sig"))))[1:] == list(
        csv.reader(io.StringIO(legacy_csv.content.decode("utf-8-sig"))))[1:]
    assert next(pack for pack in unchanged["packs"] if pack["id"] == "pack_legacy_text")["shots"] == []
    grouped = _change(client, base, "/series", {"title": "Optional series", "concept": "A shared format"})
    series_id = grouped["series"][-1]["id"]
    attached = _change(client, base, "/contents/content_active_video", {"series_id": series_id}, "PATCH")
    assert attached["contents"][0]["id"] == "content_active_video"
    assert attached["contents"][0]["series_id"] == series_id
    assert [(pack["id"], pack["revision"], pack["content_id"]) for pack in attached["packs"]] == [
        (pack["id"], pack["revision"], pack["content_id"]) for pack in revised["packs"]]
    standalone = _change(client, base, "/contents/content_active_video", {"series_id": None}, "PATCH")
    assert standalone["contents"][0]["id"] == "content_active_video"
    assert standalone["contents"][0]["series_id"] is None
    assert standalone["packs"][-1]["shots"] == revised["packs"][-1]["shots"]
