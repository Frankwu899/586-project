"""Offline phase clocks; measured job totals are distinct from network limits."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from backend.app.api import create_app
from backend.app.project_workspace.models import Job


def test_job_records_queue_and_each_phase_elapsed_without_source_content(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    runtime = app.state.project_workspace
    project = runtime.store.create("Synthetic timing")
    clock = [datetime(2026, 11, 18, tzinfo=timezone.utc)]
    def stamp():
        return clock[0].isoformat()
    monkeypatch.setattr("backend.app.project_workspace.api.now", stamp)
    job = Job(kind="analyze", created_at=stamp(), updated_at=stamp(), diagnostics={"stage": "queued", "stage_started_at": stamp()})
    runtime.store.update(project.id, None, lambda state: state.jobs.append(job))
    clock[0] += timedelta(seconds=2)
    def work():
        for stage in ("extracting", "single_video_analysis", "synthesizing", "validating", "saving"):
            runtime.progress(project.id, job.id, stage)
            clock[0] += timedelta(seconds=3)
    runtime._run(project.id, job.id, work)
    saved = runtime.store.get(project.id).jobs[-1]
    assert saved.status == "succeeded"
    assert saved.diagnostics["phase_queued_ms"] == "2000"
    for stage in ("extracting", "single_video_analysis", "synthesizing", "validating", "saving"):
        assert saved.diagnostics[f"phase_{stage}_ms"] == "3000"
    assert saved.diagnostics["stage"] == "completed"
    assert all("Synthetic" not in str(value) for value in saved.diagnostics.values())
    runtime.executor.shutdown(wait=True)


def test_admission_retains_actual_timeout_and_attempt_config_separately(tmp_path, monkeypatch):
    runtime = create_app(tmp_path).state.project_workspace
    project = runtime.store.create("Synthetic request configuration")
    settings = replace(runtime.settings(), timeout_seconds=7, max_retries=1)
    monkeypatch.setattr(runtime, "settings", lambda: settings)
    monkeypatch.setattr(runtime.executor, "submit", lambda *args: None)
    admitted = runtime.submit(project.id, project.version, "analyze", lambda: None)
    diagnostics = admitted.jobs[-1].diagnostics
    assert diagnostics["network_timeout_seconds"] == "7"
    assert diagnostics["max_network_attempts"] == "2"
    assert "api_key" not in diagnostics and "prompt" not in diagnostics
    runtime.executor.shutdown(wait=True)


def test_restart_stops_unfinished_single_analysis_without_replaying_or_discarding_completed(tmp_path):
    from backend.app.project_workspace.models import SingleVideoAnalysis
    from backend.app.project_workspace.store import ProjectStore
    store = ProjectStore(tmp_path)
    project = store.create("Synthetic interrupted analysis")
    completed = SingleVideoAnalysis(resource_id="saved_source", input_key="completed", evidence_revision=1,
        source_sha256="a" * 64, model="test", instruction_digest="test", language="English", config_digest="test",
        status="succeeded")
    unfinished = completed.model_copy(deep=True, update={"id": "single_interrupted", "input_key": "unfinished", "status": "running"})
    store.update(project.id, None, lambda state: state.single_video_analyses.extend([completed, unfinished]))
    reopened = ProjectStore(tmp_path).get(project.id)
    assert reopened.single_video_analyses[0] == completed
    assert reopened.single_video_analyses[1].status == "stopped"
    assert reopened.single_video_analyses[1].diagnostics["failure_code"] == "operation_interrupted"
    assert reopened.jobs == []
    assert ProjectStore(tmp_path).get(project.id) == reopened


def test_conversation_validation_metadata_cannot_relabel_whole_provider_phase(tmp_path, monkeypatch):
    from backend.app.project_workspace.models import Message
    runtime = create_app(tmp_path).state.project_workspace
    project = runtime.store.create("Synthetic conversation phase")
    clock = [datetime(2026, 11, 18, tzinfo=timezone.utc)]
    def stamp():
        return clock[0].isoformat()
    monkeypatch.setattr("backend.app.project_workspace.api.now", stamp)
    job = Job(kind="conversation", message_id="user_phase", attempt_id="attempt_phase", created_at=stamp(),
        diagnostics={"stage": "queued", "stage_started_at": stamp()})
    runtime.store.update(project.id, None, lambda state: state.jobs.append(job))
    def work():
        clock[0] += timedelta(seconds=8)
        def reply(state):
            state.editor_drafts["conversation_turns"] = {"user_phase": {"attempt_id": "attempt_phase", "status": "partial"}}
            state.messages.append(Message(role="assistant", text="Synthetic response", reply_to_message_id="user_phase",
                attempt_id="attempt_phase", diagnostics={"stage": "reply_validation", "reply_validation": "partial"}))
        runtime.store.update(project.id, None, reply)
    runtime._run(project.id, job.id, work)
    saved = runtime.store.get(project.id)
    assert saved.jobs[-1].diagnostics["phase_running_ms"] == "8000"
    assert "phase_reply_validation_ms" not in saved.jobs[-1].diagnostics
    assert saved.jobs[-1].diagnostics["stage"] == "completed"
    assert saved.messages[-1].diagnostics["stage"] == "reply_validation"
    runtime.executor.shutdown(wait=True)


def test_failed_synthesis_keeps_available_attempt_usage_and_request_metadata_only(tmp_path):
    from backend.app.workflow_errors import WorkflowError
    runtime = create_app(tmp_path).state.project_workspace
    project = runtime.store.create("Synthetic failed synthesis telemetry")
    job = Job(kind="analyze", diagnostics={"stage": "queued"})
    runtime.store.update(project.id, None, lambda state: state.jobs.append(job))
    def work():
        runtime.progress(project.id, job.id, "synthesizing")
        error = WorkflowError("provider_timeout", "Synthetic timeout", 504)
        error.diagnostics = {"attempts": 2, "cache_status": "miss", "provider_request_id": "request_synthetic",
            "usage": {"input_tokens": {"value": 123, "unit": "tokens"}},
            "prompt": "PRIVATE SOURCE", "response": "PRIVATE RETURN", "api_key": "PRIVATE KEY"}
        raise error
    runtime._run(project.id, job.id, work)
    failed = runtime.store.get(project.id).jobs[-1]
    assert failed.status == "failed" and failed.diagnostics["failure_stage"] == "synthesizing"
    detail = next(item for item in failed.support_details if item.get("provider_request_id") == "request_synthetic")
    assert detail["attempts"] == "2" and detail["input_tokens"] == "123" and detail["cache_status"] == "miss"
    assert "PRIVATE" not in str(failed.support_details)
    runtime.executor.shutdown(wait=True)
