"""Offline provider boundary: no fabricated sources, schema-bound citations and bounded research."""
import time

import pytest

from backend.app.models import VideoAsset, VersionRef
from backend.app.providers.base import ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.sample import sample_analysis
from backend.app.structure_models import Workspace
from backend.app.structure_provider import OpenAIStructureAgent, SampleStructureAgent, grounded_schema
from backend.app.structure_models import Graph
from backend.app.structure_service import validate_graph


@pytest.fixture
def evidence():
    video = VideoAsset(video_id='video_test', task_id='task_test', input_method='sample',
        storage_id='a'*32+'.mp4', duration_seconds=10, intake_status='ready',
        frame_timing={'fps_numerator':20, 'fps_denominator':1, 'frame_count':200,
                      'frame_boundaries_seconds':[i / 20 for i in range(201)], 'rate_mode':'constant'},
        origin={'kind':'sample','description':'Explicit test fixture'})
    analysis = sample_analysis('task_test', video, 'job_test')
    graph = SampleStructureAgent().draft(analysis, video, 'English', {})
    return analysis, video, graph


class Transport:
    def __init__(self, responses, search=None):
        self.responses = list(responses)
        self.search = search
        self.calls = []
        self.records = []
        self.prompts = []
    def json_response(self, model, prompt, schema, name, metadata=None):
        self.calls.append(('json', name, metadata))
        self.prompts.append(prompt)
        self.records.append({'usage': {'input_tokens':12, 'output_tokens':30}})
        return self.responses.pop(0)
    def web_search(self, model, prompt, *, max_tool_calls, metadata):
        self.calls.append(('search', max_tool_calls, metadata))
        return self.search


def test_initial_graph_schema_exact_event_citations_and_no_source_guessing(evidence):
    analysis, video, graph = evidence
    transport = Transport([graph.model_dump()])
    agent = OpenAIStructureAgent(ProviderSettings(), transport=transport)
    result = agent.draft(analysis, video, 'English', {})
    assert validate_graph(result, analysis, video).nodes[0].moments
    schema = grounded_schema(Graph, analysis)
    node = schema['$defs']['Node']['properties']
    assert set(node['event_ids']['items']['enum']) == {event.event_id for event in analysis.events}
    assert node['source_ids']['maxItems'] == 0
    assert node['context_ids']['maxItems'] == 0
    assert len(transport.calls) == 1


def test_research_refuses_model_invented_url(evidence):
    analysis, video, graph = evidence
    workspace = Workspace(structure_id='structure_test', task_id='task_test', video_id=video.video_id,
        analysis_ref=VersionRef(id=analysis.analysis_id, revision=1), origin='provider', graph=graph)
    content = {'graph':graph.model_dump(), 'sources':[{'id':'source_1', 'title':'Unretrieved source',
        'url':'https://invented.example/page', 'claim':'Claim', 'attribution':'Publisher statement'}]}
    transport = Transport([content], {'text':'An attributed source.', 'sources':[{'url':'https://real.example/page','title':'Source'}], 'citations':[], 'tool_calls':1})
    agent = OpenAIStructureAgent(ProviderSettings(), transport=transport)
    with pytest.raises(ProviderError) as error:
        agent.research(workspace, analysis, video, 'English', {})
    assert error.value.code == 'invalid_research_source'
    assert [call[0] for call in transport.calls] == ['search','json']
    assert transport.calls[0][1] == 2


def test_research_without_citations_stops_before_synthesis(evidence):
    analysis, video, graph = evidence
    workspace = Workspace(structure_id='structure_test', task_id='task_test', video_id=video.video_id,
        analysis_ref=VersionRef(id=analysis.analysis_id, revision=1), origin='provider', graph=graph)
    transport = Transport([], {'text':'No source found.', 'sources':[], 'citations':[], 'tool_calls':1})
    agent = OpenAIStructureAgent(ProviderSettings(), transport=transport)
    with pytest.raises(ProviderError) as error:
        agent.research(workspace, analysis, video, 'English', {})
    assert error.value.code == 'research_no_sources'
    assert len(transport.calls) == 1


def test_elapsed_run_deadline_blocks_following_billable_phase(evidence):
    analysis, video, graph = evidence
    transport = Transport([graph.model_dump()])
    agent = OpenAIStructureAgent(ProviderSettings(), transport=transport)
    with pytest.raises(ProviderError) as error:
        agent.draft(analysis, video, 'English', {'_deadline':time.monotonic()-1})
    assert error.value.code == 'structure_time_limit'
    assert transport.calls == []


