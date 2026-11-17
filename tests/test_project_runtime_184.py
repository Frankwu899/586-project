"""Offline HTTP/runtime ownership checks; injected providers never measure AI quality."""
from copy import deepcopy
from dataclasses import replace
import time

from fastapi.testclient import TestClient
import pytest

from backend.app.api import create_app
from backend.app.project_workspace.models import Job
from backend.app.providers.transport import OpenAITransport
import test_project_workspace_analysis as baseline


@pytest.fixture(autouse=True)
def prohibit_live_provider_calls(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Runtime regressions must not call a live provider")
    monkeypatch.setattr(OpenAITransport, "_request", forbidden)


@pytest.fixture
def runtime_client(tmp_path, monkeypatch):
    monkeypatch.delenv("VIDEO_MAX_BYTES", raising=False)
    _, project, _, recognizer, synthesis = baseline.workspace.__wrapped__(tmp_path)
    app = create_app(tmp_path)
    runtime = app.state.project_workspace
    runtime.analysis.recognition_factory = lambda _settings: recognizer
    runtime.analysis.transport_factory = lambda _settings: synthesis
    calls, hooks = [], []
    original = synthesis.json_response
    def observed(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(deepcopy(kwargs.get("metadata", {})))
        for hook in list(hooks):
            hook()
        return result
    synthesis.json_response = observed
    with TestClient(app) as client:
        yield client, runtime, project, recognizer, synthesis, calls, hooks


def latest(client, project):
    response = client.get("/api/projects/" + project.id)
    assert response.status_code == 200, response.text
    return response.json()


def post(client, project, suffix, body=None, *, expected=202):
    current = latest(client, project)
    response = client.post("/api/projects/" + project.id + suffix,
                           json={"expected_version": current["version"], **(body or {})})
    assert response.status_code == expected, response.text
    return response.json()


def settled(client, project, job_id):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        saved = latest(client, project)
        job = next(job for job in saved["jobs"] if job["id"] == job_id)
        if job["status"] not in {"queued", "running"}:
            return saved, job
        time.sleep(.01)
    pytest.fail("The target runtime job did not settle")


def admitted_analysis(admitted):
    return next(job for job in reversed(admitted["jobs"]) if job["kind"] == "analyze")


def test_api_parent_job_owns_only_its_frozen_sources_and_extraction_children(runtime_client):
    client, _, project, recognizer, _, metadata, _ = runtime_client
    ids = [resource.id for resource in project.resources]
    # Preserve caller order; no mutation of the request's frozen resource list.
    requested = list(reversed(ids))
    admitted = post(client, project, "/analyze", {"resource_ids": requested})
    parent = admitted_analysis(admitted)
    assert parent["resource_ids"] == requested and parent["parent_job_id"] is None
    saved, done = settled(client, project, parent["id"])
    children = [job for job in saved["jobs"] if job["kind"] == "reference_extraction"]
    assert len(children) == 2
    assert {child["parent_job_id"] for child in children} == {parent["id"]}
    assert [child["resource_id"] for child in children] == requested
    assert all(child["status"] == "succeeded" for child in children)
    assert recognizer.calls == requested
    assert done["status"] == "succeeded" and done["resource_ids"] == requested
    assert saved["analyses"][-1]["inputs"]["resource_ids"] == requested
    assert metadata[-1]["job_id"] == parent["id"] and metadata[-1]["operation"] == "new_analysis"
    assert done["diagnostics"]["analysis_id"] == saved["analyses"][-1]["id"]
    prior_evidence = deepcopy(saved["resources"])
    retry = post(client, project, "/resources/" + requested[0] + "/recognize")
    retry_parent = next(job for job in reversed(retry["jobs"]) if job["kind"] == "recognize")
    retried, retry_job = settled(client, project, retry_parent["id"])
    assert retry_job["resource_ids"] == [requested[0]] and retry_job["status"] == "succeeded"
    retry_children = [job for job in retried["jobs"] if job["parent_job_id"] == retry_parent["id"]]
    assert len(retry_children) == 1 and retry_children[0]["resource_id"] == requested[0]
    assert retried["resources"] == prior_evidence and recognizer.calls == requested


def test_another_source_scope_partial_child_does_not_taint_current_success(runtime_client):
    client, runtime, project, _, _, _, hooks = runtime_client
    selected, other = [resource.id for resource in project.resources]
    unrelated = Job(kind="recognize", resource_id=other, resource_ids=[other], status="running")
    runtime.store.update(project.id, project.version, lambda state: state.jobs.append(unrelated))
    def unrelated_partial():
        def record(state):
            parent = next(job for job in state.jobs if job.id == unrelated.id)
            parent.status = "partial"
            state.jobs.append(Job(kind="reference_extraction", resource_id=other, content_id=None,
                                  parent_job_id=unrelated.id, status="partial", progress="Unrelated saved partial"))
        runtime.store.update(project.id, None, record)
        hooks.clear()
    hooks.append(unrelated_partial)
    admitted = post(client, project, "/analyze", {"resource_ids": [selected]})
    parent = admitted_analysis(admitted)
    saved, done = settled(client, project, parent["id"])
    assert done["status"] == "succeeded" and done["error"] is None
    assert done["resource_ids"] == [selected]
    current_children = [job for job in saved["jobs"] if job["parent_job_id"] == parent["id"]]
    assert len(current_children) == 1 and current_children[0]["resource_id"] == selected
    assert current_children[0]["status"] == "succeeded"
    assert any(job["status"] == "partial" and job["parent_job_id"] == unrelated.id for job in saved["jobs"])
    assert saved["analyses"][-1]["inputs"]["resource_ids"] == [selected]


def test_summary_retry_uses_saved_evidence_without_new_extraction_or_selection_writes(runtime_client):
    client, _, project, recognizer, synthesis, metadata, _ = runtime_client
    ids = [resource.id for resource in project.resources]
    synthesis.bad_citation = True
    first = post(client, project, "/analyze", {"resource_ids": ids})
    failed_state, failed_job = settled(client, project, admitted_analysis(first)["id"])
    assert failed_job["status"] == "failed" and failed_job["error_code"] == "invalid_analysis_citation"
    assert failed_job["diagnostics"]["failure_stage"] == "validating"
    assert not failed_state["analyses"] and all(resource["evidence"] for resource in failed_state["resources"])
    evidence = {resource["id"]: deepcopy(resource["evidence"]) for resource in failed_state["resources"]}
    selection = deepcopy(failed_state["selection"])
    extraction_ids = [job["id"] for job in failed_state["jobs"] if job["kind"] == "reference_extraction"]
    recorded_calls = list(recognizer.calls)
    synthesis.bad_citation = False
    retried = post(client, project, "/analyze", {"resource_ids": ids, "synthesis_only": True})
    retry_parent = admitted_analysis(retried)
    saved, done = settled(client, project, retry_parent["id"])
    limited = any(value in {"failed", "partial", "error", "not_analyzed"}
                  for revisions in evidence.values() for value in revisions[-1]["coverage"].values())
    assert done["status"] == ("partial" if limited else "succeeded") and done["resource_ids"] == ids
    assert bool(saved["analyses"][-1]["inputs"]["limitations"]) == limited
    assert done["diagnostics"]["synthesis_only"] == "true"
    assert saved["selection"] == selection
    assert {resource["id"]: resource["evidence"] for resource in saved["resources"]} == evidence
    assert [job["id"] for job in saved["jobs"] if job["kind"] == "reference_extraction"] == extraction_ids
    assert recognizer.calls == recorded_calls
    assert not [job for job in saved["jobs"] if job["parent_job_id"] == retry_parent["id"]]
    assert metadata[-1]["operation"] == "retry_summary" and metadata[-1]["job_id"] == retry_parent["id"]
    assert len(saved["analyses"]) == 1


def test_summary_retry_cannot_silently_restore_an_older_reference_selection(runtime_client):
    client, _, project, recognizer, _, _, _ = runtime_client
    first_id, second_id = [resource.id for resource in project.resources]
    first = post(client, project, "/analyze", {"resource_ids": [first_id]})
    settled(client, project, admitted_analysis(first)["id"])
    changed = post(client, project, "/selection", {"resource_ids": [second_id]}, expected=200)
    before = deepcopy(changed)
    original_calls = list(recognizer.calls)
    response = client.post("/api/projects/" + project.id + "/analyze", json={
        "expected_version": changed["version"], "resource_ids": [first_id], "synthesis_only": True})
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "analysis_inputs_changed"
    saved = latest(client, project)
    assert saved == before
    assert saved["selection"] == before["selection"]
    assert saved["resources"] == before["resources"]
    assert saved["analyses"] == before["analyses"]
    assert saved["jobs"] == before["jobs"]
    assert recognizer.calls == original_calls


@pytest.mark.parametrize("suffix,payload", [
    ("/analyze", {"transcription_model": "unrecognized-speech-model"}),
    ("/analyze", {"synthesis_only": True, "transcription_model": "whisper-1"}),
    ("/analyze", {"synthesis_only": True, "transcription_model": "gpt-transcribe"}),
    ("/resources/{resource}/recognize", {"transcription_model": "unrecognized-speech-model"}),
])
def test_invalid_model_or_summary_model_options_fail_before_job_admission(runtime_client, suffix, payload):
    client, _, project, recognizer, synthesis, _, _ = runtime_client
    current = latest(client, project)
    resource_id = project.resources[0].id
    body = {"expected_version": current["version"], **payload}
    if suffix == "/analyze":
        body["resource_ids"] = [resource_id]
    response = client.post("/api/projects/" + project.id + suffix.format(resource=resource_id), json=body)
    assert response.status_code == 422, response.text
    assert latest(client, project) == current
    assert not recognizer.calls and synthesis.calls == 0


def test_capabilities_report_actual_media_limit_and_live_speech_profile_without_credentials(runtime_client):
    client, runtime, _, _, _, _, _ = runtime_client
    first = client.get("/api/projects/capabilities")
    assert first.status_code == 200
    capabilities = first.json()
    assert capabilities["media_limits"]["max_bytes"] == 500 * 1024 * 1024
    profiles = {profile["id"]: profile for profile in capabilities["transcription_models"]}
    assert set(profiles) == {"whisper-1", "gpt-transcribe"}
    assert profiles["whisper-1"]["timing"] == "segment" and profiles["gpt-transcribe"]["timing"] == "chunk"
    runtime.legacy_service.provider_settings = replace(runtime.legacy_service.provider_settings,
        transcription_model="gpt-transcribe", api_key="offline-private-placeholder")
    runtime.resources.media_settings = replace(runtime.resources.media_settings, max_bytes=123 * 1024 * 1024)
    second = client.get("/api/projects/capabilities")
    assert second.status_code == 200
    assert second.json()["transcription_model"] == "gpt-transcribe"
    assert second.json()["media_limits"]["max_bytes"] == 123 * 1024 * 1024
    assert second.json()["configured"] is True and "offline-private-placeholder" not in second.text
