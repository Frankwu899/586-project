"""Complete a synthetic local background job without model requests."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.project_workspace.models import Job, Resource  # noqa: E402
from backend.app.project_workspace.store import ProjectStore  # noqa: E402

store = ProjectStore(Path(sys.argv[1]))
if sys.argv[2] == "seed":
    project = store.create("Synthetic selection race")
    def seed(state):
        state.resources.append(Resource(id="video_185", name="synthetic-reference.mp4", kind="video", original_path="sources/synthetic.mp4", sha256="a" * 64, size_bytes=0, status="ready", duration_seconds=10))
    print(store.update(project.id, None, seed).model_dump_json())
    raise SystemExit
project = store.get(sys.argv[2])

def complete(state):
    state.jobs.append(Job(kind="analyze", status="succeeded", progress="Synthetic background completion"))

print(store.update(project.id, None, complete).model_dump_json())
