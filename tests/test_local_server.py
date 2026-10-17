"""Live launcher boundaries: secrets, no automatic paid work, and restart safety."""
import getpass

from fastapi.testclient import TestClient
import pytest

from backend.app.providers.transport import OpenAITransport
from scripts import local_server
from scripts.generate_sample_media import generate_sample_media


@pytest.fixture
def built_ui(tmp_path, monkeypatch):
    root = tmp_path / "app"
    build = root / "frontend" / "dist"
    build.mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>Local app</title>")
    monkeypatch.setattr(local_server, "ROOT", root)
    return root


def test_prompt_key_stays_out_of_environment_and_output(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    secret = "sk-test-not-a-real-credential"
    monkeypatch.setattr(getpass, "getpass", lambda _: secret)
    assert local_server.read_api_key() == secret
    assert "OPENAI_API_KEY" not in local_server.os.environ
    assert secret not in capsys.readouterr().out


def test_existing_environment_key_avoids_prompt(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-environment-test")
    def fail(_):
        raise AssertionError("Should not prompt when the environment supplies a key")
    monkeypatch.setattr(getpass, "getpass", fail)
    assert local_server.read_api_key() == "sk-environment-test"


def test_hidden_input_is_required(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    def insecure(_):
        raise getpass.GetPassWarning("No echo control")
    monkeypatch.setattr(getpass, "getpass", insecure)
    with pytest.raises(ValueError, match="Terminal"):
        local_server.read_api_key()


@pytest.mark.parametrize("key", ["", "sk-part\nother", "sk-中文"])
def test_invalid_key_has_no_value_in_error(key, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(getpass, "getpass", lambda _: key)
    with pytest.raises(ValueError) as error:
        local_server.read_api_key()
    if key:
        assert key not in str(error.value)


def test_live_app_uses_key_without_exposing_or_persisting_it(built_ui, tmp_path, monkeypatch):
    secret = "sk-test-backend-memory-only"
    def no_paid_calls(*args, **kwargs):
        raise AssertionError("Startup and task creation must never request a model")
    monkeypatch.setattr(OpenAITransport, "_request", no_paid_calls)
    monkeypatch.delenv("OPENAI_MAX_RETRIES", raising=False)
    monkeypatch.delenv("ANALYSIS_OUTPUT_LANGUAGE", raising=False)
    data = tmp_path / "saved"
    settings = local_server.local_settings(data, secret)
    assert settings.max_retries == 0
    assert settings.analysis_language == "Chinese"
    assert settings.cache_dir == data / "provider-cache"
    assert secret not in repr(settings)
    client = TestClient(local_server.local_app(data, settings))
    assert client.get("/").status_code == 200
    assert client.get("/api/health").json()["real_analysis"] == "configured"
    state = client.post("/api/tasks", json={"title": "Local persisted task"}).json()
    for endpoint in ("/", "/api/health", "/api/config", "/api/tasks"):
        assert secret not in client.get(endpoint).text
    reopened = TestClient(local_server.local_app(data, settings))
    assert reopened.get(f'/api/tasks/{state["task"]["task_id"]}').json() == state
    for file in data.rglob("*"):
        if file.is_file():
            assert secret.encode() not in file.read_bytes()


def test_reference_import_is_real_unanalyzed_and_respects_deleted_media(built_ui, tmp_path, monkeypatch):
    reference = generate_sample_media(tmp_path / "input.mp4")
    data = tmp_path / "saved"
    settings = local_server.local_settings(data, "sk-test-no-requests")
    def no_paid_calls(*args, **kwargs):
        raise AssertionError("Import must not analyze media")
    monkeypatch.setattr(OpenAITransport, "_request", no_paid_calls)
    app = local_server.local_app(data, settings, reference)
    state = app.state.service.store.list()[0]
    assert state.task.mode == "real"
    assert not state.analyses and not state.briefs and not state.jobs
    assert state.task.selected_direction is None
    reopened = local_server.local_app(data, settings, reference)
    assert len(reopened.state.service.store.list()) == 1
    service = reopened.state.service
    service.delete_video(state.task.task_id, state.task.version, state.task.current_video_id)
    after_deletion = local_server.local_app(data, settings, reference).state.service.store.list()
    assert len(after_deletion) == 1
    assert after_deletion[0].videos[0].deleted_at is not None
    assert len(after_deletion[0].videos) == 1


def test_unsupported_model_fails_before_serving(built_ui, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_VISION_MODEL", "not-reviewed-for-this-adapter")
    with pytest.raises(ValueError, match="模型"):
        local_server.local_settings(tmp_path / "data", "sk-test")
