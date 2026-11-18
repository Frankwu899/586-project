"""Offline attempt-race and bounded-intake contracts, not live model quality."""
from copy import deepcopy
from dataclasses import replace
import threading

from fastapi.testclient import TestClient
import httpx
import pytest

from backend.app.api import create_app
from backend.app.project_workspace.conversation import (
    ConversationService, ConversationTransport, REQUESTS_KEY, TURNS_KEY,
)
from backend.app.project_workspace.models import Fact, Job, Resource
from backend.app.project_workspace.store import ProjectStore
from backend.app.providers.base import ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.workflow_errors import WorkflowError


class ReplyTransport:
    def __init__(self):
        self.response = {"reply": "Here is a draft for review.", "proposals": [], "unresolved": []}
        self.calls = 0
        self.research_calls = 0
        self.cancelled = False
        self.before = None
        self.error = None

    def json_response(self, **kwargs):
        self.calls += 1
        if self.before:
            before, self.before = self.before, None
            before()
        if self.error:
            raise self.error
        return deepcopy(self.response)

    def web_search(self, *args, **kwargs):
        self.research_calls += 1
        raise AssertionError("Stopped work must not start public research")

    def cancel(self):
        self.cancelled = True


@pytest.fixture
def intake(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Offline intake")
    settings = ProviderSettings(api_key="offline-test-only", experiment_budget_enabled=False)
    transport = ReplyTransport()
    service = ConversationService(store, lambda: settings, lambda _: transport)
    return store, project, transport, service


def attempt(project, message_id):
    return project.editor_drafts[REQUESTS_KEY][message_id]["attempt_id"]


def test_queued_stop_is_durable_preserves_inputs_and_never_calls_provider(intake, tmp_path):
    store, project, transport, service = intake
    adopted = Fact(key="audience", value="Commuters", origin="manual", status="confirmed")
    project = service.apply_brief(project.id, project.version, [adopted])
    resource = Resource(name="brief.txt", kind="document", role="document", original_path="sources/documents/brief.txt",
                        sha256="a" * 64, size_bytes=10)
    project = store.update(project.id, project.version, lambda state: state.resources.append(resource))
    saved, message_id = service.begin_message(project.id, project.version, "My assignment", [resource.id])
    token = attempt(saved, message_id)
    media = Job(kind="recognize", resource_id=resource.id, status="running")
    saved = store.update(project.id, saved.version, lambda state: state.jobs.extend([
        Job(kind="conversation", message_id=message_id, attempt_id=token), media]))
    stopped = service.stop(project.id, saved.version, message_id, token)
    assert stopped.messages[0].resource_ids == [resource.id]
    assert stopped.messages[-1].text == "Stopped" and stopped.messages[-1].retryable
    assert stopped.briefs == project.briefs and stopped.brief_draft == project.brief_draft
    assert stopped.jobs[0].status == "stopped" and stopped.jobs[1] == media
    assert service.respond(project.id, message_id, token) == stopped
    assert transport.calls == 0
    assert service.stop(project.id, stopped.version, message_id, token) == stopped
    # Reopening does not replay stopped work or lose the saved stopped bubble.
    reopened = ProjectStore(tmp_path).get(project.id)
    assert reopened.messages == stopped.messages and not reopened.editor_drafts.get(REQUESTS_KEY)


@pytest.mark.parametrize("failure", [None, ProviderError("provider_timeout", "Timed out", True)])
def test_stop_retry_old_completion_or_failure_cannot_touch_new_attempt(intake, failure):
    store, project, transport, service = intake
    saved, message_id = service.begin_message(project.id, project.version, "Audience: commuters")
    old_token = attempt(saved, message_id)
    observed = {}
    def replace_attempt():
        current = store.get(project.id)
        stopped = service.stop(project.id, current.version, message_id, old_token)
        new, _ = service.begin_retry(project.id, stopped.version, message_id)
        observed["new"] = attempt(new, message_id)
    transport.before = replace_attempt
    transport.error = failure
    transport.response["research_query"] = "Public product question"
    if failure:
        with pytest.raises(WorkflowError):
            service.respond(project.id, message_id, old_token)
    else:
        service.respond(project.id, message_id, old_token)
    pending = store.get(project.id)
    assert observed["new"] != old_token and attempt(pending, message_id) == observed["new"]
    assert pending.editor_drafts[TURNS_KEY][message_id]["status"] == "pending"
    assert len([message for message in pending.messages if message.role == "user"]) == 1
    assert [message.text for message in pending.messages if message.role == "assistant"] == ["Stopped"]
    assert transport.cancelled and not transport.research_calls and not pending.brief_draft
    # A delayed queued callback with the old identity cannot claim the retry.
    service.respond(project.id, message_id, old_token)
    assert transport.calls == 1
    transport.error = None
    transport.response.pop("research_query")
    completed = service.respond(project.id, message_id, observed["new"])
    assert completed.messages[-1].attempt_id == observed["new"]
    assert completed.messages[-1].status == "saved"


def test_completed_stop_is_noop_and_foreign_attempt_conflicts(intake):
    store, project, _, service = intake
    saved, message_id = service.begin_message(project.id, project.version, "Draft a launch plan")
    token = attempt(saved, message_id)
    completed = service.respond(project.id, message_id, token)
    assert service.stop(project.id, completed.version, message_id, token) == completed
    with pytest.raises(WorkflowError) as error:
        service.stop(project.id, completed.version, message_id, "attempt_foreign")
    assert error.value.code == "conversation_attempt_changed"
    assert store.get(project.id) == completed


def test_conversation_http_cancellation_closes_only_active_client():
    entered, release = threading.Event(), threading.Event()
    def handler(request):
        entered.set()
        assert release.wait(3)
        return httpx.Response(200, json={"ok": True})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    other = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200)))
    transport = ConversationTransport(ProviderSettings(api_key="offline", experiment_budget_enabled=False), lambda: None)
    errors = []
    def run():
        try:
            transport._post(client, "https://offline.invalid")
        except Exception as error:
            errors.append(error)
    worker = threading.Thread(target=run)
    worker.start()
    assert entered.wait(3)
    transport.cancel()
    assert client.is_closed and not other.is_closed
    release.set()
    worker.join(3)
    assert not worker.is_alive() and not errors
    other.close()


