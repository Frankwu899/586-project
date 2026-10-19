"""HTTP integration for the additive Structure workspace and exact selection boundary."""
from fastapi.testclient import TestClient

from backend.app.api import create_app


class ImmediateExecutor:
    def submit(self, function, *args):
        function(*args)


def sample(client):
    task = client.post('/api/tasks', json={'title':'Structure API sample'}).json()
    task_id = task['task']['task_id']
    task = client.post(f'/api/tasks/{task_id}/sample', json={'expected_version':task['task']['version']}).json()
    task = client.post(f'/api/tasks/{task_id}/recognize', json={'expected_version':task['task']['version']}).json()
    assert task['analyses'][-1]['status'] == 'succeeded'
    return task_id, task


def test_structure_http_sample_handoff_isolation_and_no_editor_endpoint(tmp_path):
    app = create_app(tmp_path)
    app.state.structure_service.executor = ImmediateExecutor()
    client = TestClient(app)
    task_id, task = sample(client)
    base = f'/api/tasks/{task_id}/structure'
    assert client.get(base).json() is None
    response = client.post(base + '/analyze', json={})
    assert response.status_code == 202, response.text
    structure = response.json()
    assert structure['status'] == 'ready' and structure['origin'] == 'sample'
    assert not task['analyses'][0]['review']['user_confirmed']
    assert client.get(base).json()['analysis_ref'] == task['task']['current_analysis']
    result = client.post(base + '/handoff', json={'expected_version':structure['version'], 'method_ids':['visible_choice']})
    assert result.status_code == 200, result.text
    assert result.json()['methods'][0]['conditions']
    assert client.get(base + '/handoff').json() == result.json()
    other = client.post('/api/tasks', json={'title':'Other task'}).json()['task']['task_id']
    assert client.get(f'/api/tasks/{other}/structure/handoff').json() is None
    assert client.post(f'/api/tasks/{other}/structure/proposals/fake/adopt', json={'expected_version':1}).status_code == 409
    assert client.post(base + '/nodes', json={}).status_code == 404
    assert client.post(base + '/research/continue', json={}).status_code == 404
    assert client.post(base + '/analyze', json={'unbounded':True}).status_code == 422


def test_structure_source_evidence_does_not_get_creative_approval(tmp_path):
    app = create_app(tmp_path)
    app.state.structure_service.executor = ImmediateExecutor()
    client = TestClient(app)
    task_id, task = sample(client)
    base = f'/api/tasks/{task_id}/structure'
    structure = client.post(base + '/analyze', json={}).json()
    feedback = client.post(base + '/feedback', json={'expected_version':structure['version'], 'node_id':'feature',
        'instruction':'Does this prove the product works?', 'kind':'question'})
    assert feedback.status_code == 202, feedback.text
    assert feedback.json()['answers'][0]['question'] == 'Does this prove the product works?'
    assert 'scripted' in feedback.json()['answers'][0]['answer']
    current = client.get(f'/api/tasks/{task_id}').json()
    assert current['task']['selected_direction'] is None
    assert not current['analyses'][0]['review']['user_confirmed']
