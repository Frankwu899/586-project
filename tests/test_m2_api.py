"""Assistance HTTP races and failures use deterministic local providers only."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from fastapi.testclient import TestClient
import httpx
import pytest

from backend.app.api import create_app
from backend.app.models import M2DraftUpdate
from backend.app.providers.config import ProviderSettings
from backend.app.providers.m2 import FakeM2AssistanceAdapter, OpenAIM2AssistanceAdapter
from backend.app.providers.transport import OpenAITransport
from backend.app.sample import sample_brief
from backend.app.service import WorkflowService


@pytest.fixture
def applied(tmp_path):
    service = WorkflowService(tmp_path)
    state = service.create("Offline assistance HTTP checks")
    task_id = state.task.task_id
    fields = sample_brief(task_id).model_dump(exclude={
        "brief_id", "revision", "task_id", "schema_version", "created_at", "updated_at",
    })
    state = service.save_brief(task_id, state.task.version, fields)
    draft = service.store.get_m2_draft(task_id)
    draft = service.store.save_m2_draft(task_id, M2DraftUpdate(
        expected_draft_version=draft.draft_version, fields=draft.fields, claims=draft.claims,
        source_notes="Product: LumaCup 随行杯\nSelling point: Removable lid",
    ))
    return service, state, draft


def test_assistance_response_after_concurrent_http_autosave_is_rejected(applied):
    service, state, draft = applied
    entered, release = Event(), Event()

    class PausedAssistance:
        def assist(self, request, snapshot):
            entered.set()
            if not release.wait(timeout=10):
                raise TimeoutError("Synthetic test barrier was not released")
            return FakeM2AssistanceAdapter().assist(request, snapshot)

    service.m2_assistance = PausedAssistance()
    client = TestClient(create_app(service=service))
    path = f"/api/tasks/{state.task.task_id}"
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, path + "/m2/assist", json={
            "draft_version": draft.draft_version, "request_id": "request_concurrent",
            "mode": "extract",
        })
        try:
            assert entered.wait(timeout=10), "Assistance did not reach the injected provider"
            fields = draft.fields.model_dump()
            fields["product"] = "Newer manually entered product 中文"
            saved = client.post(path + "/m2/draft", json={
                "expected_draft_version": draft.draft_version, "fields": fields,
                "claims": [claim.model_dump() for claim in draft.claims],
                "source_notes": "Product: Newer pasted notes 原文",
            })
            assert saved.status_code == 200, saved.text
            assert saved.json()["has_pending_inputs"]
            assert client.get(path).json() == state.model_dump(mode="json")
        finally:
            release.set()
        response = pending.result(timeout=10)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "m2_stale_proposal"
    assert "Run extraction again" in response.json()["error"]["message"]
    assert client.get(path + "/m2/draft").json() == saved.json()
    assert client.get(path).json() == state.model_dump(mode="json")


@pytest.mark.parametrize("failure_mode,error_code,expected_attempts", [
    ("unsupported_field", "m2_invalid_assistance", 0),
    ("invented_excerpt", "m2_invalid_assistance", 0),
    ("timeout", "provider_timeout", 2),
    ("invalid_json", "provider_invalid_json", 1),
])
def test_assistance_api_failure_is_safe_and_retains_applied_and_draft_inputs(
    applied, failure_mode, error_code, expected_attempts,
):
    service, state, draft = applied
    calls = []

    class InvalidInjectedProvider:
        def assist(self, request, snapshot):
            response = FakeM2AssistanceAdapter().assist(request, snapshot).model_dump()
            candidate = response["candidates"][0]
            if failure_mode == "unsupported_field":
                candidate["target"] = "approval_status"
                candidate["value"] = "approved"
            else:
                candidate["source_excerpt"] = "SECRET_DIAGNOSTIC: not present in supplied notes"
            return response

    def fail_http(request):
        calls.append(request)
        if failure_mode == "timeout":
            raise httpx.ReadTimeout("SECRET_DIAGNOSTIC timeout detail", request=request)
        return httpx.Response(200, json={"status": "completed", "output": [{
            "content": [{"type": "output_text", "text": "SECRET_DIAGNOSTIC invalid json"}],
        }]})

    settings = ProviderSettings(api_key="synthetic-test-secret", timeout_seconds=1, max_retries=1)
    with httpx.Client(transport=httpx.MockTransport(fail_http)) as transport_client:
        if failure_mode in {"unsupported_field", "invented_excerpt"}:
            service.m2_assistance = InvalidInjectedProvider()
        else:
            transport = OpenAITransport(settings, client=transport_client, sleep=lambda _: None)
            service.m2_assistance = OpenAIM2AssistanceAdapter(settings, transport=transport)
        client = TestClient(create_app(service=service))
        path = f"/api/tasks/{state.task.task_id}"
        response = client.post(path + "/m2/assist", json={
            "draft_version": draft.draft_version, "request_id": "request_safe_failure",
            "mode": "extract",
        })
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == error_code
    assert response.json()["error"]["message"]
    assert "SECRET_DIAGNOSTIC" not in response.text
    assert "synthetic-test-secret" not in response.text
    assert "candidates" not in response.json()
    assert len(calls) == expected_attempts
    assert service.store.get(state.task.task_id) == state
    assert service.store.get_m2_draft(state.task.task_id) == draft
    assert not draft.has_pending_inputs
