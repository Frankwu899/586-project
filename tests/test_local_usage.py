"""Local generation is independent of the Cloud experiment cap; HTTP is mocked."""
from datetime import date
import json
import sqlite3

import httpx
from fastapi.testclient import TestClient
import pytest

from backend.app.providers.base import ProviderError
from backend.app.providers.budget import ExperimentBudget
from backend.app.providers.config import ProviderSettings
from backend.app.providers import local_usage
from backend.app.providers.transport import OpenAITransport
from scripts import local_server
from scripts.evaluate_modules import evaluation_settings
from test_local_connection import provider_settings


def blocked_ledger(path):
    ExperimentBudget(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE budget SET blocked=1,maximum=1")
    return path.read_bytes()


@pytest.mark.parametrize("module", ["vision", "m2_assistance", "creative", "structure", "research", "timestamped_transcription"])
def test_every_local_capability_ignores_old_blocked_ledger_and_skips_budget_preflight(tmp_path, module):
    settings = local_server.local_settings(tmp_path, "synthetic-key")
    before = blocked_ledger(settings.budget_path)
    calls = []
    model = settings.transcription_model if module == "timestamped_transcription" else settings.research_model if module == "research" else settings.creative_model
    def handle(request):
        calls.append(request.url.path)
        assert request.url.path in ('/v1/responses', '/v1/audio/transcriptions')
        return httpx.Response(200, json={"status": "completed", "model": model,
            "usage": {"input_tokens": 400000, "output_tokens": 100},
            "output": [{"content": [{"type": "output_text", "text": '{"ok":true}'}]}]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        transport = OpenAITransport(settings, client=client)
        payload = {"model": model, "input": "synthetic", "max_output_tokens": 8000}
        if module == "research":
            payload.update(tools=[{"type": "web_search", "search_context_size": "low"}], max_tool_calls=2)
        audio = None
        if module == "timestamped_transcription":
            audio = tmp_path / 'audio.wav'
            audio.write_bytes(b'offline fixture')
        result = transport._request('audio/transcriptions' if audio else 'responses', model,
                                    payload, metadata={"capability": module, "audio_seconds": 30}, audio_path=audio)
        assert result['status'] == 'completed'
    assert len(calls) == 1
    assert settings.budget_path.read_bytes() == before
    usage = local_usage.local_usage_summary(settings.cache_dir)
    assert usage['enforced'] is False and usage['blocked'] is False
    assert usage['maximum_usd'] is None and usage['remaining_usd'] is None
    assert usage['attempts'] == 1 and usage['unknown_attempts'] == 0
    assert 'synthetic-key' not in (settings.cache_dir / 'usage.jsonl').read_text()


def test_real_transport_path_does_not_fall_back_to_cloud_budget(tmp_path, monkeypatch):
    settings = local_server.local_settings(tmp_path, "synthetic-key")
    monkeypatch.setattr('backend.app.providers.transport.ExperimentBudget', lambda *a, **k: pytest.fail('Local transport must not construct the experiment ledger'))
    # No MockTransport shortcut is involved in obtaining this accounting policy.
    assert OpenAITransport(settings)._experiment_budget() is None


def test_client_ignores_stale_budget_environment_but_cloud_remains_capped(tmp_path, monkeypatch):
    monkeypatch.setenv('VIDEO_EXPERIMENT_MAX_USD', '0.000001')
    client = local_server.local_settings(tmp_path, '', allow_empty=True)
    assert client.experiment_budget_enabled is False
    cloud = evaluation_settings(tmp_path, {})
    assert cloud.experiment_budget_enabled is True and cloud.experiment_max_usd == '3'
    blocked_ledger(cloud.budget_path)
    with pytest.raises(ProviderError, match='budget'):
        ExperimentBudget(cloud.budget_path).reserve('gpt-6.1-sol', {'max_output_tokens': 100, '_input_tokens_bound': 100})
    monkeypatch.setenv('VIDEO_EXPERIMENT_MAX_USD', '100')
    assert local_server.local_settings(tmp_path, '', allow_empty=True).experiment_budget_enabled is False
    with pytest.raises(ValueError, match='USD 3'):
        ProviderSettings.from_env()


def test_broken_cost_reporting_and_old_prices_cannot_discard_a_generated_result(tmp_path, monkeypatch):
    settings = local_server.local_settings(tmp_path, 'synthetic-key')
    monkeypatch.setattr(local_usage, 'PRICING_VERIFIED_ON', date(2000, 1, 1))
    settings.cache_dir.mkdir()
    (settings.cache_dir / 'usage.jsonl').mkdir()  # Simulate an unwritable log destination.
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={
        'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': '{"retained":true}'}]}]}))) as client:
        transport = OpenAITransport(settings, client=client)
        assert transport.json_response('gpt-6.1-sol', 'fixture', {}, 'fixture') == {'retained': True}
    assert transport.records[0]['estimated_cost_usd'] is None
    assert transport.records[0]['diagnostics_error'] == 'usage_write_failed'
    assert not settings.budget_path.exists()


def test_usage_summary_preserves_unknown_costs_and_skips_corrupt_rows(tmp_path):
    path = tmp_path / 'usage.jsonl'
    records = [
        {'attempts': 1, 'known_estimated_cost_usd': '0.1', 'unknown_attempts': 0},
        {'attempts': 1, 'estimated_cost_usd': None},
        {'attempts': 0, 'estimated_cost_usd': None},
        {'attempts': 1, 'estimated_cost_usd': 'NaN'},
    ]
    path.write_text('\n'.join(json.dumps(row) for row in records) + '\n{broken\n')
    before = path.read_bytes()
    result = local_usage.local_usage_summary(tmp_path)
    assert result['attempts'] == 2 and result['unknown_attempts'] == 1
    assert result['known_estimated_cost_usd'] == '0.1' and result['unreadable_records'] == 2
    assert path.read_bytes() == before


def test_local_settings_api_and_adapter_replacements_never_reenable_old_budget(tmp_path, monkeypatch):
    root = tmp_path / 'app'
    (root / 'frontend/dist').mkdir(parents=True)
    (root / 'frontend/dist/index.html').write_text('<title>Offline</title>')
    monkeypatch.setattr(local_server, 'ROOT', root)
    settings = local_server.local_settings(tmp_path / 'library', 'synthetic-key')
    before = blocked_ledger(settings.budget_path)
    app = local_server.local_app(settings.budget_path.parent, settings)
    try:
        with TestClient(app) as client:
            summary = client.get('/api/local/budget').json()
            assert summary['enforced'] is False and summary['blocked'] is False
            assert client.post('/api/local/budget/reconcile').json()['reconciled_attempts'] == 0
            assert client.post('/api/local/preferences', json={'language': 'Chinese'}).status_code == 200
            assert all(s.experiment_budget_enabled is False for s in provider_settings(app))
            connection = app.state.local_connection
            connection.apply(connection.replacements('synthetic-replacement'))
            assert all(s.experiment_budget_enabled is False for s in provider_settings(app))
            assert all(s.api_key == 'synthetic-replacement' for s in provider_settings(app))
        assert settings.budget_path.read_bytes() == before
    finally:
        app.state.operations.pool.shutdown(wait=True)
        app.state.structure_service.executor.shutdown(wait=True)
