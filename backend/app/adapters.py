"""Replaceable recognition and creative boundaries with separate sample adapters.

The service owns saved revisions/currentness and gates; adapters validate their
local inputs too. Sample recognition is restricted to hash-verified generated
media in a dedicated sample task. Sample creative output is always labeled.
"""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
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
    def for_language(self, language: str) -> CreativeAdapter: ...
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
    if any(claim.confirmation_origin != "user_confirmed" for claim in brief.claim_details):
        raise ValueError("Review and confirm the input claims before creative generation")
    if brief.task_id != analysis.task_id:
        raise ValueError("Brief and analysis must belong to the same task")
    if analysis.status != "succeeded" or not analysis.review.user_confirmed:
        raise ValueError("Creative generation requires a completed, confirmed analysis")
    if analysis.frame_count is None:
        raise ValueError("Creative generation requires known reference frame timing; re-upload and analyze the source video")
    if not analysis.events:
        raise ValueError("Creative generation needs reviewed observations")


def _evidence(analysis: AnalysisResult, language: str = "English") -> list[EvidenceReference]:
    events = [event for event in analysis.events if event.kind == "visual_action"] or analysis.events
    return [EvidenceReference(analysis_id=analysis.analysis_id, analysis_revision=analysis.revision,
                              video_id=analysis.video_id, event_id=event.event_id,
                              reason=("借鉴已审阅画面的展示次序；不表示创意效果已验证。" if language == "Chinese" else
                                      "Borrow the reviewed visual presentation sequence; effectiveness is unmeasured."))
            for event in events[:3]]


def _message(brief: BrandTaskBrief) -> str:
    message = " / ".join(brief.approved_messages) if brief.approved_messages else f"Introducing {brief.product}"
    # Exact fixed wording is never translated or shortened. When it repeats a
    # qualified claim, carry its condition alongside the unchanged wording.
    for claim in brief.claim_details:
        if claim.statement in message and claim.qualification and claim.qualification not in message:
            message += " — " + claim.qualification
    return message


