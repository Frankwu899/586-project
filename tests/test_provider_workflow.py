"""Real local media + fake model results through the complete HTTP workflow."""
from copy import deepcopy
from dataclasses import replace
import io
import json
import subprocess

from fastapi.testclient import TestClient
import pytest

from backend.app.api import create_app
from backend.app.providers.creative import OpenAICreativeAdapter
from backend.app.service import find
from scripts.offline_provider_fixtures import fixture_service


@pytest.fixture
def uploaded(tmp_path):
    source = tmp_path / "synthetic.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x64:r=8:d=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264",
                    "-threads", "1", "-c:a", "aac", "-shortest", str(source)], check=True)
    service = fixture_service(tmp_path / "data")
    client = TestClient(create_app(service=service))
    state = client.post("/api/tasks", json={"title": "Offline 中文 provider workflow"}).json()
    task_id = state["task"]["task_id"]
    response = client.post(f"/api/tasks/{task_id}/video", data={"expected_version": state["task"]["version"]},
                           files={"file": ("synthetic.mp4", io.BytesIO(source.read_bytes()), "video/mp4")})
    assert response.status_code == 200, response.text
    return service, client, response.json()


def mutate(client, state, route, **fields):
    response = client.post(f"/api/tasks/{state['task']['task_id']}/{route}",
                           json={"expected_version": state["task"]["version"], **fields})
    assert response.status_code == 200, response.text
    result = response.json()
    assert not any(job["status"] == "failed" for job in result["jobs"]), result["jobs"]
    return result


def recognize(client, state):
    state = mutate(client, state, "brief", brief={
        "brand_company": "DemoCup 品牌", "product": "随行杯", "selling_points": ["方便携带"],
        "approved_messages": ["通勤随行 · Take it anywhere"], "target_audience": "commuters 通勤者",
        "platform": "short video", "communication_goal": "认识品牌", "target_duration_seconds": 12,
        "prohibited_claims": ["未经验证的保温、转化率提升"], "production_limits": "No presenter；预算有限",
    })
    return mutate(client, state, "recognize")


def test_mocked_upload_to_corrected_review_and_approved_production(uploaded, tmp_path):
    service, client, state = uploaded
    service.provider_settings = replace(service.provider_settings, cache_dir=tmp_path / "diagnostics")
    state = recognize(client, state)
    original = deepcopy(state["analyses"][0])
    assert original["status"] == "succeeded" and not original["review"]["user_confirmed"]
    assert original["coverage"]["music"] == "not_analyzed"
    assert any(event["text"] == "这款 DemoCup，take it anywhere。" for event in original["events"])
    visual = next(event for event in original["events"] if event["kind"] == "visual_action")
    details = deepcopy(visual["visual_details"])
    details["subjects"]["items"][0]["label"] = "修正：DemoCup 红杯"
    details["actions"]["items"][0]["action_type"] = None
    details["actions"]["items"][0]["description"] = "Cannot establish movement from this still image."
    state = mutate(client, state, "analysis/correct", analysis_ref=state["task"]["current_analysis"],
                   event_edits=[{"event_id": visual["event_id"], "visual_details": details}])
    assert state["analyses"][0] == original
    assert state["analyses"][-1]["corrections"][0]["before"] == visual["visual_details"]
    state = mutate(client, state, "analysis/confirm", analysis_ref=state["task"]["current_analysis"])
    inputs = {"brief_ref": state["task"]["current_brief"], "analysis_ref": state["task"]["current_analysis"]}
    state = mutate(client, state, "directions/generate", **inputs)
    assert len(state["directions"]) == 2
    direction = state["directions"][0]
    assert all(e["analysis_revision"] == 2 for e in direction["evidence"])
    state = mutate(client, state, f"directions/{direction['direction_id']}/refine", **inputs,
                   direction_revision=direction["revision"], instruction="不要人物出镜，保留 DemoCup 品牌。")
    direction = state["directions"][-1]
    assert "不要人物出镜" in direction["hook"]
    assert direction["approval_status"] == "draft"
    state = mutate(client, state, f"directions/{direction['direction_id']}/approve", **inputs,
                   direction_revision=direction["revision"])
    state = mutate(client, state, "outputs/generate", **inputs, direction_ref=state["task"]["selected_direction"])
    assert state["storyboards"][-1]["rows"][-1]["end_seconds"] == 12
    assert "DemoCup" in client.get(f"/api/tasks/{state['task']['task_id']}/export/storyboard.csv").text
    assert "制作简报" in client.get(f"/api/tasks/{state['task']['task_id']}/export/brief.md").text
    output_id = state["task"]["current_production_brief"]["id"]
    state = mutate(client, state, "outputs/generate", **inputs, direction_ref=state["task"]["selected_direction"])
    assert state["task"]["current_production_brief"] == {"id": output_id, "revision": 2}
    records = [json.loads(line) for line in (tmp_path / "diagnostics/runs.jsonl").read_text().splitlines()]
    completion = records[-1]
    assert completion["record_type"] == "persisted_job_result"
    assert completion["job_id"] == state["jobs"][-1]["job_id"]
    assert completion["output_refs"] == [
        {"type": "production_brief", **state["task"]["current_production_brief"]},
        {"type": "storyboard", **state["task"]["current_storyboard"]},
    ]
    details["subjects"]["items"][0]["label"] = "Second correction 第二次"
    state = mutate(client, state, "analysis/correct", analysis_ref=state["task"]["current_analysis"],
                   event_edits=[{"event_id": visual["event_id"], "visual_details": details}])
    assert not state["analyses"][-1]["review"]["user_confirmed"]
    assert state["task"]["selected_direction"] is None
    assert all(item["currentness"] == "outdated" for item in state["storyboards"] + state["directions"])
    assert state["analyses"][0] == original
    restored = service.store.get(state["task"]["task_id"])
    assert find(restored.analyses, restored.task.current_analysis).revision == 3


