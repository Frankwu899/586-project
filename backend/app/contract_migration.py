"""Lossless v0.3 extension into the current contract; storage archives original bytes.

The new nullable fields describe work that was not performed in older records.
Migration does not create observations, playback media, reviews or revisions.
The v0.5 claim extension records historical permission as unrecorded.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .models import TaskState, validate_state
from .m2_migration import add_v05_fields

ROOT = Path(__file__).resolve().parents[2]
_V03_VALIDATOR = Draft202012Validator(
    json.loads((ROOT / "contracts/v0.3.task-state.schema.json").read_text()),
    format_checker=FormatChecker(),
)
_COLLECTIONS = ("briefs", "videos", "analyses", "directions", "feedback",
                "production_briefs", "storyboards", "jobs")


def add_v04_fields(state: dict) -> None:
    """Upgrade a validated legacy payload in place, without touching history."""
    for record in [state["task"], *(record for name in _COLLECTIONS for record in state[name])]:
        record["schema_version"] = "0.4.0"
    for video in state["videos"]:
        video["playback"] = None
    for analysis in state["analyses"]:
        for event in analysis["events"]:
            event["visual_details"] = None


def migrate_v03_task(payload: dict) -> TaskState:
    """Preserve content/citations/review exactly and advance only task version."""
    state = deepcopy(payload)
    _V03_VALIDATOR.validate(state)
    add_v04_fields(state)
    add_v05_fields(state)
    from .workspace_migration import add_v06_fields
    add_v06_fields(state)
    state["task"]["version"] += 1
    return validate_state(state)
