"""Clearly fictional saved inputs and matching observations, never an upload fallback."""
from uuid import uuid4

from .models import AnalysisResult, BrandTaskBrief, VideoAsset
from .timing import seconds_to_frame_range


def sample_brief(task_id: str) -> BrandTaskBrief:
    return BrandTaskBrief(
        brief_id=f"brief_{uuid4().hex}", task_id=task_id,
        brand_company="Luma Studio (fictional)", product="LumaCup (fictional)",
        selling_points=["Removable lid", "Three illustrated colors"],
        claim_details=[
            {"claim_id": "sample_claim_lid", "statement": "Removable lid",
             "confirmation_origin": "user_confirmed",
             "supporting_notes": "Scripted confirmation in the fictional sample, not a real user or verified fact."},
            {"claim_id": "sample_claim_colors", "statement": "Three illustrated colors",
             "confirmation_origin": "user_confirmed",
             "supporting_notes": "Scripted confirmation in the fictional sample, not a real user or verified fact."},
        ],
        approved_messages=["Removable lid", "Explore three colors"],
        target_audience="People comparing colorful everyday drinkware",
        platform="Short-form social video", communication_goal="Introduce the fictional product and invite color exploration",
        target_duration_seconds=15, available_footage="Original simple cup illustrations; no live-action footage",
        presenters="One presenter available if needed", locations="Tabletop studio",
        tone="Clear and playful", production_limits="Small team; simple graphics; no generated storyboard images",
        prohibited_claims=["Leak-proof", "Keeps drinks hot", "Verified performance or conversion claims"],
    )


def sample_analysis(task_id: str, video: VideoAsset, job_id: str) -> AnalysisResult:
    if video.frame_timing is None:
        raise ValueError("Sample recognition requires probed frame timing")

    def interval(start: float, end: float) -> dict:
        first, stop = seconds_to_frame_range(start, end, video.frame_timing)
        return {"start_frame": first, "end_frame": stop}

    def event(event_id: str, start: float, end: float, kind: str, content: str) -> dict:
        is_text = kind in {"on_screen_text", "speech"}
        return {"event_id": event_id, "video_id": video.video_id, **interval(start, end),
                "lane": "audio" if kind in {"speech", "music", "sfx"} else "visual", "kind": kind,
                "text": content if is_text else None, "description": None if is_text else content,
                "source": "Programmatic synthetic sample manifest", "method": "Prepared matching fixture; no recognition provider was called"}
    events = [
        event("event_intro_shape", 0, 3, "visual_action", "A blue cup-shaped rectangle with an orange lid is centered on a dark background."),
        event("event_intro_text", 0, 3, "on_screen_text", "LUMACUP\nFICTIONAL SAMPLE"),
        event("event_lid_shape", 3, 7, "visual_action", "An orange rectangular lid moves upward during seconds 3–4, then stays above the blue cup shape."),
        event("event_lid_text", 3, 7, "on_screen_text", "REMOVABLE LID"),
        event("event_cta_shape", 7, 10, "visual_action", "Three blue, pink, and green cup-shaped rectangles appear with orange lids."),
        event("event_cta_text", 7, 10, "on_screen_text", "EXPLORE THE COLORS"),
        event("event_footer", 0, 10, "on_screen_text", "SYNTHETIC DEMO - NO REAL PRODUCT CLAIMS"),
        event("event_melody", 0, 10, "music", "A quiet repeating synthesized melody changes note once per second."),
        event("event_chime_1", 3, 3.25, "sfx", "A short high sine-tone chime overlaps the melody as the lid starts moving."),
        event("event_chime_2", 7, 7.25, "sfx", "A short high sine-tone chime overlaps the melody as the three colors appear."),
    ]
    segments = [
        {"segment_id": "segment_hook", "video_id": video.video_id, **interval(0, 3),
         "roles": ["hook"], "evidence_ids": ["event_intro_shape", "event_intro_text", "event_footer", "event_melody"],
         "interpretation": "An introductory product card functions as a possible Hook; effectiveness has not been measured."},
        {"segment_id": "segment_demo", "video_id": video.video_id, **interval(3, 7),
         "roles": ["product_demo"], "evidence_ids": ["event_lid_shape", "event_lid_text", "event_footer", "event_melody", "event_chime_1"],
         "interpretation": "The graphic illustrates a removable lid; this is no evidence of a real product's performance."},
        {"segment_id": "segment_cta", "video_id": video.video_id, **interval(7, 10),
         "roles": ["cta"], "evidence_ids": ["event_cta_shape", "event_cta_text", "event_footer", "event_melody", "event_chime_2"],
         "interpretation": "The final card invites color exploration; no click or conversion data exists."},
    ]
    return AnalysisResult.model_validate({
        "analysis_id": f"analysis_{uuid4().hex}", "task_id": task_id, "video_id": video.video_id,
        "duration_seconds": video.duration_seconds, "frame_count": video.frame_timing.frame_count,
        "status": "succeeded", "events": events, "segments": segments,
        "coverage": {"visual_action": "observations", "on_screen_text": "observations", "speech": "none_found",
                     "music": "observations", "sfx": "observations"},
        "origin": {"kind": "sample", "description": f"Deterministic fictional matching-media fixture, job {job_id}; no model run."},
    })
