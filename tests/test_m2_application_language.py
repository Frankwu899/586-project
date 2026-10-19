"""Application language governs authored assistance; supplied facts stay verbatim."""
import pytest

from backend.app.providers.config import ProviderSettings
from backend.app.providers.m2 import OpenAIM2AssistanceAdapter
from test_m2_assistance import FixtureTransport, draft, request


@pytest.mark.parametrize(('language', 'source', 'suggestion', 'note'), [
    ('English', '产品：便携水杯', 'People comparing portable drinkware', 'Audience is a suggestion.'),
    ('Chinese', 'Product: Portable cup', '正在比较便携饮具的人群', '受众是建议，需由用户确认。'),
])
def test_suggestions_and_notes_request_app_language(language, source, suggestion, note):
    transport = FixtureTransport({'candidates': [{'target': 'target_audience', 'origin': 'suggested',
        'value': suggestion, 'source_excerpt': None}], 'unresolved_notes': [note]})
    adapter = OpenAIM2AssistanceAdapter(ProviderSettings(analysis_language=language), transport=transport)
    result = adapter.assist(request(mode='suggest_task_field', requested_field='target_audience'), draft(source))
    assert result.candidates[0].value == suggestion and result.unresolved_notes == [note]
    prompt = transport.calls[0]['prompt']
    assert f'Write suggested values and unresolved_notes in {language}' in prompt
    assert 'separate Ideas generation language' in prompt


@pytest.mark.parametrize(('language', 'source', 'value'), [
    ('English', '批准文案：温暖，刚刚好', '温暖，刚刚好'),
    ('Chinese', 'Approved message: Warm, just right.', 'Warm, just right.'),
])
def test_extracted_fixed_wording_remains_source_language(language, source, value):
    transport = FixtureTransport({'candidates': [{'target': 'approved_messages', 'origin': 'extracted',
        'value': [value], 'source_excerpt': source}], 'unresolved_notes': []})
    adapter = OpenAIM2AssistanceAdapter(ProviderSettings(analysis_language=language), transport=transport)
    result = adapter.assist(request(), draft(source))
    assert result.candidates[0].value == [value]
    assert result.candidates[0].source_excerpt == source
    assert 'preserve those verbatim from source_notes' in transport.calls[0]['prompt']
