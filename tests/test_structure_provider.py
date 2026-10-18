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
    def json_response(self, model, prompt, schema, name, metadata=None):
        self.calls.append(('json', name, metadata))
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
