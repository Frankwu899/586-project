"""Real bounded local imports; no model request or large in-memory payload."""
from dataclasses import replace

import pytest

from backend.app.media import MediaSettings
from backend.app.project_workspace.resources import ResourceService
from backend.app.project_workspace.store import ProjectStore
from backend.app.storage import WorkflowError


class RepeatingStream:
    def __init__(self, total):
        self.remaining = total
        self.chunk = b"x" * (1024 * 1024)

    def read(self, size):
        count = min(size, self.remaining)
        self.remaining -= count
        return self.chunk[:count]


def test_streamed_original_above_the_previous_50_mib_limit_is_saved(tmp_path, monkeypatch):
    monkeypatch.delenv("VIDEO_MAX_BYTES", raising=False)
    store = ProjectStore(tmp_path)
    service = ResourceService(store)
    project = store.create("Larger local originals")
    size = 51 * 1024 * 1024
    saved = service.import_file(project.id, project.version, "larger-original.mp4", RepeatingStream(size))
    resource = saved.resources[0]
    original = store.resolve_path(saved.id, resource.original_path)
    assert service.media_settings.max_bytes == 500 * 1024 * 1024
    assert original.stat().st_size == resource.size_bytes == size
    assert resource.status == "stored"
    assert saved.jobs == [] and resource.evidence == []
    # This is a byte-stream/import test, not proof that these synthetic bytes
    # decode as MP4 or that a 500 MiB video has been analyzed.


def test_configured_limit_still_rejects_without_leaving_an_original(tmp_path):
    store = ProjectStore(tmp_path)
    service = ResourceService(store)
    service.media_settings = replace(MediaSettings(), max_bytes=1024)
    project = store.create("Bounded import")
    with pytest.raises(WorkflowError) as error:
        service.import_file(project.id, project.version, "oversized.mp4", RepeatingStream(1025))
    assert error.value.code == "resource_too_large"
    assert store.get(project.id).resources == []
    assert not list(store.project_dir(project.id).rglob("*.part"))
    assert not list(store.project_dir(project.id).rglob("oversized.mp4"))


def test_existing_explicit_file_limit_remains_configurable(monkeypatch):
    monkeypatch.setenv("VIDEO_MAX_BYTES", "104857600")
    settings = MediaSettings.from_env()
    assert settings.max_bytes == 100 * 1024 * 1024
    assert settings.max_duration_seconds == 180
    assert (settings.max_width, settings.max_height) == (1920, 1920)
