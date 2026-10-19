from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import plistlib
import sys
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

import pytest

from scripts import mac_launcher as launcher
from scripts.mac_app_bundle import bundle_entries, package_fingerprint
from scripts.mac_keychain import KeychainError, MacKeychain, NOT_FOUND


def record(data_dir: Path, root: Path) -> dict:
    return {"url": "http://127.0.0.1:8201", "instance_id": "i" * 64,
            "control_token": "c" * 64, "pid": 12345, "data_dir": str(data_dir.resolve()),
            "package_root": str(root.resolve()), "package_fingerprint": package_fingerprint(root),
            "launcher_protocol": 1}


def test_native_keychain_reads_and_releases_allocated_data():
    secret = ctypes.create_string_buffer(b"sk-test-only")
    data = ctypes.cast(secret, ctypes.c_void_p)
    released = []
    keychain = MacKeychain.__new__(MacKeychain)
    keychain._find = lambda **_: (0, ctypes.c_uint32(12), data, ctypes.c_void_p(4))
    keychain.security = SimpleNamespace(SecKeychainItemFreeContent=lambda _, pointer: released.append("data"))
    keychain.core = SimpleNamespace(CFRelease=lambda pointer: released.append("item"))
    assert keychain.get() == "sk-test-only"
    assert released == ["data", "item"]


def test_native_keychain_updates_existing_item_without_command_arguments():
    calls = []
    keychain = MacKeychain.__new__(MacKeychain)
    keychain._find = lambda **_: (0, None, None, ctypes.c_void_p(8))
    keychain.security = SimpleNamespace(SecKeychainItemModifyAttributesAndData=lambda *args: calls.append(args) or 0)
    keychain.core = SimpleNamespace(CFRelease=lambda _: None)
    keychain.set("sk-replacement")
    assert calls[0][2:] == (14, b"sk-replacement")


def test_native_keychain_missing_and_denied_are_distinct():
    keychain = MacKeychain.__new__(MacKeychain)
    keychain._find = lambda **_: (NOT_FOUND, None, None, None)
    assert keychain.get() is None
    keychain.delete()
    keychain._find = lambda **_: (-25293, None, None, None)
    with pytest.raises(KeychainError, match="Unlock the login Keychain"):
        keychain.get()
    with pytest.raises(KeychainError, match="without spaces"):
        keychain.set("sk-invalid\nkey")


@pytest.mark.parametrize("url", ["https://127.0.0.1:8000", "http://localhost:8000", "http://example.com:8000",
                                  "http://127.0.0.1:0", "http://127.0.0.1:8000/next", "http://user@127.0.0.1:8000",
                                  "http://127.0.0.1:8000#secret", "http://127.0.0.1:bad"])
def test_discovery_rejects_external_or_ambiguous_addresses(url):
    assert not launcher.local_url(url)


def test_discovery_record_is_private_and_cannot_change_library(tmp_path):
    saved = record(tmp_path / "library", tmp_path / "app")
    target = tmp_path / "instance.json"
    launcher.save_record(target, saved)
    assert target.stat().st_mode & 0o777 == 0o600
    assert launcher.read_record(target, tmp_path / "library") == saved
    assert launcher.read_record(target, tmp_path / "another-library") is None
    target.unlink()
    target.symlink_to(tmp_path / "real.json")
    assert launcher.read_record(target, tmp_path / "library") is None


def test_reused_port_with_wrong_identity_is_not_trusted(tmp_path, monkeypatch):
    saved = record(tmp_path, tmp_path)
    response = {**saved, "instance_id": "another-process"}
    monkeypatch.setattr(launcher, "request_json", lambda _: response)
    assert not launcher.verified_instance(saved)
    response["instance_id"] = saved["instance_id"]
    assert launcher.verified_instance(saved)


def test_startup_lock_prevents_duplicate_start(tmp_path):
    with launcher.launch_lock(tmp_path):
        with pytest.raises(launcher.LauncherBusy):
            with launcher.launch_lock(tmp_path):
                pytest.fail("duplicate launcher acquired the startup lock")


def test_reopen_reuses_verified_server_without_setup_or_key_prompt(tmp_path, monkeypatch):
    library, root, cache = tmp_path / "library", tmp_path / "app", tmp_path / "cache"
    cache.mkdir()
    saved = record(library, root)
    launcher.save_record(cache / "launcher-instance.json", saved)
    monkeypatch.setattr(launcher, "default_data_dir", lambda: library)
    monkeypatch.setattr(launcher, "default_cache_dir", lambda: cache)
    monkeypatch.setattr(launcher, "verified_instance", lambda value: value == saved)
    monkeypatch.setattr(launcher, "prepare_runtime", lambda *_: pytest.fail("must not prepare runtime again"))
    opened = []
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda args, **_: opened.append(args))
    assert launcher.launch(root) == saved["url"]
    assert opened == [["/usr/bin/open", saved["url"]]]