def claim_context(brief: BrandTaskBrief) -> list[str]:
    """Keep exact usable wording and its conditions visible in generated plans."""
    result = []
    for claim in brief.claim_details:
        result.append(f"User-confirmed claim (permission, not verification): {claim.statement}")
        if claim.qualification:
            result.append(f"Required claim qualification: {claim.qualification}")
        if claim.supporting_notes:
            result.append(f"User-supplied support (not independently verified): {claim.supporting_notes}")
        if claim.source_urls:
            result.append("User-supplied references (not fetched): " + "; ".join(claim.source_urls))
    return result


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
    """Clearly synthetic, bilingual templates; never a real-provider fallback.

    Refinement demonstrates only explicit presenter-free phrases. Other feedback
    returns None and is saved as uninterpreted by the workflow service.
    """
    def __init__(self, language: str = "English"):
        if language not in {"English", "Chinese"}:
            raise ValueError("Choose English or Chinese for creative generation")
        self.language = language

    def for_language(self, language: str) -> SampleCreativeAdapter:
        if language not in {"English", "Chinese"}:
            raise ValueError("Choose English or Chinese for creative generation")
        scoped = copy(self)
        scoped.language = language
        return scoped

    def _text(self, english: str, chinese: str) -> str:
        return chinese if self.language == "Chinese" else english

    def _presenter_free(self, brief, direction=None):
        # This is a small transparent template rule, not arbitrary instruction
        # understanding. Approved text, never stale requirements, drives it.
        constraints = " ".join(filter(None, [brief.presenters, brief.production_limits,
                                             direction.hook if direction else None,
                                             direction.narrative if direction else None])).casefold()
        return any(term in constraints for term in ("presenter-free", "no presenter", "no on-camera presenter",
                                                    "product-only", "无人出镜", "不出镜", "无需出镜"))

    def _requirements(self, brief, presenter_free):
        return [
            self._text("Presenter-free: prepare product illustrations or permitted product footage and text cards; no spoken dialogue."
                       if presenter_free else
                       "Presenter-led: prepare one presenter and a product/illustration setup; confirm availability before shooting.",
                       "无人出镜：准备产品插画或获准使用的产品素材及文字卡，不安排对白。" if presenter_free else
                       "准备一位出镜讲解者和产品或插画布景；开拍前确认人员与素材可用。"),
            self._text(f"Plan {brief.target_duration_seconds:g} seconds for {brief.platform}.",
                       f"按 {brief.platform} 安排 {brief.target_duration_seconds:g} 秒内容。"),
        ]

    def _notes(self, brief):
        notes = claim_context(brief)
        for english, chinese, value in [
            ("Available footage", "已填写素材", brief.available_footage),
            ("Presenters", "出镜条件", brief.presenters), ("Locations", "场地条件", brief.locations),
            ("Tone", "语气", brief.tone), ("Production limits", "制作限制", brief.production_limits),
        ]:
            if value:
                notes.append(f"{self._text(english, chinese)}: {value}")
        if brief.prohibited_claims:
            notes.append(self._text("Do not claim: ", "禁止宣称：") + "; ".join(brief.prohibited_claims))
        return notes

    def _hypotheses(self, brief):
        return [self._text(
            f"Unverified hypothesis: the sequence helps {brief.target_audience} describe the approved message. "
            "Ask reviewers to retell the message and identify confusing shots; no effectiveness measurement exists.",
            f"待验证假设：该顺序帮助 {brief.target_audience} 理解已确认信息。"
            "请评审者复述信息并指出难懂的镜头；尚无效果测量。")]

    def generate_directions(self, brief: BrandTaskBrief, analysis: AnalysisResult) -> list[CreativeDirection]:
        _inputs(brief, analysis)
        free = self._presenter_free(brief)
        common = {**_base(brief, analysis), "core_message": _message(brief),
                  "evidence": _evidence(analysis, self.language), "production_notes": self._notes(brief),
                  "origin": Origin(kind="sample", description="Deterministic fictional creative templates; no model call or validated strategy."),
                  "hypotheses": self._hypotheses(brief)}
        a_hook = self._text(
            f"Product-only introduction: center {brief.product} on a plain background and reveal the message: {_message(brief)}."
            if free else f"A presenter introduces {brief.product} beside its illustration with the message: {_message(brief)}.",
            f"无人出镜：在纯色背景居中展示 {brief.product}，出现已确认文案：{_message(brief)}。"
            if free else f"讲解者在 {brief.product} 插画旁开场，展示已确认文案：{_message(brief)}。")
        return [
            CreativeDirection(**common, direction_id=f"direction_{uuid4().hex}",
                              hook=a_hook,
                              narrative=self._text(
                                  f"Follow the reference structure: product introduction → close detail demonstration → invitation. "
                                  f"Use only the approved message {_message(brief)} to support the goal: {brief.communication_goal}.",
                                  f"贴近参考结构：产品亮相 → 局部细节展示 → 行动邀请。"
                                  f"仅使用已确认信息 {_message(brief)}，服务本次目标：{brief.communication_goal}。"),
                              cta=self._text(f"Explore {brief.product} from {brief.brand_company}.",
                                             f"了解 {brief.brand_company} 的 {brief.product}。"),
                              production_requirements=self._requirements(brief, free),
                              rationale=self._text(
                                  f"A keeps the reference's introduction/detail/CTA progression to introduce {brief.product} "
                                  f"to {brief.target_audience}. This supports the stated goal without a performance prediction.",
                                  f"A 保留参考的亮相、细节、邀请顺序，向 {brief.target_audience} 介绍 {brief.product}，"
                                  "对应已填写目标；不预测传播效果。")),
            CreativeDirection(**common, direction_id=f"direction_{uuid4().hex}",
                              hook=self._text(
                                  f"Product-only question card: 'Which detail would you explore first?' Reveal {brief.product} only after the question.",
                                  f"无人出镜，先用提问卡开场：“你想先了解哪个细节？”随后才揭示 {brief.product}。"),
                              narrative=self._text(
                                  f"Start with the viewer's choice, then work backward from a finished product card to a close detail. "
                                  f"Reassemble the product view and end with {_message(brief)} and an invitation supporting {brief.communication_goal}.",
                                  f"从观众的选择切入，把结尾式产品卡前置，再倒回局部细节；重新组合完整产品画面，"
                                  f"以 {_message(brief)} 和对应 {brief.communication_goal} 的邀请收尾。"),
                              cta=self._text(f"Discover the details of {brief.product}.", f"探索 {brief.product} 的细节。"),
                              production_requirements=self._requirements(brief, True),
                              rationale=self._text(
                                  f"B reorganizes the observed product/detail elements around a question for {brief.target_audience}; "
                                  f"the question and reverse reveal are original proposals for {brief.brand_company}, not observations or measured improvements.",
                                  f"B 为 {brief.target_audience} 把参考中的产品与细节元素重排成提问和反向揭示；"
                                  f"这是给 {brief.brand_company} 的原创建议，不是源视频观察或已验证的提升。")),
        ]

    def refine_direction(self, brief: BrandTaskBrief, analysis: AnalysisResult, target: CreativeDirection,
                         feedback: CreativeFeedback) -> CreativeDirection | None:
        _matches(target, brief, analysis)
        if (feedback.task_id != brief.task_id or feedback.target_direction != VersionRef(id=target.direction_id, revision=target.revision)
                or feedback.brief_ref != target.brief_ref or feedback.analysis_ref != target.analysis_ref):
            raise ValueError("Feedback must identify this exact direction and its input versions")
        literal = feedback.instruction.strip().lower().rstrip(".! 。！")
        if literal not in {"make this direction presenter-free", "make it presenter-free", "presenter-free", "改成无人出镜", "无人出镜"}:
            return None
        fields = target.model_dump()
        fields.update(revision=target.revision+1, updated_at=utc_now(), approval_status="draft", approved_at=None,
                      auxiliary_status="current",
                      hook=self._text(f"Open with a product-only close-up of {brief.product}; show '{_message(brief)}' as on-screen text.",
                                      f"无人出镜：以 {brief.product} 的局部特写开场，屏幕保留文案：{_message(brief)}。"),
                      narrative=self._text(
                          f"Presenter-free sequence: product close-ups, graphics carrying {_message(brief)}, then the CTA. No on-camera presenter or spoken dialogue.",
                          f"无人出镜顺序：产品特写、承载 {_message(brief)} 的图形卡、行动邀请。不安排出镜者或对白。"),
                      production_requirements=self._requirements(brief, True),
                      production_notes=[*self._notes(brief), self._text("Applied literal sample instruction: ", "已应用支持的示例指令：") + feedback.instruction],
                      rationale=self._text("The revised product-only sequence retains the reference progression while removing presenter needs. Review its fit with the applied audience and goal.",
                                           "修改后的纯产品顺序保留参考结构，同时移除出镜需求；请结合当前受众与目标审阅适配性。"),
                      hypotheses=self._hypotheses(brief), evidence=_evidence(analysis, self.language),
                      feedback_refs=[*target.feedback_refs, VersionRef(id=feedback.feedback_id, revision=feedback.revision)],
                      origin=Origin(kind="sample", description="Deterministic presenter-free sample refinement; exact saved feedback received, no unrestricted language interpretation."))
        return CreativeDirection.model_validate(fields)

    def generate_production(self, brief: BrandTaskBrief, analysis: AnalysisResult,
                            direction: CreativeDirection) -> tuple[ProductionCreativeBrief, TextStoryboard]:
        _matches(direction, brief, analysis)
        if direction.approval_status != "approved" or direction.approved_at is None:
            raise ValueError("Production generation requires explicit approval of this exact direction revision")
        presenter_free = self._presenter_free(brief, direction)
        stale = direction.auxiliary_status == "needs_review"
        notes = [self._text(f"Fictional sample production plan for {brief.brand_company} / {brief.product}.",
                           f"虚构示例制作计划：{brief.brand_company} / {brief.product}。"),
                 self._text(f"Audience: {brief.target_audience}. Platform: {brief.platform}. Target: {brief.target_duration_seconds:g} seconds.",
                            f"受众：{brief.target_audience}。平台：{brief.platform}。目标时长：{brief.target_duration_seconds:g} 秒。"),
                 self._text(f"Goal: {brief.communication_goal}.", f"目标：{brief.communication_goal}。"),
                 self._text(f"Approved wording (preserved exactly): {_message(brief)}", f"已确认文案（保留原文）：{_message(brief)}"),
                 *self._notes(brief)]
        if not stale:
            notes.extend([*direction.production_requirements, *direction.production_notes])
        else:
            notes.append(self._text("Earlier direction explanations were excluded after manual editing; production follows the current approved text and applied inputs.",
                                    "方向手改前的辅助说明未被沿用；本方案依据当前已批准正文及已应用输入。"))
        notes.append(self._text("To prepare: permitted product visuals, a simple background, approved text cards and any licensed/original sound; confirm these resources before shooting.",
                                "需要准备：获准使用的产品画面、简单背景、已确认文字卡，以及需要时的授权或原创声音；拍摄前确认资源。"))
        common = {**_base(brief, analysis), "direction_ref": VersionRef(id=direction.direction_id, revision=direction.revision),
                  "feedback_refs": direction.feedback_refs,
                  "origin": Origin(kind="sample", description="Deterministic fictional production draft from exact approved text; not a model result or validated shooting plan.")}
        evidence = _evidence(analysis, self.language) if stale else direction.evidence
        creative_brief = ProductionCreativeBrief(**common, output_id=f"production_{uuid4().hex}",
                                                 title=self._text(f"{brief.product}: production creative brief", f"{brief.product}：制作简报"),
                                                 core_message=direction.core_message, hook=direction.hook,
                                                 narrative=direction.narrative, cta=direction.cta,
                                                 production_notes=list(dict.fromkeys(notes)), evidence=evidence)
        duration = brief.target_duration_seconds
        count = min(12, max(3, math.ceil(duration / 6)))
        rows = []
        for index in range(count):
            start, end = duration * index / count, duration * (index+1) / count
            last = index == count-1
            reverse_opening = "work backward" in direction.narrative or "倒回" in direction.narrative
            original = index > 1 or not evidence or (index == 0 and (stale or reverse_opening))
            refs = [] if original else evidence[index:index+1]
            if index == 0:
                visual = self._text(f"Opening on a plain background. {direction.hook}", f"纯色背景开场。{direction.hook}")
            elif index == 1:
                visual = self._text(f"Close view of {brief.product} or its illustration on a simple background. Highlight one visible detail without claiming unapproved performance.",
                                    f"简单背景中展示 {brief.product} 或其插画的局部特写；突出一个可见细节，不暗示未经确认的性能。")
            elif last:
                visual = self._text(f"Hold a clean end card on a plain background with {brief.brand_company}, {brief.product} and the invitation: {direction.cta}",
                                    f"纯色背景上停留结尾卡，展示 {brief.brand_company}、{brief.product} 和邀请：{direction.cta}")
            else:
                visual = self._text(f"On a new plain-background card, move a product illustration into the center and reveal one approved message. Follow this approved story: {direction.narrative}",
                                    f"新的纯色背景卡中，将产品插画移到中央并展示一条已确认信息。按照当前批准叙事推进：{direction.narrative}")
            if not refs:
                visual = self._text("Original production suggestion: ", "原创制作建议：") + visual
            card = direction.cta if last else (_message(brief) if index == 1 else None)
            # Never shorten or silently translate fixed copy to fit a template.
            # Long copy remains exact in the brief for human scheduling review.
            units = len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", card or ""))
            if units > (end-start) * 2.5:
                card = None
            rows.append({"row_id": f"row_{uuid4().hex}", "start_seconds": start, "end_seconds": end,
                         "visual": visual, "dialogue": None,
                         "on_screen_text": card,
                         "sound": self._text("Optional original or licensed instrumental bed; proposed sound, not source recognition.",
                                             "可选原创或授权纯音乐；这是声音建议，不是识别结果。") if index == 0 else None,
                         "cta": direction.cta if last else None, "evidence": refs})
        if not presenter_free:
            creative_brief.production_notes.append(self._text("Presenter is optional; the template leaves dialogue empty for review and does not invent a spoken performance claim.",
                                                               "讲解者可按需要安排；示例将对白留空供审阅，不编造口播性能承诺。"))
        creative_brief.production_notes.append(self._text("Long approved copy stays in the brief instead of being squeezed into short cards; review reading time before shooting.",
                                                         "较长的已确认文案保留在简报中，不强塞进短镜头；拍摄前核查阅读时长。"))
        storyboard = TextStoryboard(**common, output_id=f"storyboard_{uuid4().hex}", target_duration_seconds=duration, rows=rows)
        return creative_brief, storyboard
