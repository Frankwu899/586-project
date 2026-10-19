"""Local-only credential configuration; no keys enter task storage or responses."""
from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
import hmac
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, SecretStr

from backend.app.adapters import UnconfiguredRecognitionAdapter
from backend.app.providers.auth import check_openai_connection, normalize_api_key
from backend.app.providers.base import ProviderError
from backend.app.providers.budget import ExperimentBudget
from backend.app.providers.creative import OpenAICreativeAdapter
from backend.app.providers.m2 import build_m2_assistance
from backend.app.providers.recognition import ProviderRecognitionAdapter
from backend.app.structure_provider import OpenAIStructureAgent
from backend.app.workflow_errors import WorkflowError
from scripts.mac_keychain import KeychainError, MacKeychain
from scripts.app_preferences import AppPreferences, write_preferences


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr
    remember: bool = False


class ConnectionCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr | None = None


def available_keychain():
    if sys.platform != "darwin":
        return None
    try:
        return MacKeychain()
    except (OSError, KeychainError):
        return None


def keychain_disabled(preference_path: Path | None) -> bool:
    if preference_path is None or not preference_path.exists():
        return False
    try:
        return json.loads(preference_path.read_text()).get("disable_keychain") is not False
    except (OSError, ValueError, AttributeError):
        # Damaged preferences must not unexpectedly re-enable an old credential.
        return True


def set_keychain_disabled(preference_path: Path | None, disabled: bool):
    if preference_path is None:
        return
    temporary = None
    try:
        preference_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".credential-preferences-", dir=preference_path.parent)
        with os.fdopen(descriptor, "w") as output:
            json.dump({"disable_keychain": disabled}, output)
        os.replace(temporary, preference_path)
    except OSError:
        raise WorkflowError("credential_preferences_unavailable", "Credential preferences could not be saved. The active API connection was not changed.", 409) from None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def running_work(service) -> bool:
    if any(job.status in ("pending", "running") for task in service.store.list() for job in task.jobs):
        return True
    with sqlite3.connect(service.store.path) as db:
        if db.execute("SELECT 1 FROM background_operations WHERE status IN ('queued','running') LIMIT 1").fetchone():
            return True
        return any(json.loads(row[0]).get("status") in ("analyzing", "researching")
                   or json.loads(row[0]).get("feedback_status") == "running"
                   for row in db.execute("SELECT payload FROM structure_runs"))


class LocalConnection:
    def __init__(self, app, *, keychain=None, key_source="none", remembered=False, keychain_error=None,
                 checker=check_openai_connection, preference_path=None):
        self.app, self.service, self.keychain = app, app.state.service, keychain
        self.key_source = key_source if self.service.provider_settings.api_key else "none"
        self.remembered, self.keychain_error = remembered, keychain_error
        self.last_check, self.checker = None, checker
        self.preference_path = preference_path

    def status(self):
        return {"available": True, "configured": bool(self.service.provider_settings.api_key),
                "key_source": self.key_source, "can_remember": self.keychain is not None,
                "remembered": self.remembered, "keychain_error": self.keychain_error,
                "last_check": asdict(self.last_check) if self.last_check else None}

    def check(self, key=None):
        settings = self.service.provider_settings
        result = self.checker(replace(settings, api_key=key) if key is not None else settings)
        if key is None:
            self.last_check = result
        return result

    def replacements(self, key, **preferences):
        # Reuse every configured model, cache and budget setting. Never recreate
        # WorkflowService: doing so would recover/interfere with existing jobs.
        settings = replace(self.service.provider_settings, api_key=key, **preferences)
        recognition = (ProviderRecognitionAdapter(settings, media_store=self.service.media)
                       if key else UnconfiguredRecognitionAdapter())
        return settings, recognition, OpenAICreativeAdapter(settings), build_m2_assistance(settings), OpenAIStructureAgent(settings)

    def apply(self, replacements):
        settings, recognition, creative, m2, structure = replacements
        self.service.provider_settings = settings
        self.service.real_recognition, self.service.real_creative = recognition, creative
        self.service.m2_assistance = m2
        self.app.state.structure_service.agent = structure

    def save(self, body):
        try:
            key = normalize_api_key(body.api_key.get_secret_value())
        except ProviderError as exc:
            raise WorkflowError(exc.code, exc.message, 422) from None
        if body.remember and self.keychain is None:
            raise WorkflowError("keychain_unavailable", "Keychain is unavailable. Save for this session without Remember on this Mac.", 409)
        result = self.check(key)
        if result.status == "rejected":
            raise WorkflowError(result.code, result.message, 422)
        replacements = self.replacements(key)
        warning = None
        if body.remember:
            previously_disabled = keychain_disabled(self.preference_path)
            # Never activate a newly stored credential until preferences commit.
            set_keychain_disabled(self.preference_path, True)
            try:
                self.keychain.set(key)
            except KeychainError as exc:
                set_keychain_disabled(self.preference_path, previously_disabled)
                raise WorkflowError("keychain_unavailable", str(exc), 409) from None
            try:
                set_keychain_disabled(self.preference_path, False)
            except WorkflowError:
                self.remembered = False
                if self.key_source == "keychain":
                    self.key_source = "session"
                self.keychain_error = "The saved credential is disabled until preferences can be saved. The current session connection is unchanged."
                raise
        else:
            # Disable future loading before trying to remove the saved item.
            # A locked Keychain must still allow a temporary replacement.
            set_keychain_disabled(self.preference_path, True)
            if self.keychain is not None:
                try:
                    self.keychain.delete()
                except KeychainError:
                    warning = "The old Keychain item could not be removed, but it is disabled for future launches. This connection is session-only."
        self.apply(replacements)
        self.key_source = "keychain" if body.remember else "session"
        self.remembered, self.keychain_error, self.last_check = body.remember, warning, result
        return self.status()

    def forget(self):
        replacements = self.replacements("")
        set_keychain_disabled(self.preference_path, True)
        warning = None
        if self.keychain is not None:
            try:
                self.keychain.delete()
            except KeychainError:
                warning = "The Keychain item could not be removed, but it is disabled for future launches. The current connection has been cleared."
        self.apply(replacements)
        self.key_source, self.remembered, self.last_check = "none", False, None
        self.keychain_error = warning
        return self.status()


