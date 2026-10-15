from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from backend.app.adapters import RecognitionRequest, SampleCreativeAdapter, SampleRecognitionAdapter, UnconfiguredRecognitionAdapter
from backend.app.media import MediaStore
from backend.app.models import AnalysisResult, CreativeFeedback, ReviewState, VersionRef, utc_now
from backend.app.sample import sample_brief


@pytest.fixture(scope="module")
def matched(tmp_path_factory):
    store = MediaStore(tmp_path_factory.mktemp("adapter-media"))
    video = store.create_sample("task_sample")
    request = RecognitionRequest("task_sample", video, "job_sample", "sample", store.path_for(video))
    return request


def confirmed_analysis(request):
    analysis = SampleRecognitionAdapter().analyze(request)
    timestamp = utc_now()
    analysis.review = ReviewState(user_confirmed=True, confirmed_at=timestamp)
    analysis.updated_at = timestamp
    return AnalysisResult.model_validate(analysis.model_dump())


def feedback_for(direction, instruction):
    return CreativeFeedback(feedback_id="feedback_refinement", task_id=direction.task_id,
                            instruction=instruction, target_direction=VersionRef(id=direction.direction_id, revision=direction.revision),
                            brief_ref=direction.brief_ref, analysis_ref=direction.analysis_ref)


def test_sample_has_matching_overlaps_audio_coverage_and_no_speech_claim(matched):
    analysis = SampleRecognitionAdapter().analyze(matched)
    assert analysis.status == "succeeded" and analysis.origin.kind == "sample"
    assert analysis.coverage.speech == "none_found"
    assert analysis.coverage.music == analysis.coverage.sfx == "observations"
    assert not [event for event in analysis.events if event.kind == "speech"]
    assert any(a.event_id != b.event_id and a.start_frame < b.end_frame and b.start_frame < a.end_frame
               for a in analysis.events for b in analysis.events)
    assert analysis.frame_count == 200
    chime = next(event for event in analysis.events if event.event_id == "event_chime_1")
    assert (chime.start_frame, chime.end_frame) == (60, 65)
    assert "start_seconds" not in chime.model_dump()
    assert analysis.review.user_confirmed is False
    assert matched.video.public_metrics is None


def test_arbitrary_upload_never_gets_sample_results_even_if_it_is_a_copy(matched):
    upload = matched.video.model_copy(update={"input_method": "file", "sample_key": None})
    for request in [replace(matched, task_mode="real"), replace(matched, video=upload), replace(matched, task_id="task_other"), replace(matched, media_path=None)]:
        result = SampleRecognitionAdapter().analyze(request)
        assert result.status == "failed" and result.error.code == "sample_media_mismatch"
        assert result.events == []
    result = UnconfiguredRecognitionAdapter().analyze(replace(matched, video=upload, task_mode="real"))
    assert result.status == "failed" and result.error.code == "real_analysis_not_configured"
    assert result.events == [] and result.coverage.speech == "not_analyzed"


def test_sample_hash_must_match_saved_media(matched, tmp_path):
    changed = tmp_path / "tampered.mp4"
    changed.write_bytes(Path(matched.media_path).read_bytes() + b"changed")
    result = SampleRecognitionAdapter().analyze(replace(matched, media_path=changed))
    assert result.status == "failed" and result.error.code == "sample_media_mismatch"


def test_refinement_receives_exact_feedback_and_changes_production(matched):
    brief = sample_brief(matched.task_id)
    brief.brand_company, brief.product = "Example Brand", "Custom Product"
    brief.approved_messages, brief.target_duration_seconds = ["Approved exact message"], 23
    analysis = confirmed_analysis(matched)
    adapter = SampleCreativeAdapter()
    directions = adapter.generate_directions(brief, analysis)
    assert len(directions) == 2 and directions[0].hook != directions[1].hook
    target = directions[0]
    feedback = feedback_for(target, "Make this direction presenter-free.")
    refined = adapter.refine_direction(brief, analysis, target, feedback)
    assert refined is not None
    assert refined.revision == 2 and refined.approval_status == "draft"
    assert target.revision == 1 and "presenter introduces" in target.hook
    assert refined.feedback_refs == [VersionRef(id=feedback.feedback_id, revision=1)]
    assert feedback.instruction in " ".join(refined.production_notes)
    assert "Presenter-free" in refined.narrative
    with pytest.raises(ValueError, match="approval"):
        adapter.generate_production(brief, analysis, refined)
    refined.approval_status, refined.approved_at = "approved", utc_now()
    refined.updated_at = refined.approved_at
    production, storyboard = adapter.generate_production(brief, analysis, refined)
    assert production.direction_ref == VersionRef(id=refined.direction_id, revision=2)
    assert production.feedback_refs == refined.feedback_refs
    assert "Approved exact message" in production.core_message
    assert "Custom Product" in production.title
    assert any("Presenter-free" in note for note in production.production_notes)
    assert all(row.dialogue is None for row in storyboard.rows)
    assert storyboard.rows[0].start_seconds == 0
    assert storyboard.rows[-1].end_seconds == 23 != analysis.duration_seconds
    assert all(left.end_seconds == right.start_seconds for left, right in zip(storyboard.rows, storyboard.rows[1:]))
    assert all(ref.analysis_revision == analysis.revision for row in storyboard.rows for ref in row.evidence)


def test_unsupported_feedback_is_not_claimed_interpreted_and_wrong_target_rejected(matched):
    brief, analysis = sample_brief(matched.task_id), confirmed_analysis(matched)
    adapter = SampleCreativeAdapter()
    target = adapter.generate_directions(brief, analysis)[0]
    feedback = feedback_for(target, "Do not make it presenter-free; invent a strategy")
    assert adapter.refine_direction(brief, analysis, target, feedback) is None
    assert feedback.instruction == "Do not make it presenter-free; invent a strategy"
    wrong = feedback.model_copy(update={"target_direction": VersionRef(id=target.direction_id, revision=99)})
    with pytest.raises(ValueError, match="exact direction"):
        adapter.refine_direction(brief, analysis, target, wrong)


def test_adapter_rejects_unconfirmed_mismatched_and_failed_inputs(matched):
    brief, analysis = sample_brief(matched.task_id), confirmed_analysis(matched)
    adapter = SampleCreativeAdapter()
    unconfirmed = deepcopy(analysis)
    unconfirmed.review = ReviewState()
    with pytest.raises(ValueError, match="confirmed"):
        adapter.generate_directions(brief, unconfirmed)
    partial = analysis.model_copy(update={"status": "partial"})
    with pytest.raises(ValueError, match="confirmed"):
        adapter.generate_directions(brief, partial)
    unknown_timing = analysis.model_copy(update={"frame_count": None})
    with pytest.raises(ValueError, match="frame timing"):
        adapter.generate_directions(brief, unknown_timing)
    wrong = brief.model_copy(update={"task_id": "task_other"})
    with pytest.raises(ValueError, match="same task"):
        adapter.generate_directions(wrong, analysis)
    failed = UnconfiguredRecognitionAdapter().analyze(matched)
    with pytest.raises(ValueError, match="confirmed"):
        adapter.generate_directions(brief, failed)
    direction = adapter.generate_directions(brief, analysis)[0]
    direction.approval_status, direction.approved_at = "approved", utc_now()
    direction.brief_ref = VersionRef(id=brief.brief_id, revision=99)
    with pytest.raises(ValueError, match="exact current"):
        adapter.generate_production(brief, analysis, direction)