def test_new_package_safely_stops_previous_verified_version_then_starts(tmp_path, monkeypatch):
    library, root, cache = tmp_path / "library", tmp_path / "new-app", tmp_path / "cache"
    cache.mkdir()
    previous, fresh = record(library, tmp_path / "old-app"), record(library, root)
    launcher.save_record(cache / "launcher-instance.json", previous)
    monkeypatch.setattr(launcher, "default_data_dir", lambda: library)
    monkeypatch.setattr(launcher, "default_cache_dir", lambda: cache)
    monkeypatch.setattr(launcher, "verified_instance", lambda _: True)
    events = []
    monkeypatch.setattr(launcher, "stop_instance", lambda value: events.append(("stop", value)))
    monkeypatch.setattr(launcher, "prepare_runtime", lambda *_: Path("/python"))
    monkeypatch.setattr(launcher, "start_server", lambda *_: events.append(("start", fresh)) or fresh)
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *_, **__: None)
    launcher.launch(root)
    assert events == [("stop", previous), ("start", fresh)]
    assert launcher.read_record(cache / "launcher-instance.json", library) == fresh


def test_same_path_replacement_restarts_backend_instead_of_mixing_versions(tmp_path, monkeypatch):
    library, root, cache = tmp_path / "library", tmp_path / "installed-app", tmp_path / "cache"
    cache.mkdir()
    root.mkdir()
    manifest = root / "PACKAGE_MANIFEST.json"
    manifest.write_text('{"version":"old"}')
    previous = record(library, root)
    launcher.save_record(cache / "launcher-instance.json", previous)
    manifest.write_text('{"version":"new"}')
    fresh = record(library, root)
    assert fresh["package_fingerprint"] != previous["package_fingerprint"]
    monkeypatch.setattr(launcher, "default_data_dir", lambda: library)
    monkeypatch.setattr(launcher, "default_cache_dir", lambda: cache)
    monkeypatch.setattr(launcher, "verified_instance", lambda _: True)
    events = []
    monkeypatch.setattr(launcher, "stop_instance", lambda value: events.append(("stop", value)))
    monkeypatch.setattr(launcher, "prepare_runtime", lambda *_: Path("/python"))
    monkeypatch.setattr(launcher, "start_server", lambda *_: events.append(("start", fresh)) or fresh)
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *_, **__: None)
    launcher.launch(root)
    assert events == [("stop", previous), ("start", fresh)]


