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
    parser.add_argument("--local-api", action="store_true", help="Name the bundle for the live local launcher")
    parser.add_argument("--private-reference", type=Path, help="Include an owner-supplied MP4 in a private local API bundle only")
    args = parser.parse_args()
    if args.private_reference and (not args.local_api or not args.private_reference.is_file()
                                   or args.private_reference.suffix.lower() != ".mp4"):
        parser.error("--private-reference requires --local-api and an existing owner-supplied MP4")
    if not (ROOT / "frontend/dist/index.html").is_file():
        parser.error("Build frontend first")
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    paths = [ROOT / name for name in files if name and (not name.startswith(".env") or name == ".env.example")]
    paths.extend((ROOT / "frontend/dist").rglob("*"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bundle_root = Path("video-anatomy-local" if args.local_api else "video-anatomy-demo")
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(paths)):
            if path.is_file():
                archive.write(path, bundle_root / path.relative_to(ROOT))
        if args.private_reference:
            archive.write(args.private_reference, bundle_root / "samples" / "guandan-reference.mp4")
    print(f"Demo bundle: {args.output.resolve()}")


if __name__ == "__main__":
    main()
