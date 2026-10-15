"""HTTP integration, durable reopening, upload honesty, and safe exports."""
import csv
import io

from fastapi.testclient import TestClient

from backend.app.api import create_app


def post(client, task, suffix, **body):
    response = client.post(f"/api/tasks/{task['task']['task_id']}/{suffix}", json={"expected_version": task["task"]["version"], **body})
    assert response.status_code == 200, response.text
    return response.json()


def loaded(client):
    task = client.post("/api/tasks", json={"title": "Persistent API sample"}).json()
    task = post(client, task, "sample")
    return post(client, task, "recognize")


def produced(client):
    task = loaded(client)
    task = post(client, task, "analysis/confirm", analysis_ref=task["task"]["current_analysis"])
    inputs = {"brief_ref": task["task"]["current_brief"], "analysis_ref": task["task"]["current_analysis"]}
    task = post(client, task, "directions/generate", **inputs)
    direction = task["directions"][0]
    task = post(client, task, f"directions/{direction['direction_id']}/approve", direction_revision=direction["revision"], **inputs)
    return post(client, task, "outputs/generate", direction_ref=task["task"]["selected_direction"], **inputs)


def test_api_restart_range_export_and_invalid_mutation(tmp_path):
    client = TestClient(create_app(tmp_path))
    task = produced(client)
    task_id = task["task"]["task_id"]
    video = task["videos"][0]
    assert client.get("/api/health").json()["schema_version"] == "0.3.0"
    assert video["frame_timing"]["fps_numerator"] == 20
    assert video["frame_timing"]["frame_count"] == 200
    assert task["analyses"][0]["events"][0]["start_frame"] == 0
    assert "start_seconds" not in task["analyses"][0]["events"][0]
    url = f"/api/tasks/{task_id}/media/{video['video_id']}"
    response = client.get(url, headers={"Range": "bytes=0-99"})
    assert response.status_code == 206 and len(response.content) == 100
    assert response.headers["content-range"].startswith("bytes 0-99/")
    assert client.get(url, headers={"Range": "bytes=999999999-"}).status_code == 416
    rows = task["storyboards"][-1]["rows"]
    rows[0]["visual"] = '=SUM(A1,A2), "quoted"\nsecond line'
    task = post(client, task, "outputs/edit", production_brief_ref=task["task"]["current_production_brief"], storyboard_ref=task["task"]["current_storyboard"], brief_fields={"core_message": "<script>alert(1)</script> [link](javascript:alert(1))"}, rows=rows)
    exported = client.get(f"/api/tasks/{task_id}/export/storyboard.csv")
    parsed = list(csv.DictReader(io.StringIO(exported.text)))
    assert parsed[0]["visual"] == "'" + rows[0]["visual"]
    assert parsed[0]["origin"] == "sample" and parsed[0]["status"] == "current"
    assert float(parsed[-1]["planned_end_seconds"]) == 15
    assert "planned_end_frame" not in parsed[-1]
    markdown = client.get(f"/api/tasks/{task_id}/export/brief.md")
    assert "<script>" not in markdown.text and "&lt;script&gt;" in markdown.text
    new_client = TestClient(create_app(tmp_path))
    assert new_client.get(f"/api/tasks/{task_id}").json() == task
    assert len(new_client.get("/api/tasks").json()) == 1
    error = client.post(f"/api/tasks/{task_id}/analysis/correct", json={"expected_version": task["task"]["version"], "analysis_ref": task["task"]["current_analysis"], "event_edits": [{"event_id": "event_intro_text", "start_frame": 2}]} )
    assert error.status_code == 422 and error.json()["error"]["code"] == "immutable_analysis_field"


def test_upload_unconfigured_provider_never_returns_sample(tmp_path):
    client = TestClient(create_app(tmp_path))
    sample = loaded(client)
    media = client.get(f"/api/tasks/{sample['task']['task_id']}/media/{sample['videos'][0]['video_id']}").content
    task = client.post("/api/tasks", json={"title": "Real upload"}).json()
    task_id = task["task"]["task_id"]
    upload = client.post(f"/api/tasks/{task_id}/video", data={"expected_version": task["task"]["version"]}, files={"file": ("../../unsafe.mp4", media, "video/mp4")})
    assert upload.status_code == 200, upload.text
    task = upload.json()
    assert task["videos"][0]["original_file_name"] == "unsafe.mp4"
    assert task["videos"][0]["input_method"] == "file" and task["task"]["mode"] == "real"
    task = post(client, task, "recognize")
    assert task["analyses"][-1]["status"] == "failed"
    assert task["jobs"][-1]["error"]["code"] == "real_analysis_not_configured"
    assert not task["analyses"][-1]["events"]
    response = client.post(f"/api/tasks/{task_id}/sample", json={"expected_version": task["task"]["version"]})
    assert response.status_code == 409 and response.json()["error"]["code"] == "sample_requires_empty_task"


def test_unreadable_upload_validation_and_task_isolation(tmp_path):
    client = TestClient(create_app(tmp_path))
    first = client.post("/api/tasks", json={"title": "First"}).json()
    second = client.post("/api/tasks", json={"title": "Second"}).json()
    path = f"/api/tasks/{first['task']['task_id']}"
    response = client.post(path + "/video", data={"expected_version": 1}, files={"file": ("broken.mp4", b"not a video", "video/mp4")})
    assert response.status_code == 422 and "error" in response.json()
    assert client.get(path).json()["videos"] == []
    assert client.get(f"/api/tasks/{second['task']['task_id']}").json() == second
    response = client.post(path + "/brief", json={"expected_version": 1, "brief": {"brand_company": "Incomplete"}})
    assert response.status_code == 422 and response.json()["error"]["code"] == "validation_error"
    assert client.post("/api/tasks", json={"title": ""}).status_code == 422
