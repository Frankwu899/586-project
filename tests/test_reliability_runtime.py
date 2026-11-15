"""Injected-provider 1.8.2 HTTP/job/restart checks; no live API requests."""
from copy import deepcopy
from dataclasses import replace
import threading
import time

from fastapi.testclient import TestClient
import pytest

from backend.app.api import create_app
from backend.app.project_workspace.models import Job, Message
from backend.app.providers.base import ProviderError
from backend.app.providers.transport import OpenAITransport


def response(*proposals):
    return {"reply": "Would you prefer awareness or sign-ups as the primary objective?",
            "proposals": list(proposals), "unresolved": [], "research_query": None}


def objective(value="Awareness", source_index=0):
    return {"key": "objective", "value": value, "kind": "extracted",
            "source_index": source_index, "excerpt": "Objective: Awareness"}


class InjectedConversation:
    def __init__(self, result=None, *, error=None, block=False):
        self.result = result or response()
        self.error = error
        self.calls = []
        self.started = threading.Event()
        self.release = threading.Event()
        if not block:
            self.release.set()

    def json_response(self, **kwargs):
        self.calls.append(kwargs)
        self.started.set()
        assert self.release.wait(5), "Test failed to release injected response"
        if self.error:
            raise self.error
        return deepcopy(self.result)


