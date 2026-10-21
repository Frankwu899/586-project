"""Local language and budget controls use durable state, never real API calls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
import threading

from fastapi.testclient import TestClient
import pytest

from backend.app.models import ProcessingJob, VersionRef
from backend.app.providers.budget import ExperimentBudget
from backend.app.providers.config import ProviderSettings
from backend.app.providers.transport import OpenAITransport
from backend.app.structure_models import Workspace
from scripts import app_preferences, local_connection, local_server
from scripts.app_preferences import AppPreferences, read_preferences, write_preferences
from test_local_connection import FakeKeychain, provider_settings


KEY = "sk-offline-language-private-fixture"


@pytest.fixture
def local_preferences(tmp_path, monkeypatch):
    build = tmp_path / "app/frontend/dist"
    build.mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>Preferences fixture</title>")
    monkeypatch.setattr(local_server, "ROOT", build.parents[1])
    monkeypatch.setattr(OpenAITransport, "_request", lambda *args, **kwargs: pytest.fail("No paid API calls are allowed"))
    monkeypatch.setattr(local_server.getpass, "getpass", lambda *args: pytest.fail("No terminal key prompt is allowed"))
    data = tmp_path / "library"
    data.mkdir()
    settings = ProviderSettings(api_key=KEY, budget_path=data / "provider-budget.sqlite3",
                                cache_dir=data / "provider-cache", max_retries=0)
    ledger = ExperimentBudget(settings.budget_path)
    keychain = FakeKeychain(KEY)
    app = local_server.local_app(data, settings, keychain=keychain, key_source="keychain", remembered=True)
    app.state.local_connection.checker = lambda *args: pytest.fail("Language and budget controls must not check keys")
    with TestClient(app) as client:
        yield app, client, settings, keychain, ledger, data
    app.state.operations.pool.shutdown(wait=True)
    app.state.structure_service.executor.shutdown(wait=True)


@pytest.mark.parametrize("contents", [None, "{", "[]", '{"language":"French"}', '{"language":"Chinese","api_key":"unexpected"}'])
def test_missing_or_invalid_preferences_default_to_english(tmp_path, contents):
    path = tmp_path / "app-preferences.json"
    if contents is not None:
        path.write_text(contents)
    assert read_preferences(path) == AppPreferences(language="English")
    assert read_preferences(None) == AppPreferences(language="English")
    if contents is not None:
        assert path.read_text() == contents  # Reading defaults never destroys the source.


def test_language_rebuilds_all_adapters_and_preserves_ideas_key_library_cache_and_ledger(local_preferences):
    app, client, settings, keychain, ledger, data = local_preferences
    assert client.get("/api/local/preferences").json() == {"language": "English"}
    task = client.post("/api/tasks", json={"title": "Independent Ideas language"}).json()
    base = f"/api/tasks/{task['task']['task_id']}"
    task = client.post(base + "/language", json={"expected_version": task["task"]["version"], "generation_language": "Chinese"}).json()
    service = app.state.service
    identities = service, service.store, service.media
    prior_adapters = service.real_recognition, service.real_creative, service.m2_assistance, app.state.structure_service.agent
    settings.cache_dir.mkdir(exist_ok=True)
    cached = settings.cache_dir / "existing-result.json"
    cached.write_text('{"cached":"paid result"}')
    before_budget = ledger.summary()
    before_connection = client.get("/api/local/connection").json()

    response = client.post("/api/local/preferences", json={"language": "Chinese"})
    assert response.status_code == 200 and response.json() == {"language": "Chinese"}
    assert all(value == replace(settings, analysis_language="Chinese") for value in provider_settings(app))
    assert all(before is not after for before, after in zip(prior_adapters,
        (service.real_recognition, service.real_creative, service.m2_assistance, app.state.structure_service.agent)))
    assert (app.state.service, service.store, service.media) == identities
    assert client.get(base).json() == task
    assert client.get("/api/local/connection").json() == before_connection
    assert ledger.summary() == before_budget
    assert cached.read_text() == '{"cached":"paid result"}'
    assert keychain.key == KEY and keychain.calls == []
    assert (data / "app-preferences.json").read_text() == '{"language": "Chinese"}'
    assert client.get("/api/config").json()["analysis_output_language"] == "Chinese"

    response = client.post("/api/local/preferences", json={"language": "English"})
    assert response.status_code == 200
    assert all(value == settings for value in provider_settings(app))
    assert client.get(base).json()["task"]["generation_language"] == "Chinese"
    for endpoint in ("/api/local/preferences", "/api/local/budget", "/api/config"):
        assert KEY not in client.get(endpoint).text
    for path in data.rglob("*"):
        if path.is_file():
            assert KEY.encode() not in path.read_bytes()


def test_persisted_language_is_loaded_at_local_restart(local_preferences, monkeypatch):
    app, client, settings, _, ledger, data = local_preferences
    assert client.post("/api/local/preferences", json={"language": "Chinese"}).status_code == 200
    # The local UI preference overrides an older launcher's analysis env default.
    monkeypatch.setenv("ANALYSIS_OUTPUT_LANGUAGE", "English")
    monkeypatch.setenv("VIDEO_EXPERIMENT_BUDGET_PATH", str(settings.budget_path))
    monkeypatch.setenv("CREATIVE_OUTPUT_LANGUAGE", "English")
    reloaded_settings = local_server.local_settings(data, KEY)
    assert reloaded_settings.analysis_language == "Chinese"
    before_budget = ledger.summary()
    restarted = local_server.local_app(data, reloaded_settings)
    try:
        with TestClient(restarted) as reopened:
            assert reopened.get("/api/local/preferences").json() == {"language": "Chinese"}
            assert reopened.get("/api/config").json()["analysis_output_language"] == "Chinese"
            assert restarted.state.service.provider_settings.api_key == KEY
            assert ledger.summary() == before_budget
    finally:
        restarted.state.operations.pool.shutdown(wait=True)
        restarted.state.structure_service.executor.shutdown(wait=True)


def test_preferences_file_failure_is_atomic_and_leaves_live_adapters_untouched(local_preferences, monkeypatch):
    app, client, settings, _, ledger, data = local_preferences
    path = data / "app-preferences.json"
    write_preferences(path, AppPreferences())
    before_file, before_budget = path.read_bytes(), ledger.summary()
    before_adapters = app.state.service.real_recognition, app.state.service.real_creative, app.state.service.m2_assistance, app.state.structure_service.agent

    def cannot_replace(*args):
        raise OSError("Simulated unavailable destination")

    monkeypatch.setattr(app_preferences.os, "replace", cannot_replace)
    response = client.post("/api/local/preferences", json={"language": "Chinese"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "preferences_unavailable"
    assert path.read_bytes() == before_file
    assert app.state.service.provider_settings == settings
    assert (app.state.service.real_recognition, app.state.service.real_creative,
            app.state.service.m2_assistance, app.state.structure_service.agent) == before_adapters
    assert ledger.summary() == before_budget
    assert not list(data.glob(".app-preferences-*"))
    assert client.get("/api/local/preferences").json() == {"language": "English"}


@pytest.mark.parametrize("body", [{"language": "French"}, {"language": None}, {"language": "Chinese", "api_key": "do-not-save"}])
def test_invalid_preference_requests_do_not_change_runtime_or_file(local_preferences, body):
    app, client, settings, _, _, data = local_preferences
    response = client.post("/api/local/preferences", json=body)
    assert response.status_code == 422
    assert app.state.service.provider_settings == settings
    assert not (data / "app-preferences.json").exists()


@pytest.mark.parametrize("active", ["queued", "running", "analyzing", "researching", "feedback", "job_pending", "job_running"])
def test_active_work_blocks_language_change_and_budget_reconciliation(local_preferences, active):
    app, client, settings, _, _, data = local_preferences
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
    for endpoint, body in (("/api/local/preferences", {"language": "Chinese"}), ("/api/local/budget/reconcile", None)):
        response = client.post(endpoint, json=body)
        assert response.status_code == 409 and response.json()["error"]["code"] == "provider_connection_busy"
    assert client.get("/api/local/preferences").status_code == 200
    assert client.get("/api/local/budget").status_code == 200
    assert service.provider_settings == settings
    assert not (data / "app-preferences.json").exists()


def test_synchronous_write_blocks_language_change_and_reconciliation(local_preferences, monkeypatch):
    app, client, settings, _, _, _ = local_preferences
    entered, finish = threading.Event(), threading.Event()
    original_create = app.state.service.create

    def delayed_create(*args):
        entered.set()
        assert finish.wait(5)
        return original_create(*args)

    monkeypatch.setattr(app.state.service, "create", delayed_create)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, "/api/tasks", json={"title": "Save in flight"})
        try:
            assert entered.wait(5)
            assert client.post("/api/local/preferences", json={"language": "Chinese"}).status_code == 409
            assert client.post("/api/local/budget/reconcile").status_code == 409
            assert app.state.service.provider_settings == settings
        finally:
            finish.set()
        assert pending.result(timeout=5).status_code == 201


def test_language_change_blocks_new_writes_until_settings_commit(local_preferences, monkeypatch):
    app, client, settings, _, _, _ = local_preferences
    entered, finish = threading.Event(), threading.Event()
    original = local_connection.write_preferences

    def delayed_write(*args):
        entered.set()
        assert finish.wait(5)
        original(*args)

    monkeypatch.setattr(local_connection, "write_preferences", delayed_write)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, "/api/local/preferences", json={"language": "Chinese"})
        try:
            assert entered.wait(5)
            assert client.post("/api/tasks", json={"title": "Wait for settings"}).status_code == 409
            assert client.post("/api/local/preferences", json={"language": "English"}).status_code == 409
            assert client.get("/api/local/preferences").json() == {"language": "English"}
            assert app.state.service.provider_settings == settings
        finally:
            finish.set()
        assert pending.result(timeout=5).status_code == 200
    assert client.get("/api/local/preferences").json() == {"language": "Chinese"}
    assert client.post("/api/tasks", json={"title": "After settings"}).status_code == 201


def test_budget_get_never_reconciles_and_explicit_recovery_only_releases_known_auth(local_preferences):
    _, client, _, _, ledger, _ = local_preferences
    model, payload = "gpt-4.1-mini", {"max_output_tokens": 1000}
    attempts = {}
    for failure in ("provider_authentication", "provider_permission", "provider_timeout", "provider_rate_limit"):
        attempt = ledger.reserve(model, payload, {"capability": "vision"})
        ledger.finish(attempt, model, payload, failure_code="provider_timeout")
        # Emulate the previous launcher's persisted unknown 401/403 records.
        with ledger._transaction() as db:
            db.execute("UPDATE attempts SET failure_code=? WHERE id=?", (failure, attempt))
        attempts[failure] = attempt
    pending = ledger.reserve(model, payload, {"capability": "structure"})
    before = ledger.summary()
    assert before["recoverable_rejected_attempts"] == 2 and before["unknown_attempts"] == 5
    for _ in range(2):
        response = client.get("/api/local/budget")
        assert response.status_code == 200 and response.json() == before
    assert ledger.summary() == before

    response = client.post("/api/local/budget/reconcile")
    assert response.status_code == 200
    after = response.json()
    assert after["reconciled_attempts"] == 2
    assert after["attempts"] == before["attempts"] and after["maximum_usd"] == before["maximum_usd"] == "3"
    assert after["recoverable_rejected_attempts"] == 0 and after["unknown_attempts"] == 3
    assert after["provider_billed_cost_usd"] is None
    assert Decimal(after["held_usd"]) + Decimal(after["released_usd"]) == Decimal(before["held_usd"])
    with ledger._transaction() as db:
        rows = {row["id"]: dict(row) for row in db.execute("SELECT * FROM attempts")}
    for code in ("provider_authentication", "provider_permission"):
        assert rows[attempts[code]]["held"] == 0
        assert rows[attempts[code]]["estimated"] == 0
        assert rows[attempts[code]]["failure_code"] == code
        assert rows[attempts[code]]["reserved"] > 0
    for code in ("provider_timeout", "provider_rate_limit"):
        assert rows[attempts[code]]["held"] == rows[attempts[code]]["reserved"] > 0
        assert rows[attempts[code]]["estimated"] is None
    assert rows[pending]["status"] == "reserved" and rows[pending]["held"] > 0
    second = client.post("/api/local/budget/reconcile").json()
    assert second["reconciled_attempts"] == 0 and second["released_usd"] == "0"
    assert second["held_usd"] == after["held_usd"]
