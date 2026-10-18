"""Authoritative v0.6 records and semantic validation for Video Anatomy.

Frame intervals in events/segments belong to the reference video; storyboard
row times remain seconds in the planned new video. JSON Schema is generated from these models.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, field_validator, model_validator

ID = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{1,63}$")]
Nonempty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"\S")]
Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]
PositiveSeconds = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Revision = Annotated[int, Field(ge=1)]
Frame = Annotated[int, Field(ge=0, strict=True)]
PositiveInteger = Annotated[int, Field(gt=0, strict=True)]
Role = Literal["hook", "product_demo", "proof", "cta", "other"]
EventKind = Literal["visual_action", "on_screen_text", "speech", "music", "sfx"]
CoverageStatus = Literal["not_analyzed", "observations", "none_found", "failed"]
SubjectKind = Literal["person", "animal", "plant", "physical_object", "digital_interface", "graphic", "environment", "other"]
SubjectRole = Literal["product", "presenter", "product_user", "context", "other"]
ActionType = Literal["hold", "pick_up", "put_down", "open", "close", "pour", "apply", "operate", "assemble", "disassemble", "wear", "eat_drink", "point", "move", "other"]
ProductPresentationType = Literal["appearance", "feature_demo", "use_case", "result_display", "comparison", "packaging", "unboxing", "other"]
StorageID = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}\.mp4$")]


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
    schema_version: Literal["0.6.0", "0.7.0"] = "0.7.0"
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


class VisualSubject(ContractModel):
    subject_id: ID
    kind: SubjectKind | None
    label: Nonempty
    description: Nonempty | None
    roles: Annotated[list[SubjectRole], Field(min_length=1, json_schema_extra={
        "uniqueItems": True,
        "allOf": [{"if": {"contains": {"const": "other"}}, "then": {"maxItems": 1}}],
    })] | None

    model_config = ConfigDict(json_schema_extra={"allOf": [{
        "if": {"anyOf": [
            {"properties": {"kind": {"const": "other"}}},
            {"properties": {"roles": {"type": "array", "contains": {"const": "other"}}}},
        ]},
        "then": {"properties": {"description": {"type": "string", "minLength": 1, "pattern": r"\S"}}},
    }]})

    @model_validator(mode="after")
    def valid_roles(self):
        if self.roles is not None:
            if len(set(self.roles)) != len(self.roles):
                raise ValueError("subject roles must be unique")
            if "other" in self.roles and len(self.roles) != 1:
                raise ValueError("other must be the only subject role")
        if (self.kind == "other" or "other" in (self.roles or [])) and self.description is None:
            raise ValueError("an other subject kind or role requires an explanatory description")
        return self


class VisualAction(ContractModel):
    action_type: ActionType | None
    actor_subject_ids: list[ID] = Field(json_schema_extra={"uniqueItems": True})
    target_subject_ids: list[ID] = Field(json_schema_extra={"uniqueItems": True})
    description: Nonempty

    @field_validator("actor_subject_ids", "target_subject_ids")
    @classmethod
    def unique_references(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("action subject references must be unique")
        return value


class ProductPresentation(ContractModel):
    product_subject_ids: list[ID] = Field(min_length=1, json_schema_extra={"uniqueItems": True})
    presentation_type: ProductPresentationType | None
    description: Nonempty

    @field_validator("product_subject_ids")
    @classmethod
    def unique_references(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("product subject references must be unique")
        return value


Observation = TypeVar("Observation")


class ObservationGroup(ContractModel, Generic[Observation]):
    status: CoverageStatus
    items: list[Observation]
    error: ErrorInfo | None

    model_config = ConfigDict(json_schema_extra={"allOf": [
        {"if": {"properties": {"status": {"const": "observations"}}},
         "then": {"properties": {"items": {"minItems": 1}}},
         "else": {"properties": {"items": {"maxItems": 0}}}},
        {"if": {"properties": {"status": {"const": "failed"}}},
         "then": {"properties": {"error": {"type": "object"}}},
         "else": {"properties": {"error": {"type": "null"}}}},
    ]})

    @model_validator(mode="after")
    def truthful_coverage(self):
        if bool(self.items) != (self.status == "observations"):
            raise ValueError("structured group observations status requires nonempty items; other statuses require empty items")
        if (self.status == "failed") != (self.error is not None):
            raise ValueError("structured group error is required exactly when status is failed")
        return self


class VisualDetails(ContractModel):
    """Event-local observations inheriting their parent source-frame interval."""

    subjects: ObservationGroup[VisualSubject]
    actions: ObservationGroup[VisualAction]
    product_presentations: ObservationGroup[ProductPresentation]

    @model_validator(mode="after")
    def local_references(self):
        subjects = {subject.subject_id: subject for subject in self.subjects.items}
        if len(subjects) != len(self.subjects.items):
            raise ValueError("subject IDs must be unique within an event")
        for action in self.actions.items:
            if any(ref not in subjects for ref in [*action.actor_subject_ids, *action.target_subject_ids]):
                raise ValueError("action references must resolve to subjects in the same event")
        for presentation in self.product_presentations.items:
            for ref in presentation.product_subject_ids:
                if ref not in subjects or "product" not in (subjects[ref].roles or []):
                    raise ValueError("product presentation references must resolve to local subjects with the product role")
        return self

    def has_failures(self) -> bool:
        return any(group.status == "failed" for group in (self.subjects, self.actions, self.product_presentations))


def validate_visual_details_correction(before: VisualDetails | dict | None,
                                       after: VisualDetails | dict | None) -> VisualDetails:
    """Validate an atomic label edit without repairing or replacing observations.

    Subject IDs and item positions identify the existing observations. Actions
    and presentations have no independent IDs; their relationship arrays and
    positions stay fixed while their category/description leaves can change.
    """
    if before is None or after is None:
        raise ValueError("structured corrections require existing visual details; missing extraction cannot be added or removed")
    old = VisualDetails.model_validate(before.model_dump() if isinstance(before, VisualDetails) else before)
    new = VisualDetails.model_validate(after.model_dump() if isinstance(after, VisualDetails) else after)
    for name, editable in (
        ("subjects", {"kind", "roles", "label", "description"}),
        ("actions", {"action_type", "description"}),
        ("product_presentations", {"presentation_type", "description"}),
    ):
        previous, current = getattr(old, name), getattr(new, name)
        if previous.status != current.status or previous.error != current.error:
            raise ValueError("structured corrections cannot change extraction status or errors")
        if len(previous.items) != len(current.items):
            raise ValueError("structured corrections cannot add or delete observations")
        old_items = [item.model_dump_json() for item in previous.items]
        new_items = [item.model_dump_json() for item in current.items]
        if old_items != new_items and sorted(old_items) == sorted(new_items):
            raise ValueError("structured corrections cannot reorder existing observations")
        for left, right in zip(previous.items, current.items, strict=True):
            if left.model_dump(exclude=editable) != right.model_dump(exclude=editable):
                raise ValueError("structured corrections cannot change subject IDs, item order or relationship references")
    return new


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
    generation_language: Literal["English", "Chinese"] | None = None
    progress: Literal["setup", "analysis", "review", "directions", "production"] = "setup"
    version: Revision = 1
    current_brief: VersionRef | None = None
    current_video_id: ID | None = None
    current_analysis: VersionRef | None = None
    chosen_direction: VersionRef | None = None
    selected_direction: VersionRef | None = None
    current_production_brief: VersionRef | None = None
    current_storyboard: VersionRef | None = None


class ClaimDetail(ContractModel):
    """Permission to use exact supplied wording; never a factual verification."""
    claim_id: ID
    statement: Nonempty
    supporting_notes: str | None = None
    source_urls: list[str] = Field(default_factory=list, max_length=10)
    qualification: str | None = None
    confirmation_origin: Literal["user_confirmed", "legacy_unrecorded"]

    @field_validator("source_urls")
    @classmethod
    def safe_sources(cls, values):
        from urllib.parse import urlsplit
        for value in values:
            url = urlsplit(value)
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or any(c.isspace() for c in value):
                raise ValueError("claim source URLs must be safe http or https references")
        return values


class M2Claim(ContractModel):
    claim_id: ID
    statement: str = Field(default="")
    supporting_notes: str | None = Field(default=None)
    source_urls: list[str] = Field(default_factory=list, max_length=10)
    qualification: str | None = Field(default=None)
    confirmed_for_use: bool = False

    _safe_sources = field_validator("source_urls")(ClaimDetail.safe_sources.__func__)


class M2Fields(ContractModel):
    """Partial task-local input; null is unknown, explicit 'none' remains text."""
    brand_company: str | None = Field(default=None)
    product: str | None = Field(default=None)
    target_audience: str | None = Field(default=None)
    platform: str | None = Field(default=None)
    communication_goal: str | None = Field(default=None)
    target_duration_seconds: Annotated[float, Field(gt=0, strict=True, allow_inf_nan=False)] | None = None
    available_footage: str | None = Field(default=None)
    presenters: str | None = Field(default=None)
    locations: str | None = Field(default=None)
    tone: str | None = Field(default=None)
    production_limits: str | None = Field(default=None)
    approved_messages: list[Nonempty] = Field(default_factory=list)
    prohibited_claims: list[Nonempty] = Field(default_factory=list)


class M2Draft(ContractModel):
    task_id: ID
    draft_version: Revision = 1
    based_on_brief: VersionRef | None = None
    fields: M2Fields = Field(default_factory=M2Fields)
    claims: list[M2Claim] = Field(default_factory=list)
    source_notes: str = Field(default="", max_length=30000)
    reviewed_input_checkpoint: str
    has_pending_inputs: bool = False
    legacy_review_required: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("updated_at")
    @classmethod
    def utc_date(cls, value):
        return aware_utc(value)


class M2DraftUpdate(ContractModel):
    expected_draft_version: Revision
    fields: M2Fields
    claims: list[M2Claim]
    source_notes: str = Field(max_length=30000)

    @field_validator("claims")
    @classmethod
    def unique_claim_ids(cls, values):
        if len({claim.claim_id for claim in values}) != len(values):
            raise ValueError("claim IDs must be unique")
        return values


class M2ApplyRequest(ContractModel):
    expected_draft_version: Revision
    expected_version: Revision
    based_on_brief: VersionRef | None


class M2DiscardRequest(ContractModel):
    expected_draft_version: Revision


class BrandTaskBrief(Record):
    brief_id: ID
    revision: Revision = 1
    task_id: ID
    brand_company: Nonempty
    product: Nonempty
    selling_points: list[Nonempty] = Field(min_length=1)
    claim_details: list[ClaimDetail] = Field(min_length=1)
    approved_messages: list[Nonempty] = Field(default_factory=list)
    target_audience: Nonempty
    platform: Nonempty
    communication_goal: Nonempty
    target_duration_seconds: Annotated[float, Field(gt=0, strict=True, allow_inf_nan=False)]
    available_footage: str | None = None
    presenters: str | None = None
    locations: str | None = None
    tone: str | None = None
    production_limits: str | None = None
    prohibited_claims: list[Nonempty] = Field(default_factory=list)


    @model_validator(mode="after")
    def claim_projection(self):
        if self.selling_points != [claim.statement for claim in self.claim_details]:
            raise ValueError("selling_points must exactly match ordered claim_details statements")
        if len({claim.claim_id for claim in self.claim_details}) != len(self.claim_details):
            raise ValueError("applied claim IDs must be unique")
        return self


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


class PlaybackRepresentation(ContractModel):
    """Browser derivative with one measured presentation frame per source frame."""

    storage_id: StorageID
    video_codec: Literal["h264"]
    audio_codec: Literal["aac"] | None
    duration_seconds: PositiveSeconds
    frame_timing: FrameTiming

    @model_validator(mode="after")
    def valid_duration(self):
        if not math.isclose(self.frame_timing.frame_boundaries_seconds[-1], self.duration_seconds,
                            rel_tol=0, abs_tol=1e-6):
            raise ValueError("playback final frame boundary must equal its measured duration")
        return self


class VideoAsset(Record):
    video_id: ID
    task_id: ID
    deleted_at: datetime | None = None
    purpose: Literal["reference", "draft"] = "reference"
    input_method: Literal["file", "sample", "legacy"]
    storage_id: StorageID | None = None
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None = None
    sample_key: str | None = None
    original_file_name: str | None = None
    source_url: str | None = None
    duration_seconds: PositiveSeconds | None = None
    frame_timing: FrameTiming | None = None
    playback: PlaybackRepresentation | None = None
    width: Annotated[int, Field(gt=0)] | None = None
    height: Annotated[int, Field(gt=0)] | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    has_audio: bool | None = None
    intake_status: Literal["ready", "failed", "missing"]
    origin: Origin
    public_metrics: PublicMetrics | None = None
    error: ErrorInfo | None = None

    @field_validator("deleted_at")
    @classmethod
    def utc_deleted(cls, value):
        return aware_utc(value) if value else None

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
        if self.playback is not None:
            if self.frame_timing is None or self.playback.frame_timing.frame_count != self.frame_timing.frame_count:
                raise ValueError("playback requires one presentation frame for each original source frame")
            if self.playback.storage_id == self.storage_id:
                raise ValueError("playback derivative must preserve the original stored asset separately")
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
    visual_details: VisualDetails | None = None

    @model_validator(mode="after")
    def valid_event(self):
        expected_lane = "visual" if self.kind in ("visual_action", "on_screen_text") else "audio"
        if self.lane != expected_lane:
            raise ValueError("event kind must use its visual/audio lane")
        if self.text is None and self.description is None:
            raise ValueError("event needs recognized text or an observation description")
        if self.visual_details is not None and self.kind != "visual_action":
            raise ValueError("visual details are permitted only on visual_action events")
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
    field: Literal["text", "description", "roles", "visual_details"]
    before: JsonValue
    after: JsonValue

    @model_validator(mode="after")
    def allowed_field(self):
        if (self.target_type == "segment") != (self.field == "roles"):
            raise ValueError("only event text/descriptions/visual details and segment roles are editable")
        if self.field == "visual_details":
            revised = validate_visual_details_correction(self.before, self.after)
            self.before = VisualDetails.model_validate(self.before).model_dump(mode="json")
            self.after = revised.model_dump(mode="json")
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
        if self.revision == 1 and self.corrections:
            raise ValueError("original extraction cannot contain human correction history")
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
        failed_extraction = "failed" in self.coverage.model_dump().values() or any(
            event.visual_details is not None and event.visual_details.has_failures() for event in self.events
        )
        if self.status == "succeeded" and failed_extraction:
            raise ValueError("failed extraction categories require partial analysis status")
        if self.status == "partial" and not failed_extraction:
            raise ValueError("partial analysis must identify failed extraction categories or structured groups")
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
    analysis_ref: VersionRef | None = None
    structure_handoff_id: ID | None = None
    feedback_refs: list[VersionRef] = Field(default_factory=list)
    core_message: Nonempty
    hook: Nonempty
    narrative: Nonempty
    cta: Nonempty
    production_requirements: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    rationale: Nonempty
    auxiliary_status: Literal["current", "needs_review"] = "current"
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
    analysis_ref: VersionRef | None = None
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
    bundle_id: ID | None = None
    output_id: ID
    revision: Revision = 1
    task_id: ID
    direction_ref: VersionRef
    brief_ref: VersionRef
    analysis_ref: VersionRef | None = None
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


class M2ApplyResult(ContractModel):
    changed: bool
    draft: M2Draft
    task: TaskState


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

    def citations(items: list[EvidenceReference], analysis: AnalysisResult | None):
        if analysis is None:
            if items:
                raise ValueError("original creative work cannot contain invented reference evidence")
            return
        valid_ids = {event.event_id for event in analysis.events}
        for item in items:
            if (item.analysis_id, item.analysis_revision, item.video_id) != (analysis.analysis_id, analysis.revision, analysis.video_id) or item.event_id not in valid_ids:
                raise ValueError("evidence must resolve within the exact recorded analysis revision and video")

    def inputs(record):
        brief = resolve("briefs", record.brief_ref)
        analysis = resolve("analyses", record.analysis_ref) if record.analysis_ref else None
        if record.currentness == "current":
            if record.brief_ref != task.current_brief:
                raise ValueError("current creative records must use exact current task inputs")
            if analysis is not None:
                if record.analysis_ref != task.current_analysis or analysis.video_id != task.current_video_id:
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
            # Legacy imports can contain only the original and a later snapshot.
            # Preserve every available earlier log without inventing missing revisions.
            previous = max((item for item in state.analyses
                            if item.analysis_id == analysis.analysis_id and item.revision < analysis.revision),
                           key=lambda item: item.revision)
            if analysis.corrections[:len(previous.corrections)] != previous.corrections:
                raise ValueError("analysis corrections must preserve all earlier correction history")
            for field in ("status", "coverage", "error", "empty_result_reason"):
                if getattr(analysis, field) != getattr(original, field):
                    raise ValueError("analysis corrections cannot change extraction status or coverage")
            old_events = {event.event_id: event for event in original.events}
            old_segments = {segment.segment_id: segment for segment in original.segments}
            if list(old_events) != [event.event_id for event in analysis.events] or list(old_segments) != [segment.segment_id for segment in analysis.segments]:
                raise ValueError("analysis corrections must preserve observation and section IDs and order")
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
                for field in ("text", "description", "visual_details"):
                    if event.model_dump()[field] != replay_events[event.event_id][field]:
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
        if resolve("videos", VersionRef(id=task.current_video_id, revision=1)).deleted_at is not None:
            raise ValueError("current reference cannot be deleted media")
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


EditorScope = Annotated[str, StringConstraints(pattern=r"^(idea|analysis|production|direction-[A-Za-z][A-Za-z0-9_-]{1,63})$")]


class EditorDraft(ContractModel):
    task_id: ID
    scope: EditorScope
    draft_version: Revision = 1
    base_refs: dict[str, VersionRef] = Field(default_factory=dict)
    content: dict[str, JsonValue] = Field(default_factory=dict)
    has_pending_changes: bool = False
    conflict: bool = False
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("updated_at")
    @classmethod
    def utc_updated(cls, value):
        return aware_utc(value)


class EditorDraftUpdate(ContractModel):
    expected_draft_version: Revision
    base_refs: dict[str, VersionRef]
    content: dict[str, JsonValue]


class EditorDiscardRequest(ContractModel):
    expected_draft_version: Revision