def install_connection_api(app, *, keychain=None, key_source="none", remembered=False,
                           keychain_error=None, checker=check_openai_connection,
                           control_token=None, shutdown=None, preference_path=None,
                           app_preference_path=None):
    connection = LocalConnection(app, keychain=keychain, key_source=key_source,
                                 remembered=remembered, keychain_error=keychain_error, checker=checker,
                                 preference_path=preference_path)
    app.state.local_connection = connection
    gate = asyncio.Lock()
    active_writes, changing, closing = 0, False, False
    exclusive = {"/api/local/connection", "/api/local/connection/forget", "/api/local/shutdown",
                 "/api/local/preferences", "/api/local/budget/reconcile"}

    @app.middleware("http")
    async def credential_boundary(request: Request, call_next):
        nonlocal active_writes, changing, closing
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await call_next(request)
        is_change = request.url.path in exclusive
        async with gate:
            if closing or changing or (is_change and (active_writes or running_work(connection.service))):
                return JSONResponse(status_code=409, content={"error": {"code": "provider_connection_busy",
                    "message": "Wait for current work to finish before changing app settings or closing the app.", "retryable": True}})
            if is_change:
                changing = True
            else:
                active_writes += 1
        try:
            response = await call_next(request)
            if request.url.path == "/api/local/shutdown" and response.status_code == 200:
                closing = True
            return response
        finally:
            async with gate:
                if is_change:
                    changing = False
                else:
                    active_writes -= 1

    @app.get("/api/local/connection")
    def status():
        return connection.status()

    @app.post("/api/local/connection/check")
    def check(body: ConnectionCheckInput):
        return asdict(connection.check(body.api_key.get_secret_value() if body.api_key is not None else None))

    @app.post("/api/local/connection")
    def save(body: ConnectionInput):
        return connection.save(body)

    @app.post("/api/local/connection/forget")
    def forget():
        return connection.forget()

    @app.get("/api/local/preferences")
    def preferences():
        return AppPreferences(language=connection.service.provider_settings.analysis_language)

    @app.post("/api/local/preferences")
    def save_preferences(body: AppPreferences):
        replacements = connection.replacements(connection.service.provider_settings.api_key,
                                                analysis_language=body.language)
        write_preferences(app_preference_path, body)
        connection.apply(replacements)
        return body

    def budget():
        settings = connection.service.provider_settings
        if settings.budget_path is None:
            raise WorkflowError("budget_unavailable", "Budget tracking is unavailable in this server.", 404)
        return ExperimentBudget(settings.budget_path, maximum=settings.experiment_max_usd)

    @app.get("/api/local/budget")
    def budget_status():
        return budget().summary()

    @app.post("/api/local/budget/reconcile")
    def reconcile_budget():
        ledger = budget()
        result = ledger.reconcile_rejected_attempts()
        return {**ledger.summary(), **result}

    @app.post("/api/local/shutdown")
    def stop(request: Request):
        if not control_token or not shutdown or not hmac.compare_digest(
                request.headers.get("x-video-anatomy-control", ""), control_token):
            raise WorkflowError("local_control_required", "Close the application using its own launcher.", 403)
        shutdown()
        return {"stopping": True}

    return connection
