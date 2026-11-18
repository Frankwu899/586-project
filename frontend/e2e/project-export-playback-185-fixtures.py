"""Authored export/playback fixtures with real local media, never model output."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.project_workspace.models import (  # noqa: E402
    ContentItem, EvidenceEvent, EvidenceRevision, InputManifest, ProductionPack, ProductionShot, SourceRef,
)
from backend.app.project_workspace.resources import ResourceService  # noqa: E402
from backend.app.project_workspace.store import ProjectStore  # noqa: E402

store = ProjectStore(Path(sys.argv[1]))
project = store.create("Synthetic 1.8.5 export/playback acceptance")
if sys.argv[2] == "playback":
    service = ResourceService(store)
    with Path(sys.argv[3]).open("rb") as stream:
        project = service.import_file(project.id, project.version, "cache-recovery.mov", stream)
    project = service.extract(project.id, project.resources[0].id)


def seed(state):
    state.contents = [ContentItem(id="content_export", title="Synthetic output")]
    state.active_content_id = state.contents[0].id
    if sys.argv[2] == "playback":
        state.resources[0].evidence = [
            EvidenceRevision(revision=1, reviewed=True, events=[EvidenceEvent(
                id="historical_sample", kind="visual", text="Historical blue sample", start_seconds=2, end_seconds=2.1, precision="sample")]),
            EvidenceRevision(revision=2, reviewed=True, events=[EvidenceEvent(
                id="current_sample", kind="visual", text="Current blue sample", start_seconds=5, end_seconds=5.1, precision="sample")]),
        ]
        return
    source = SourceRef(resource_id="source_a", event_id="event_original", evidence_revision=3,
                       start_seconds=1.25, end_seconds=2.5, excerpt="Original evidence <card>")
    shots = [ProductionShot(id=f"shot_{i:02d}", start_seconds=i - 1, end_seconds=i,
                           framing_camera="Static close-up", visual=f"Marker{i:02d}\n第一行\n第二行 | literal <card>",
                           dialogue="Proposed narration.\nKeep the necessary qualifier.",
                           on_screen_text="<script>window.badExport=true</script>",
                           sound="New creative music suggestion", notes="Saved row notes.\nProduction is an estimate.", sources=[source])
             for i in range(1, 37)]
    first = ProductionPack(id="pack_print", revision=1, content_id="content_export", inputs=InputManifest(),
                           production_brief="Authored synthetic r1; no generated-quality claim.",
                           script="obsolete mirrored script", storyboard="obsolete mirrored storyboard", shot_list="obsolete mirrored list",
                           sheet_format="storyboard_sheet", shots=shots)
    second = first.model_copy(deep=True, update={"revision": 2})
    second.shots[0].dialogue = "Human-edited r2 is not evidence of r1 generation quality."
    state.packs = [first, second]


project = store.update(project.id, project.version, seed)
if sys.argv[2] == "playback":
    service.path(project.id, project.resources[0].id, "playback").write_bytes(b"synthetic corrupt cache")
print(project.model_dump_json())
