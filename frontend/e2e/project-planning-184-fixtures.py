"""Synthetic authored planning with real save/approval gates and retained 1.8.2 history.

No provider transport runs: current manifests come from PlanningService and the
structured concept-mode sheet is explicitly human-authored fixture content.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.project_workspace.models import ContentItem, Job, ProductionShot, Series  # noqa: E402
from backend.app.project_workspace.store import ProjectStore  # noqa: E402
from backend.app.project_workspace.planning import PlanningService  # noqa: E402
from backend.app.providers.config import ProviderSettings  # noqa: E402

root = Path(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) > 2 else "multiple"
spec = spec_from_file_location("release_fixture", Path(__file__).with_name("project-release-183-fixtures.py"))
module = module_from_spec(spec)
spec.loader.exec_module(module)
receipt = module.seed_legacy_project(root)
store = ProjectStore(root)
project = store.get(receipt["project"]["id"])


def seed(state):
    state.workspace = "content"
    state.series = [Series(id="series_managed", title="Commuter tests"),
                    Series(id="series_other", title="A different series")]
    state.contents[0].series_id = "series_managed"
    if mode == "concept":
        state.series[0].concept = "Synthetic shared creative context: show a commuter demonstration in one continuous observation."
    if mode == "single":
        state.contents = [state.contents[0]]
        state.contents[0].series_id = None
        state.series = []
        return
    state.contents.extend([
        ContentItem(id="content_series_second", title="A second series Video", series_id="series_managed"),
        ContentItem(id="content_pretrashed", title="Previously trashed Video", series_id="series_managed",
                    trashed_at="2026-11-17T01:00:00+00:00"),
    ])


project = store.update(project.id, project.version, seed)
# Preserve the historical legacy direction rather than declaring it current.
# A real manual save establishes the current canonical context, and the formal
# approval service independently validates it before recording approval.
service = PlanningService(store, lambda: ProviderSettings(api_key="", experiment_budget_enabled=False))
original = project.contents[0].directions[-1]
fields = {key: getattr(original, key) for key in ("title", "concept", "hook", "narrative", "cta")}
project = service.save_direction(project.id, project.version, "content_active_video", fields,
                                 direction_id=original.id, direction_revision=original.revision)
current = project.contents[0].directions[-1]
project = service.approve_direction(project.id, project.version, "content_active_video", current.id, current.revision)
assert service.direction_readiness(project.id, "content_active_video")["direction_current"]
if mode == "concept":
    project = service.create_manual_pack(project.id, project.version, "content_active_video")
    pack = project.packs[-1]
    project = service.save_pack(project.id, project.version, pack.id, pack.revision, {
        "production_brief": "Synthetic human-authored six-second commuter shoot brief.",
        "shots": [ProductionShot(id="shot_authored_concept", start_seconds=0, end_seconds=6,
            framing_camera="Static medium shot", visual="A continuous commuter demonstration.",
            dialogue="An authored line for the planned video.", on_screen_text="Commuter test",
            sound="Natural room tone", notes="Authored fixture, no provider generation.").model_dump(mode="json")],
    })
if mode == "busy":
    project = store.update(project.id, project.version, lambda state: state.jobs.append(
        Job(id="authored_running_production", kind="production", content_id="content_active_video", status="running")))
print(project.model_dump_json())
