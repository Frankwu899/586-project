#!/usr/bin/env python3
"""Create a fictional task through the same persistent services used by the API.

The optional --complete walkthrough includes scripted review and approval of
fictional records. It is demonstration setup, never a user's real approval.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.models import validate_state  # noqa: E402
from backend.app.service import WorkflowService, find, ref  # noqa: E402


def load_sample(data_dir: Path, complete: bool = False):
    service = WorkflowService(data_dir)
    label = "Fictional LumaCup sample"
    if complete:
        label += " — scripted review and approval walkthrough"
    state = service.create(label)
    task_id = state.task.task_id
    state = service.load_sample(task_id, state.task.version)
    state = service.recognize(task_id, state.task.version, state.task.current_video_id)
    if not state.task.current_analysis:
        raise RuntimeError("Sample recognition did not produce a result; inspect the saved job error.")
    if complete:
        analysis = find(state.analyses, state.task.current_analysis)
        visual = next(event for event in analysis.events if event.kind == "visual_action")
        state = service.correct_analysis(
            task_id,
            state.task.version,
            state.task.current_analysis,
            [{"event_id": visual.event_id, "description": "A flat blue illustrated cup is shown against a dark background; this is a synthetic drawing."}],
            [{"segment_id": analysis.segments[0].segment_id, "roles": ["other"]}],
        )
        state = service.confirm_analysis(task_id, state.task.version, state.task.current_analysis)
        state = service.generate_directions(
            task_id, state.task.version, state.task.current_brief, state.task.current_analysis
        )
        direction = state.directions[0]
        state = service.refine_direction(
            task_id, state.task.version, direction.direction_id, direction.revision,
            state.task.current_brief, state.task.current_analysis, "Make it presenter-free",
        )
        direction = state.directions[-1]
        state = service.approve_direction(
            task_id, state.task.version, direction.direction_id, direction.revision,
            state.task.current_brief, state.task.current_analysis,
        )
        state = service.generate_outputs(
            task_id, state.task.version, ref(direction), state.task.current_brief,
            state.task.current_analysis,
        )
        if not state.task.current_storyboard:
            raise RuntimeError("Sample production generation failed; inspect the saved job error.")
        production = find(state.production_briefs, state.task.current_production_brief)
        storyboard = find(state.storyboards, state.task.current_storyboard)
        rows = [row.model_dump(mode="json") for row in storyboard.rows]
        rows[0]["sound"] = "Soft original instrumental bed; keep any dialogue intelligible."
        state = service.edit_outputs(
            task_id, state.task.version, ref(production), ref(storyboard),
            {"title": "Fictional LumaCup production plan — edited sample"}, rows,
        )
    return validate_state(state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("VIDEO_ANATOMY_DATA_DIR", ".local-data")))
    parser.add_argument("--complete", action="store_true", help="Seed a fully fictional walkthrough including scripted approval and output edits")
    parser.add_argument("--write-fixture", type=Path, help="Save a JSON contract example; media remains in the data directory")
    args = parser.parse_args()
    state = load_sample(args.data_dir, args.complete)
    if args.write_fixture:
        args.write_fixture.parent.mkdir(parents=True, exist_ok=True)
        args.write_fixture.write_text(json.dumps(state.model_dump(mode="json"), indent=2) + "\n")
    print(f"Created {state.task.title}: {state.task.task_id}")
    print(f"Data: {args.data_dir.resolve()}")
    print("Start the app using this data directory and select this task from the task list.")


if __name__ == "__main__":
    main()
