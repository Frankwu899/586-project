"""Canonical 1.8 project contract. Provider results never control identity or approval."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SourceRef(Model):
    resource_id: str | None = None
    message_id: str | None = None
    locator: str = ""
    excerpt: str = ""
    url: str | None = None
    evidence_revision: int | None = None
    extraction_revision: int | None = Field(default=None, ge=1)
    event_id: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None


class Fact(Model):
    id: str = Field(default_factory=lambda: uid("fact"))
    key: str
    value: str
    status: Literal["suggested", "confirmed", "unresolved", "rejected"] = "suggested"
    origin: Literal["conversation", "document", "research", "manual", "legacy"] = "conversation"
    sources: list[SourceRef] = Field(default_factory=list)
    permitted_for_use: bool = False


class Message(Model):
    id: str = Field(default_factory=lambda: uid("message"))
    role: Literal["user", "assistant", "system"]
    text: str
    resource_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now)
    status: Literal["saved", "failed"] = "saved"
    reply_to_message_id: str | None = None
    diagnostics: dict[str, str] = Field(default_factory=dict)
    retryable: bool = False


class BriefRevision(Model):
    revision: int = Field(ge=1)
    facts: list[Fact]
    created_at: str = Field(default_factory=now)


class ExtractedBlock(Model):
    id: str = Field(default_factory=lambda: uid("block"))
    locator: str
    text: str
    original_text: str | None = None


class EvidenceEvent(Model):
    id: str
    kind: Literal["speech", "on_screen_text", "visual", "sound"]
    text: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    start_frame: int | None = None
    end_frame: int | None = None
    interpretation: str | None = None

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end_seconds < self.start_seconds:
            raise ValueError("Evidence end must not precede its start")
        return self


class EvidenceRevision(Model):
    diagnostics: dict[str, str] = Field(default_factory=dict)
    support_details: list[dict[str, str]] = Field(default_factory=list)
    revision: int = Field(ge=1)
    events: list[EvidenceEvent] = Field(default_factory=list)
    coverage: dict[str, str] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    processor: str = ""
    created_at: str = Field(default_factory=now)
    reviewed: bool = False
    correction_note: str | None = None


class Resource(Model):
    id: str = Field(default_factory=lambda: uid("resource"))
    name: str
    kind: Literal["document", "video", "audio", "image", "other"]
    role: Literal["reference", "document", "asset"] = "reference"
    origin: Literal["upload", "discovery", "legacy"] = "upload"
    source_url: str | None = None
    provenance: str = ""
    original_path: str
    sha256: str
    size_bytes: int = Field(ge=0)
    mime_type: str = "application/octet-stream"
    created_at: str = Field(default_factory=now)
    status: Literal["stored", "processing", "ready", "partial", "failed", "unsupported", "missing"] = "stored"
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    blocks: list[ExtractedBlock] = Field(default_factory=list)
    extraction_revision: int = 1
    extraction_history: list[dict] = Field(default_factory=list)
    duration_seconds: float | None = None
    thumbnail_path: str | None = None
    playback_path: str | None = None
    media_metadata: dict = Field(default_factory=dict)
    evidence: list[EvidenceRevision] = Field(default_factory=list)


class Selection(Model):
    revision: int = Field(default=1, ge=1)
    resource_ids: list[str] = Field(default_factory=list)


class InputManifest(Model):
    exploratory: bool = False
    visual_only: bool = False
    limitations: list[str] = Field(default_factory=list)
    brief_revision: int | None = None
    selection_revision: int = 1
    resource_ids: list[str] = Field(default_factory=list)
    evidence_revisions: dict[str, int] = Field(default_factory=dict)
    direction_id: str | None = None
    direction_revision: int | None = None
    instruction_version: str = "1.8.0"
    instruction_digest: str | None = None
    context_digest: str | None = None
    claim_ids: list[str] = Field(default_factory=list)
    model: str | None = None


class StructureNode(Model):
    id: str
    label: str
    detail: str
    kind: Literal["observation", "interpretation", "source_claim", "user_context"] = "interpretation"
    sources: list[SourceRef] = Field(default_factory=list)


class StructureEdge(Model):
    source: str
    target: str
    label: str
    explanation: str
    sources: list[SourceRef] = Field(default_factory=list)


class ReferenceStructure(Model):
    resource_id: str
    summary: str
    nodes: list[StructureNode]
    edges: list[StructureEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_links(self):
        ids = {node.id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("Structure node identities must be unique")
        for edge in self.edges:
            if edge.source not in ids or edge.target not in ids or edge.source == edge.target:
                raise ValueError("Structure relationships must connect distinct nodes in the same reference")
        for item in [*self.nodes, *self.edges]:
            if any(source.resource_id not in (None, self.resource_id) for source in item.sources):
                raise ValueError("Structure sources must belong to their reference")
        return self


class Analysis(Model):
    id: str = Field(default_factory=lambda: uid("analysis"))
    content_id: str | None = None
    inputs: InputManifest
    conclusion: str
    findings: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    structures: list[ReferenceStructure] = Field(default_factory=list)
    created_at: str = Field(default_factory=now)
    needs_review: bool = False


class Direction(Model):
    id: str = Field(default_factory=lambda: uid("direction"))
    revision: int = Field(default=1, ge=1)
    title: str
    concept: str
    hook: str = ""
    narrative: str = ""
    cta: str = ""
    inputs: InputManifest = Field(default_factory=InputManifest)
    sources: list[SourceRef] = Field(default_factory=list)
    approved: bool = False
    approved_at: str | None = None
    needs_review: bool = False
    created_at: str = Field(default_factory=now)


class Series(Model):
    id: str = Field(default_factory=lambda: uid("series"))
    title: str
    concept: str = ""
    inputs: InputManifest | None = None
    needs_review: bool = False


class ContentItem(Model):
    id: str = Field(default_factory=lambda: uid("content"))
    series_id: str | None = None
    title: str
    description: str = ""
    inputs: InputManifest | None = None
    needs_review: bool = False
    selection: Selection = Field(default_factory=Selection)
    directions: list[Direction] = Field(default_factory=list)
    approved_direction_id: str | None = None
    approved_direction_revision: int | None = None


class ProductionShot(Model):
    id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    visual: str
    dialogue: str = ""
    on_screen_text: str = ""
    sound: str = ""
    notes: str = ""

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end_seconds <= self.start_seconds:
            raise ValueError("A production shot must have positive duration")
        return self


class ProductionPack(Model):
    id: str = Field(default_factory=lambda: uid("pack"))
    revision: int = Field(default=1, ge=1)
    content_id: str
    inputs: InputManifest
    production_brief: str
    script: str
    storyboard: str
    shot_list: str
    shots: list[ProductionShot] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    needs_review: bool = False
    created_at: str = Field(default_factory=now)


class Job(Model):
    error_code: str | None = None
    id: str = Field(default_factory=lambda: uid("job"))
    kind: str
    resource_id: str | None = None
    content_id: str | None = None
    message_id: str | None = None
    diagnostics: dict[str, str] = Field(default_factory=dict)
    support_details: list[dict[str, str]] = Field(default_factory=list)
    status: Literal["queued", "running", "succeeded", "partial", "failed"] = "queued"
    progress: str = "Queued"
    error: str | None = None
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)


class Project(Model):
    schema_version: Literal["1.8.0"] = "1.8.0"
    id: str = Field(default_factory=lambda: uid("project"))
    title: str = "Untitled project"
    version: int = Field(default=1, ge=1)
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    trashed_at: str | None = None
    duplicated_from: str | None = None
    legacy_task_id: str | None = None
    workspace: str = "overview"
    active_content_id: str | None = None
    conversation_draft: str = ""
    messages: list[Message] = Field(default_factory=list)
    brief_draft: list[Fact] = Field(default_factory=list)
    brief_draft_version: int = Field(default=1, ge=1)
    unresolved: list[str] = Field(default_factory=list)
    briefs: list[BriefRevision] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)
    selection: Selection = Field(default_factory=Selection)
    analyses: list[Analysis] = Field(default_factory=list)
    series: list[Series] = Field(default_factory=list)
    contents: list[ContentItem] = Field(default_factory=list)
    packs: list[ProductionPack] = Field(default_factory=list)
    jobs: list[Job] = Field(default_factory=list)
    editor_drafts: dict[str, dict] = Field(default_factory=dict)
    editor_draft_versions: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_identities(self):
        def unique(values, label):
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {label} identity")
        for label in ("resources", "messages", "series", "contents", "jobs"):
            unique([item.id for item in getattr(self, label)], label)
        unique([item.revision for item in self.briefs], "brief revision")
        unique([(item.id, item.revision) for item in self.packs], "pack revision")
        resources = {item.id for item in self.resources}
        series = {item.id for item in self.series}
        for selection in [self.selection, *[item.selection for item in self.contents]]:
            unique(selection.resource_ids, "selected resource")
            if not set(selection.resource_ids).issubset(resources):
                raise ValueError("A selection references a resource outside its project")
        for resource in self.resources:
            unique([item.revision for item in resource.evidence], "evidence revision")
            unique([item.id for item in resource.blocks], "extracted block")
            for revision in resource.evidence:
                unique([item.id for item in revision.events], "evidence event")
        for content in self.contents:
            if content.series_id is not None and content.series_id not in series:
                raise ValueError("A content item references an unknown series")
            unique([(item.id, item.revision) for item in content.directions], "direction revision")
            if content.approved_direction_id is not None and not any(
                d.id == content.approved_direction_id and d.revision == content.approved_direction_revision
                for d in content.directions
            ):
                raise ValueError("A content item references an unknown approved direction")
        return self


def invalidate(project: Project, *, brief: bool = False, resource_id: str | None = None, content_id: str | None = None):
    """Only applied input changes affect descendants; saved drafts never call this."""
    for analysis in project.analyses:
        if ((brief and analysis.inputs.brief_revision is not None) or resource_id in analysis.inputs.resource_ids
                or (content_id is not None and analysis.content_id == content_id)):
            analysis.needs_review = True
    for content in project.contents:
        if content.inputs is not None and (brief or resource_id in content.inputs.resource_ids):
            content.needs_review = True
        for direction in content.directions:
            if brief or (resource_id is not None and resource_id in direction.inputs.resource_ids) or content.id == content_id:
                direction.needs_review = True
                direction.approved = False
        if brief or content.id == content_id or any(resource_id in d.inputs.resource_ids for d in content.directions):
            content.approved_direction_id = None
            content.approved_direction_revision = None
    for series in project.series:
        if series.inputs is not None and (brief or resource_id in series.inputs.resource_ids):
            series.needs_review = True
    for pack in project.packs:
        if brief or (resource_id is not None and resource_id in pack.inputs.resource_ids) or pack.content_id == content_id:
            pack.needs_review = True