def set_question(transport, question="Which audience should lead?", dimension="audience", **extra):
    transport.response = {"reply": "We can keep this exploratory. " + question, "proposals": [], "unresolved": [],
                          "question": question, "question_dimension": dimension, "context_sufficient": False, **extra}


def test_sufficient_input_zero_questions_and_reviewable_draft_without_auto_apply(intake):
    _, project, transport, service = intake
    set_question(transport, context_sufficient=True)
    saved = service.send(project.id, project.version, "Create a 20-second Instagram introduction for commuters.")
    assert "?" not in saved.messages[-1].text and "ready for review" in saved.messages[-1].text
    assert saved.messages[-1].diagnostics["response_kind"] == "draft"
    assignment = next(fact for fact in saved.brief_draft if fact.key == "assignment")
    assert assignment.status == "suggested"
    assert assignment.sources[0].message_id == saved.messages[0].id
    duration = next(fact for fact in saved.brief_draft if fact.key == "duration")
    assert duration.value == "20 seconds" and duration.status == "suggested"
    assert saved.briefs == []


def test_two_persisted_proactive_turns_then_limited_draft_even_if_provider_keeps_asking(intake):
    store, project, transport, service = intake
    set_question(transport)
    first = service.send(project.id, project.version, "I have a rough concept.")
    assert first.messages[-1].text.count("?") == 1
    set_question(transport, "Which objective should lead?", "objective")
    second = service.send(project.id, first.version, "Use commuters as the audience.")
    assert second.messages[-1].diagnostics["response_kind"] == "clarification"
    # Use a fresh service to prove that the bound is saved, not process-local.
    fresh = ConversationService(store, service.settings_provider, lambda _: transport)
    third = fresh.send(project.id, second.version, "Awareness is the goal.")
    assert "?" not in third.messages[-1].text and "draft" in third.messages[-1].text
    assert third.messages[-1].diagnostics["response_kind"] == "draft"
    assert not third.briefs and transport.calls == 3


