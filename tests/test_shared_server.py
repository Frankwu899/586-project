"""Hosted boundary checks; fake credentials, no provider calls."""
import base64
import pytest
from fastapi.testclient import TestClient

from scripts.shared_server import create_shared_app, shared_settings


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-server-key-for-offline-tests")
    monkeypatch.setenv("VIDEO_TEAM_PASSWORD", "test-only-team-password-with-32-characters")
    monkeypatch.setenv("VIDEO_PUBLIC_ORIGIN", "https://workspace.example")
    monkeypatch.setenv("VIDEO_ANATOMY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VIDEO_TEAM_USERNAME", "team")
    # Backend tests do not require a Node build; browser tests use the real dist.
    static = tmp_path / "frontend" / "dist"
    static.mkdir(parents=True)
    (static / "index.html").write_text("<html>Test workspace</html>")
    monkeypatch.setattr("scripts.local_server.ROOT", tmp_path)
    return tmp_path


def client(app, authenticated=True):
    authorization = base64.b64encode(b"team:test-only-team-password-with-32-characters").decode()
    return TestClient(app, base_url="https://workspace.example",
                      headers={"Authorization": f"Basic {authorization}"} if authenticated else {})


CHANGE = {"X-Video-Anatomy-Request": "1", "Origin": "https://workspace.example"}


@pytest.mark.parametrize("name", ["OPENAI_API_KEY", "VIDEO_TEAM_PASSWORD", "VIDEO_PUBLIC_ORIGIN", "VIDEO_ANATOMY_DATA_DIR"])
def test_required_configuration(configured, monkeypatch, name):
    monkeypatch.delenv(name)
    with pytest.raises(ValueError, match=name):
        create_shared_app()


@pytest.mark.parametrize("origin", ["http://workspace.example", "https://workspace.example/path", "https://user:pass@workspace.example", "https://workspace.example?query=1"])
def test_invalid_public_origin(configured, monkeypatch, origin):
    monkeypatch.setenv("VIDEO_PUBLIC_ORIGIN", origin)
    with pytest.raises(ValueError, match="HTTPS origin"):
        create_shared_app()


def test_pins_all_models_and_providers(configured, monkeypatch):
    for capability in ("VISION", "CREATIVE", "M2", "STRUCTURE", "RESEARCH"):
        monkeypatch.setenv(f"OPENAI_{capability}_MODEL", "stale-unsupported-model")
    for capability in ("VISION", "CREATIVE", "M2", "TRANSCRIPTION"):
        monkeypatch.setenv(f"VIDEO_{capability}_PROVIDER", "mock")
    monkeypatch.setenv("OPENAI_TRANSCRIPTION_MODEL", "disabled")
    settings = shared_settings(configured)
    for capability in ("vision", "creative", "m2", "structure", "research"):
        assert getattr(settings, f"{capability}_model") == "gpt-6.1-sol"
    for capability in ("vision", "creative", "m2", "transcription"):
        assert getattr(settings, f"{capability}_provider") == "openai"
    assert settings.transcription_model == "whisper-1"
    assert settings.api_key == "sk-fake-server-key-for-offline-tests"
    assert not settings.experiment_budget_enabled
    assert settings.max_retries == 0


def test_team_password_and_storage(configured, monkeypatch):
    monkeypatch.setenv("VIDEO_TEAM_PASSWORD", "short")
    with pytest.raises(ValueError, match="separate team password"):
        create_shared_app()
    monkeypatch.setenv("VIDEO_TEAM_PASSWORD", "test-only-team-password-with-32-characters")
    monkeypatch.setenv("VIDEO_ANATOMY_DATA_DIR", "relative-data")
    with pytest.raises(ValueError, match="absolute persistent"):
        create_shared_app()


@pytest.mark.parametrize("path", ["/", "/api/tasks", "/api/config", "/api/local/connection", "/api/tasks/fake/videos/fake/media"])
def test_auth_protects_every_surface(configured, path):
    with client(create_shared_app(), False) as c:
        response = c.get(path)
        assert response.status_code == 401
        assert "Basic" in response.headers["www-authenticate"]
        assert "sk-fake" not in response.text
        assert c.get("/healthz").json() == {"status": "ok"}


def test_boundary_and_persistence(configured):
    with client(create_shared_app()) as c:
        assert c.get("/api/tasks", headers={"Host": "attacker.example"}).status_code == 403
        assert c.get("/api/tasks", headers={"Origin": "https://attacker.example"}).status_code == 403
        assert c.post("/api/tasks", json={"title": "Blocked"}).status_code == 403
        assert c.post("/api/tasks", json={"title": "Blocked"}, headers={**CHANGE, "Origin": "https://attacker.example"}).status_code == 403
        response = c.post("/api/tasks", json={"title": "Team project"}, headers=CHANGE)
        assert response.status_code == 201, response.text
        assert response.headers["cache-control"] == "no-store"
        task_id = response.json()["task"]["task_id"]
    with client(create_shared_app()) as c:
        assert c.get(f"/api/tasks/{task_id}").json()["task"]["title"] == "Team project"


@pytest.mark.parametrize("path", ["/api/local/connection", "/api/local/connection/check", "/api/local/connection/forget", "/api/local/shutdown", "/api/local/budget/reconcile"])
def test_team_cannot_mutate_operator_settings(configured, path):
    app = create_shared_app()
    with client(app) as c:
        assert c.post(path, headers=CHANGE, json={"api_key": "replacement"}).status_code == 403
        assert c.get("/api/local/runtime").status_code == 403
        assert c.get("/api/local/connection").json() == {"available": False, "configured": True, "mode": "shared"}
        assert app.state.service.provider_settings.api_key == "sk-fake-server-key-for-offline-tests"


def test_preferences_keep_key_and_model(configured):
    app = create_shared_app()
    with client(app) as c:
        response = c.post("/api/local/preferences", headers=CHANGE, json={"language": "Chinese"})
        assert response.status_code == 200, response.text
        assert "sk-fake" not in response.text
        assert app.state.service.provider_settings.research_model == "gpt-6.1-sol"
        assert app.state.service.provider_settings.api_key == "sk-fake-server-key-for-offline-tests"
    assert shared_settings(configured).analysis_language == "Chinese"
