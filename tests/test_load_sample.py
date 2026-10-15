"""Sample setup must stop at a failed operation before claiming a walkthrough."""
import pytest

from backend.app.adapters import UnconfiguredRecognitionAdapter
from backend.app.service import WorkflowService
from scripts import load_sample as loader


@pytest.mark.parametrize("complete", [False, True])
def test_sample_loader_verifies_successful_jobs(tmp_path, complete):
    state = loader.load_sample(tmp_path, complete)
    assert all(job.status == "succeeded" for job in state.jobs)
    assert [job.operation for job in state.jobs] == (["analyze", "directions", "refine", "production"] if complete else ["analyze"])
    assert state.analyses[-1].status == "succeeded"
    if complete:
        assert state.feedback[-1].status == "applied"
        assert state.production_briefs[-1].edited and state.storyboards[-1].edited


def test_sample_loader_rejects_failed_analysis_even_when_result_is_saved(tmp_path, monkeypatch):
    service = WorkflowService(tmp_path, recognition=UnconfiguredRecognitionAdapter())
    monkeypatch.setattr(loader, "WorkflowService", lambda _: service)
    with pytest.raises(RuntimeError, match="real_analysis_not_configured"):
        loader.load_sample(tmp_path)
    saved = service.store.list()[0]
    assert saved.task.current_analysis is not None and saved.analyses[-1].status == "failed"
    assert not saved.directions and saved.jobs[-1].status == "failed"


@pytest.mark.parametrize(("method", "operation"), [
    ("generate_directions", "directions"),
    ("refine_direction", "refine"),
    ("generate_production", "production"),
])
def test_complete_sample_stops_at_failed_generation(tmp_path, monkeypatch, method, operation):
    service = WorkflowService(tmp_path)

    def fail(*args):
        raise RuntimeError("Synthetic generation failure")

    monkeypatch.setattr(service.creative, method, fail)
    monkeypatch.setattr(loader, "WorkflowService", lambda _: service)
    with pytest.raises(RuntimeError, match=f"Sample {operation}.*generation_failed"):
        loader.load_sample(tmp_path, complete=True)
    saved = service.store.list()[0]
    assert saved.jobs[-1].operation == operation and saved.jobs[-1].status == "failed"
    assert not saved.production_briefs and not saved.storyboards
    if operation == "refine":
        assert saved.task.selected_direction is None
        assert saved.feedback[-1].status == "not_interpreted"


def test_complete_sample_requires_applied_refinement_before_approval(tmp_path, monkeypatch):
    service = WorkflowService(tmp_path)
    monkeypatch.setattr(service.creative, "refine_direction", lambda *args: None)
    monkeypatch.setattr(loader, "WorkflowService", lambda _: service)
    with pytest.raises(RuntimeError, match="Sample refine.*result_type=feedback"):
        loader.load_sample(tmp_path, complete=True)
    saved = service.store.list()[0]
    assert saved.jobs[-1].status == "succeeded" and saved.feedback[-1].status == "not_interpreted"
    assert saved.task.selected_direction is None and not saved.production_briefs and not saved.storyboards