def test_absolute_run_deadline_reaches_structured_and_search_transports(evidence):
    analysis, video, graph = evidence
    deadline = time.monotonic() + 30
    transport = Transport([graph.model_dump()], {'text': 'No source found.', 'sources': [], 'citations': []})
    agent = OpenAIStructureAgent(ProviderSettings(), transport=transport)
    agent.draft(analysis, video, 'English', {'_deadline': deadline})
    assert transport.calls[0][2]['_deadline'] == deadline
    workspace = Workspace(structure_id='structure_test', task_id='task_test', video_id=video.video_id,
        analysis_ref=VersionRef(id=analysis.analysis_id, revision=1), origin='provider', graph=graph)
    with pytest.raises(ProviderError, match='no attributable sources'):
        agent.research(workspace, analysis, video, 'English', {'_deadline': deadline})
    assert transport.calls[-1][2]['_deadline'] == deadline


def test_external_background_never_acquires_invented_video_time(evidence):
    analysis, video, graph = evidence
    from backend.app.structure_models import Node, Source
    source = Source(id='external', title='Article', url='https://example.org/article',
                    claim='The publisher makes this claim.', attribution='Publisher')
    graph.nodes.append(Node(id='background', label='Publisher context', explanation='Attributed contextual statement.',
        kind='source_claim', event_ids=[], source_ids=['external'], context_ids=[]))
    result = validate_graph(graph, analysis, video, [source])
    assert result.nodes[-1].moments == []
    assert result.nodes[-1].kind == 'source_claim'


def test_sampled_visual_observation_retains_point_precision(evidence):
    analysis, video, graph = evidence
    analysis.events[0].end_frame = 1
    result = validate_graph(graph, analysis, video)
    assert result.nodes[0].moments[0].precision == 'sample'
    assert result.nodes[0].moments[0].end_seconds == .05


def test_structure_receives_visual_details_and_coverage_limits(evidence):
    from backend.app.structure_provider import source_payload
    analysis, _, _ = evidence
    original_visual = next(event for event in analysis.events if event.kind == 'visual_action')
    from backend.app.models import VisualDetails
    original_visual.visual_details = VisualDetails.model_validate({
        name: {'status': 'none_found', 'items': [], 'error': None}
        for name in ('subjects', 'actions', 'product_presentations')})
    payload = source_payload(analysis)
    visual = next(event for event in payload['events'] if event['event_id'] == original_visual.event_id)
    assert visual['visual_details'] == original_visual.visual_details.model_dump(mode='json')
    assert not payload['coverage_limits']
    analysis.events = [event for event in analysis.events if event.kind not in ('visual_action', 'on_screen_text')]
    analysis.status = 'partial'
    limits = source_payload(analysis)['coverage_limits']
    assert len(limits) == 3
    assert any('No usable visual observations' in limit for limit in limits)
    assert any('No readable on-screen text' in limit for limit in limits)


def test_method_generation_is_grounded_mechanism_analysis_in_requested_language(evidence):
    analysis, video, graph = evidence
    transport = Transport([graph.model_dump()])
    agent = OpenAIStructureAgent(ProviderSettings(), transport=transport)
    agent.draft(analysis, video, 'English', {})
    prompt = transport.prompts[-1]
    assert 'all titles, labels, summaries, explanations, methods, conditions, gaps and answers in English' in prompt
    assert 'prerequisites for transfer and a limitation' in prompt
    assert 'specific communication mechanism' in prompt
    assert 'Keep quoted source words' in prompt
    assert 'transcript is evidence of what someone says' in prompt
    assert 'rod tips' not in prompt and 'seat rotation' not in prompt


def test_speech_only_claim_is_not_promoted_to_a_visual_observation(evidence):
    from backend.app.structure_provider import source_payload
    analysis, _, _ = evidence
    from backend.app.models import EvidenceEvent
    speech = EvidenceEvent(event_id='speech_only', video_id=analysis.video_id, lane='audio', kind='speech',
        start_frame=0, end_frame=2, text='It fits in a pocket.', source='offline fixture', method='transcription')
    analysis.events = [speech]
    analysis.segments = []
    analysis.status = 'partial'
    analysis.coverage.visual_action = analysis.coverage.on_screen_text = 'failed'
    analysis.coverage.speech = 'observations'
    payload = source_payload(analysis)
    assert payload['events'][0]['text'] == 'It fits in a pocket.'
    assert payload['events'][0]['visual_details'] is None
    assert payload['coverage']['visual_action'] == 'failed'
    assert len(payload['coverage_limits']) == 3
