"""Synthetic 1.8.2 records and real local bytes for cross-module regression.

The payload intentionally omits every added 1.8.3 field. Evidence and creative
text are authored fixtures, not provider output or model-quality evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.project_workspace.models import (  # noqa: E402
    Analysis, BriefRevision, ContentItem, Direction, EvidenceEvent,
    EvidenceRevision, ExtractedBlock, Fact, InputManifest, Message,
    ProductionPack, ReferenceStructure, Resource, Selection, SourceRef,
    StructureNode,
)
from backend.app.project_workspace.store import ProjectStore  # noqa: E402


def seed_legacy_project(root: Path, mode: str = "seed") -> dict:
    store = ProjectStore(root)
    project = store.create("Synthetic 1.8.2 integration history")
    directory = store.project_dir(project.id)
    media = directory / "sources/media/legacy-reference.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        "color=c=blue:s=160x90:r=24:d=6", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", str(media),
    ], check=True)
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(media),
    ], text=True))
    duration = float(probe["format"]["duration"])
    digest = hashlib.sha256(media.read_bytes()).hexdigest()
    notes = directory / "sources/documents/legacy-notes.txt"
    notes.write_text("Saved source notes. No performance claim is established.\n")

    old_source = SourceRef(resource_id="resource_legacy_reference",
        evidence_revision=1, event_id="visual_old", locator="Historical observation",
        excerpt="Original observation at one second.", start_seconds=1, end_seconds=1)
    latest_source = SourceRef(resource_id="resource_legacy_reference",
        evidence_revision=2, event_id="visual_corrected", locator="Corrected observation",
        excerpt="Human-corrected observation at three seconds.", start_seconds=3, end_seconds=3)
    user = Message(role="user", text="Prepare a six-second commuter introduction.")
    facts = [Fact(id=f"fact_legacy_{key}", key=key, value=value,
                  origin="manual", status="confirmed") for key, value in [
        ("objective", "A commuter introduction"), ("audience", "Commuters"),
        ("platform", "Instagram"), ("duration", "6 seconds"),
    ]]
    reference = Resource(id="resource_legacy_reference", name="Legacy reference.mp4",
        kind="video", role="reference", origin="legacy", original_path=str(media.relative_to(directory)),
        playback_path=str(media.relative_to(directory)), sha256=digest,
        size_bytes=media.stat().st_size, mime_type="video/mp4", status="ready",
        duration_seconds=duration, thumbnail_path=None, evidence=[
            EvidenceRevision(revision=1, reviewed=True, processor="authored-fixture",
                events=[EvidenceEvent(id="visual_old", kind="visual", text=old_source.excerpt,
                                      start_seconds=1, end_seconds=1)],
                coverage={"visual": "complete", "speech": "no_audio"}),
            EvidenceRevision(revision=2, reviewed=True, processor="authored-fixture",
                correction_note="Saved human correction",
                events=[EvidenceEvent(id="visual_corrected", kind="visual", text=latest_source.excerpt,
                                      start_seconds=3, end_seconds=3)],
                coverage={"visual": "complete", "speech": "no_audio"}),
        ])
    document = Resource(id="resource_legacy_document", name="Legacy notes.txt",
        kind="document", role="document", origin="legacy",
        original_path=str(notes.relative_to(directory)),
        sha256=hashlib.sha256(notes.read_bytes()).hexdigest(), size_bytes=notes.stat().st_size,
        mime_type="text/plain", status="ready", blocks=[
            ExtractedBlock(id="block_legacy", locator="Line 1", text=notes.read_text().strip()),
        ])
    manifest = InputManifest(brief_revision=1, resource_ids=[reference.id],
        evidence_revisions={reference.id: 2})
    direction = Direction(id="direction_legacy", revision=1, title="The saved direction",
        concept="Show a six-second commuter introduction.", approved=True,
        inputs=manifest.model_copy(deep=True), sources=[latest_source])
    active = ContentItem(id="content_active_video", title="The planned Video",
        selection=Selection(resource_ids=[reference.id]), directions=[direction],
        approved_direction_id=direction.id, approved_direction_revision=1)
    other = ContentItem(id="content_browsed_video", title="Another planned Video")
    pack = ProductionPack(id="pack_legacy_text", content_id=active.id,
        inputs=InputManifest(**{**manifest.model_dump(), "direction_id": direction.id,
                               "direction_revision": 1}),
        production_brief="A saved short production brief.", script="Saved script from 1.8.2.",
        storyboard="Hand-edited free-text storyboard. No synchronized shot rows exist.",
        shot_list="Hand-edited old shot list.", shots=[], sources=[old_source])
    report = Analysis(id="analysis_legacy_source", content_id=other.id,
        inputs=InputManifest(resource_ids=[reference.id], evidence_revisions={reference.id: 1}),
        conclusion="An authored historical analysis, retained without recomputation.",
        findings=["The original observation remains available in its own revision."],
        opportunities=["Review the old source before reusing this interpretation."],
        sources=[old_source], structures=[ReferenceStructure(resource_id=reference.id,
            summary="A historical source structure.", nodes=[StructureNode(id="historical_node",
                label="Historical observation", detail="The report used evidence revision one.",
                kind="observation", sources=[old_source])])])

    def populate(state):
        state.messages = [user]
        state.briefs = [BriefRevision(revision=1, facts=facts)]
        state.brief_draft = [fact.model_copy(deep=True) for fact in facts]
        state.resources = [reference, document]
        state.contents = [active, other]
        state.active_content_id = active.id
        state.selection = Selection(resource_ids=[reference.id])
        state.analyses = [report]
        state.packs = [pack]
        state.workspace = "resources"

    saved = store.update(project.id, project.version, populate)
    payload = saved.model_dump(mode="json")
    payload.pop("resource_folders", None)
    payload.pop("topic_suggestions", None)
    for resource in payload["resources"]:
        resource.pop("folder_id", None)
        resource.pop("trashed_at", None)
        for revision in resource["evidence"]:
            for event in revision["events"]:
                event.pop("precision", None)
    for message in payload["messages"]:
        message.pop("attempt_id", None)
    for analysis in payload["analyses"]:
        analysis.pop("key_insights", None)
    for production in payload["packs"]:
        production.pop("sheet_format", None)
        for shot in production["shots"]:
            shot.pop("framing_camera", None)
    if mode in {"missing_revision", "mismatched_time", "unversioned_time"}:
        report = payload["analyses"][0]
        citations = [*report["sources"], *report["structures"][0]["nodes"][0]["sources"]]
        for citation in citations:
            if mode == "missing_revision":
                citation["evidence_revision"] = 99
            elif mode == "unversioned_time":
                citation["evidence_revision"], citation["event_id"] = None, None
            else:
                # The real historical event is at one second, not five.
                citation["start_seconds"], citation["end_seconds"] = 5, 5
    with sqlite3.connect(directory / "project.sqlite3") as db:
        db.execute("UPDATE project SET payload=? WHERE id=?", (json.dumps(payload), saved.id))
    return {"project": payload, "media_sha256": digest,
            "old_source": old_source.model_dump(mode="json"),
            "latest_source": latest_source.model_dump(mode="json")}


if __name__ == "__main__":
    print(json.dumps(seed_legacy_project(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "seed"), ensure_ascii=False))