@pytest.mark.parametrize("user_text", ["Go ahead with a draft", "请先继续，不要再问", "Don't ask me more questions; proceed"])
def test_direct_proceed_stops_proactive_questions(intake, user_text):
    _, project, transport, service = intake
    set_question(transport)
    saved = service.send(project.id, project.version, user_text)
    assert "?" not in saved.messages[-1].text and "ready for review" in saved.messages[-1].text
    assert not saved.briefs


def test_multiple_questions_reduce_to_one_declared_consequential_question(intake):
    _, project, transport, service = intake
    set_question(transport)
    transport.response["reply"] += " Which platform? What duration?"
    saved = service.send(project.id, project.version, "I have an assignment.")
    assert saved.messages[-1].text.count("?") == 1
    assert "Which audience should lead?" in saved.messages[-1].text


def test_explicit_depth_can_continue_beyond_default_limit(intake):
    _, project, transport, service = intake
    set_question(transport)
    first = service.send(project.id, project.version, "I have a rough concept.")
    second = service.send(project.id, first.version, "A small audience.")
    third = service.send(project.id, second.version, "Please ask me more and go deeper.")
    assert third.messages[-1].text.count("?") == 1
    assert third.messages[-1].diagnostics["proactive_clarification"] == "false"


def test_unresolved_core_fact_does_not_prevent_consequential_clarification(intake):
    store, project, transport, service = intake
    def facts(state):
        state.brief_draft = [Fact(key=key, value=value, origin="manual", status=status) for key, value, status in [
            ("objective", "awareness or sign-ups", "unresolved"), ("audience", "commuters", "suggested"),
            ("platform", "Instagram", "suggested"), ("duration", "20 seconds", "suggested")]]
    project = store.update(project.id, project.version, facts)
    set_question(transport, "Which objective should lead?", "objective")
    saved = service.send(project.id, project.version, "I am still choosing the main outcome.")
    assert saved.messages[-1].diagnostics["response_kind"] == "clarification"


def test_one_consequential_question_then_answer_produces_unapplied_draft(intake):
    _, project, transport, service = intake
    set_question(transport, "Which objective should lead?", "objective")
    asked = service.send(project.id, project.version, "I have a video concept for commuters.")
    set_question(transport, context_sufficient=True)
    drafted = service.send(project.id, asked.version, "Awareness is the main objective.")
    assert asked.messages[-1].diagnostics["response_kind"] == "clarification"
    assert drafted.messages[-1].diagnostics["response_kind"] == "draft"
    assert "?" not in drafted.messages[-1].text and drafted.brief_draft and not drafted.briefs
    assert transport.calls == 2


def test_rejected_question_metadata_cannot_reenter_safe_reply(intake):
    _, project, transport, service = intake
    set_question(transport, "Which objective at https://invented.invalid should lead?", "objective")
    transport.response["reply"] = "Which objective matters most?"
    saved = service.send(project.id, project.version, "I have a video concept.")
    assert "invented.invalid" not in saved.messages[-1].text
    assert "clarification_metadata_schema" in saved.messages[-1].diagnostics["validation_issues"]


