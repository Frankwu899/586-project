"""Generate/check the 1.8 serialized project schema without changing legacy contracts."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.project_workspace.models import Project  # noqa: E402


def schema_text():
    schema = Project.model_json_schema(mode="serialization")
    # Responses always contain model defaults; clients should not invent defaults.
    def required(value):
        if isinstance(value, dict):
            if "properties" in value:
                value["required"] = list(value["properties"])
            for child in value.values():
                required(child)
        elif isinstance(value, list):
            for child in value:
                required(child)
    required(schema)
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = ROOT / "contracts/v1.8.project.schema.json"
    content = schema_text()
    if args.check:
        if not path.exists() or path.read_text() != content:
            raise SystemExit("Project schema is stale; run scripts/export_project_contracts.py")
    else:
        path.write_text(content)
