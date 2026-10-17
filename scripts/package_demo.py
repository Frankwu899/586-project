#!/usr/bin/env python3
"""Bundle tracked source and built UI, excluding credentials and runtime data."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if not (ROOT / "frontend/dist/index.html").is_file():
        parser.error("Build frontend first")
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    paths = [ROOT / name for name in files if name and (not name.startswith(".env") or name == ".env.example")]
    paths.extend((ROOT / "frontend/dist").rglob("*"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(paths)):
            if path.is_file():
                archive.write(path, Path("video-anatomy-demo") / path.relative_to(ROOT))
    print(f"Demo bundle: {args.output.resolve()}")


if __name__ == "__main__":
    main()
