#!/usr/bin/env python3
"""Run the built workspace locally with a backend-only, in-memory API key."""
from __future__ import annotations

import argparse
from dataclasses import replace
import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path
import socket
import sys
import threading
import warnings
import webbrowser

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT))

from fastapi import Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
import uvicorn  # noqa: E402
from backend.app.api import create_app  # noqa: E402
from backend.app.providers.config import ProviderSettings  # noqa: E402
from backend.app.providers.transport import STRUCTURED_VISION_MODELS, TIMESTAMP_MODELS  # noqa: E402
from backend.app.service import WorkflowService  # noqa: E402
from scripts.local_storage import (  # noqa: E402
    default_cache_dir, default_data_dir, library_lock, prepare_library, storage_info,
)
from scripts.local_connection import available_keychain, install_connection_api, keychain_disabled  # noqa: E402
from scripts.mac_keychain import KeychainError  # noqa: E402
from scripts.mac_app_bundle import package_fingerprint  # noqa: E402
from scripts.app_preferences import read_preferences  # noqa: E402


def read_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        print("Paste your OpenAI API key and press Return (hidden input; never saved to a file).", flush=True)
        # Never fall back to echoed stdin when no secure terminal is available.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            try:
                key = getpass.getpass("API Key: ").strip()
            except (getpass.GetPassWarning, EOFError) as exc:
                raise ValueError("Run this launcher in a local Terminal or PowerShell window to enter your key securely.") from exc
    if not key or any(character.isspace() for character in key) or not key.isascii():
        raise ValueError("The API key is empty or contains invalid characters. Copy the complete key again.")
    return key


def local_settings(data_dir: Path, api_key: str, *, allow_empty=False) -> ProviderSettings:
    settings = replace(
        ProviderSettings.from_env(experiment_budget_enabled=False), api_key=api_key, cache_dir=data_dir / "provider-cache",
        budget_path=Path(os.getenv("VIDEO_EXPERIMENT_BUDGET_PATH", str(data_dir / "provider-budget.sqlite3"))),
        timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "90")),
        # A failed first experiment must not silently start another paid attempt.
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "0")),
        analysis_language=read_preferences(data_dir / "app-preferences.json").language,
        # The owner selected one baseline for the distributed local app. Do not
        # let old shell/model settings silently retain Luna or another model.
        # Cloud evaluation still selects its models through ProviderSettings.
        vision_model="gpt-6.1-sol", creative_model="gpt-6.1-sol",
        m2_model="gpt-6.1-sol", structure_model="gpt-6.1-sol",
        research_model="gpt-6.1-sol",
        # The owner approved dedicated timestamped speech. Restore it even if
        # an older launch environment still carries the v0.7.3 disabled value.
        transcription_model="whisper-1",
    )
    if not settings.api_key and not allow_empty:
        raise ValueError("Live mode requires a backend API key.")
    text_models = (settings.vision_model, settings.creative_model, settings.m2_model)
    if any(model not in STRUCTURED_VISION_MODELS for model in text_models):
        raise ValueError("The configured text or vision model is not supported by this adapter. See LOCAL_API.md.")
    if settings.transcription_model != "disabled" and settings.transcription_model not in TIMESTAMP_MODELS:
        raise ValueError("The speech model must be disabled or use the separately authorized timestamped transcription adapter. See LOCAL_API.md.")
    return settings