def test_structured_api_edit_rejects_relationship_shape_status_and_stale_changes(uploaded):
    _, client, state = uploaded
    state = recognize(client, state)
    visual = next(event for event in state["analyses"][-1]["events"] if event["visual_details"])
    details = visual["visual_details"]
    variants = []
    for field, value in (("subject_id", "changed_id"), ("roles", ["context"])):
        changed = deepcopy(details)
        changed["subjects"]["items"][0][field] = value
        variants.append(changed)
    changed = deepcopy(details)
    changed["actions"]["items"][0]["actor_subject_ids"] = []
    variants.append(changed)
    changed = deepcopy(details)
    changed["subjects"]["items"].append(deepcopy(changed["subjects"]["items"][0]))
    variants.append(changed)
    changed = deepcopy(details)
    changed["actions"] = {"status": "none_found", "items": [], "error": None}
    variants.append(changed)
    for changed in variants:
        response = client.post(f"/api/tasks/{state['task']['task_id']}/analysis/correct", json={
            "expected_version": state["task"]["version"], "analysis_ref": state["task"]["current_analysis"],
            "event_edits": [{"event_id": visual["event_id"], "visual_details": changed}],
        })
        assert response.status_code == 422, response.text
    changed = deepcopy(details)
    changed["subjects"]["items"][0]["label"] = "合法修改"
    previous = state
    state = mutate(client, state, "analysis/correct", analysis_ref=state["task"]["current_analysis"],
                   event_edits=[{"event_id": visual["event_id"], "visual_details": changed}])
    response = client.post(f"/api/tasks/{state['task']['task_id']}/analysis/correct", json={
        "expected_version": previous["task"]["version"], "analysis_ref": previous["task"]["current_analysis"],
        "event_edits": [{"event_id": visual["event_id"], "visual_details": details}],
    })
    assert response.status_code == 409


def test_real_creative_missing_configuration_has_no_sample_fallback(uploaded):
    service, client, state = uploaded
    state = recognize(client, state)
    state = mutate(client, state, "analysis/confirm", analysis_ref=state["task"]["current_analysis"])
    service.real_creative = OpenAICreativeAdapter(service.provider_settings)
    response = client.post(f"/api/tasks/{state['task']['task_id']}/directions/generate", json={
        "expected_version": state["task"]["version"], "brief_ref": state["task"]["current_brief"],
        "analysis_ref": state["task"]["current_analysis"],
    })
    assert response.status_code == 200
    result = response.json()
    assert result["jobs"][-1]["status"] == "failed"
    assert result["jobs"][-1]["error"]["code"] == "provider_not_configured"
    assert result["directions"] == []
    health = client.get("/api/health").json()
    assert health["creative_generation"] == "unconfigured_for_real_tasks"
    assert health["sample_workflow"] == "available_offline"
