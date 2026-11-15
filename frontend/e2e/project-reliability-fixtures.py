"""Persisted UI fixtures, never live-provider or transcription-quality evidence."""
import hashlib
from pathlib import Path
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.project_workspace.models import (  # noqa: E402
    EvidenceEvent, EvidenceRevision, Fact, Job, Message, Resource,
)
from backend.app.project_workspace.store import ProjectStore  # noqa: E402

store = ProjectStore(Path(sys.argv[1]))
mode = sys.argv[2]
if mode == "restart":
    # Constructing the store runs the same interruption recovery as app startup.
    print(store.get(sys.argv[3]).model_dump_json())
    raise SystemExit
project = store.create("Synthetic 1.8.2 " + mode)


def populate(state):
    if mode == "pending":
        user = Message(role="user", text="Keep my saved draft while assistance is pending.")
        state.messages = [user]
        state.jobs = [Job(kind="conversation", status="running", message_id=user.id)]
        state.editor_drafts["conversation_requests"] = {user.id: {"fingerprint": "synthetic"}}
    elif mode == "partial":
        user = Message(role="user", text="WellPath brings wellness information together. Awareness or sign-ups? No clinical benefits have been established. 健康信息集中展示。")
        state.messages = [user, Message(role="assistant", reply_to_message_id=user.id,
            text="I recommend choosing one primary outcome. Awareness builds familiarity; sign-ups ask for an immediate action. Which outcome matters most for this launch? Some information could not be added to the brief. The valid suggestions are available for review.",
            diagnostics={"application_version": "1.8.2", "source_commit": "synthetic", "outcome": "partial", "validation_rule": "source_mismatch", "validation_field": "proposals[1].excerpt", "rejected_proposals": "1"})]
        state.brief_draft = [Fact(key="objective", value="Awareness or sign-ups?", status="unresolved", origin="conversation"), Fact(key="prohibited_claim", value="No clinical benefits have been established.", status="suggested", origin="conversation", sources=[{"message_id": user.id, "locator": "Conversation message", "excerpt": "No clinical benefits have been established."}])]
        state.brief_draft.extend([
            Fact(key="benefit", value="WellPath brings wellness information together.", sources=[{"message_id": user.id, "locator": "Conversation message", "excerpt": "WellPath brings wellness information together."}]),
            Fact(key="产品优势", value="健康信息集中展示。", sources=[{"message_id": user.id, "locator": "Conversation message", "excerpt": "健康信息集中展示。"}]),
        ])
    elif mode == "speech":
        resource = Resource(name="Synthetic silent audio.wav", kind="audio", original_path="sources/media/synthetic.wav", sha256="0" * 64, size_bytes=64044, mime_type="audio/wav", duration_seconds=2, status="partial")
        path = store.resolve_path(state.id, resource.original_path)
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 32000)
        resource.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        resource.size_bytes = path.stat().st_size
        resource.playback_path = resource.original_path
        resource.evidence = [EvidenceRevision(revision=2,
            events=[EvidenceEvent(id="speech_saved", kind="speech", text="User-corrected original-language wording 中文.", start_seconds=0, end_seconds=0.8)],
            coverage={"speech": "partial"}, diagnostics={"speech": "audio_timestamps_invalid"},
            correction_note="Authored correction fixture", support_details=[
                {"stage": "transcription_chunk", "cache_status": "hit", "requested_model": "whisper-1", "chunk_start_seconds": "0", "chunk_end_seconds": "1", "validation_outcome": "valid"},
                {"stage": "transcription_chunk", "cache_status": "miss", "requested_model": "whisper-1", "chunk_start_seconds": "1", "chunk_end_seconds": "2", "validation_outcome": "partial", "failure_code": "audio_timestamps_invalid"}],
            limitations=["Authored fixture: no real recognition was performed."])]
        state.resources = [resource]
        state.workspace = "resources"


print(store.update(project.id, project.version, populate).model_dump_json())
