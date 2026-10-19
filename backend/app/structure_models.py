"""Additive Structure contracts: observations, attributed context and inference stay distinct."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .models import VersionRef

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class StructureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Moment(StructureModel):
    event_id: Key
    start_frame: int | None
    end_frame: int | None
    start_seconds: float
    end_seconds: float
    precision: Literal["sample", "interval"]


class Node(StructureModel):
    id: Key
    label: Text
    explanation: Text
    kind: Literal["observation", "source_claim", "inference", "user_context"]
    event_ids: list[Key] = Field(max_length=12)
    source_ids: list[Key] = Field(max_length=8)
    context_ids: list[Key] = Field(max_length=8)
    moments: list[Moment] = Field(default_factory=list, max_length=12)


class Edge(StructureModel):
    id: Key
    from_node: Key
    to_node: Key
    relation: Text
    explanation: Text


class Method(StructureModel):
    id: Key
    title: Text
    explanation: Text
    node_ids: list[Key] = Field(min_length=1, max_length=12)
    conditions: list[Text] = Field(min_length=1, max_length=8)


class Gap(StructureModel):
    id: Key
    question: Text
    why_it_matters: Text


class Graph(StructureModel):
    title: Text
    summary: Text
    nodes: list[Node] = Field(min_length=1, max_length=20)
    edges: list[Edge] = Field(max_length=30)
    methods: list[Method] = Field(max_length=8)
    research_gaps: list[Gap] = Field(max_length=3)

    @model_validator(mode="after")
    def references(self):
        for items in (self.nodes, self.edges, self.methods, self.research_gaps):
            if len({item.id for item in items}) != len(items):
                raise ValueError("Structure identifiers must be unique within each collection")
        node_ids = {node.id for node in self.nodes}
        for edge in self.edges:
            if edge.from_node not in node_ids or edge.to_node not in node_ids or edge.from_node == edge.to_node:
                raise ValueError("Structure relationships must connect two existing, distinct nodes")
        for method in self.methods:
            if not set(method.node_ids) <= node_ids:
                raise ValueError("Transferable methods must cite existing nodes")
        for node in self.nodes:
            for refs in (node.event_ids, node.source_ids, node.context_ids):
                if len(set(refs)) != len(refs):
                    raise ValueError("Structure evidence references must be unique")
            if not (node.event_ids or node.source_ids or node.context_ids):
                raise ValueError("Every Structure node must identify its evidence or supplied context")
            if node.kind == "observation" and (not node.event_ids or node.source_ids or node.context_ids):
                raise ValueError("An observation must cite video evidence only")
            if node.kind == "source_claim" and not (node.source_ids or node.event_ids):
                raise ValueError("An attributed claim needs its video or external source")
            if node.kind == "user_context" and not node.context_ids:
                raise ValueError("User context must cite its saved context record")
        return self


class Source(StructureModel):
    id: Key
    title: Text
    url: Text
    claim: Text
    attribution: Text
    retrieved_at: str = Field(default_factory=timestamp)

    @model_validator(mode="after")
    def public_link(self):
        parts = urlsplit(self.url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            raise ValueError("Research sources must use HTTP(S) URLs without credentials")
        return self


class UserContext(StructureModel):
    id: Key
    node_id: Key
    text: Text
    created_at: str = Field(default_factory=timestamp)


class Answer(StructureModel):
    id: Key
    node_id: Key
    question: Text
    answer: Text
    event_ids: list[Key]
    source_ids: list[Key]
    created_at: str = Field(default_factory=timestamp)


class Proposal(StructureModel):
    id: Key
    reason: Text
    graph: Graph
    sources: list[Source]
    affected_node_ids: list[Key]
    base_graph_revision: int
    status: Literal["pending", "adopted", "superseded"] = "pending"
    created_at: str = Field(default_factory=timestamp)


class StructureError(StructureModel):
    code: Key
    message: Text


class Workspace(StructureModel):
    structure_id: Key
    output_language: Literal["English", "Chinese"] | None = None
    task_id: Key
    video_id: Key
    analysis_ref: VersionRef
    version: int = 1
    graph_revision: int = 0
    status: Literal["analyzing", "researching", "ready", "partial", "failed"] = "analyzing"
    origin: Literal["sample", "provider"]
    graph: Graph | None = None
    sources: list[Source] = Field(default_factory=list)
    contexts: list[UserContext] = Field(default_factory=list)
    proposals: list[Proposal] = Field(default_factory=list)
    answers: list[Answer] = Field(default_factory=list)
    feedback_status: Literal["idle", "running", "failed"] = "idle"
    error: StructureError | None = None
    research_note: str | None = None
    outdated: bool = False
    source_deleted: bool = False
    created_at: str = Field(default_factory=timestamp)
    updated_at: str = Field(default_factory=timestamp)


class AnalyzeRequest(StructureModel):
    analysis_ref: VersionRef | None = None


class FeedbackRequest(StructureModel):
    expected_version: int = Field(ge=1)
    node_id: Key
    instruction: Text
    kind: Literal["question", "context", "reconsider"]


class AdoptRequest(StructureModel):
    expected_version: int = Field(ge=1)


class HandoffRequest(StructureModel):
    expected_version: int = Field(ge=1)
    node_ids: list[Key] = Field(default_factory=list, max_length=20)
    method_ids: list[Key] = Field(default_factory=list, max_length=8)
    all: bool = False


class Handoff(StructureModel):
    handoff_id: Key
    task_id: Key
    structure_id: Key
    structure_version: int
    analysis_ref: VersionRef
    video_id: Key
    title: Text
    nodes: list[Node]
    edges: list[Edge]
    methods: list[Method]
    sources: list[Source]
    contexts: list[UserContext]
    created_at: str = Field(default_factory=timestamp)
    note: str = "Research context, not a new product claim or an approved creative direction."