def prepare_reference(service: WorkflowService, source: Path) -> str:
    """Import supplied real media once; never analyze, apply, or approve it."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    for state in service.store.list():
        # A tombstone also counts: reopening must respect an explicit deletion.
        if any(video.content_sha256 == digest for video in state.videos):
            return state.task.task_id
    state = service.create("Guandan reference · Real video experiment")
    with source.open("rb") as stream:
        state = service.upload(state.task.task_id, state.task.version, source.name, stream)
    return state.task.task_id


def local_app(data_dir: Path, settings: ProviderSettings, reference: Path | None = None, *,
              session_token: str | None = None, address: str | None = None,
              cache_dir: Path | None = None, migration: dict | None = None,
              keychain=None, key_source="none", remembered=False, keychain_error=None,
              instance_id=None, control_token=None, shutdown=None, build_fingerprint=None):
    service = WorkflowService(data_dir, provider_settings=settings)
    if reference is not None:
        prepare_reference(service, reference)
    app = create_app(service=service)
    install_connection_api(app, keychain=keychain, key_source=key_source, remembered=remembered,
                           keychain_error=keychain_error, control_token=control_token, shutdown=shutdown,
                           preference_path=data_dir / "credential-preferences.json",
                           app_preference_path=data_dir / "app-preferences.json")

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if session_token and not hmac.compare_digest(
            request.headers.get("x-video-anatomy-token", ""), session_token
        ):
            return JSONResponse(status_code=401, content={"error": {"code": "local_auth_required", "message": "Open the desktop application to connect."}})
        # The desktop host attaches a process-local token. Browser launchers also
        # reject cross-origin mutations and DNS-rebinding hosts when bound live.
        if address:
            from urllib.parse import urlparse
            expected = urlparse(address).netloc
            if request.headers.get("host") != expected:
                return JSONResponse(status_code=403, content={"error": {"code": "invalid_local_host", "message": "Use the local address printed by the launcher."}})
            origin = request.headers.get("origin")
            if origin and origin != address:
                return JSONResponse(status_code=403, content={"error": {"code": "cross_origin_request", "message": "Open the app in its local window."}})

        return await call_next(request)

    @app.get("/api/local/runtime")
    def runtime_info():
        return {**storage_info(data_dir, cache_dir or default_cache_dir(), migration),
                "mode": "live" if service.provider_settings.api_key else "offline",
                "desktop": session_token is not None, "instance_id": instance_id, "url": address,
                "pid": os.getpid(), "package_root": str(ROOT.resolve()),
                "launcher_protocol": 1 if instance_id else None, "package_fingerprint": build_fingerprint}

    app.mount("/", StaticFiles(directory=ROOT / "frontend" / "dist", html=True), name="workspace")
    return app


def desktop_credentials() -> tuple[str, str]:
    """Accept credentials on an inherited pipe, never command-line arguments."""
    try:
        payload = json.loads(sys.stdin.readline(16384))
        key, token = payload.get("api_key", ""), payload["session_token"]
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("Invalid desktop session.")
        if not isinstance(key, str) or any(c.isspace() for c in key) or not key.isascii():
            raise ValueError("Invalid API key.")
        return key, token
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("The desktop launcher could not establish a private session.") from exc


def managed_identity() -> tuple[str, str]:
    try:
        payload = json.loads(sys.stdin.readline(16384))
        instance_id, token = payload["instance_id"], payload["control_token"]
        if any(not isinstance(value, str) or not 32 <= len(value) <= 128 or not value.isalnum()
               for value in (instance_id, token)):
            raise ValueError("Invalid identity")
        return instance_id, token
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("The application launcher could not establish its local session.") from exc


def initial_credentials(*, keychain=None, managed=False, offline=False, prompt=False, preference_path=None):
    """Managed apps ignore stale shell keys. Startup itself never calls OpenAI."""
    if offline:
        return "", "none", False, None
    if prompt:
        return read_api_key(), "session", False, None
    if keychain is not None and not keychain_disabled(preference_path):
        try:
            saved = keychain.get()
            if saved:
                return saved, "keychain", True, None
        except KeychainError as exc:
            return "", "none", False, str(exc)
    key = "" if managed else os.getenv("OPENAI_API_KEY", "").strip()
    return key, "environment" if key else "none", False, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    parser.add_argument("--migrate-from", type=Path, help="Copy and verify an old .local-data/live folder into an absent destination")
    parser.add_argument("--reference", type=Path, help="Prepare a real video without analyzing it")
    parser.add_argument("--no-open", action="store_true", help="Do not open this machine's browser")
    parser.add_argument("--offline", action="store_true", help="Run without credentials or paid model requests")
    parser.add_argument("--desktop", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--managed-launcher", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--prompt-key", action="store_true", help="Enter a session key in Terminal instead of API settings")
    args = parser.parse_args()
    if args.desktop and args.managed_launcher:
        parser.error("Select one application launcher mode.")
    if not (1 <= args.port <= 65535 or ((args.desktop or args.managed_launcher) and args.port == 0)):
        parser.error("Port must be between 1 and 65535.")
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        parser.error("Built frontend missing. Use scripts/start-local.sh or scripts/start-local.ps1.")
    args.data_dir = args.data_dir.expanduser().absolute()
    args.cache_dir = args.cache_dir.expanduser().absolute()
    reference = args.reference
    bundled_reference = ROOT / "samples" / "guandan-reference.mp4"
    if reference is None and bundled_reference.is_file():
        reference = bundled_reference
    if reference is not None and not reference.is_file():
        parser.error("Reference file not found.")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", args.port))
        except OSError:
            parser.error(f"Port {args.port} is already in use. Close the old server or add --port {args.port + 1}.")
        actual_port = listener.getsockname()[1]
        address = f"http://127.0.0.1:{actual_port}"
        try:
            with library_lock(args.data_dir):
                keychain = available_keychain()
                instance_id, control_token = managed_identity() if args.managed_launcher else (None, None)
                build_fingerprint = package_fingerprint(ROOT) if args.managed_launcher else None
                key_source, remembered, keychain_error = "none", False, None
                if args.desktop:
                    api_key, session_token = desktop_credentials()
                    key_source = "session" if api_key else "none"
                else:
                    api_key, key_source, remembered, keychain_error = initial_credentials(
                        keychain=keychain, managed=args.managed_launcher, offline=args.offline, prompt=args.prompt_key,
                        preference_path=args.data_dir / "credential-preferences.json")
                    session_token = None
                settings = local_settings(args.data_dir, api_key, allow_empty=True)
                migration = prepare_library(args.data_dir, args.migrate_from or ROOT / ".local-data" / "live",
                                            explicit_import=args.migrate_from is not None)
                args.cache_dir.mkdir(parents=True, exist_ok=True)
                server_holder = {}
                def request_shutdown():
                    timer = threading.Timer(.3, lambda: setattr(server_holder["server"], "should_exit", True))
                    timer.daemon = True
                    timer.start()
                app = local_app(args.data_dir, settings, reference, session_token=session_token,
                                address=address, cache_dir=args.cache_dir, migration=migration,
                                keychain=keychain, key_source=key_source, remembered=remembered,
                                keychain_error=keychain_error, instance_id=instance_id,
                                control_token=control_token, shutdown=request_shutdown, build_fingerprint=build_fingerprint)
                print(f"\nVideo Anatomy: {address}\nLibrary: {args.data_dir}", flush=True)
                print(f"Derived cache: {args.cache_dir}", flush=True)
                print("Paid results, original media and drafts are retained in the library.", flush=True)
                if migration["status"] == "copied_and_verified":
                    print(f"Legacy library copied and verified. Original retained at: {migration['source']}", flush=True)
                elif migration["status"] == "existing_library_preserved":
                    print(migration["message"], flush=True)
                if api_key:
                    print("API key configured in backend memory; access and billing have not been verified.", flush=True)
                    print(f"Vision / Ideas / Brief: {settings.vision_model} / {settings.creative_model} / {settings.m2_model}")
                    print(f"Speech: {settings.transcription_model}; automatic retries: {settings.max_retries}")
                    print("Startup and import do not call models. Analysis and AI generation can incur API charges.", flush=True)
                else:
                    print("No API key configured. Open API connection in the workspace to configure it. Saved work remains available.", flush=True)
                print("Stop with Ctrl+C or close the desktop app. Saved tasks remain available next time.", flush=True)

                @app.on_event("startup")
                async def ready():
                    if args.desktop or args.managed_launcher:
                        print("VIDEO_ANATOMY_READY " + json.dumps({"url": address,
                            "instance_id": instance_id, "pid": os.getpid(), "data_dir": str(args.data_dir.resolve()),
                            "package_root": str(ROOT.resolve()), "launcher_protocol": 1,
                            "package_fingerprint": build_fingerprint}), flush=True)
                    elif not args.no_open:
                        timer = threading.Timer(1, webbrowser.open, args=(address,))
                        timer.daemon = True
                        timer.start()

                server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=actual_port, access_log=not args.desktop))
                server_holder["server"] = server
                server.run(sockets=[listener])
        except ValueError as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
