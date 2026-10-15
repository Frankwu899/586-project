"""Replaceable recognition and creative boundaries. No provider requests are made.

The service owns saved revisions/currentness and gates; adapters validate their
local inputs too. Sample recognition is restricted to hash-verified generated
media in a dedicated sample task. Sample creative output is always labeled.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from .media import SAMPLE_DESCRIPTION, SAMPLE_KEY
from .models import (AnalysisResult, BrandTaskBrief, CreativeDirection, CreativeFeedback,
                     EvidenceReference, Origin, ProductionCreativeBrief, TextStoryboard,
                     VersionRef, VideoAsset, utc_now)
from .sample import sample_analysis


@dataclass(frozen=True)
class RecognitionRequest:
    task_id: str
    video: VideoAsset
    job_id: str
    task_mode: str = "real"
    media_path: Path | None = None


class RecognitionAdapter(Protocol):
    def analyze(self, request: RecognitionRequest) -> AnalysisResult: ...


class CreativeAdapter(Protocol):
    def generate_directions(self, brief: BrandTaskBrief, analysis: AnalysisResult) -> list[CreativeDirection]: ...
    def refine_direction(self, brief: BrandTaskBrief, analysis: AnalysisResult, target: CreativeDirection,
                         feedback: CreativeFeedback) -> CreativeDirection | None: ...
    def generate_production(self, brief: BrandTaskBrief, analysis: AnalysisResult,
                            direction: CreativeDirection) -> tuple[ProductionCreativeBrief, TextStoryboard]: ...


def _failure(request: RecognitionRequest, code: str, message: str) -> AnalysisResult:
    if request.video.duration_seconds is None:
        raise ValueError("Recognition requires a saved video with measured duration")
    return AnalysisResult.model_validate({
        "analysis_id": f"analysis_{uuid4().hex}", "task_id": request.task_id,
        "video_id": request.video.video_id, "duration_seconds": request.video.duration_seconds,
        "frame_count": request.video.frame_timing.frame_count if request.video.frame_timing else None,
        "status": "failed", "origin": {"kind": "manual", "description": "No recognition provider was run; explicit unavailable/rejected input result."},
        "error": {"code": code, "message": message, "retryable": False},
    })


class UnconfiguredRecognitionAdapter:
    def analyze(self, request: RecognitionRequest) -> AnalysisResult:
        return _failure(request, "real_analysis_not_configured",
                        "Real analysis is not configured. This upload was saved but has not been recognized. Load a dedicated fictional sample task to try the full workflow.")


class SampleRecognitionAdapter:
    def analyze(self, request: RecognitionRequest) -> AnalysisResult:
        video = request.video
        valid = (request.task_mode == "sample" and video.task_id == request.task_id
                 and video.input_method == "sample" and video.origin.kind == "sample"
                 and video.origin.description == SAMPLE_DESCRIPTION and video.sample_key == SAMPLE_KEY
                 and video.intake_status == "ready" and video.duration_seconds is not None and video.frame_timing is not None
                 and abs(video.duration_seconds - 10) < .1 and video.content_sha256 is not None)
        if valid and request.media_path is not None:
            try:
                with Path(request.media_path).open("rb") as source:
                    valid = hashlib.file_digest(source, "sha256").hexdigest() == video.content_sha256
            except OSError:
                valid = False
        else:
            valid = False
        if not valid:
            return _failure(request, "sample_media_mismatch",
                            "Sample recognition requires the dedicated generated sample task and its unchanged matching media. It cannot analyze arbitrary uploads.")
        return sample_analysis(request.task_id, video, request.job_id)


def _inputs(brief: BrandTaskBrief, analysis: AnalysisResult) -> None:
    if brief.task_id != analysis.task_id:
        raise ValueError("Brief and analysis must belong to the same task")
    if analysis.status != "succeeded" or not analysis.review.user_confirmed:
        raise ValueError("Creative generation requires a completed, confirmed analysis")
    if analysis.frame_count is None:
        raise ValueError("Creative generation requires known reference frame timing; re-upload and analyze the source video")
    if not analysis.events:
        raise ValueError("The sample creative adapter needs reviewed observations")


def _evidence(analysis: AnalysisResult) -> list[EvidenceReference]:
    events = [event for event in analysis.events if event.kind == "visual_action"] or analysis.events
    return [EvidenceReference(analysis_id=analysis.analysis_id, analysis_revision=analysis.revision,
                              video_id=analysis.video_id, event_id=event.event_id,
                              reason="Consider this reviewed visual sequence as a structural reference; effectiveness is unmeasured.")
            for event in events[:3]]


def _message(brief: BrandTaskBrief) -> str:
    return " / ".join(brief.approved_messages) if brief.approved_messages else f"Introducing {brief.product}"


def _base(brief: BrandTaskBrief, analysis: AnalysisResult) -> dict:
    return {"task_id": brief.task_id, "brief_ref": VersionRef(id=brief.brief_id, revision=brief.revision),
            "analysis_ref": VersionRef(id=analysis.analysis_id, revision=analysis.revision)}


def _matches(direction: CreativeDirection, brief: BrandTaskBrief, analysis: AnalysisResult) -> None:
    _inputs(brief, analysis)
    if (direction.task_id != brief.task_id or direction.brief_ref != VersionRef(id=brief.brief_id, revision=brief.revision)
            or direction.analysis_ref != VersionRef(id=analysis.analysis_id, revision=analysis.revision)
            or direction.currentness != "current"):
        raise ValueError("Direction must match the exact current brief and reviewed analysis")
    event_ids = {event.event_id for event in analysis.events}
    for ref in direction.evidence:
        if (ref.analysis_id != analysis.analysis_id or ref.analysis_revision != analysis.revision
                or ref.video_id != analysis.video_id or ref.event_id not in event_ids):
            raise ValueError("Direction evidence must resolve within the exact analysis revision")


class SampleCreativeAdapter:
    """Templates plus one literal instruction demonstration; no language model.

    Supported, case-insensitive instruction: "Make this direction presenter-free."
    Also accepts "Make it presenter-free" and "presenter-free", with optional final
    punctuation. Other instructions return None for saved not_interpreted notes.
    """
    def generate_directions(self, brief: BrandTaskBrief, analysis: AnalysisResult) -> list[CreativeDirection]:
        _inputs(brief, analysis)
        common = {**_base(brief, analysis), "core_message": _message(brief), "evidence": _evidence(analysis),
                  "origin": Origin(kind="sample", description="Deterministic sample creative templates; not model output or validated strategy."),
                  "hypotheses": [f"A clear product sequence may help {brief.target_audience} understand the approved message; test with reviewers before claiming effectiveness."]}
        return [
            CreativeDirection(**common, direction_id=f"direction_{uuid4().hex}",
                              hook=f"A presenter introduces {brief.product} with the message: {_message(brief)}.",
                              narrative=f"Presenter-led introduction, a close product view, then an invitation supporting the goal: {brief.communication_goal}.",
                              cta=f"Explore {brief.product} from {brief.brand_company}.",
                              production_requirements=["Presenter-led: one on-camera presenter and a simple product setup.",
                                                       f"Plan {brief.target_duration_seconds:g} seconds for {brief.platform}."],
                              rationale="A guided introduction is a sample hypothesis using the reviewed opening-to-demonstration-to-CTA sequence."),
            CreativeDirection(**common, direction_id=f"direction_{uuid4().hex}",
                              hook=f"Open with a product-only graphic reveal of {brief.product} and an on-screen message: {_message(brief)}.",
                              narrative=f"Use product-only details and short text cards to communicate {_message(brief)}, ending with {brief.communication_goal}.",
                              cta=f"Discover the details of {brief.product}.",
                              production_requirements=["Presenter-free: product-only visuals and on-screen text; no spoken dialogue.",
                                                       f"Plan {brief.target_duration_seconds:g} seconds for {brief.platform}."],
                              rationale="A text-led graphic sequence offers a distinct production approach; any comprehension benefit remains a hypothesis."),
        ]

    def refine_direction(self, brief: BrandTaskBrief, analysis: AnalysisResult, target: CreativeDirection,
                         feedback: CreativeFeedback) -> CreativeDirection | None:
        _matches(target, brief, analysis)
        if (feedback.task_id != brief.task_id or feedback.target_direction != VersionRef(id=target.direction_id, revision=target.revision)
                or feedback.brief_ref != target.brief_ref or feedback.analysis_ref != target.analysis_ref):
            raise ValueError("Feedback must identify this exact direction and its input versions")
        literal = feedback.instruction.strip().lower().rstrip(".! ")
        if literal not in {"make this direction presenter-free", "make it presenter-free", "presenter-free"}:
            return None
        fields = target.model_dump()
        fields.update(revision=target.revision+1, updated_at=utc_now(), approval_status="draft", approved_at=None,
                      hook=f"Open with a product-only close-up of {brief.product}; show '{_message(brief)}' as on-screen text.",
                      narrative=f"Presenter-free sequence: product close-ups, graphics carrying {_message(brief)}, then the CTA. No on-camera presenter or spoken dialogue.",
                      production_requirements=["Presenter-free: no on-camera presenter or spoken dialogue; use product-only visuals and on-screen text.",
                                               f"Plan {brief.target_duration_seconds:g} seconds for {brief.platform}."],
                      production_notes=[*target.production_notes, f"Applied literal sample instruction: {feedback.instruction}"],
                      feedback_refs=[*target.feedback_refs, VersionRef(id=feedback.feedback_id, revision=feedback.revision)],
                      origin=Origin(kind="sample", description="Deterministic presenter-free sample refinement; exact saved feedback received, no unrestricted language interpretation."))
        return CreativeDirection.model_validate(fields)

    def generate_production(self, brief: BrandTaskBrief, analysis: AnalysisResult,
                            direction: CreativeDirection) -> tuple[ProductionCreativeBrief, TextStoryboard]:
        _matches(direction, brief, analysis)
        if direction.approval_status != "approved" or direction.approved_at is None:
            raise ValueError("Production generation requires explicit approval of this exact direction revision")
        presenter_free = any(item.startswith("Presenter-free:") for item in direction.production_requirements)
        notes = [f"Sample production plan for {brief.brand_company} / {brief.product}.",
                 f"Audience: {brief.target_audience}. Platform: {brief.platform}. Target: {brief.target_duration_seconds:g} seconds.",
                 f"Goal: {brief.communication_goal}.", f"Approved messages: {_message(brief)}.",
                 *direction.production_requirements, *direction.production_notes]
        for label, value in [("Available footage", brief.available_footage), ("Available presenters", brief.presenters),
                             ("Locations", brief.locations), ("Tone", brief.tone), ("Production limits", brief.production_limits)]:
            if value:
                notes.append(f"Input constraint — {label}: {value}")
        if brief.prohibited_claims:
            notes.append("Do not claim: " + "; ".join(brief.prohibited_claims))
        common = {**_base(brief, analysis), "direction_ref": VersionRef(id=direction.direction_id, revision=direction.revision),
                  "feedback_refs": direction.feedback_refs,
                  "origin": Origin(kind="sample", description="Template production draft from exact approved direction and saved task inputs; not validated effectiveness.")}
        creative_brief = ProductionCreativeBrief(**common, output_id=f"production_{uuid4().hex}",
                                                 title=f"{brief.product}: production creative brief", core_message=direction.core_message,
                                                 hook=direction.hook, narrative=direction.narrative, cta=direction.cta,
                                                 production_notes=notes, evidence=direction.evidence)
        duration = brief.target_duration_seconds
        times = [0, duration*.2, duration*.5, duration*.8, duration]
        visuals = [direction.hook,
                   f"{'Product-only' if presenter_free else 'Presenter-guided'} detail view of {brief.product}. Use approved message cards; do not imply unapproved performance.",
                   direction.narrative,
                   f"Product-only end card for {brief.brand_company} and {brief.product}. {direction.cta}"]
        text_cards = [direction.core_message, _message(brief), direction.core_message, direction.cta]
        rows = []
        for index in range(4):
            rows.append({"row_id": f"row_{index+1}", "start_seconds": times[index], "end_seconds": times[index+1],
                         "visual": visuals[index], "dialogue": None if presenter_free else text_cards[index],
                         "on_screen_text": text_cards[index],
                         "sound": "Optional licensed or original instrumental bed; no spoken dialogue." if presenter_free else "Optional licensed or original instrumental bed under presenter dialogue.",
                         "cta": direction.cta if index == 3 else None,
                         "evidence": direction.evidence[min(index, len(direction.evidence)-1):min(index, len(direction.evidence)-1)+1]})
        storyboard = TextStoryboard(**common, output_id=f"storyboard_{uuid4().hex}", target_duration_seconds=duration, rows=rows)
        return creative_brief, storyboard
