"""Single-team hosted workspace; credentials are owned by the server operator."""
from __future__ import annotations

import base64
import binascii
from dataclasses import replace
import hmac
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse
import uvicorn

from backend.app.providers.config import ProviderSettings
from scripts.app_preferences import read_preferences
from scripts.local_server import local_app
from scripts.local_storage import library_lock


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Configure {name} in the server environment before starting.")
    return value


def public_origin() -> str:
    explicit = os.environ.get("VIDEO_PUBLIC_ORIGIN", "").strip()
    if explicit:
        return explicit.rstrip("/")
    if os.environ.get("RENDER") == "true":
        return required("RENDER_EXTERNAL_URL").rstrip("/")
    return required("VIDEO_PUBLIC_ORIGIN").rstrip("/")


def shared_settings(data_dir: Path) -> ProviderSettings:
    # This deployment is pinned to the owner's selected baseline. Stale model
    # environment overrides must not silently select another reasoning model.
    return replace(
        ProviderSettings.from_env(experiment_budget_enabled=False),
        api_key=required("OPENAI_API_KEY"),
        vision_provider="openai", creative_provider="openai",
        m2_provider="openai", transcription_provider="openai",
        cache_dir=data_dir / "provider-cache",
        budget_path=data_dir / "provider-budget.sqlite3",
        timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "90")),
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "0")),
        analysis_language=read_preferences(data_dir / "app-preferences.json").language,
        vision_model="gpt-6.1-sol", creative_model="gpt-6.1-sol",
        m2_model="gpt-6.1-sol", structure_model="gpt-6.1-sol",
        research_model="gpt-6.1-sol", transcription_model="whisper-1",
    )


def create_shared_app():
    origin = public_origin()
    url = urlsplit(origin)
    local_http = url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost"}
    if (url.scheme != "https" and not local_http) or not url.hostname or url.path or url.query or url.fragment or url.username or url.password:
        raise ValueError("VIDEO_PUBLIC_ORIGIN must be an HTTPS origin (or localhost HTTP for development).")
    password = required("VIDEO_TEAM_PASSWORD")
    username = os.getenv("VIDEO_TEAM_USERNAME", "team")
    if len(password) < 32 or password == os.getenv("OPENAI_API_KEY"):
        raise ValueError("Use a separate team password of at least 32 characters.")
    if not username or ":" in username:
        raise ValueError("VIDEO_TEAM_USERNAME must be nonempty and contain no colon.")
    data_dir = Path(required("VIDEO_ANATOMY_DATA_DIR"))
    if not data_dir.is_absolute():
        raise ValueError("VIDEO_ANATOMY_DATA_DIR must be an absolute persistent directory.")
    settings = shared_settings(data_dir)
    app = local_app(data_dir, settings, key_source="environment")
    expected_user, expected_password = username.encode(), password.encode()

    def error(code: str, message: str, status: int, headers=None):
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}}, headers=headers)

    @app.middleware("http")
    async def shared_boundary(request: Request, call_next):
        if request.url.path == "/healthz" and request.method == "GET":
            return JSONResponse({"status": "ok"}, headers={"Cache-Control": "no-store"})
        if request.headers.get("host", "").lower() != url.netloc.lower():
            return error("invalid_host", "Use the shared workspace address.", 403)
        authorized = False
        authorization = request.headers.get("authorization", "")
        if len(authorization) <= 4096:
            try:
                scheme, encoded = authorization.split(" ", 1)
                user, supplied = base64.b64decode(encoded, validate=True).split(b":", 1)
                authorized = (scheme.lower() == "basic" and
                              hmac.compare_digest(user, expected_user) &
                              hmac.compare_digest(supplied, expected_password))
            except (ValueError, binascii.Error):
                pass
        if not authorized:
            return error("team_login_required", "Sign in with the team's workspace credentials.", 401,
                         {"WWW-Authenticate": 'Basic realm="Video Anatomy team", charset="UTF-8"',
                          "Cache-Control": "no-store"})
        supplied_origin = request.headers.get("origin")
        if supplied_origin and supplied_origin != origin:
            return error("cross_origin_request", "Open the shared workspace directly.", 403)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("x-video-anatomy-request") != "1":
            return error("invalid_request_origin", "Send changes from the workspace.", 403)
        # Never register a usable credential editor, key-check override or process
        # shutdown for team users. Existing local launchers keep their own behavior.
        if request.url.path.startswith("/api/local/"):
            if request.url.path == "/api/local/connection" and request.method == "GET":
                return JSONResponse({"available": False, "configured": True, "mode": "shared"},
                                    headers={"Cache-Control": "no-store"})
            if request.url.path != "/api/local/preferences":
                return error("operator_managed", "This setting is managed by the workspace owner.", 403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    return app


if __name__ == "__main__":
    # One process owns the persisted jobs/library. TLS terminates at the hosting
    # ingress; no arbitrary X-Forwarded-* headers are trusted by this process.
    with library_lock(Path(required("VIDEO_ANATOMY_DATA_DIR"))):
        application = create_shared_app()
        host = "127.0.0.1" if public_origin().startswith("http:") else "0.0.0.0"
        uvicorn.run(application, host=host, port=int(os.getenv("PORT", "8000")), proxy_headers=False)