def test_development_fingerprint_tracks_source_but_excludes_private_runtime(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    source = backend / "app.py"
    source.write_text("version = 1\n")
    original = package_fingerprint(tmp_path)
    (tmp_path / ".env").write_text("private runtime settings")
    (tmp_path / "tasks.sqlite3").touch()
    assert package_fingerprint(tmp_path) == original
    source.write_text("version = 2\n")
    assert package_fingerprint(tmp_path) != original


def test_stop_refuses_unverified_server_and_busy_work(tmp_path, monkeypatch):
    saved = record(tmp_path, tmp_path)
    monkeypatch.setattr(launcher, "verified_instance", lambda _: False)
    monkeypatch.setattr(launcher, "request_json", lambda *_, **__: pytest.fail("must not stop unverified server"))
    with pytest.raises(launcher.LauncherError, match="No process was stopped"):
        launcher.stop_instance(saved)
    monkeypatch.setattr(launcher, "verified_instance", lambda _: True)
    def busy(*_, **__):
        raise HTTPError(saved["url"], 409, "busy", {}, None)
    monkeypatch.setattr(launcher, "request_json", busy)
    with pytest.raises(launcher.LauncherError, match="still processing work"):
        launcher.stop_instance(saved)


def test_background_environment_does_not_inherit_old_credentials_or_library(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-do-not-inherit")
    monkeypatch.setenv("VIDEO_ANATOMY_DATA_DIR", "/old-library")
    monkeypatch.setenv("PYTHONPATH", "/old-python")
    result = launcher.clean_environment()
    assert "OPENAI_API_KEY" not in result
    assert "VIDEO_ANATOMY_DATA_DIR" not in result
    assert "PYTHONPATH" not in result
    assert os.environ["OPENAI_API_KEY"] == "sk-do-not-inherit"


def test_shared_runtime_reuses_successful_dependency_install(tmp_path, monkeypatch):
    root, cache = tmp_path / "app", tmp_path / "cache"
    root.mkdir()
    (root / "requirements.lock").write_text("example==1.0\n")
    digest = launcher.hashlib.sha256((root / "requirements.lock").read_bytes()).hexdigest()
    runtime = cache / "runtime" / digest
    (runtime / "bin").mkdir(parents=True)
    (runtime / "bin" / "python").touch()
    (runtime / "ready.sha256").write_text(digest)
    monkeypatch.setattr(launcher.shutil, "which", lambda *_, **__: "/usr/local/bin/tool")
    monkeypatch.setattr(launcher.subprocess, "run", lambda *_, **__: pytest.fail("must not install again"))
    assert launcher.prepare_runtime(root, cache) == runtime / "bin" / "python"


def test_bundle_is_embedded_finder_app_without_terminal_or_secret_prompt():
    entries = bundle_entries()
    metadata = plistlib.loads(entries["Contents/Info.plist"][0])
    assert metadata["CFBundleExecutable"] == "VideoAnatomy"
    assert metadata["CFBundlePackageType"] == "APPL"
    assert entries["Contents/MacOS/VideoAnatomy"][1] == 0o755
    executable = entries["Contents/MacOS/VideoAnatomy"][0].decode()
    assert "../Resources/app" in executable
    assert "mac_launcher.py" in executable
    assert "OPENAI_API_KEY" not in executable
    assert 'tell application "Terminal"' not in executable


def test_shutdown_http_cannot_redirect_control_token():
    redirect = launcher.NoRedirect()
    assert redirect.redirect_request(None, None, 302, "moved", {}, "https://example.com") is None


def test_corrupt_discovery_is_not_accepted(tmp_path):
    path = tmp_path / "instance.json"
    path.write_text(json.dumps(["unexpected"]))
    assert launcher.read_record(path, tmp_path) is None
    path.write_text("invalid")
    assert launcher.read_record(path, tmp_path) is None


def test_real_managed_server_reopens_and_restarts_without_losing_tasks(tmp_path, monkeypatch):
    """Real subprocess + loopback; Finder, Keychain and dependency install are injected.

    This verifies the launcher/server contract on the current host. It is not a
    claim that an unsigned app passed Gatekeeper or was exercised on macOS.
    """
    root = Path(__file__).resolve().parents[1]
    if not (root / "frontend" / "dist" / "index.html").is_file():
        pytest.skip("The local launcher integration needs a built frontend")
    cache, library = tmp_path / "cache", tmp_path / "library"
    monkeypatch.setattr(launcher, "default_data_dir", lambda: library)
    monkeypatch.setattr(launcher, "default_cache_dir", lambda: cache)
    monkeypatch.setattr(launcher, "prepare_runtime", lambda *_: Path(sys.executable))
    monkeypatch.setattr(launcher, "gui_message", lambda *_, **__: pytest.fail("unexpected GUI setup"))
    # Even an inherited stale secret must not configure a managed backend.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-inherited-secret-must-not-be-used")
    real_popen, processes, opened = launcher.subprocess.Popen, [], []

    def capture_popen(command, **kwargs):
        if command[0] == "/usr/bin/open":
            opened.append(command[1])
            return None
        process = real_popen(command, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(launcher.subprocess, "Popen", capture_popen)
    try:
        address = launcher.launch(root)
        saved = launcher.read_record(cache / "launcher-instance.json", library)
        assert launcher.verified_instance(saved)
        runtime = launcher.request_json(address + "/api/local/runtime")
        assert runtime["mode"] == "offline"
        assert "control_token" not in runtime
        assert launcher.request_json(address + "/api/local/connection")["configured"] is False
        opener = build_opener(ProxyHandler({}))
        request = Request(address + "/api/tasks", data=b'{"title":"Retained demo task"}',
                          headers={"Content-Type": "application/json"})
        with opener.open(request, timeout=3) as response:
            task = json.load(response)
        assert launcher.launch(root) == address
        assert len(processes) == 1
        assert opened == [address, address]
        launcher.launch(root, stop=True)
        processes[0].wait(timeout=5)
        assert not launcher.verified_instance(saved)
        reopened = launcher.launch(root)
        restarted = launcher.read_record(cache / "launcher-instance.json", library)
        assert len(processes) == 2
        assert restarted["instance_id"] != saved["instance_id"]
        retained = launcher.request_json(reopened + "/api/tasks/" + task["task"]["task_id"])
        assert retained["task"]["title"] == "Retained demo task"
        log = (cache / "launcher-server.log").read_text()
        assert "sk-inherited-secret" not in log
        assert restarted["control_token"] not in log
        launcher.launch(root, stop=True)
        processes[1].wait(timeout=5)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
