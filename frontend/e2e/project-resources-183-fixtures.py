"""Real local video preparation plus authored evidence; never live inference."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.project_workspace.models import (  # noqa: E402
    Analysis, AnalysisInsight, ContentItem, EvidenceEvent, EvidenceRevision,
    InputManifest, Job, ReferenceStructure, SourceRef, StructureNode,
)
from backend.app.project_workspace.resources import ResourceService  # noqa: E402
from backend.app.project_workspace.store import ProjectStore  # noqa: E402

store = ProjectStore(Path(sys.argv[1]))
service = ResourceService(store)
project = store.create("Synthetic 1.8.3 Media Pool")
for name in ["commute-demo.mp4", "desk-routine.mp4"]:
    with Path(sys.argv[2]).open("rb") as media:
        project = service.import_file(project.id, project.version, name, media, folder_id="folder_references")
    project = service.extract(project.id, project.resources[-1].id)


def seed(state):
    for index, resource in enumerate(state.resources):
        resource.evidence = [
            EvidenceRevision(revision=1, reviewed=True, coverage={"visual": "sampled", "speech": "partial"}, events=[
                EvidenceEvent(id=f"visual_{index}", kind="visual", text=f"Historical observation {index}", start_seconds=2, end_seconds=2.04, precision="sample"),
                EvidenceEvent(id=f"speech_{index}", kind="speech", text=f"Historical saved speech {index}", start_seconds=3, end_seconds=4, precision="estimated"),
            ]),
            EvidenceRevision(revision=2, reviewed=True, coverage={"visual": "sampled", "speech": "complete"}, events=[
                EvidenceEvent(id=f"visual_{index}", kind="visual", text=f"Current corrected observation {index}", start_seconds=5, end_seconds=5.04, precision="sample"),
                EvidenceEvent(id=f"speech_{index}", kind="speech", text=f"Current corrected speech {index}", start_seconds=6, end_seconds=7, precision="estimated"),
            ]),
        ]
    state.contents = [ContentItem(title="Keep this planned Video selected")]
    state.active_content_id = state.contents[0].id
    resource = state.resources[0]
    source = SourceRef(resource_id=resource.id, evidence_revision=1, event_id="visual_0", start_seconds=2, end_seconds=2.04, excerpt="Historical observation 0", locator="Recorded sample")
    mode = sys.argv[3] if len(sys.argv) > 3 else "valid"
    if mode == "missing_revision":
        source.evidence_revision = 99
    elif mode == "missing_event":
        source.event_id = "unavailable_event"
    elif mode == "conflicting_time":
        source.start_seconds, source.end_seconds = 5, 5.04
    elif mode == "outside_time":
        source.start_seconds, source.end_seconds = 99, 100
    elif mode == "source_only":
        source.evidence_revision, source.event_id = None, None
    elif mode == "playback_failure":
        resource.evidence[-1].coverage["speech"] = "partial"
        resource.evidence[-1].diagnostics["speech"] = "audio_timestamps_invalid"
    elif mode.startswith("speech_failure:"):
        resource.evidence[-1].coverage["speech"] = "partial"
        resource.evidence[-1].created_at = "2026-11-17T00:00:00+00:00"
        resource.evidence[-1].limitations = ["Earlier transcript coverage is incomplete; its completed observations are retained."]
        resource.error = "Earlier transcript coverage is incomplete; its completed observations are retained."
        state.jobs.append(Job(resource_id=resource.id, kind="recognize", status="failed",
            error="The latest speech retry failed.", error_code=mode.split(":", 1)[1],
            created_at="2026-11-17T00:01:00+00:00", updated_at="2026-11-17T00:02:00+00:00"))
    state.analyses = [Analysis(inputs=InputManifest(resource_ids=[item.id for item in state.resources], evidence_revisions={item.id: 1 for item in state.resources}),
        conclusion="Historical report context retained once.", findings=["An unlinked legacy finding."], differences=["The two references show different proof contexts."],
        key_insights=[AnalysisInsight(id="insight_test", observation="Show the evidence before explaining.", application="Open with a visible demonstration.", sources=[source])], sources=[source],
        structures=[ReferenceStructure(resource_id=resource.id, summary="Recorded structure interpretation", nodes=[StructureNode(id="node_test", label="Make the test visible", detail="A saved interpretation of this exact sample.", sources=[source])])])]


print(store.update(project.id, project.version, seed).model_dump_json())
