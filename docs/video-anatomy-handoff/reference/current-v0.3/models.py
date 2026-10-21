"""Authoritative v0.3 records and semantic validation for Video Anatomy.

Frame intervals in events/segments belong to the reference video; storyboard
row times remain seconds in the planned new video. JSON Schema is generated from these models.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, field_validator, model_validator

ID = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{1,63}$")]
Nonempty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]
PositiveSeconds = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Revision = Annotated[int, Field(ge=1)]
Frame = Annotated[int, Field(ge=0, strict=True)]
PositiveInteger = Annotated[int, Field(gt=0, strict=True)]
Role = Literal["hook", "product_demo", "proof", "cta", "other"]
EventKind = Literal["visual_action", "on_screen_text", "speech", "music", "sfx"]
CoverageStatus = Literal["not_analyzed", "observations", "none_found", "failed"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(timezone.utc)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=False,
                              json_schema_serialization_defaults_required=True)


class Record(ContractModel):
    schema_version: Literal["0.3.0"] = "0.3.0"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc_dates(cls, value: datetime) -> datetime:
        return aware_utc(value)

    @model_validator(mode="after")
    def chronological(self):
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self


class VersionRef(ContractModel):
    id: ID
    revision: Revision


class Origin(ContractModel):
    kind: Literal["sample", "provider", "manual", "legacy"]
    description: Nonempty


class ErrorInfo(ContractModel):
    code: Nonempty
    message: Nonempty
    retryable: bool = False


class PublicMetrics(ContractModel):
    source_url: Nonempty
    captured_at: datetime | None = None
    views: Annotated[int, Field(ge=0)] | None = None
    likes: Annotated[int, Field(ge=0)] | None = None
    comments: Annotated[int, Field(ge=0)] | None = None

    @field_validator("captured_at")
    @classmethod
    def utc_date(cls, value):
        return aware_utc(value) if value else None


class CreativeTask(Record):
    task_id: ID
    title: Nonempty
    mode: Literal["real", "sample"] = "real"
    progress: Literal["setup", "analysis", "review", "directions", "production"] = "setup"
    version: Revision = 1
    current_brief: VersionRef | None = None
    current_video_id: ID | None = None
    current_analysis: VersionRef | None = None
    chosen_direction: VersionRef | None = None
    selected_direction: VersionRef | None = None
    current_production_brief: VersionRef | None = None
    current_storyboard: VersionRef | None = None


class BrandTaskBrief(Record):
    brief_id: ID
    revision: Revision = 1
    task_id: ID
    brand_company: Nonempty
    product: Nonempty
    selling_points: list[Nonempty] = Field(min_length=1)
    approved_messages: list[Nonempty] = Field(default_factory=list)
    target_audience: Nonempty
    platform: Nonempty
    communication_goal: Nonempty
    target_duration_seconds: PositiveSeconds
    available_footage: str | None = None
    presenters: str | None = None
    locations: str | None = None
    tone: str | None = None
    production_limits: str | None = None
    prohibited_claims: list[Nonempty] = Field(default_factory=list)


class FrameTiming(ContractModel):
    """Decoded presentation-order frames; the final boundary is video duration.

    Frame IDs are zero-based and intervals are half-open. The nominal rational
    rate is for readable timecode; actual boundaries map frames to playback,
    including variable-rate footage without assuming a constant interval.
    Boundaries remain relative to frame zero; add media_start_seconds to reach
    the original source presentation timestamps used by browser playback.
    """

    fps_numerator: PositiveInteger
    fps_denominator: PositiveInteger
    frame_count: PositiveInteger
    media_start_seconds: float = Field(
        default=0.0, allow_inf_nan=False,
        description="First source frame presentation timestamp in browser playback seconds. "
                    "Add this signed origin to zero-relative frame boundaries when seeking.",
    )
    frame_boundaries_seconds: list[Seconds] = Field(min_length=2)
    rate_mode: Literal["constant", "variable"]
    source: Literal["probed"] = "probed"

    @model_validator(mode="after")
    def valid_boundaries(self):
        boundaries = self.frame_boundaries_seconds
        if len(boundaries) != self.frame_count + 1:
            raise ValueError("frame boundaries must contain frame_count + 1 entries")
        if boundaries[0] != 0:
            raise ValueError("frame boundaries must start at zero")
        if any(end <= start for start, end in zip(boundaries, boundaries[1:])):
            raise ValueError("frame boundaries must be strictly increasing")
        return self


class VideoAsset(Record):
    video_id: ID
    task_id: ID
    purpose: Literal["reference", "draft"] = "reference"
    input_method: Literal["file", "sample", "legacy"]
    storage_id: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}\.mp4$")] | None = None
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None = None
    sample_key: str | None = None
    original_file_name: str | None = None
    source_url: str | None = None
    duration_seconds: PositiveSeconds | None = None
    frame_timing: FrameTiming | None = None
    width: Annotated[int, Field(gt=0)] | None = None
    height: Annotated[int, Field(gt=0)] | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    has_audio: bool | None = None
    intake_status: Literal["ready", "failed", "missing"]
    origin: Origin
    public_metrics: PublicMetrics | None = None
    error: ErrorInfo | None = None

    @model_validator(mode="after")
    def valid_intake(self):
        if self.intake_status == "ready" and (not self.storage_id or self.duration_seconds is None or self.frame_timing is None):
            raise ValueError("ready media requires storage_id, measured duration and frame timing")
        if self.frame_timing is not None and (self.duration_seconds is None or not math.isclose(
            self.frame_timing.frame_boundaries_seconds[-1], self.duration_seconds, rel_tol=0, abs_tol=1e-6
        )):
            raise ValueError("final frame boundary must equal measured video duration")
        if self.intake_status == "failed" and self.error is None:
            raise ValueError("failed media requires an actionable error")
        if self.public_metrics is not None and self.public_metrics.source_url != self.source_url:
            raise ValueError("public metrics must describe this video's source")
        return self


class LegacySeconds(ContractModel):
    """Preserved legacy interval when source media is unavailable for probing."""

    start_seconds: Seconds
    end_seconds: PositiveSeconds

    @model_validator(mode="after")
    def valid_interval(self):
        if self.start_seconds >= self.end_seconds:
            raise ValueError("legacy interval start must be before end")
        return self


class ReferenceInterval(ContractModel):
    start_frame: Frame | None = None
    end_frame: Frame | None = None
    legacy_seconds: LegacySeconds | None = None

    @model_validator(mode="after")
    def valid_reference_interval(self):
        if self.start_frame is None and self.end_frame is None:
            if self.legacy_seconds is None:
                raise ValueError("reference interval requires frames or preserved legacy seconds")
        elif self.start_frame is None or self.end_frame is None:
            raise ValueError("reference interval requires both frame boundaries")
        elif self.legacy_seconds is not None:
            raise ValueError("reference interval cannot mix frames and legacy seconds")
        elif self.start_frame >= self.end_frame:
            raise ValueError("reference start frame must be before end frame")
        return self

    def interval_bounds(self) -> tuple[int, int] | tuple[float, float]:
        if self.legacy_seconds is not None:
            return self.legacy_seconds.start_seconds, self.legacy_seconds.end_seconds
        assert self.start_frame is not None and self.end_frame is not None
        return self.start_frame, self.end_frame


class EvidenceEvent(ReferenceInterval):
    event_id: ID
    video_id: ID
    lane: Literal["visual", "audio"]
    kind: EventKind
    text: str | None = None
    description: str | None = None
    source: Nonempty
    method: Nonempty
    uncertainty: str | None = None

    @model_validator(mode="after")
    def valid_event(self):
        expected_lane = "visual" if self.kind in ("visual_action", "on_screen_text") else "audio"
        if self.lane != expected_lane:
            raise ValueError("event kind must use its visual/audio lane")
        if self.text is None and self.description is None:
            raise ValueError("event needs recognized text or an observation description")
        return self


class ContentSegment(ReferenceInterval):
    segment_id: ID
    video_id: ID
    roles: list[Role] = Field(min_length=1)
    evidence_ids: list[ID] = Field(default_factory=list)
    interpretation: str | None = None

    @model_validator(mode="after")
    def valid_segment(self):
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("segment roles must be unique")
        if "other" in self.roles and len(self.roles) != 1:
            raise ValueError("other must be the only role")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("segment evidence IDs must be unique")
        return self


class Coverage(ContractModel):
    visual_action: CoverageStatus = "not_analyzed"
    on_screen_text: CoverageStatus = "not_analyzed"
    speech: CoverageStatus = "not_analyzed"
    music: CoverageStatus = "not_analyzed"
    sfx: CoverageStatus = "not_analyzed"


class ReviewState(ContractModel):
    user_confirmed: bool = False
    confirmed_at: datetime | None = None

    @field_validator("confirmed_at")
    @classmethod
    def utc_date(cls, value):
        return aware_utc(value) if value else None

    @model_validator(mode="after")
    def valid_confirmation(self):
        if self.user_confirmed != (self.confirmed_at is not None):
            raise ValueError("confirmation requires exactly one confirmation timestamp")
        return self


class Correction(ContractModel):
    target_type: Literal["event", "segment"]
    target_id: ID
    field: Literal["text", "description", "roles"]
    before: JsonValue
    after: JsonValue

    @model_validator(mode="after")
    def allowed_field(self):
        if (self.target_type == "segment") != (self.field == "roles"):
            raise ValueError("only event text/descriptions and segment roles are editable")
        return self


class AnalysisResult(Record):
    analysis_id: ID
    revision: Revision = 1
    task_id: ID
    video_id: ID
    duration_seconds: PositiveSeconds
    frame_count: PositiveInteger | None = None
    status: Literal["pending", "running", "succeeded", "partial", "failed"]
    events: list[EvidenceEvent] = Field(default_factory=list)
    segments: list[ContentSegment] = Field(default_factory=list)
    coverage: Coverage = Field(default_factory=Coverage)
    origin: Origin
    original_revision: Revision = 1
    review: ReviewState = Field(default_factory=ReviewState)
    corrections: list[Correction] = Field(default_factory=list)
    error: ErrorInfo | None = None
    empty_result_reason: str | None = None

    @model_validator(mode="after")
    def valid_analysis(self):
        completed = self.status in ("succeeded", "partial")
        if not completed and (self.events or self.segments or self.review.user_confirmed):
            raise ValueError("unfinished or failed analysis cannot contain usable observations or confirmation")
        if self.status == "failed" and self.error is None:
            raise ValueError("failed analysis requires an actionable error")
        if self.status != "failed" and self.error is not None:
            raise ValueError("analysis error is reserved for failed processing")
        if completed and not self.events and not self.empty_result_reason:
            raise ValueError("completed empty analysis requires an explanation")
        if self.events and self.empty_result_reason is not None:
            raise ValueError("nonempty analysis must not carry an empty-result reason")
        if self.original_revision != 1 or self.original_revision > self.revision:
            raise ValueError("analysis original revision must remain 1")
        if self.review.confirmed_at is not None and not self.created_at <= self.review.confirmed_at <= self.updated_at:
            raise ValueError("confirmation time must fall within analysis creation/update times")
        event_map = {event.event_id: event for event in self.events}
        if len(event_map) != len(self.events):
            raise ValueError("duplicate evidence event IDs")
        if len({segment.segment_id for segment in self.segments}) != len(self.segments):
            raise ValueError("duplicate content segment IDs")
        limit = self.frame_count if self.frame_count is not None else self.duration_seconds
        for interval in [*self.events, *self.segments]:
            if (interval.legacy_seconds is None) != (self.frame_count is not None):
                raise ValueError("analysis and reference intervals must use the same frame or unavailable legacy clock")
            if interval.video_id != self.video_id or interval.interval_bounds()[1] > limit:
                raise ValueError("reference interval must belong to this video within its frame count or legacy duration")
        previous_end = 0
        for segment in self.segments:
            segment_start, segment_end = segment.interval_bounds()
            if segment_start < previous_end:
                raise ValueError("primary segments must be ordered and nonoverlapping")
            previous_end = segment_end
            for event_id in segment.evidence_ids:
                if event_id not in event_map:
                    raise ValueError("dangling segment evidence reference")
                event_start, event_end = event_map[event_id].interval_bounds()
                if event_end <= segment_start or event_start >= segment_end:
                    raise ValueError("section evidence must overlap that section's interval")
        for kind, coverage in self.coverage.model_dump().items():
            has_events = any(event.kind == kind for event in self.events)
            if has_events != (coverage == "observations"):
                raise ValueError(f"{kind} coverage must agree with canonical observations")
        if self.status == "succeeded" and "failed" in self.coverage.model_dump().values():
            raise ValueError("failed extraction categories require partial analysis status")
        if self.status == "partial" and "failed" not in self.coverage.model_dump().values():
            raise ValueError("partial analysis must identify failed extraction categories")
        return self


class EvidenceReference(ContractModel):
    analysis_id: ID
    analysis_revision: Revision
    video_id: ID
    event_id: ID
    reason: Nonempty


class CreativeDirection(Record):
    direction_id: ID
    revision: Revision = 1
    task_id: ID
    brief_ref: VersionRef
    analysis_ref: VersionRef
    feedback_refs: list[VersionRef] = Field(default_factory=list)
    core_message: Nonempty
    hook: Nonempty
    narrative: Nonempty
    cta: Nonempty
    production_requirements: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    rationale: Nonempty
    hypotheses: list[str] = Field(default_factory=list)
    production_notes: list[str] = Field(default_factory=list)
    origin: Origin
    approval_status: Literal["draft", "approved"] = "draft"
    approved_at: datetime | None = None
    currentness: Literal["current", "outdated"] = "current"

    @field_validator("approved_at")
    @classmethod
    def utc_date(cls, value):
        return aware_utc(value) if value else None

    @model_validator(mode="after")
    def valid_approval(self):
        if (self.approval_status == "approved") != (self.approved_at is not None):
            raise ValueError("approval requires an exact approval timestamp")
        if self.approved_at is not None and not self.created_at <= self.approved_at <= self.updated_at:
            raise ValueError("approval time must fall within creation/update times")
        return self


class CreativeFeedback(Record):
    feedback_id: ID
    revision: Revision = 1
    task_id: ID
    instruction: Nonempty
    target_direction: VersionRef
    brief_ref: VersionRef
    analysis_ref: VersionRef
    status: Literal["pending", "applied", "not_interpreted"] = "pending"
    resulting_direction: VersionRef | None = None
    explanation: str | None = None

    @model_validator(mode="after")
    def valid_result(self):
        if (self.status == "applied") != (self.resulting_direction is not None):
            raise ValueError("applied feedback must identify its resulting draft")
        if self.status == "not_interpreted" and not self.explanation:
            raise ValueError("uninterpreted feedback needs an explicit explanation")
        return self


class ProductionOutput(Record):
    output_id: ID
    revision: Revision = 1
    task_id: ID
    direction_ref: VersionRef
    brief_ref: VersionRef
    analysis_ref: VersionRef
    feedback_refs: list[VersionRef] = Field(default_factory=list)
    origin: Origin
    currentness: Literal["current", "outdated"] = "current"
    edited: bool = False


class ProductionCreativeBrief(ProductionOutput):
    title: Nonempty
    core_message: Nonempty
    hook: Nonempty
    narrative: Nonempty
    cta: Nonempty
    production_notes: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class StoryboardRow(ContractModel):
    row_id: ID
    start_seconds: Seconds
    end_seconds: PositiveSeconds
    visual: Nonempty
    dialogue: str | None = None
    on_screen_text: str | None = None
    sound: str | None = None
    cta: str | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_interval(self):
        if self.start_seconds >= self.end_seconds:
            raise ValueError("planned row start must precede end")
        return self


class TextStoryboard(ProductionOutput):
    target_duration_seconds: PositiveSeconds
    rows: list[StoryboardRow] = Field(min_length=1)

    @model_validator(mode="after")
    def planned_timeline(self):
        if len({row.row_id for row in self.rows}) != len(self.rows):
            raise ValueError("storyboard row IDs must be unique")
        previous_end = 0.0
        for row in self.rows:
            if row.start_seconds < previous_end or row.end_seconds > self.target_duration_seconds:
                raise ValueError("planned rows must be ordered, nonoverlapping and within target duration")
            previous_end = row.end_seconds
        if not math.isclose(self.rows[0].start_seconds, 0.0, abs_tol=1e-6) or not math.isclose(previous_end, self.target_duration_seconds, abs_tol=1e-6):
            raise ValueError("storyboard must begin at zero and finish at the planned target duration")
        return self


class ProcessingJob(Record):
    job_id: ID
    task_id: ID
    operation: Literal["analyze", "directions", "refine", "production"]
    status: Literal["pending", "running", "succeeded", "failed"]
    input_refs: dict[str, VersionRef] = Field(default_factory=dict)
    video_id: ID | None = None
    result_ref: VersionRef | None = None
    result_type: str | None = None
    error: ErrorInfo | None = None
    attempt: Revision = 1
    partial_coverage: bool = False

    @model_validator(mode="after")
    def valid_job(self):
        if (self.status == "failed") != (self.error is not None):
            raise ValueError("failed jobs require an error; other jobs must not carry errors")
        if self.status == "succeeded" and (self.result_ref is None or self.result_type is None):
            raise ValueError("successful jobs require a result reference and its type")
        if self.status != "succeeded" and (self.result_ref is not None or self.result_type is not None):
            raise ValueError("unfinished or failed jobs must not expose a successful result")
        return self


class TaskState(ContractModel):
    task: CreativeTask
    briefs: list[BrandTaskBrief] = Field(default_factory=list)
    videos: list[VideoAsset] = Field(default_factory=list)
    analyses: list[AnalysisResult] = Field(default_factory=list)
    directions: list[CreativeDirection] = Field(default_factory=list)
    feedback: list[CreativeFeedback] = Field(default_factory=list)
    production_briefs: list[ProductionCreativeBrief] = Field(default_factory=list)
    storyboards: list[TextStoryboard] = Field(default_factory=list)
    jobs: list[ProcessingJob] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_references(self):
        _validate_references(self)
        return self


def _validate_references(state: TaskState) -> None:
    task = state.task
    indexes = {}
    for collection, id_field in (("briefs", "brief_id"), ("videos", "video_id"), ("analyses", "analysis_id"),
                                  ("directions", "direction_id"), ("feedback", "feedback_id"),
                                  ("production_briefs", "output_id"), ("storyboards", "output_id"), ("jobs", "job_id")):
        records = getattr(state, collection)
        index = {}
        for record in records:
            if record.task_id != task.task_id:
                raise ValueError(f"{collection}: wrong-task record")
            key = (getattr(record, id_field), getattr(record, "revision", 1))
            if key in index:
                raise ValueError(f"{collection}: duplicate ID/revision")
            index[key] = record
        indexes[collection] = index

    def resolve(collection: str, ref: VersionRef):
        result = indexes[collection].get((ref.id, ref.revision))
        if result is None:
            raise ValueError(f"{collection}: dangling or wrong-revision reference")
        return result

    def citations(items: list[EvidenceReference], analysis: AnalysisResult):
        valid_ids = {event.event_id for event in analysis.events}
        for item in items:
            if (item.analysis_id, item.analysis_revision, item.video_id) != (analysis.analysis_id, analysis.revision, analysis.video_id) or item.event_id not in valid_ids:
                raise ValueError("evidence must resolve within the exact recorded analysis revision and video")

    def inputs(record):
        brief = resolve("briefs", record.brief_ref)
        analysis = resolve("analyses", record.analysis_ref)
        if record.currentness == "current":
            if record.brief_ref != task.current_brief or record.analysis_ref != task.current_analysis or analysis.video_id != task.current_video_id:
                raise ValueError("current creative records must use exact current task inputs")
            if analysis.status != "succeeded" or not analysis.review.user_confirmed:
                raise ValueError("current creative records require reviewed successful analysis")
            if analysis.frame_count is None:
                raise ValueError("current creative records require available reference frame timing")
        for ref in record.feedback_refs:
            feedback = resolve("feedback", ref)
            if feedback.brief_ref != record.brief_ref or feedback.analysis_ref != record.analysis_ref:
                raise ValueError("feedback must reference the artifact's exact upstream inputs")
        return brief, analysis

    for analysis in state.analyses:
        video = resolve("videos", VersionRef(id=analysis.video_id, revision=1))
        if video.duration_seconds is None or not math.isclose(video.duration_seconds, analysis.duration_seconds, abs_tol=1e-6):
            raise ValueError("analysis duration must match its video")
        expected_count = video.frame_timing.frame_count if video.frame_timing is not None else None
        if analysis.frame_count != expected_count:
            raise ValueError("analysis frame count must match its video's frame timing")
        original = resolve("analyses", VersionRef(id=analysis.analysis_id, revision=analysis.original_revision))
        if original.video_id != analysis.video_id or original.origin != analysis.origin or original.frame_count != analysis.frame_count:
            raise ValueError("analysis revisions must preserve video identity, frame count and origin")
        if analysis.revision > 1:
            old_events = {event.event_id: event for event in original.events}
            old_segments = {segment.segment_id: segment for segment in original.segments}
            if set(old_events) != {event.event_id for event in analysis.events} or set(old_segments) != {segment.segment_id for segment in analysis.segments}:
                raise ValueError("analysis corrections must preserve observation and section IDs")
            for event in analysis.events:
                old = old_events[event.event_id]
                for field in ("video_id", "start_frame", "end_frame", "legacy_seconds", "lane", "kind", "source", "method", "uncertainty"):
                    if getattr(event, field) != getattr(old, field):
                        raise ValueError("analysis corrections cannot change evidence identity/timing/provenance")
            for segment in analysis.segments:
                old = old_segments[segment.segment_id]
                for field in ("video_id", "start_frame", "end_frame", "legacy_seconds", "evidence_ids"):
                    if getattr(segment, field) != getattr(old, field):
                        raise ValueError("analysis corrections cannot change section identity/timing/evidence links")
            # The cumulative correction log must reproduce the current editable content.
            replay_events = {key: value.model_dump() for key, value in old_events.items()}
            replay_segments = {key: value.model_dump() for key, value in old_segments.items()}
            for correction in analysis.corrections:
                records = replay_events if correction.target_type == "event" else replay_segments
                if correction.target_id not in records:
                    raise ValueError("correction log contains a dangling target")
                target = records[correction.target_id]
                if target[correction.field] != correction.before:
                    raise ValueError("correction log before-value does not match its recorded lineage")
                target[correction.field] = correction.after
            for event in analysis.events:
                for field in ("text", "description"):
                    if getattr(event, field) != replay_events[event.event_id][field]:
                        raise ValueError("changed event content requires a complete correction log")
            for segment in analysis.segments:
                if segment.roles != replay_segments[segment.segment_id]["roles"]:
                    raise ValueError("changed section roles require a complete correction log")
                if segment.interpretation not in (None, old_segments[segment.segment_id].interpretation):
                    raise ValueError("corrections may clear interpretations but cannot rewrite them")
    for direction in state.directions:
        _, analysis = inputs(direction)
        citations(direction.evidence, analysis)
    for feedback in state.feedback:
        target = resolve("directions", feedback.target_direction)
        if target.brief_ref != feedback.brief_ref or target.analysis_ref != feedback.analysis_ref:
            raise ValueError("feedback input references must match its target draft")
        if feedback.resulting_direction:
            result = resolve("directions", feedback.resulting_direction)
            if result.direction_id != target.direction_id or result.revision <= target.revision:
                raise ValueError("feedback result must be a newer revision of its target")
    for output in [*state.production_briefs, *state.storyboards]:
        brief, analysis = inputs(output)
        direction = resolve("directions", output.direction_ref)
        if direction.brief_ref != output.brief_ref or direction.analysis_ref != output.analysis_ref or direction.feedback_refs != output.feedback_refs:
            raise ValueError("production output inputs must match its exact direction revision")
        if output.currentness == "current" and (direction.approval_status != "approved" or direction.currentness != "current" or task.selected_direction != output.direction_ref):
            raise ValueError("current production output requires the selected approved direction")
        if isinstance(output, TextStoryboard):
            if not math.isclose(output.target_duration_seconds, brief.target_duration_seconds, abs_tol=1e-6):
                raise ValueError("storyboard planned duration must match its brief, not reference media")
            for row in output.rows:
                citations(row.evidence, analysis)
        else:
            citations(output.evidence, analysis)
    for field, collection in (("current_brief", "briefs"), ("current_analysis", "analyses"),
                              ("chosen_direction", "directions"), ("selected_direction", "directions"), ("current_production_brief", "production_briefs"),
                              ("current_storyboard", "storyboards")):
        ref = getattr(task, field)
        if ref is not None:
            record = resolve(collection, ref)
            if field == "current_analysis" and record.video_id != task.current_video_id:
                raise ValueError("current analysis must belong to current video")
            if field == "chosen_direction" and record.currentness != "current":
                raise ValueError("chosen direction must be a current draft or approved direction")
    if task.current_video_id is not None:
        resolve("videos", VersionRef(id=task.current_video_id, revision=1))
    for job in state.jobs:
        if job.video_id is not None:
            resolve("videos", VersionRef(id=job.video_id, revision=1))
        for kind, ref in job.input_refs.items():
            collection = {"brief": "briefs", "analysis": "analyses", "direction": "directions", "feedback": "feedback"}.get(kind)
            if collection is None:
                raise ValueError("unknown processing job input type")
            resolve(collection, ref)
        if job.result_ref and job.result_type:
            collection = {"analysis": "analyses", "direction": "directions", "production_brief": "production_briefs", "storyboard": "storyboards", "feedback": "feedback"}.get(job.result_type)
            if collection is None:
                raise ValueError("unknown processing job result type")
            resolve(collection, job.result_ref)


def validate_state(state: TaskState | dict) -> TaskState:
    """Validate even after model_copy, which intentionally bypasses Pydantic checks."""
    return TaskState.model_validate(state.model_dump(mode="python") if isinstance(state, TaskState) else state)

