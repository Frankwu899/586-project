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


def local_settings(data_dir: Path, api_key: str) -> ProviderSettings:
    settings = replace(
        ProviderSettings.from_env(), api_key=api_key, cache_dir=data_dir / "provider-cache",
        budget_path=Path(os.getenv("VIDEO_EXPERIMENT_BUDGET_PATH", str(data_dir / "provider-budget.sqlite3"))),
        timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "90")),
        # A failed first experiment must not silently start another paid attempt.
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "0")),
        analysis_language=os.getenv("ANALYSIS_OUTPUT_LANGUAGE", "Chinese"),
    )
    if not settings.api_key:
        raise ValueError("Live mode requires a backend API key.")
    text_models = (settings.vision_model, settings.creative_model, settings.m2_model)
    if any(model not in STRUCTURED_VISION_MODELS for model in text_models):
        raise ValueError("The configured text or vision model is not supported by this adapter. See LOCAL_API.md.")
    if settings.transcription_model not in TIMESTAMP_MODELS:
        raise ValueError("The timestamped transcription adapter requires whisper-1. See LOCAL_API.md.")
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
              cache_dir: Path | None = None, migration: dict | None = None):
    service = WorkflowService(data_dir, provider_settings=settings)
    if reference is not None:
        prepare_reference(service, reference)
    app = create_app(service=service)

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
                "mode": "live" if settings.api_key else "offline",
                "desktop": session_token is not None}

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
    args = parser.parse_args()
    if not (1 <= args.port <= 65535 or (args.desktop and args.port == 0)):
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
                if args.desktop:
                    api_key, session_token = desktop_credentials()
                else:
                    api_key, session_token = ("" if args.offline else read_api_key()), None
                settings = (local_settings(args.data_dir, api_key) if api_key else
                            replace(ProviderSettings.from_env(), api_key="", cache_dir=args.data_dir / "provider-cache",
                                    budget_path=Path(os.getenv("VIDEO_EXPERIMENT_BUDGET_PATH", str(args.data_dir / "provider-budget.sqlite3"))), max_retries=0))
                migration = prepare_library(args.data_dir, args.migrate_from or ROOT / ".local-data" / "live",
                                            explicit_import=args.migrate_from is not None)
                args.cache_dir.mkdir(parents=True, exist_ok=True)
                app = local_app(args.data_dir, settings, reference, session_token=session_token,
                                address=address, cache_dir=args.cache_dir, migration=migration)
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
                    print("Offline mode: no API key is configured. Saved work and the fictional sample remain available.", flush=True)
                print("Stop with Ctrl+C or close the desktop app. Saved tasks remain available next time.", flush=True)

                @app.on_event("startup")
                async def ready():
                    if args.desktop:
                        print("VIDEO_ANATOMY_READY " + json.dumps({"url": address}), flush=True)
                    elif not args.no_open:
                        timer = threading.Timer(1, webbrowser.open, args=(address,))
                        timer.daemon = True
                        timer.start()

                server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=actual_port, access_log=not args.desktop))
                server.run(sockets=[listener])
        except ValueError as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
