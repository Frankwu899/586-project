"""Structure stays source-grounded, durable and independent of creative approvals."""
import threading
from dataclasses import replace

import pytest

from backend.app.providers.base import ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.service import WorkflowService
from backend.app.structure_models import (AdoptRequest, AnalyzeRequest, FeedbackRequest, Gap,
                                         HandoffRequest, Source)
from backend.app.structure_provider import FeedbackContent, SampleStructureAgent
from backend.app.structure_service import StructureService, provider_graph, validate_graph
from backend.app.workflow_errors import WorkflowError


class ImmediateExecutor:
    def submit(self, function, *args):
        function(*args)


@pytest.fixture
def source(tmp_path):
    workflow = WorkflowService(tmp_path, provider_settings=ProviderSettings(cache_dir=tmp_path / 'provider-cache'))
    state = workflow.create('Structure source')
    state = workflow.load_sample(state.task.task_id, state.task.version)
    state = workflow.recognize(state.task.task_id, state.task.version)
    analysis = state.analyses[-1]
    video = state.videos[-1]
    return workflow, state, analysis, video


def real_source(source):
    workflow, state, analysis, video = source
    def convert(item):
        item.task.mode = 'real'
        item.videos[-1].input_method = 'file'
        item.videos[-1].sample_key = None
        item.videos[-1].origin.kind = 'provider'
        item.analyses[-1].origin.kind = 'provider'
    state = workflow.store.update(state.task.task_id, state.task.version, convert)
    return workflow, state, state.analyses[-1], state.videos[-1]


class ResearchAgent(SampleStructureAgent):
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []

    def draft(self, *args):
        self.calls.append('draft')
        graph = super().draft(*args)
        graph.research_gaps = [Gap(id='gap_context', question='What does the source actually claim?', why_it_matters='Attribute a claim accurately.')]
        return graph

    def research(self, workspace, *args):
        self.calls.append('research')
        if self.failure:
            raise self.failure
        graph = provider_graph(workspace.graph)
        graph.research_gaps = []
        graph.nodes[1].source_ids = ['source_brand']
        sources = [Source(id='source_brand', title='Brand source', url='https://example.org/product', claim='The brand describes a removable lid.', attribution='Brand claim, not independent validation')]
        return graph, sources

    def feedback(self, workspace, analysis, video, instruction, kind, node_id, language, metadata):
        self.calls.append('feedback')
        graph = provider_graph(workspace.graph) if kind != 'question' else None
        if graph:
            graph.nodes[1].explanation = 'The user-supplied context suggests a feature-to-choice connection.'
            graph.nodes[1].context_ids = [workspace.contexts[-1].id]
        return FeedbackContent(answer='This is an interpretation; it does not establish effectiveness.',
                               event_ids=['event_lid_text'], source_ids=[], graph=graph)


@pytest.mark.parametrize(('app_language', 'ideas_language'), [('English', 'Chinese'), ('Chinese', 'English')])
def test_structure_language_follows_application_not_ideas(source, app_language, ideas_language):
    workflow, state, analysis, video = real_source(source)
    workflow.provider_settings = replace(workflow.provider_settings, analysis_language=app_language)
    state = workflow.store.update(state.task.task_id, state.task.version,
        lambda item: setattr(item.task, 'generation_language', ideas_language))

    class LanguageAgent(ResearchAgent):
        def __init__(self):
            super().__init__()
            self.languages = []

        def draft(self, analysis, video, language, metadata):
            self.languages.append(language)
            return super().draft(analysis, video, language, metadata)

        def research(self, workspace, analysis, video, language, metadata):
            self.languages.append(language)
            return super().research(workspace, analysis, video, language, metadata)

        def feedback(self, workspace, analysis, video, instruction, kind, node_id, language, metadata):
            self.languages.append(language)
            return super().feedback(workspace, analysis, video, instruction, kind, node_id, language, metadata)

    agent = LanguageAgent()
    service = StructureService(workflow, agent=agent, executor=ImmediateExecutor())
    result = service.analyze(state.task.task_id, AnalyzeRequest())
    service.feedback(state.task.task_id, FeedbackRequest(expected_version=result.version,
        node_id='feature', instruction='Explain the mechanism.', kind='question'))
    assert agent.languages == [app_language, app_language, app_language]
    assert result.output_language == app_language


