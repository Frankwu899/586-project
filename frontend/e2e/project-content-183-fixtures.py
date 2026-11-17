"""Authored planning previews and exact evidence links; no live provider calls."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.project_workspace.models import BriefRevision, Fact  # noqa: E402
from backend.app.project_workspace.planning import PlanningService  # noqa: E402
from backend.app.project_workspace.store import ProjectStore  # noqa: E402
from backend.app.providers.config import ProviderSettings  # noqa: E402

root = Path(sys.argv[1])
mode = sys.argv[2]
store = ProjectStore(root)
if mode == "topics":
    project = store.create("Synthetic topic preview")
    project = store.update(project.id, project.version, lambda state: state.briefs.append(
        BriefRevision(revision=1, facts=[Fact(key="assignment", value="A commuter introduction.", origin="manual", status="confirmed")])) )

    class AuthoredTransport:
        def json_response(self, **_kwargs):
            return {"series": [], "standalone": [{"title": "A commuter topic", "description": "An authored topic preview."}],
                    "used_claim_ids": [], "claim_uses": []}

    service = PlanningService(store, lambda: ProviderSettings(api_key="offline-fixture-only", creative_model="gpt-6.1-sol", experiment_budget_enabled=False), lambda _: AuthoredTransport())
    print(service.suggest_topics(project.id).model_dump_json())
else:
    spec = spec_from_file_location("release_fixture", Path(__file__).with_name("project-release-183-fixtures.py"))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt = module.seed_legacy_project(root)
    project = store.get(receipt["project"]["id"])
    source = receipt["latest_source"]

    def seed(state):
        state.workspace = "content"
        state.active_content_id = "content_browsed_video"
        if mode == "inspiration":
            state.resources[0].evidence[-1].reviewed = False
            state.editor_drafts["content-inspiration"] = {
                "analysis_id": "synthetic_current_analysis", "insight_id": "synthetic_insight",
                "observation": "A useful observed mechanism.", "application": "Use a simple commuter demonstration.", "sources": [source]}
            state.editor_drafts["manual-direction-content_browsed_video"] = {
                "title": "", "concept": "Existing manual concept.", "hook": "", "narrative": "", "cta": "", "source_refs": []}
    print(store.update(project.id, project.version, seed).model_dump_json())
