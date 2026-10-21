"""Lossless v0.5 extension; language was not explicitly selected in old tasks."""
from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .models import TaskState, validate_state

ROOT = Path(__file__).resolve().parents[2]
_V05_VALIDATOR = Draft202012Validator(
    json.loads((ROOT / "contracts/v0.5.task-state.schema.json").read_text()),
    format_checker=FormatChecker(),
)


def add_v06_fields(state: dict) -> None:
    for record in [state["task"], *(record for values in state.values() if isinstance(values, list) for record in values)]:
        record["schema_version"] = "0.6.0"
    state["task"]["generation_language"] = None
    for video in state["videos"]:
        video["deleted_at"] = None
    for output in [*state["production_briefs"], *state["storyboards"]]:
        output["bundle_id"] = None
    for direction in state["directions"]:
        direction["auxiliary_status"] = "current"


def migrate_v05_task(payload: dict) -> TaskState:
    _V05_VALIDATOR.validate(payload)
    state = deepcopy(payload)
    add_v06_fields(state)
    state["task"]["version"] += 1
    return validate_state(state)