def test_feedback_preserves_saved_structure_language_after_app_switch(source):
    workflow, state, _, _ = real_source(source)
    agent = ResearchAgent()
    service = StructureService(workflow, agent=agent, executor=ImmediateExecutor())
    result = service.analyze(state.task.task_id, AnalyzeRequest())
    assert result.output_language == 'English'
    workflow.provider_settings = replace(workflow.provider_settings, analysis_language='Chinese')
    languages = []
    original_feedback = agent.feedback

    def feedback(workspace, analysis, video, instruction, kind, node_id, language, metadata):
        languages.append(language)
        return original_feedback(workspace, analysis, video, instruction, kind, node_id, language, metadata)

    agent.feedback = feedback
    service.feedback(state.task.task_id, FeedbackRequest(expected_version=result.version,
        node_id='feature', instruction='Explain the mechanism.', kind='question'))
    assert languages == ['English']


def test_explicit_sample_structure_respects_chinese_application_language(source):
    workflow, state, _, _ = source
    workflow.provider_settings = replace(workflow.provider_settings, analysis_language='Chinese')
    service = StructureService(workflow, executor=ImmediateExecutor())
    result = service.analyze(state.task.task_id, AnalyzeRequest())
    assert result.output_language == 'Chinese'
    assert result.graph.title == 'LumaCup：从功能展示到选择的虚构示例'
    assert result.origin == 'sample'


def test_sample_does_not_require_brief_approval_or_review_and_handoff_preserves_evidence(source):
    workflow, state, analysis, video = source
    assert not analysis.review.user_confirmed
    service = StructureService(workflow, executor=ImmediateExecutor())
    result = service.analyze(state.task.task_id, AnalyzeRequest())
    assert result.status == 'ready' and result.origin == 'sample'
    assert result.graph.nodes[0].moments[0].start_seconds == 0
    handoff = service.handoff(state.task.task_id, HandoffRequest(expected_version=result.version, method_ids=['visible_choice']))
    assert {n.id for n in handoff.nodes} == {'feature', 'choice'}
    assert handoff.analysis_ref == state.task.current_analysis
    assert handoff.methods[0].conditions
    assert service.get_handoff(state.task.task_id) == handoff
    reopened = StructureService(workflow, executor=ImmediateExecutor())
    assert reopened.get(state.task.task_id).graph == result.graph
    assert workflow.store.get(state.task.task_id) == state


def test_unknown_upload_cannot_get_sample_even_if_bytes_match_fixture(source):
    workflow, state, analysis, video = real_source(source)
    service = StructureService(workflow, executor=ImmediateExecutor())
    result = service.analyze(state.task.task_id, AnalyzeRequest())
    assert result.status == 'failed' and result.graph is None
    assert result.origin == 'provider'
    assert result.error.code == 'provider_not_configured'


@pytest.mark.parametrize('code', ['research_budget_exhausted', 'provider_timeout', 'research_no_sources'])
def test_research_failure_keeps_completed_video_graph_and_stops(source, code):
    workflow, state, analysis, video = real_source(source)
    agent = ResearchAgent(ProviderError(code, 'Research stopped.'))
    service = StructureService(workflow, agent=agent, executor=ImmediateExecutor())
    result = service.analyze(state.task.task_id, AnalyzeRequest())
    assert result.status == 'partial' and result.graph
    assert result.error.code == code and agent.calls == ['draft', 'research']
    assert 'ended' in result.research_note


def test_made_up_evidence_and_provider_timestamps_are_rejected(source):
    _, _, analysis, video = source
    graph = SampleStructureAgent().draft(analysis, video, 'English', {})
    graph.nodes[0].event_ids = ['from-another-analysis']
    with pytest.raises(ValueError, match='exact source'):
        validate_graph(graph, analysis, video)
    graph = SampleStructureAgent().draft(analysis, video, 'English', {})
    graph = validate_graph(graph, analysis, video)
    with pytest.raises(ValueError, match='manufacture'):
        validate_graph(graph, analysis, video)