@pytest.fixture(autouse=True)
def prohibit_live_requests(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def prohibited(*_args, **_kwargs):
        raise AssertionError("Runtime tests must not call a live provider")

    monkeypatch.setattr(OpenAITransport, "json_response", prohibited)
    monkeypatch.setattr(OpenAITransport, "web_search", prohibited)


def configure(app, transport):
    runtime = app.state.project_workspace
    runtime.legacy_service.provider_settings = replace(
        runtime.legacy_service.provider_settings,
        api_key="injected-test-key", experiment_budget_enabled=False)
    runtime.conversation.transport_factory = lambda _settings: transport
    return runtime


def create(client):
    result = client.post("/api/projects", json={"title": "Runtime regression"})
    assert result.status_code == 201
    return result.json()


def refresh(client, project):
    result = client.get(f"/api/projects/{project['id']}")
    assert result.status_code == 200
    return result.json()


def mutate(client, project, path, **values):
    return client.post(f"/api/projects/{project['id']}{path}",
                       json={"expected_version": project["version"], **values})


def settle(client, project):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        current = refresh(client, project)
        if not any(job["status"] in {"queued", "running"} for job in current["jobs"]):
            return current
        threading.Event().wait(0.01)
    pytest.fail("Injected background job did not settle")


def test_failed_turn_retry_preserves_user_and_cannot_replay_success(tmp_path):
    fixture = InjectedConversation(error=ProviderError("provider_timeout", "The request timed out. Retry explicitly.", True))
    app = create_app(tmp_path)
    configure(app, fixture)
    with TestClient(app) as client:
        project = create(client)
        admitted = mutate(client, project, "/messages", text="Objective: Awareness")
        assert admitted.status_code == 202
        failed = settle(client, admitted.json())
        user = failed["messages"][0]
        reply = failed["messages"][-1]
        job = failed["jobs"][-1]
        assert job["status"] == "failed" and job["message_id"] == user["id"]
        assert job["error_code"] == "provider_timeout"
        assert reply["reply_to_message_id"] == user["id"] and reply["retryable"]
        assert reply["diagnostics"]["job_id"] == job["id"]
        assert job["diagnostics"]["job_id"] == job["id"]
        fixture.error = None
        retry = mutate(client, failed, f"/messages/{user['id']}/retry")
        assert retry.status_code == 202, retry.text
        completed = settle(client, retry.json())
        assert completed["jobs"][-1]["status"] == "succeeded"
        assert completed["jobs"][-1]["message_id"] == user["id"]
        assert [item for item in completed["messages"] if item["role"] == "user"] == [user]
        assert len(fixture.calls) == 2
        again = mutate(client, completed, f"/messages/{user['id']}/retry")
        assert again.status_code == 409
        assert len(fixture.calls) == 2
        assert refresh(client, completed) == completed
    with TestClient(create_app(tmp_path)) as client:
        assert refresh(client, completed) == completed


def test_invalid_proposal_marks_partial_job_without_discarding_valid_reply(tmp_path):
    fixture = InjectedConversation(response(objective(), objective("Fabricated goal", source_index=800)))
    app = create_app(tmp_path)
    configure(app, fixture)
    with TestClient(app) as client:
        project = create(client)
        admitted = mutate(client, project, "/messages", text="Objective: Awareness")
        assert admitted.status_code == 202
        completed = settle(client, admitted.json())
        job = completed["jobs"][-1]
        assert job["status"] == "partial", job
        assert completed["messages"][-1]["status"] == "saved"
        assert "primary objective?" in completed["messages"][-1]["text"]
        assert [fact["value"] for fact in completed["brief_draft"]] == ["Awareness"]
        assert completed["briefs"] == []
        assert completed["messages"][-1]["diagnostics"]["job_id"] == job["id"]
        assert len(fixture.calls) == 1  # deterministic invalid proposal is not repaired in a paid loop
        no_replay = mutate(client, completed, f"/messages/{completed['messages'][0]['id']}/retry")
        assert no_replay.status_code == 409
    with TestClient(create_app(tmp_path)) as client:
        assert refresh(client, completed) == completed


@pytest.mark.parametrize("unsafe_reply", [None, "Read https://fabricated-source.invalid/clinical-proof for our verified results."])
def test_rejected_reply_keeps_independent_fact_and_explicit_retry_only(tmp_path, unsafe_reply):
    raw = response(objective())
    raw["reply"] = unsafe_reply
    fixture = InjectedConversation(raw)
    app = create_app(tmp_path)
    configure(app, fixture)
    with TestClient(app) as client:
        project = create(client)
        admitted = mutate(client, project, "/messages", text="Objective: Awareness")
        assert admitted.status_code == 202
        failed = settle(client, admitted.json())
        assert failed["jobs"][-1]["status"] == "failed"
        reply = failed["messages"][-1]
        assert reply["status"] == "failed" and reply["retryable"]
        assert "fabricated-source" not in reply["text"]
        assert reply["diagnostics"]["validation_rule"]
        assert [fact["value"] for fact in failed["brief_draft"]] == ["Awareness"]
        assert failed["briefs"] == [] and len(fixture.calls) == 1
        fixture.result = response(objective())
        retry = mutate(client, failed, f"/messages/{failed['messages'][0]['id']}/retry")
        assert retry.status_code == 202
        recovered = settle(client, retry.json())
        assert recovered["jobs"][-1]["status"] == "succeeded"
        assert [fact["value"] for fact in recovered["brief_draft"]] == ["Awareness"]
        assert len([message for message in recovered["messages"] if message["role"] == "user"]) == 1
        assert len(fixture.calls) == 2


def test_pending_turn_blocks_retry_and_double_send_without_appending_user(tmp_path):
    fixture = InjectedConversation(block=True)
    app = create_app(tmp_path)
    configure(app, fixture)
    with TestClient(app) as client:
        project = create(client)
        admitted = mutate(client, project, "/messages", text="Compare campaign objectives.")
        assert admitted.status_code == 202 and fixture.started.wait(3)
        current = refresh(client, admitted.json())
        user = current["messages"][0]
        try:
            assert current["jobs"][-1]["status"] == "running"
            retry = mutate(client, current, f"/messages/{user['id']}/retry")
            assert retry.status_code == 409
            resend = mutate(client, current, "/messages", text="Compare campaign objectives.")
            assert resend.status_code == 409
            assert len(fixture.calls) == 1
        finally:
            fixture.release.set()
        completed = settle(client, project)
        assert completed["jobs"][-1]["status"] == "succeeded"
        assert [item for item in completed["messages"] if item["role"] == "user"] == [user]


def test_pending_reply_survives_navigation_but_does_not_overwrite_newer_brief(tmp_path):
    fixture = InjectedConversation(response(objective()), block=True)
    app = create_app(tmp_path)
    configure(app, fixture)
    with TestClient(app) as client:
        project = create(client)
        admitted = mutate(client, project, "/messages", text="Objective: Awareness")
        assert admitted.status_code == 202 and fixture.started.wait(3)
        current = refresh(client, project)
        try:
            navigation = client.patch(f"/api/projects/{project['id']}",
                json={"expected_version": current["version"], "workspace": "resources"})
            assert navigation.status_code == 200
            current = navigation.json()
            facts = [{"id": "fact_updated", "key": "objective", "value": "Prioritize sign-ups",
                      "status": "confirmed", "origin": "manual"}]
            newer = mutate(client, current, "/brief/apply", facts=facts,
                           expected_draft_version=current["brief_draft_version"])
            assert newer.status_code == 200, newer.text
        finally:
            fixture.release.set()
        completed = settle(client, project)
        assert completed["workspace"] == "resources"
        assert completed["briefs"][-1]["facts"][0]["value"] == "Prioritize sign-ups"
        assert [fact["value"] for fact in completed["brief_draft"]] == ["Prioritize sign-ups"]
        assert completed["jobs"][-1]["status"] == "failed"
        assert completed["jobs"][-1]["error_code"] == "conversation_context_changed"
        assert completed["messages"][-1]["status"] == "failed"
    with TestClient(create_app(tmp_path)) as client:
        assert refresh(client, completed) == completed


def test_restart_marks_interrupted_turn_failed_until_explicit_retry(tmp_path):
    app = create_app(tmp_path)
    fixture = InjectedConversation()
    runtime = configure(app, fixture)
    with TestClient(app) as client:
        project = create(client)
        pending, message_id = runtime.conversation.begin_message(project["id"], project["version"], "Compare campaign objectives.")
        interrupted = Job(kind="conversation", message_id=message_id, status="running")
        runtime.store.update(project["id"], pending.version, lambda state: state.jobs.append(interrupted))
        assert fixture.calls == []
    restarted = create_app(tmp_path)
    configure(restarted, fixture)
    with TestClient(restarted) as client:
        recovered = refresh(client, project)
        assert recovered["jobs"][-1]["status"] == "failed"
        assert recovered["jobs"][-1]["error_code"] == "conversation_interrupted"
        reply = recovered["messages"][-1]
        assert reply["reply_to_message_id"] == message_id
        assert reply["status"] == "failed" and reply["retryable"]
        assert recovered["editor_drafts"]["conversation_turns"][message_id]["status"] == "failed"
        assert not recovered["editor_drafts"].get("conversation_requests")
        assert fixture.calls == []
        retry = mutate(client, recovered, f"/messages/{message_id}/retry")
        assert retry.status_code == 202, retry.text
        completed = settle(client, retry.json())
        assert len(fixture.calls) == 1
        assert len([item for item in completed["messages"] if item["role"] == "user"]) == 1
        assert completed["jobs"][-1]["status"] == "succeeded"


def test_retry_for_other_project_turn_rejected_without_provider_call(tmp_path):
    app = create_app(tmp_path)
    fixture = InjectedConversation()
    runtime = configure(app, fixture)
    with TestClient(app) as client:
        first, second = create(client), create(client)
        _, message_id = runtime.conversation.begin_message(first["id"], first["version"], "Compare objectives.")
        response = mutate(client, second, f"/messages/{message_id}/retry")
        assert response.status_code == 404
        assert fixture.calls == []
        assert refresh(client, second) == second


@pytest.mark.parametrize("legacy_status", ["failed", "saved"])
def test_upgrade_recovers_only_latest_failed_legacy_turn_for_explicit_retry(tmp_path, legacy_status):
    """1.8.1 records have no correlation/turn state; preserve their message text."""
    fixture = InjectedConversation()
    app = create_app(tmp_path)
    runtime = configure(app, fixture)
    user = Message(role="user", text="Compare awareness and sign-up objectives.")
    legacy_reply = Message(role="assistant", status=legacy_status, text=(
        "Assistance returned an unsupported or ungrounded result; retry or correct the brief manually."
        if legacy_status == "failed" else "Would you prefer awareness or sign-ups as the primary objective?"))
    with TestClient(app) as client:
        project = create(client)
        runtime.store.update(project["id"], project["version"],
                             lambda state: state.messages.extend([user, legacy_reply]))
        legacy = refresh(client, project)
        assert not legacy["editor_drafts"].get("conversation_turns")
        assert legacy["messages"][-1]["reply_to_message_id"] is None
        assert fixture.calls == []

    upgraded_app = create_app(tmp_path)
    configure(upgraded_app, fixture)
    with TestClient(upgraded_app) as client:
        upgraded = refresh(client, project)
        assert [message["text"] for message in upgraded["messages"]] == [user.text, legacy_reply.text]
        assert len([message for message in upgraded["messages"] if message["role"] == "user"]) == 1
        assert fixture.calls == []  # Upgrade never replays a potentially billed request.
        if legacy_status == "failed":
            assert upgraded["messages"][-1]["reply_to_message_id"] == user.id
            assert upgraded["messages"][-1]["retryable"]
            assert upgraded["editor_drafts"]["conversation_turns"][user.id]["status"] == "failed"
            retry = mutate(client, upgraded, f"/messages/{user.id}/retry")
            assert retry.status_code == 202, retry.text
            recovered = settle(client, retry.json())
            assert recovered["jobs"][-1]["status"] == "succeeded"
            assert len(fixture.calls) == 1
            assert [message["text"] for message in recovered["messages"][:2]] == [user.text, legacy_reply.text]
            assert len([message for message in recovered["messages"] if message["role"] == "user"]) == 1
        else:
            assert not upgraded["messages"][-1]["retryable"]
            retry = mutate(client, upgraded, f"/messages/{user.id}/retry")
            assert retry.status_code == 409
            assert fixture.calls == []
            assert refresh(client, upgraded) == upgraded
