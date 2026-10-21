"""Local API-key changes use fake checks/Keychain, never external providers."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import threading

from fastapi.testclient import TestClient
import pytest

from backend.app.adapters import UnconfiguredRecognitionAdapter
from backend.app.models import ProcessingJob, VersionRef
from backend.app.providers.auth import ConnectionCheck
from backend.app.providers.config import ProviderSettings
from backend.app.providers.transport import OpenAITransport
from backend.app.structure_models import Workspace
from scripts import local_connection as connection_module, local_server
from scripts.mac_keychain import KeychainError


OLD_KEY = "sk-offline-old-key-private"
NEW_KEY = "sk-offline-new-key-private"
CHECKED = ConnectionCheck("verified", "provider_connection_verified", "Offline fixture: key accepted; inference permissions untested.")


class FakeKeychain:
    def __init__(self, key=OLD_KEY):
        self.key, self.calls, self.failure = key, [], None

    def _call(self, operation):
        self.calls.append(operation)
        if self.failure == operation:
            raise KeychainError("Unlock the login Keychain and try again.")

    def get(self):
        self._call("get")
        return self.key

    def set(self, value):
        self._call("set")
        self.key = value

    def delete(self):
        self._call("delete")
        self.key = None


@pytest.fixture
def local_connection(tmp_path, monkeypatch):
    build = tmp_path / "app" / "frontend" / "dist"
    build.mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>Local fixture</title>")
    monkeypatch.setattr(local_server, "ROOT", build.parents[1])
    monkeypatch.setattr(OpenAITransport, "_request", lambda *args, **kwargs: pytest.fail("No inference call is allowed"))
    monkeypatch.setattr(local_server.getpass, "getpass", lambda *args: pytest.fail("No terminal key prompt is allowed"))
    keychain = FakeKeychain()
    data = tmp_path / "library"
    ledger = tmp_path / "original-shared-ledger.sqlite3"
    ledger.write_bytes(b"Unchanged preexisting ledger fixture; never opened by a key check.")
    settings = ProviderSettings(api_key=OLD_KEY, budget_path=ledger, cache_dir=data / "provider-cache",
                                vision_model="gpt-4o-mini", creative_model="gpt-4.1",
                                m2_model="gpt-4.1-nano", structure_model="gpt-4.1-mini",
                                research_model="gpt-4.1-mini", max_retries=0)
    app = local_server.local_app(data, settings, keychain=keychain, key_source="keychain", remembered=True)
    connection = app.state.local_connection
    checked = []

    def checker(current):
        checked.append(current)
        return CHECKED

    connection.checker = checker
    with TestClient(app) as client:
        yield app, client, keychain, checked, settings, data
    app.state.operations.pool.shutdown(wait=True)
    app.state.structure_service.executor.shutdown(wait=True)


def provider_settings(app):
    service = app.state.service
    return (service.provider_settings, service.real_recognition.settings,
            service.real_recognition.vision_provider.settings,
            service.real_recognition.vision_provider.transport.settings,
            service.real_recognition.transcription_provider.transport.settings,
            service.real_creative.settings, service.real_creative.transport.settings,
            service.m2_assistance.settings, service.m2_assistance.transport.settings,
            app.state.structure_service.agent.settings, app.state.structure_service.agent.transport.settings)


def test_save_replaces_every_provider_without_restarting_service_or_touching_shared_budget(local_connection):
    app, client, keychain, checked, settings, data = local_connection
    service, media, store = app.state.service, app.state.service.media, app.state.service.store
    task = client.post("/api/tasks", json={"title": "Retained classroom task"}).json()
    before = settings.budget_path.read_bytes()
    response = client.post("/api/local/connection", json={"api_key": " \n" + NEW_KEY + "\t ", "remember": True})
    assert response.status_code == 200, response.text
    assert response.json()["configured"] and response.json()["remembered"]
    assert response.json()["key_source"] == "keychain"
    assert response.json()["last_check"]["endpoint_permissions_verified"] is False
    assert keychain.key == NEW_KEY and keychain.calls == ["set"]
    assert len(checked) == 1 and checked[0].api_key == NEW_KEY
    assert all(value == replace(settings, api_key=NEW_KEY) for value in provider_settings(app))
    assert settings.budget_path.read_bytes() == before
    assert app.state.service is service and service.media is media and service.store is store
    assert client.get(f'/api/tasks/{task["task"]["task_id"]}').json() == task
    for endpoint in ("/api/local/connection", "/api/local/runtime", "/api/health", "/api/config", "/api/tasks", "/openapi.json"):
        text = client.get(endpoint).text
        assert OLD_KEY not in text and NEW_KEY not in text
    assert OLD_KEY not in response.text and NEW_KEY not in response.text
    for path in data.rglob("*"):
        if path.is_file():
            contents = path.read_bytes()
            assert OLD_KEY.encode() not in contents and NEW_KEY.encode() not in contents


def test_explicit_candidate_check_does_not_change_saved_credential_or_status(local_connection):
    app, client, keychain, checked, settings, _ = local_connection
    response = client.post("/api/local/connection/check", json={"api_key": NEW_KEY})
    assert response.status_code == 200 and response.json()["status"] == "verified"
    assert checked[-1].api_key == NEW_KEY
    assert app.state.service.provider_settings == settings
    assert keychain.key == OLD_KEY and keychain.calls == []
    assert client.get("/api/local/connection").json()["last_check"] is None
    current = client.post("/api/local/connection/check", json={})
    assert current.status_code == 200 and checked[-1].api_key == OLD_KEY
    assert client.get("/api/local/connection").json()["last_check"] == current.json()


@pytest.mark.parametrize("key,rejected", [("sk-...masked", False), (NEW_KEY, True)])
def test_invalid_or_rejected_key_keeps_previous_connection_unchanged(local_connection, key, rejected):
    app, client, keychain, checked, settings, _ = local_connection
    if rejected:
        app.state.local_connection.checker = lambda _: ConnectionCheck("rejected", "provider_authentication", "Credential rejected (HTTP 401).")
    old_adapters = provider_settings(app)
    response = client.post("/api/local/connection", json={"api_key": key, "remember": True})
    assert response.status_code == 422
    assert app.state.service.provider_settings == settings
    assert provider_settings(app) == old_adapters
    assert keychain.key == OLD_KEY and not keychain.calls
    assert key not in response.text
    if not rejected:
        assert not checked


def test_restricted_models_read_is_warning_and_does_not_block_using_session_key(local_connection):
    app, client, keychain, _, _, _ = local_connection
    app.state.local_connection.checker = lambda _: ConnectionCheck("unverified", "provider_models_permission", "Models read denied; inference permission not known.")
    response = client.post("/api/local/connection", json={"api_key": NEW_KEY, "remember": False})
    assert response.status_code == 200
    assert response.json()["last_check"]["status"] == "unverified"
    assert response.json()["key_source"] == "session" and response.json()["remembered"] is False
    assert app.state.service.provider_settings.api_key == NEW_KEY
    assert keychain.key is None and keychain.calls == ["delete"]


def test_keychain_remember_failure_does_not_half_apply_runtime_changes(local_connection):
    app, client, keychain, _, settings, _ = local_connection
    keychain.failure = "set"
    old_status = client.get("/api/local/connection").json()
    old_adapters = provider_settings(app)
    response = client.post("/api/local/connection", json={"api_key": NEW_KEY, "remember": True})
    assert response.status_code == 409 and response.json()["error"]["code"] == "keychain_unavailable"
    assert app.state.service.provider_settings == settings
    assert provider_settings(app) == old_adapters
    assert client.get("/api/local/connection").json() == old_status
    assert keychain.key == OLD_KEY


@pytest.mark.parametrize("operation", ["session", "forget"])
def test_locked_keychain_allows_session_or_disconnect_and_does_not_resurrect_old_key(local_connection, operation, monkeypatch):
    app, client, keychain, _, _, data = local_connection
    keychain.failure = "delete"
    if operation == "session":
        response = client.post("/api/local/connection", json={"api_key": NEW_KEY, "remember": False})
    else:
        response = client.post("/api/local/connection/forget")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is (operation == "session")
    assert body["remembered"] is False and body["keychain_error"]
    assert keychain.key == OLD_KEY and keychain.calls == ["delete"]
    assert app.state.service.provider_settings.api_key == (NEW_KEY if operation == "session" else "")
    preferences = data / "credential-preferences.json"
    assert json.loads(preferences.read_text()) == {"disable_keychain": True}
    assert OLD_KEY not in preferences.read_text() and NEW_KEY not in preferences.read_text()
    monkeypatch.setenv("OPENAI_API_KEY", OLD_KEY)
    assert local_server.initial_credentials(keychain=keychain, managed=True, preference_path=preferences) == ("", "none", False, None)
    assert keychain.calls == ["delete"]  # A restart does not even request the old key.


def test_remember_after_session_save_reenables_only_the_new_saved_key(local_connection):
    _, client, keychain, _, _, data = local_connection
    assert client.post("/api/local/connection", json={"api_key": NEW_KEY}).status_code == 200
    preferences = data / "credential-preferences.json"
    assert json.loads(preferences.read_text())["disable_keychain"] is True
    assert client.post("/api/local/connection", json={"api_key": NEW_KEY, "remember": True}).status_code == 200
    assert json.loads(preferences.read_text())["disable_keychain"] is False
    assert local_server.initial_credentials(keychain=keychain, managed=True, preference_path=preferences) == (NEW_KEY, "keychain", True, None)


@pytest.mark.parametrize("operation", ["session", "forget"])
@pytest.mark.parametrize("failure", ["create", "replace"])
def test_preference_write_failure_keeps_runtime_and_keychain_unchanged_with_safe_error(local_connection, monkeypatch, operation, failure):
    app, client, keychain, _, settings, data = local_connection

    def fail_write(*args, **kwargs):
        raise OSError("private filesystem detail")

    if failure == "create":
        monkeypatch.setattr(connection_module.tempfile, "mkstemp", fail_write)
    else:
        monkeypatch.setattr(connection_module.os, "replace", fail_write)
    if operation == "session":
        response = client.post("/api/local/connection", json={"api_key": NEW_KEY})
    else:
        response = client.post("/api/local/connection/forget")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "credential_preferences_unavailable"
    assert "private filesystem" not in response.text
    assert app.state.service.provider_settings == settings and keychain.key == OLD_KEY
    assert not keychain.calls and not list(data.glob(".credential-preferences-*"))


def test_remember_preference_commit_failure_does_not_activate_or_reload_the_new_key(local_connection, monkeypatch):
    app, client, keychain, _, settings, data = local_connection
    real_replace = connection_module.os.replace
    replacements = []

    def fail_activation(source, destination):
        replacements.append(destination)
        if len(replacements) == 2:
            raise OSError("private activation detail")
        return real_replace(source, destination)

    monkeypatch.setattr(connection_module.os, "replace", fail_activation)
    response = client.post("/api/local/connection", json={"api_key": NEW_KEY, "remember": True})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "credential_preferences_unavailable"
    assert "private activation" not in response.text
    assert app.state.service.provider_settings == settings
    assert keychain.key == NEW_KEY
    preferences = data / "credential-preferences.json"
    assert json.loads(preferences.read_text()) == {"disable_keychain": True}
    assert local_server.initial_credentials(keychain=keychain, managed=True, preference_path=preferences) == ("", "none", False, None)
    assert keychain.calls == ["set"]
    assert not list(data.glob(".credential-preferences-*"))


def test_failed_remember_preserves_existing_suppression_of_saved_key(local_connection):
    _, client, keychain, _, _, data = local_connection
    keychain.failure = "delete"
    assert client.post("/api/local/connection", json={"api_key": NEW_KEY}).status_code == 200
    assert keychain.key == OLD_KEY
    keychain.failure = "set"
    response = client.post("/api/local/connection", json={"api_key": NEW_KEY, "remember": True})
    assert response.status_code == 409 and response.json()["error"]["code"] == "keychain_unavailable"
    preferences = data / "credential-preferences.json"
    assert json.loads(preferences.read_text()) == {"disable_keychain": True}
    calls = list(keychain.calls)
    assert local_server.initial_credentials(keychain=keychain, managed=True, preference_path=preferences) == ("", "none", False, None)
    assert keychain.calls == calls


def test_forget_removes_only_app_credential_and_preserves_task_library_and_budget(local_connection):
    app, client, keychain, _, settings, data = local_connection
    task = client.post("/api/tasks", json={"title": "Retain me"}).json()
    original_files = {path: path.read_bytes() for path in data.rglob("*") if path.is_file()}
    ledger = settings.budget_path.read_bytes()
    response = client.post("/api/local/connection/forget")
    assert response.status_code == 200
    assert not response.json()["configured"] and not response.json()["remembered"]
    assert response.json()["key_source"] == "none" and response.json()["last_check"] is None
    assert keychain.key is None and keychain.calls == ["delete"]
    assert app.state.service.provider_settings == replace(settings, api_key="")
    assert isinstance(app.state.service.real_recognition, UnconfiguredRecognitionAdapter)
    assert app.state.service.real_creative.settings.api_key == ""
    assert app.state.service.m2_assistance.settings.api_key == ""
    assert app.state.structure_service.agent.settings.api_key == ""
    assert client.get(f'/api/tasks/{task["task"]["task_id"]}').json() == task
    assert {path: path.read_bytes() for path in original_files} == original_files
    assert settings.budget_path.read_bytes() == ledger


def test_remember_without_keychain_is_actionable_but_session_save_works(local_connection):
    app, client, _, checked, _, _ = local_connection
    app.state.local_connection.keychain = None
    response = client.post("/api/local/connection", json={"api_key": NEW_KEY, "remember": True})
    assert response.status_code == 409 and not checked
    assert response.json()["error"]["code"] == "keychain_unavailable"
    response = client.post("/api/local/connection", json={"api_key": NEW_KEY, "remember": False})
    assert response.status_code == 200 and response.json()["can_remember"] is False
    assert app.state.service.provider_settings.api_key == NEW_KEY


@pytest.mark.parametrize("payload", [{"api_key": {"secret": NEW_KEY}}, {"api_key": NEW_KEY, "extra": OLD_KEY}, {"api_key": NEW_KEY, "remember": NEW_KEY}])
def test_validation_does_not_echo_credentials(local_connection, payload):
    _, client, keychain, checked, _, _ = local_connection
    response = client.post("/api/local/connection", json=payload)
    assert response.status_code == 422
    assert OLD_KEY not in response.text and NEW_KEY not in response.text
    assert not keychain.calls and not checked


@pytest.mark.parametrize("active", ["queued", "running", "analyzing", "researching", "feedback", "job_pending", "job_running"])
def test_active_work_blocks_credential_replacement_and_forget(local_connection, active):
    app, client, keychain, checked, settings, _ = local_connection
    service = app.state.service
    task = service.create("Active work").task
    if active in {"queued", "running"}:
        with app.state.operations.connect() as db:
            db.execute("INSERT INTO background_operations VALUES (?,?,?,?,?,?,NULL)",
                       ("op_fixture", task.task_id, "recognize", active, "2026-10-19", "2026-10-19"))
    elif active.startswith("job_"):
        service.store.update(task.task_id, task.version, lambda state: state.jobs.append(
            ProcessingJob(job_id="job_fixture", task_id=task.task_id, operation="analyze", status=active[4:])))
    else:
        app.state.structure_service.store.create(Workspace(structure_id="structure_fixture", task_id=task.task_id,
            video_id="video_fixture", analysis_ref=VersionRef(id="analysis_fixture", revision=1), origin="provider",
            status="ready" if active == "feedback" else active,
            feedback_status="running" if active == "feedback" else "idle"))
    for endpoint, body in (("/api/local/connection", {"api_key": NEW_KEY, "remember": True}),
                           ("/api/local/connection/forget", None)):
        response = client.post(endpoint, json=body)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "provider_connection_busy"
    assert client.get("/api/local/connection").status_code == 200
    assert app.state.service.provider_settings == settings and not checked and not keychain.calls


def test_inflight_direct_mutation_blocks_key_change_without_racing_service_replacement(local_connection, monkeypatch):
    app, client, keychain, checked, settings, _ = local_connection
    entered, finish = threading.Event(), threading.Event()
    original_create = app.state.service.create

    def delayed_create(*args, **kwargs):
        entered.set()
        assert finish.wait(5), "Test mutation was not released"
        return original_create(*args, **kwargs)

    monkeypatch.setattr(app.state.service, "create", delayed_create)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(client.post, "/api/tasks", json={"title": "Concurrent saved task"})
        try:
            assert entered.wait(5)
            response = client.post("/api/local/connection", json={"api_key": NEW_KEY})
            assert response.status_code == 409 and not checked and not keychain.calls
            assert app.state.service.provider_settings == settings
        finally:
            finish.set()
        assert pending.result(timeout=5).status_code == 201
    assert client.post("/api/local/connection", json={"api_key": NEW_KEY}).status_code == 200


def test_inflight_key_check_prevents_new_mutations_until_atomic_replacement_finishes(local_connection):
    app, client, _, _, settings, _ = local_connection
    entered, finish = threading.Event(), threading.Event()

    def delayed_check(current):
        entered.set()
        assert finish.wait(5), "Test check was not released"
        assert current.api_key == NEW_KEY
        return CHECKED

    app.state.local_connection.checker = delayed_check
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(client.post, "/api/local/connection", json={"api_key": NEW_KEY})
        try:
            assert entered.wait(5)
            response = client.post("/api/tasks", json={"title": "Wait until save completes"})
            assert response.status_code == 409
            assert client.get("/api/local/connection").status_code == 200
            assert app.state.service.provider_settings == settings
        finally:
            finish.set()
        assert pending.result(timeout=5).status_code == 200
    assert client.post("/api/tasks", json={"title": "After save"}).status_code == 201


def test_managed_startup_uses_keychain_without_shell_key_prompt_or_http(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-stale-environment-private")
    monkeypatch.setattr(local_server, "read_api_key", lambda: pytest.fail("Managed startup must not prompt"))
    keychain = FakeKeychain(NEW_KEY)
    assert local_server.initial_credentials(keychain=keychain, managed=True) == (NEW_KEY, "keychain", True, None)
    keychain.key = None
    assert local_server.initial_credentials(keychain=keychain, managed=True) == ("", "none", False, None)
    assert local_server.initial_credentials(managed=True) == ("", "none", False, None)
    assert local_server.initial_credentials(managed=False) == ("sk-stale-environment-private", "environment", False, None)
    assert keychain.calls == ["get", "get"]


def test_keychain_startup_failure_is_safe_and_offline_never_reads_saved_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", OLD_KEY)
    keychain = FakeKeychain(NEW_KEY)
    keychain.failure = "get"
    result = local_server.initial_credentials(keychain=keychain, managed=True)
    assert result[:3] == ("", "none", False)
    assert "Keychain" in result[3]
    assert OLD_KEY not in json.dumps(result) and NEW_KEY not in json.dumps(result)
    keychain.calls.clear()
    assert local_server.initial_credentials(keychain=keychain, managed=True, offline=True) == ("", "none", False, None)
    assert keychain.calls == []


@pytest.mark.parametrize("body", ["broken JSON", "[]", "{}", '{"disable_keychain": true}', '{"disable_keychain": null}'])
def test_missing_or_corrupt_preference_flag_cannot_reenable_an_old_credential(tmp_path, body):
    preference_path = tmp_path / "credential-preferences.json"
    preference_path.write_text(body)
    keychain = FakeKeychain(OLD_KEY)
    assert local_server.initial_credentials(keychain=keychain, managed=True, preference_path=preference_path) == ("", "none", False, None)
    assert not keychain.calls