def test_feedback_is_previewed_before_adoption_and_user_context_persists(source):
    workflow, state, analysis, video = real_source(source)
    agent = ResearchAgent()
    service = StructureService(workflow, agent=agent, executor=ImmediateExecutor())
    result = service.analyze(state.task.task_id, AnalyzeRequest())
    original_graph = result.graph.model_copy(deep=True)
    result = service.feedback(state.task.task_id, FeedbackRequest(expected_version=result.version,
        node_id='feature', instruction='Focus on a useful choice rather than low price.', kind='context'))
    assert result.feedback_status == 'idle' and result.contexts
    assert result.graph == original_graph and result.proposals[0].status == 'pending'
    assert agent.calls == ['draft', 'research', 'feedback']  # No further search.
    result = service.adopt(state.task.task_id, result.proposals[0].id, AdoptRequest(expected_version=result.version))
    assert result.graph != original_graph and result.contexts[0].text.startswith('Focus')
    assert result.proposals[0].status == 'adopted'
    assert result.graph.nodes[1].kind == 'inference'
    with pytest.raises(WorkflowError, match='changed'):
        service.handoff(state.task.task_id, HandoffRequest(expected_version=1, all=True))


def test_old_proposal_cannot_overwrite_adopted_changes(source):
    workflow, state, _, _ = real_source(source)
    service = StructureService(workflow, agent=ResearchAgent(), executor=ImmediateExecutor())
    item = service.analyze(state.task.task_id, AnalyzeRequest())
    for instruction in ['First correction', 'Second correction']:
        item = service.feedback(state.task.task_id, FeedbackRequest(expected_version=item.version, node_id='feature', instruction=instruction, kind='reconsider'))
    item = service.adopt(state.task.task_id, item.proposals[1].id, AdoptRequest(expected_version=item.version))
    assert item.proposals[0].status == 'superseded'
    with pytest.raises(WorkflowError):
        service.adopt(state.task.task_id, item.proposals[0].id, AdoptRequest(expected_version=item.version))


def test_source_change_marks_history_and_prevents_new_handoff(source):
    workflow, state, _, _ = source
    service = StructureService(workflow, executor=ImmediateExecutor())
    item = service.analyze(state.task.task_id, AnalyzeRequest())
    state = workflow.recognize(state.task.task_id, state.task.version)
    assert service.get(state.task.task_id).outdated
    with pytest.raises(WorkflowError) as error:
        service.handoff(state.task.task_id, HandoffRequest(expected_version=item.version, all=True))
    assert error.value.code == 'structure_source_changed'
    assert service.get(state.task.task_id).graph == item.graph


def test_restart_retains_draft_and_does_not_resume_paid_work(source):
    workflow, state, _, _ = source
    service = StructureService(workflow, executor=ImmediateExecutor())
    item = service.analyze(state.task.task_id, AnalyzeRequest())
    service.store.update(item.structure_id, lambda value: setattr(value, 'status', 'researching'))
    reopened = StructureService(workflow, executor=ImmediateExecutor())
    result = reopened.get(state.task.task_id)
    assert result.status == 'partial' and result.graph
    assert result.error.code == 'interrupted_structure'


def test_draft_is_visible_while_research_is_running_and_navigation_data_available(source):
    workflow, state, _, _ = real_source(source)
    entered, release = threading.Event(), threading.Event()
    class WaitingAgent(ResearchAgent):
        def research(self, *args):
            entered.set()
            assert release.wait(5)
            return super().research(*args)
    service = StructureService(workflow, agent=WaitingAgent())
    try:
        service.analyze(state.task.task_id, AnalyzeRequest())
        assert entered.wait(5)
        item = service.get(state.task.task_id)
        assert item.graph and item.status == 'researching'
        assert workflow.store.get(state.task.task_id).task.task_id == state.task.task_id
        with pytest.raises(WorkflowError) as error:
            service.analyze(state.task.task_id, AnalyzeRequest())
        assert error.value.code == 'structure_busy'
    finally:
        release.set()
        service.executor.shutdown(wait=True)
