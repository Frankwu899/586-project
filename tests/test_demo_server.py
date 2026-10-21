"""The one-command demo never inherits credentials or calls paid providers."""
from fastapi.testclient import TestClient

from scripts import demo_server


def test_demo_ignores_inherited_credentials_and_serves_ui_beside_api(tmp_path, monkeypatch):
    # A deterministic built-entry fixture keeps backend tests independent of a
    # Node installation; the real Vite build is checked separately in CI/demo.
    build = tmp_path / 'app' / 'frontend' / 'dist'
    build.mkdir(parents=True)
    index = '<!doctype html><html><title>Video Anatomy</title><div id="root"></div><script src="/assets/workspace.js"></script></html>'
    (build / 'index.html').write_text(index)
    (build / 'assets').mkdir()
    (build / 'assets' / 'workspace.js').write_text('window.demoAssetLoaded = true;')
    monkeypatch.setattr(demo_server, 'ROOT', tmp_path / 'app')
    monkeypatch.setenv('OPENAI_API_KEY', 'inherited-secret-that-must-never-be-used')
    monkeypatch.setenv('M2_PROVIDER', 'openai')
    def disallow_environment_config(cls):
        raise AssertionError('The offline demo must never construct provider settings from the environment')
    monkeypatch.setattr(demo_server.ProviderSettings, 'from_env', classmethod(disallow_environment_config))
    app = demo_server.demo_app(tmp_path / 'saved-tasks')
    assert app.state.service.provider_settings.api_key == ''
    assert app.state.service.provider_settings.m2_provider == 'disabled'
    client = TestClient(app)
    assert client.get('/').text == index
    assert client.get('/assets/workspace.js').status_code == 200
    health = client.get('/api/health')
    assert health.status_code == 200
    assert health.json()['schema_version'] == '0.7.0'
    assert health.json()['real_analysis'] == 'unconfigured'
    assert health.json()['creative_generation'] == 'unconfigured_for_real_tasks'
    assert health.json()['sample_workflow'] == 'available_offline'
    created = client.post('/api/tasks', json={'title': 'Offline persisted demo'})
    assert created.status_code == 201
    task_id = created.json()['task']['task_id']
    reopened = TestClient(demo_server.demo_app(tmp_path / 'saved-tasks'))
    assert reopened.get(f'/api/tasks/{task_id}').json()['task']['title'] == 'Offline persisted demo'
