"""Non-secret local application preferences, separate from credential storage."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.app.workflow_errors import WorkflowError


class AppPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["English", "Chinese"] = "English"


def read_preferences(path: Path | None) -> AppPreferences:
    try:
        return AppPreferences.model_validate_json(path.read_text()) if path else AppPreferences()
    except (OSError, ValueError):
        return AppPreferences()


def write_preferences(path: Path | None, preferences: AppPreferences):
    if path is None:
        return
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".app-preferences-", dir=path.parent)
        with os.fdopen(descriptor, "w") as output:
            json.dump(preferences.model_dump(), output)
        os.replace(temporary, path)
    except OSError:
        raise WorkflowError("preferences_unavailable", "App language could not be saved. Your current language is unchanged.", 409) from None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
