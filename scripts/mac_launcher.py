#!/usr/bin/env python3
"""Start or reopen the browser workspace from Finder without a Terminal window."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.local_storage import default_cache_dir, default_data_dir  # noqa: E402
from scripts.mac_app_bundle import package_fingerprint  # noqa: E402

PROTOCOL = 1
IDENTITY_FIELDS = ("url", "instance_id", "pid", "data_dir", "package_root",
                   "package_fingerprint", "launcher_protocol")


class LauncherError(RuntimeError):
    """A safe actionable message; never include API keys or raw provider errors."""


class LauncherBusy(LauncherError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def clean_environment() -> dict[str, str]:
    environment = dict(os.environ)
    # Credentials belong to the backend's Keychain/settings flow. A new GUI
    # launch must not accidentally adopt an old terminal's key or data path.
    for name in ("OPENAI_API_KEY", "VIDEO_ANATOMY_DATA_DIR", "PYTHONPATH", "PYTHONHOME"):
        environment.pop(name, None)
    environment["PYTHONUNBUFFERED"] = "1"
    environment["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + environment.get("PATH", "")
    return environment


def gui_message(message: str, *, notification: bool = False) -> None:
    # Send the script on stdin. All messages are authored text, not shell code.
    quoted = json.dumps(message, ensure_ascii=False)
    script = (f'display notification {quoted} with title "Video Anatomy"' if notification else
              f'display dialog {quoted} with title "Video Anatomy" buttons {{"OK"}} '
              'default button "OK" with icon caution')
    subprocess.run(["/usr/bin/osascript"], input=script, text=True, capture_output=True, check=False)


@contextmanager
def launch_lock(cache_dir: Path):
    import fcntl
    cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(cache_dir / "launcher.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LauncherBusy("Video Anatomy is already starting. Its window will open when setup finishes.") from exc
        yield
    finally:
        os.close(descriptor)


def local_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
                and parsed.port is not None and 1 <= parsed.port <= 65535
                and not parsed.username and not parsed.password
                and not parsed.query and not parsed.fragment and not parsed.path)
    except ValueError:
        return False


def read_record(path: Path, data_dir: Path) -> dict | None:
    try:
        if path.is_symlink() or path.stat().st_size > 16384:
            return None
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            return None
        if (value.get("launcher_protocol") != PROTOCOL or not local_url(value.get("url"))
                or value.get("data_dir") != str(data_dir.resolve())
                or not isinstance(value.get("instance_id"), str) or len(value["instance_id"]) < 32
                or not isinstance(value.get("control_token"), str) or len(value["control_token"]) < 32
                or not isinstance(value.get("package_root"), str)
                or not isinstance(value.get("package_fingerprint"), str)
                or len(value["package_fingerprint"]) != 64
                or type(value.get("pid")) is not int or value["pid"] <= 1):
            return None
        return value
    except (OSError, ValueError, TypeError):
        return None


def request_json(url: str, *, token: str | None = None) -> dict:
    # The launcher only talks to loopback. Ignore proxy environment variables and
    # never follow a redirect that could disclose the local shutdown token.
    headers = {"x-video-anatomy-control": token} if token else {}
    request = Request(url, data=b"{}" if token else None, headers=headers)
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=3) as response:
        raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("Unexpected local response")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Unexpected local response")
        return result


def verified_instance(record: dict | None) -> bool:
    if record is None:
        return False
    try:
        runtime = request_json(record["url"] + "/api/local/runtime")
        return all(runtime.get(key) == record[key] for key in IDENTITY_FIELDS)
    except (OSError, ValueError, URLError):
        return False


def stop_instance(record: dict) -> None:
    if not verified_instance(record):
        raise LauncherError("The saved app session could not be verified. No process was stopped.")
    try:
        request_json(record["url"] + "/api/local/shutdown", token=record["control_token"])
    except HTTPError as exc:
        if exc.code == 409:
            raise LauncherError("The previous Video Anatomy version is still processing work. Let it finish, then reopen this version.") from exc
        raise LauncherError("The previous Video Anatomy session could not be closed. Close it before opening this version.") from exc
    except (OSError, ValueError, URLError) as exc:
        raise LauncherError("The previous Video Anatomy session did not confirm shutdown. No process was forcibly stopped.") from exc
    for _ in range(60):
        if not verified_instance(record):
            return
        time.sleep(0.25)
    raise LauncherError("Video Anatomy is still closing. Wait a moment and reopen this version.")


def save_record(path: Path, record: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".launcher-instance-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as target:
            json.dump(record, target)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prepare_runtime(root: Path, cache_dir: Path) -> Path:
    environment = clean_environment()
    if not shutil.which("ffmpeg", path=environment["PATH"]) or not shutil.which("ffprobe", path=environment["PATH"]):
        raise LauncherError("FFmpeg is required. Run this once in Terminal: brew install python@3.12 ffmpeg. Then reopen Video Anatomy.")
    requirements = root / "requirements.lock"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    runtime = cache_dir / "runtime" / digest
    python = runtime / "bin" / "python"
    marker = runtime / "ready.sha256"
    if marker.is_file() and python.is_file() and marker.read_text() == digest:
        return python
    gui_message("Preparing the local runtime. The first launch can take a few minutes. Your workspace will open automatically.", notification=True)
    runtime.parent.mkdir(parents=True, exist_ok=True)
    log_path = cache_dir / "runtime-setup.log"
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as log:
        commands = []
        if not python.is_file():
            commands.append([sys.executable, "-m", "venv", str(runtime)])
        commands.append([str(python), "-m", "pip", "install", "-r", str(requirements)])
        try:
            for command in commands:
                subprocess.run(command, cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT,
                               check=True, timeout=900)
        except (OSError, subprocess.SubprocessError) as exc:
            raise LauncherError(f"Runtime setup did not finish. Check your internet connection, then reopen Video Anatomy. Setup log: {log_path}") from exc
    marker.write_text(digest)
    return python


def start_server(root: Path, python: Path, data_dir: Path, cache_dir: Path) -> dict:
    instance_id, control_token = secrets.token_hex(32), secrets.token_hex(32)
    fingerprint = package_fingerprint(root)
    log_path = cache_dir / "launcher-server.log"
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as log:
        process = subprocess.Popen(
            [str(python), str(root / "scripts" / "local_server.py"), "--managed-launcher",
             "--no-open", "--port", "0", "--data-dir", str(data_dir), "--cache-dir", str(cache_dir)],
            cwd=root, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
            env=clean_environment(), start_new_session=True, close_fds=True,
        )
        assert process.stdin is not None
        process.stdin.write(json.dumps({"instance_id": instance_id, "control_token": control_token}).encode() + b"\n")
        process.stdin.close()
    expected = {"instance_id": instance_id, "pid": process.pid, "data_dir": str(data_dir.resolve()),
                "package_root": str(root.resolve()), "package_fingerprint": fingerprint,
                "launcher_protocol": PROTOCOL}
    deadline = time.monotonic() + 90
    with log_path.open() as output:
        while time.monotonic() < deadline:
            line = output.readline(65536)
            if line.startswith("VIDEO_ANATOMY_READY "):
                try:
                    ready = json.loads(line.split(" ", 1)[1])
                    if all(ready.get(key) == value for key, value in expected.items()) and local_url(ready.get("url")):
                        record = {**expected, "url": ready["url"], "control_token": control_token}
                        # FastAPI emits the handshake inside lifespan startup,
                        # just before Uvicorn begins accepting connections.
                        for _ in range(30):
                            if verified_instance(record):
                                return record
                            if process.poll() is not None:
                                break
                            time.sleep(0.1)
                except (ValueError, AttributeError):
                    pass
                if process.poll() is None:
                    process.terminate()
                raise LauncherError("The local server's identity could not be verified. No browser window was opened.")
            if not line:
                if process.poll() is not None:
                    raise LauncherError(f"Video Anatomy could not start. If an older Terminal launcher is open, stop it with Control+C once and reopen this app. Startup log: {log_path}")
                time.sleep(0.1)
    # This is our own just-started child, never a PID read from a stale file.
    # A hung startup has not been opened to the user or admitted a paid request.
    process.terminate()
    raise LauncherError(f"The local server took too long to start. Reopen Video Anatomy. Startup log: {log_path}")


def launch(root: Path = ROOT, *, stop: bool = False) -> str | None:
    environment = clean_environment()
    # Read defaults without inheriting an old development data directory.
    previous = os.environ.pop("VIDEO_ANATOMY_DATA_DIR", None)
    try:
        data_dir = default_data_dir().resolve()
    finally:
        if previous is not None:
            os.environ["VIDEO_ANATOMY_DATA_DIR"] = previous
    cache_dir = default_cache_dir().resolve()
    path = cache_dir / "launcher-instance.json"
    with launch_lock(cache_dir):
        record = read_record(path, data_dir)
        live = verified_instance(record)
        if stop:
            if live:
                stop_instance(record)
            return None
        if (live and record["package_root"] == str(root.resolve())
                and record["package_fingerprint"] == package_fingerprint(root)):
            address = record["url"]
        else:
            if live:
                stop_instance(record)
            python = prepare_runtime(root, cache_dir)
            record = start_server(root, python, data_dir, cache_dir)
            save_record(path, record)
            address = record["url"]
        subprocess.Popen(["/usr/bin/open", address], env=environment,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return address


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stop", action="store_true", help="Gracefully stop the verified local app")
    arguments = parser.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("This Finder launcher requires macOS. Use scripts/start-local.sh on Linux.")
    try:
        launch(stop=arguments.stop)
    except LauncherBusy as exc:
        gui_message(str(exc), notification=True)
    except LauncherError as exc:
        gui_message(str(exc))
    except Exception:
        # Raw exceptions can include configuration or private local state.
        gui_message("Video Anatomy could not open. Check that the app is fully extracted into a writable folder, then try again. Your library has not been deleted.")


if __name__ == "__main__":
    main()
