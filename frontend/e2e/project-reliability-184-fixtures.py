"""Synthetic UI records and real generated silent WAV originals; no provider calls."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.project_workspace.models import (  # noqa: E402
    Analysis, ContentItem, EvidenceEvent, EvidenceRevision, InputManifest, Job,
    Resource, Selection,
)
from backend.app.project_workspace.store import ProjectStore  # noqa: E402

store = ProjectStore(Path(sys.argv[1]))
project = store.create("Synthetic 1.8.4 independent reliability checks")
stamp = "2026-11-17T01:00:00+00:00"


def populate(state):
    state.workspace = "resources"
    if len(sys.argv) > 2 and sys.argv[2] == "empty":
        return
    resources = []
    for key, name in [("alpha", "Alpha partial.wav"), ("beta", "Beta partial.wav"),
                      ("gamma", "Gamma chunk.wav")]:
        relative = f"sources/media/{key}.wav"
        path = store.resolve_path(state.id, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 32000)
        chunk = key == "gamma"
        diagnostic = "provider_timeout" if key == "beta" else "audio_timestamps_invalid"
        evidence = EvidenceRevision(revision=1, created_at=stamp,
            events=[EvidenceEvent(id=f"{key}_speech_v1", kind="speech",
                text=f"Authored {key} saved text; this is not recognized speech.",
                start_seconds=0, end_seconds=2 if chunk else 1,
                precision="interval" if chunk else "estimated")],
            coverage={"speech": "complete" if chunk else "partial"},
            diagnostics={"speech_model": "gpt-transcribe" if chunk else "whisper-1",
                         "speech_timing": "chunk" if chunk else "segment",
                         **({} if chunk else {"speech": diagnostic})},
            support_details=[{"stage": "transcription_chunk", "requested_model": "gpt-transcribe" if chunk else "whisper-1",
                "cache_status": "hit", "evidence_revision": "1", "chunk_start_seconds": "0", "chunk_end_seconds": "2",
                "validation_outcome": "accepted" if chunk else "partial", "failure_code": "" if chunk else diagnostic}],
            limitations=["Authored synthetic provider records; no recognition was performed."])
        resource = Resource(id=f"resource_{key}", name=name, kind="audio", role="reference",
            folder_id="folder_inbox", original_path=relative, playback_path=relative,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), size_bytes=path.stat().st_size,
            mime_type="audio/wav", duration_seconds=2, status="ready" if chunk else "partial",
            evidence=[evidence], created_at=stamp,
            media_metadata={"playback_mapping": "identity", "playback_duration_seconds": 2})
        if key == "alpha":
            newer = evidence.model_copy(deep=True)
            newer.revision = 2
            newer.created_at = "2026-11-17T02:00:00+00:00"
            newer.events[0].id = "alpha_speech_v2"
            newer.events[0].text = "Authored newer Alpha text, not historical text."
            newer.diagnostics["speech"] = "provider_timeout"
            newer.support_details = [{"stage": "transcription_chunk", "requested_model": "whisper-1", "evidence_revision": "2", "failure_code": "provider_timeout", "validation_outcome": "partial"}]
            resource.evidence.append(newer)
        resources.append(resource)
    ids = [resource.id for resource in resources]
    target = ContentItem(id="content_target", title="Frozen report Video", selection=Selection(resource_ids=ids))
    if len(sys.argv) > 2 and sys.argv[2] == "changed_scope":
        target.selection = Selection(resource_ids=[ids[1]])
    other = ContentItem(id="content_active", title="Production selection stays here")
    state.resources = resources
    state.contents = [target, other]
    state.active_content_id = other.id
    state.selection = Selection(resource_ids=[ids[2]])
    state.editor_drafts["recognition-settings"] = {"transcription_model": "whisper-1"}
    state.analyses = [Analysis(id="saved_prior_report", content_id=target.id,
        inputs=InputManifest(resource_ids=ids, evidence_revisions={rid: 1 for rid in ids}),
        conclusion="Authored earlier report remains available.")]
    parent = Job(id="failed_summary", kind="analyze", resource_ids=ids, content_id=target.id,
        status="failed", progress="Report synthesis failed after saved source extraction",
        error="The analysis summary did not satisfy its citation contract.", error_code="invalid_analysis_citation",
        diagnostics={"stage": "completed", "failure_phase": "validating", "visual_only": "false", "validation_outcome": "rejected"},
        created_at=stamp, updated_at="2026-11-17T01:10:00+00:00")
    children = [Job(id=f"child_{key}", kind="reference_extraction", parent_job_id=parent.id,
        resource_id=resource.id, content_id=target.id, resource_ids=[resource.id],
        status="succeeded" if key == "gamma" else "partial", error=None,
        progress="Evidence ready for review" if key == "gamma" else "Partial evidence retained",
        diagnostics={"evidence_revision": "1", "speech_model": "gpt-transcribe" if key == "gamma" else "whisper-1"},
        support_details=resource.evidence[0].support_details,
        created_at=stamp, updated_at="2026-11-17T01:05:00+00:00")
        for key, resource in zip(["alpha", "beta", "gamma"], resources)]
    latest_failure = Job(id="alpha_new_auth_failure", kind="recognize", resource_id=ids[0],
        resource_ids=[ids[0]], status="failed", progress="Speech retry failed",
        error="The service rejected the API key.", error_code="provider_authentication",
        diagnostics={"stage": "transcription_chunk", "requested_speech_model": "gpt-transcribe"},
        support_details=[{"stage": "transcription_chunk", "failure_code": "provider_authentication", "validation_outcome": "rejected"}],
        created_at="2026-11-17T03:00:00+00:00", updated_at="2026-11-17T03:00:01+00:00")
    state.jobs = [parent, *children, latest_failure]
    if len(sys.argv) > 2 and sys.argv[2] == "complete_failure":
        resources[0].evidence[-1].coverage["speech"] = "complete"
        resources[0].evidence[-1].diagnostics.pop("speech", None)
        resources[0].status, resources[0].error = "ready", None
        latest_failure.error_code = "evidence_pending_changes"
        latest_failure.error = "Apply or discard the pending evidence corrections before retrying recognition. Saved evidence and your draft are retained."
        latest_failure.support_details[0]["failure_code"] = latest_failure.error_code


saved = store.update(project.id, project.version, populate)
if len(sys.argv) > 2 and sys.argv[2] == "legacy_job":
    # A genuinely omitted additive Job field, as persisted before 1.8.4.
    payload = saved.model_dump(mode="json")
    for job in payload["jobs"]:
        job.pop("resource_ids", None)
        job.pop("parent_job_id", None)
    with sqlite3.connect(store.project_dir(project.id) / "project.sqlite3") as db:
        db.execute("UPDATE project SET payload=? WHERE id=?", (json.dumps(payload), project.id))
    saved = store.get(project.id)
print(saved.model_dump_json())
