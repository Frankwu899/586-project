"""Release identity from packaged provenance, or the actual development checkout."""
from pathlib import Path
import json
import re
import subprocess

VERSION = "1.8.3"
ROOT = Path(__file__).resolve().parents[2]


def release_info():
    commit = None
    manifest = ROOT / "PACKAGE_MANIFEST.json"
    try:
        if manifest.is_file():
            commit = json.loads(manifest.read_text(encoding="utf-8")).get("source_commit")
        elif (ROOT / ".git").exists():
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             text=True, stderr=subprocess.DEVNULL, timeout=2).strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        commit = None
    return {"version": VERSION, "source_commit": commit}
