"""Asynchronous source-bound Structure orchestration with durable partial results."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import time
from uuid import uuid4

from pydantic import ValidationError

from .models import VersionRef
from .providers.base import ProviderError
from .structure_models import (Answer, Graph, Handoff, Moment, Proposal, StructureError,
                               UserContext, Workspace)
from .structure_provider import OpenAIStructureAgent, SampleStructureAgent, PROMPT_VERSION
from .structure_store import StructureStore
from .workflow_errors import WorkflowError


def uid(prefix):
    return f"{prefix}_{uuid4().hex}"


def validate_graph(graph, analysis, video, sources=(), contexts=()):
    """The model chooses citations, never clocks; exact source timing is server-owned."""
    graph = Graph.model_validate(graph.model_dump())
    event_map = {event.event_id: event for event in analysis.events}
    source_ids, context_ids = {s.id for s in sources}, {c.id for c in contexts}
    if len(source_ids) != len(sources):
        raise ValueError("Research source IDs must be unique")
    for node in graph.nodes:
        if not set(node.event_ids) <= event_map.keys() or not set(node.source_ids) <= source_ids or not set(node.context_ids) <= context_ids:
            raise ValueError("Structure evidence must belong to the exact source analysis and supplied sources/context")
        if node.moments:
            raise ValueError("Providers must not manufacture source timing")
        for event_id in node.event_ids:
            event = event_map[event_id]
            if event.start_frame is not None and video.frame_timing:
                start = video.frame_timing.frame_boundaries_seconds[event.start_frame]
                end = video.frame_timing.frame_boundaries_seconds[event.end_frame]
                precision = "sample" if event.lane == "visual" and event.end_frame - event.start_frame == 1 else "interval"
            elif event.legacy_seconds:
                start, end, precision = event.legacy_seconds.start_seconds, event.legacy_seconds.end_seconds, "interval"
            else:
                raise ValueError("Source evidence has no usable measured timing")
            node.moments.append(Moment(event_id=event_id, start_frame=event.start_frame, end_frame=event.end_frame,
                                       start_seconds=start, end_seconds=end, precision=precision))
    return graph


def provider_graph(graph):
    graph = graph.model_copy(deep=True)
    for node in graph.nodes:
        node.moments = []
    return graph


class StructureService:
    def __init__(self, workflow, *, agent=None, executor=None, recover=True, max_seconds=None):
        self.workflow = workflow
        self.store = StructureStore(workflow.store.path)
        self.agent = agent or OpenAIStructureAgent(workflow.provider_settings)
        self.sample_agent = SampleStructureAgent()
        self.executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="structure")
        self.max_seconds = max_seconds or getattr(workflow.provider_settings, "structure_max_seconds", 120)
        if recover:
            self.store.recover()

    def get(self, task_id):
        state = self.workflow.store.get(task_id)
        workspace = self.store.latest(task_id)
        if workspace:
            workspace.outdated = state.task.current_analysis != workspace.analysis_ref
            video = next((v for v in state.videos if v.video_id == workspace.video_id), None)
            workspace.source_deleted = video is None or video.deleted_at is not None
        return workspace

    def _source(self, task_id, analysis_ref=None):
        state = self.workflow.store.get(task_id)
        ref = analysis_ref or state.task.current_analysis
        if ref is None or ref != state.task.current_analysis:
            raise WorkflowError("structure_source_changed", "Select the current video analysis before starting Structure.")
        analysis = next((a for a in state.analyses if a.analysis_id == ref.id and a.revision == ref.revision), None)
        if analysis is None or analysis.status not in ("succeeded", "partial") or not analysis.events:
            raise WorkflowError("structure_needs_observations", "Analyze the video first. Structure needs usable video observations, but does not require creative approval.")
        video = next((v for v in state.videos if v.video_id == analysis.video_id), None)
        if video is None or video.deleted_at is not None:
            raise WorkflowError("structure_source_deleted", "This source video was removed. Its saved Structure remains available.")
        sample = state.task.mode == "sample" and video.input_method == "sample" and analysis.origin.kind == "sample"
        return analysis, video, self.workflow.provider_settings.analysis_language, sample

    def analyze(self, task_id, request):
        analysis, video, language, sample = self._source(task_id, request.analysis_ref)
        workspace = Workspace(structure_id=uid("structure"), task_id=task_id, video_id=video.video_id,
                              analysis_ref=VersionRef(id=analysis.analysis_id, revision=analysis.revision),
                              origin="sample" if sample else "provider", output_language=language)
        self.store.create(workspace)
        self.executor.submit(self._analyze, workspace.structure_id, analysis, video, language, sample)
        return self.get(task_id)

    def _metadata(self, workspace):
        return {"capability": "structure", "structure_id": workspace.structure_id,
                "task_id": workspace.task_id, "analysis_id": workspace.analysis_ref.id,
                "analysis_revision": workspace.analysis_ref.revision, "prompt_version": PROMPT_VERSION}

    def _analyze(self, structure_id, analysis, video, language, sample):
        started = time.monotonic()
        workspace = self.store.get(structure_id)
        agent = self.sample_agent if sample else self.agent
        metadata = {**self._metadata(workspace), "_deadline": started + self.max_seconds}
        try:
            graph = validate_graph(agent.draft(analysis, video, language, metadata), analysis, video)
            research_needed = bool(graph.research_gaps) and not sample
            def publish(item):
                item.graph = graph
                item.graph_revision += 1
                item.status = "researching" if research_needed else "ready"
                item.research_note = ("Fictional sample; no API or research calls." if sample else
                                      "Checking focused background sources." if research_needed else "No external background was required by this analysis.")
            workspace = self.store.update(structure_id, publish)
            if not research_needed:
                return
            if time.monotonic() - started >= self.max_seconds:
                raise ProviderError("structure_time_limit", "The run reached its time limit. Completed analysis is retained.")
            research_input = workspace.model_copy(deep=True)
            research_input.graph = provider_graph(research_input.graph)
            graph, sources = agent.research(research_input, analysis, video, language, metadata)
            graph = validate_graph(graph, analysis, video, sources, workspace.contexts)
            def finish(item):
                # Concurrent supplied context is never silently erased by research.
                if item.contexts != workspace.contexts or item.graph_revision != workspace.graph_revision:
                    item.proposals.append(self._proposal(item, graph, sources, "Background research suggests these updates."))
                    item.research_note = "Research completed; an update is available for preview. Your context is preserved."
                else:
                    item.graph, item.sources = graph, sources
                    item.graph_revision += 1
                    item.research_note = "Background sources were added. Interpretive claims remain inferences."
                item.status = "partial" if graph.research_gaps else "ready"
            self.store.update(structure_id, finish)
        except Exception as exc:
            self._fail(structure_id, exc)

    def _fail(self, structure_id, exc, *, feedback=False):
        if isinstance(exc, (ProviderError, WorkflowError)):
            code, message = exc.code, exc.message
        elif isinstance(exc, (ValueError, ValidationError)):
            code, message = "invalid_structure_output", "The agent returned unsupported citations or an invalid graph. Completed work is retained."
        else:
            code, message = "structure_failed", "Structure processing could not finish. Completed work and supplied context are retained."
        def fail(item):
            item.error = StructureError(code=code, message=message)
            if feedback:
                item.feedback_status = "failed"
            else:
                item.status = "partial" if item.graph else "failed"
                item.research_note = "Showing completed analysis. This run has ended."
        self.store.update(structure_id, fail)

    def _editable(self, task_id):
        workspace = self.get(task_id)
        if workspace is None or workspace.graph is None:
            raise WorkflowError("structure_not_ready", "Structure has no completed graph yet.")
        if workspace.outdated or workspace.source_deleted:
            raise WorkflowError("structure_source_changed", "This saved Structure uses a previous or removed source. Open a current analysis to create new results.")
        return workspace

    def feedback(self, task_id, request):
        workspace = self._editable(task_id)
        if request.node_id not in {n.id for n in workspace.graph.nodes}:
            raise WorkflowError("structure_node_not_found", "This node does not belong to the saved graph.", 422)
        analysis, video, language, sample = self._source(task_id, workspace.analysis_ref)
        language = workspace.output_language or language
        def begin(item):
            if item.feedback_status == "running":
                raise WorkflowError("structure_feedback_busy", "A response is already being prepared for this graph.")
            item.feedback_status = "running"
            item.error = None
            if request.kind in ("context", "reconsider"):
                item.contexts.append(UserContext(id=uid("context"), node_id=request.node_id, text=request.instruction))
        workspace = self.store.update(workspace.structure_id, begin, request.expected_version)
        self.executor.submit(self._feedback, workspace, request, analysis, video, language, sample)
        return self.get(task_id)

    def _feedback(self, workspace, request, analysis, video, language, sample):
        try:
            agent = self.sample_agent if sample else self.agent
            agent_input = workspace.model_copy(deep=True)
            agent_input.graph = provider_graph(agent_input.graph)
            content = agent.feedback(agent_input, analysis, video, request.instruction, request.kind,
                                     request.node_id, language, self._metadata(workspace))
            if not set(content.event_ids) <= {e.event_id for e in analysis.events} or not set(content.source_ids) <= {s.id for s in workspace.sources}:
                raise ValueError("Feedback cited unavailable evidence")
            if request.kind == "question" and content.graph is not None:
                raise ValueError("A question must not mutate the graph")
            graph = validate_graph(content.graph, analysis, video, workspace.sources, workspace.contexts) if content.graph else None
            def finish(item):
                item.answers.append(Answer(id=uid("answer"), node_id=request.node_id, question=request.instruction,
                    answer=content.answer, event_ids=content.event_ids, source_ids=content.source_ids))
                if graph:
                    item.proposals.append(self._proposal(workspace, graph, workspace.sources, content.answer))
                item.feedback_status = "idle"
            self.store.update(workspace.structure_id, finish)
        except Exception as exc:
            self._fail(workspace.structure_id, exc, feedback=True)

    def _proposal(self, workspace, graph, sources, reason):
        old = {n.id: n.model_dump() for n in workspace.graph.nodes}
        new = {n.id: n.model_dump() for n in graph.nodes}
        affected = [key for key in sorted(old.keys() | new.keys()) if old.get(key) != new.get(key)]
        return Proposal(id=uid("proposal"), reason=reason, graph=graph, sources=sources,
                        affected_node_ids=affected, base_graph_revision=workspace.graph_revision)

    def adopt(self, task_id, proposal_id, request):
        workspace = self._editable(task_id)
        def apply(item):
            proposal = next((p for p in item.proposals if p.id == proposal_id), None)
            if proposal is None or proposal.status != "pending":
                raise WorkflowError("structure_proposal_not_found", "This pending update is no longer available.", 404)
            if proposal.base_graph_revision != item.graph_revision:
                raise WorkflowError("structure_proposal_outdated", "The graph changed after this proposal. Your adopted changes have been preserved.")
            item.graph, item.sources = proposal.graph.model_copy(deep=True), proposal.sources
            item.graph_revision += 1
            proposal.status = "adopted"
            for other in item.proposals:
                if other.id != proposal.id and other.status == "pending":
                    other.status = "superseded"
        self.store.update(workspace.structure_id, apply, request.expected_version)
        return self.get(task_id)

    def handoff(self, task_id, request):
        workspace = self._editable(task_id)
        if request.expected_version != workspace.version:
            raise WorkflowError("structure_version_conflict", "Structure changed. Refresh before selecting research for Ideas.")
        graph = workspace.graph
        method_ids = {m.id for m in graph.methods} if request.all else set(request.method_ids)
        node_ids = {n.id for n in graph.nodes} if request.all else set(request.node_ids)
        if not method_ids <= {m.id for m in graph.methods} or not node_ids <= {n.id for n in graph.nodes}:
            raise WorkflowError("invalid_structure_selection", "Select nodes and methods from this saved graph.", 422)
        methods = [m for m in graph.methods if m.id in method_ids]
        for method in methods:
            node_ids.update(method.node_ids)
        nodes = [n for n in graph.nodes if n.id in node_ids]
        if not nodes:
            raise WorkflowError("empty_structure_selection", "Select a node, a method or the complete analysis.", 422)
        source_ids = {sid for node in nodes for sid in node.source_ids}
        context_ids = {cid for node in nodes for cid in node.context_ids}
        handoff = Handoff(handoff_id=uid("handoff"), task_id=task_id, structure_id=workspace.structure_id,
            structure_version=workspace.version, analysis_ref=workspace.analysis_ref, video_id=workspace.video_id,
            title=graph.title, nodes=nodes, edges=[e for e in graph.edges if e.from_node in node_ids and e.to_node in node_ids],
            methods=methods, sources=[s for s in workspace.sources if s.id in source_ids],
            contexts=[c for c in workspace.contexts if c.id in context_ids])
        return self.store.save_handoff(handoff)

    def get_handoff(self, task_id):
        self.workflow.store.get(task_id)
        return self.store.latest_handoff(task_id)
