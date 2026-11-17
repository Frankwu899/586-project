"""HTTP source adoption preserves exact provenance and omitted-field semantics."""
import hashlib

from fastapi.testclient import TestClient

from backend.app.api import create_app
from backend.app.project_workspace.models import EvidenceEvent, EvidenceRevision, Resource


def test_direction_source_request_wrappers_adopt_preserve_and_explicitly_clear(tmp_path):
    app = create_app(tmp_path)
    runtime = app.state.project_workspace
    project = runtime.store.create("Explicit inspiration fixture")
    content = b"Synthetic original; this test does not decode or send media."
    original = runtime.store.project_dir(project.id) / "sources/media/reference.mp4"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(content)
    resource = Resource(id="resource_inspiration_api", name="Reference.mp4", kind="video", status="ready",
        original_path="sources/media/reference.mp4", sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content),
        duration_seconds=4, evidence=[EvidenceRevision(revision=1, events=[EvidenceEvent(
            id="event_inspiration_api", kind="visual", text="A bag opens before the product appears", start_seconds=1,
            end_seconds=2, precision="sample")])])
    project = runtime.store.update(project.id, project.version, lambda state: state.resources.append(resource))
    with TestClient(app) as client:
        base = "/api/projects/" + project.id
        def post(path, body, *, expected=200):
            current = client.get(base).json()
            response = client.post(base + path, json={"expected_version": current["version"], **body})
            assert response.status_code == expected, response.text
            return response.json()
        post("/brief/apply", {"facts": [{"id": "fact_goal", "key": "goal", "value": "Explain a new opening mechanism",
                                          "origin": "manual", "status": "confirmed"}]})
        created = post("/contents", {"title": "An inspired standalone video"})
        video_id = created["contents"][-1]["id"]
        assert created["contents"][-1]["selection"]["resource_ids"] == []
        ref = {"resource_id": resource.id, "evidence_revision": 1, "event_id": "event_inspiration_api",
               "start_seconds": 1, "end_seconds": 2, "excerpt": "User's noncanonical label", "locator": "An insight"}
        saved = post(f"/contents/{video_id}/directions", {"title": "Bag-first reveal", "concept": "Adapt the reveal mechanism.",
                                                         "source_refs": [ref]})
        video = saved["contents"][-1]
        direction = video["directions"][-1]
        assert video["selection"]["resource_ids"] == [resource.id]
        assert direction["sources"][0]["excerpt"] == resource.evidence[0].events[0].text
        assert direction["sources"][0]["evidence_revision"] == 1
        assert direction["sources"][0]["start_seconds"] == 1 and direction["sources"][0]["end_seconds"] == 2
        assert not saved["resources"][0]["evidence"][0]["reviewed"] and not saved["jobs"]
        route = f"/contents/{video_id}/directions/{direction['id']}"
        rejected = post(route + "/approve", {"revision": 1}, expected=422)
        assert rejected["error"]["code"] == "reference_review_required"
        # Omission is a text-only edit, so it cannot accidentally clear adopted provenance.
        edited = post(route + "/edit", {"revision": 1, "fields": {"concept": "Use a quiet bag-first reveal."}})
        latest = edited["contents"][-1]["directions"][-1]
        assert latest["revision"] == 2 and latest["sources"] == direction["sources"]
        nullable = post(route + "/edit", {"revision": 2, "fields": {"hook": "A quiet bag opening"}, "source_refs": None})
        current = nullable["contents"][-1]["directions"][-1]
        assert current["sources"] == direction["sources"]
        explicit = post(route + "/edit", {"revision": current["revision"], "fields": {"concept": latest["concept"]}, "source_refs": []})
        assert explicit["contents"][-1]["directions"][-1]["sources"] == []
        assert explicit["contents"][-1]["directions"][0]["sources"] == direction["sources"]
        assert original.read_bytes() == content


def test_direction_original_and_foreign_source_requests_do_not_auto_adopt(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"title": "Original concept fixture"}).json()
        base = "/api/projects/" + project["id"]
        created = client.post(base + "/contents", json={"expected_version": project["version"], "title": "Original video"}).json()
        video_id = created["contents"][-1]["id"]
        route = base + f"/contents/{video_id}/directions"
        original = client.post(route, json={"expected_version": created["version"], "title": "Original direction",
                                            "concept": "Film a new demonstration."})
        assert original.status_code == 200, original.text
        saved = original.json()
        assert saved["contents"][-1]["directions"][-1]["sources"] == []
        foreign = client.post(route, json={"expected_version": saved["version"], "title": "Invalid source direction",
            "concept": "Must not be saved", "source_refs": [{"resource_id": "resource_foreign", "evidence_revision": 1,
                                                               "event_id": "foreign", "start_seconds": 0, "end_seconds": 1}]})
        assert foreign.status_code == 422, foreign.text
        assert client.get(base).json() == saved
