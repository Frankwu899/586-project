"""Lossless v0.4-to-v0.5 extension: historical permission stays unrecorded."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .models import TaskState, validate_state

ROOT = Path(__file__).resolve().parents[2]
_V04_VALIDATOR = Draft202012Validator(json.loads((ROOT / "contracts/v0.4.task-state.schema.json").read_text()), format_checker=FormatChecker())


def add_v05_fields(state: dict) -> None:
    for record in [state["task"], *(record for values in state.values() if isinstance(values, list) for record in values)]:
        record["schema_version"] = "0.5.0"
    for brief in state["briefs"]:
        brief["claim_details"] = [{"claim_id": "claim_" + hashlib.sha256(f"{brief['brief_id']}:{index}".encode()).hexdigest()[:20],
            "statement": statement, "supporting_notes": None, "source_urls": [], "qualification": None,
            "confirmation_origin": "legacy_unrecorded"} for index, statement in enumerate(brief["selling_points"])]


def migrate_v04_task(payload: dict) -> TaskState:
    _V04_VALIDATOR.validate(payload)
    state = deepcopy(payload)
    add_v05_fields(state)
    from .workspace_migration import add_v06_fields
    add_v06_fields(state)
    state["task"]["version"] += 1
    return validate_state(state)
