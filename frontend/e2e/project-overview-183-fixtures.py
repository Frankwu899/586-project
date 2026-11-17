"""Persist a real pending attempt; no provider or worker is started."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.project_workspace.conversation import ConversationService  # noqa: E402
from backend.app.project_workspace.models import Job  # noqa: E402
from backend.app.project_workspace.store import ProjectStore  # noqa: E402

store = ProjectStore(Path(sys.argv[1]))
project = store.create("Synthetic 1.8.3 " + sys.argv[2])
service = ConversationService(store, lambda: None)
project, message_id = service.begin_message(project.id, project.version, "Keep this saved message when I stop.")
attempt = project.editor_drafts["conversation_requests"][message_id]["attempt_id"]


def seed(state):
    state.jobs.append(Job(kind="conversation", status=sys.argv[2], message_id=message_id, attempt_id=attempt))


print(store.update(project.id, project.version, seed).model_dump_json())