def test_legacy_182_records_receive_additive_defaults_and_stopped_reload_preserves_them(intake):
    store, project, _, service = intake
    from backend.app.project_workspace.models import Message, Project
    legacy = project.model_dump()
    legacy["messages"] = [{"role": "user", "text": "Legacy assignment"}]
    legacy["jobs"] = [{"kind": "conversation", "status": "failed"}]
    loaded = Project.model_validate(legacy)
    assert loaded.messages[0].attempt_id is None and loaded.messages[0].status == "saved"
    assert loaded.jobs[0].attempt_id is None
    assert Message(role="assistant", text="Saved legacy output").attempt_id is None
    # The new identity is assigned on new/retried work, not fabricated for history.
    saved, message_id = service.begin_message(project.id, project.version, "New assignment")
    stopped = service.stop(project.id, saved.version, message_id, attempt(saved, message_id))
    assert store.get(project.id).messages[-1] == stopped.messages[-1]


class ManualExecutor:
    def __init__(self):
        self.pending = []

    def submit(self, callback, *args):
        self.pending.append((callback, args))

    def shutdown(self, **kwargs):
        pass


def test_http_queued_stop_retry_and_old_background_callback(tmp_path):
    app = create_app(tmp_path)
    runtime = app.state.project_workspace
    runtime.executor.shutdown(wait=True)
    manual = ManualExecutor()
    runtime.executor = manual
    transport = ReplyTransport()
    runtime.conversation.transport_factory = lambda _: transport
    settings = replace(runtime.settings(), api_key="offline", experiment_budget_enabled=False)
    runtime.conversation.settings_provider = lambda: settings
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"title": "Queued stop fixture"}).json()
        base = "/api/projects/" + project["id"]
        pending = client.post(base + "/messages", json={"expected_version": project["version"], "text": "An assignment"}).json()
        job = pending["jobs"][-1]
        route = base + "/messages/" + job["message_id"]
        stopped_response = client.post(route + "/stop", json={"expected_version": pending["version"], "attempt_id": job["attempt_id"]})
        assert stopped_response.status_code == 200
        stopped = stopped_response.json()
        retried = client.post(route + "/retry", json={"expected_version": stopped["version"]}).json()
        assert retried["jobs"][-1]["attempt_id"] != job["attempt_id"]
        old_callback, old_args = manual.pending[0]
        old_callback(*old_args)
        assert transport.calls == 0
        new_callback, new_args = manual.pending[1]
        new_callback(*new_args)
        done = client.get(base).json()
        assert [item["status"] for item in done["jobs"]] == ["stopped", "succeeded"]
        assert len([message for message in done["messages"] if message["role"] == "user"]) == 1
        assert done["messages"][-1]["attempt_id"] == retried["jobs"][-1]["attempt_id"]


def test_stop_before_background_admission_never_queues_work(tmp_path):
    app = create_app(tmp_path)
    runtime = app.state.project_workspace
    runtime.executor.shutdown(wait=True)
    runtime.executor = ManualExecutor()
    project = runtime.store.create("Admission race")
    saved, message_id = runtime.conversation.begin_message(project.id, project.version, "An assignment")
    token = attempt(saved, message_id)
    stopped = runtime.conversation.stop(project.id, saved.version, message_id, token)
    result = runtime.submit(project.id, None, "conversation", lambda: pytest.fail("Stopped callback ran"),
                            message_id=message_id, attempt_id=token)
    assert result == stopped and not result.jobs and not runtime.executor.pending


def test_stale_failed_reply_does_not_consume_a_delivered_question_turn(intake):
    store, project, transport, service = intake
    set_question(transport)
    transport.before = lambda: store.update(project.id, None, lambda state: state.brief_draft.append(
        Fact(key="constraint", value="Newer saved instruction", origin="manual")))
    with pytest.raises(WorkflowError, match="newer context"):
        service.send(project.id, project.version, "An assignment")
    current = store.get(project.id)
    assert current.messages[-1].status == "failed"
    for text in ["A follow-up", "Another follow-up"]:
        current = service.send(project.id, current.version, text)
        assert current.messages[-1].diagnostics["response_kind"] == "clarification"
