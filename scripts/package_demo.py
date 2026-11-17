#!/usr/bin/env python3
"""Bundle application source and the built UI without credentials or user data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.release import VERSION  # noqa: E402

LOCAL_FILES = {"LOCAL_API.md", "MAC_APP.md", "requirements.lock", "requirements.in", "pyproject.toml",
               "Start Video Anatomy.command", "Start Video Anatomy.cmd", ".env.example"}
LOCAL_DIRS = {"backend", "scripts", "contracts", "data", "desktop"}
RUNTIME_SKILL = ("skills", "video-anatomy-professional-generation")
RELEASE_DOCS = {"docs/project-workspace-1.8.md", "docs/handoff/project-workspace-1.8.md",
                f"docs/releases/{VERSION}.md", f"docs/handoff/project-workspace-{VERSION}.md",
                "docs/decisions/provider-reliability-1.8.2.md"}
EXCLUDED_PARTS = {".git", ".agents", ".local-data", ".venv", "node_modules", "__pycache__",
                  "runtime", "release", "build", "test-results", "playwright-report"}


def distributable(path: Path, *, local_api: bool) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.name.startswith(".env") and path.name != ".env.example":
        return False
    if path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".sqlite3", ".db", ".mp4", ".mov", ".webm", ".mkv", ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".pyc", ".zip"}:
        return False
    if local_api:
        if relative.as_posix() == "scripts/package_citation_fix.py":
            return False  # Historical patch generator is not a current launcher.
        return (relative.as_posix() in LOCAL_FILES or relative.as_posix() in RELEASE_DOCS
                or relative.parts[0] in LOCAL_DIRS
                or relative.parts[:2] in {("frontend", "dist"), RUNTIME_SKILL})
    return True


def source_identity(expected_commit: str | None = None, *, include_working_tree: bool = False):
    """A release labels committed bytes only; dirty development snapshots are explicit."""
    if expected_commit is not None and not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise ValueError("--expected-commit must be the reviewed full 40-character Git SHA")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if expected_commit is not None and commit != expected_commit:
        raise ValueError("The checkout differs from --expected-commit")
    clean = not subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True,
    ).strip()
    if not clean and not include_working_tree:
        raise ValueError("Release packaging requires a clean working tree at the reviewed commit")
    return commit, clean


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--local-api", action="store_true", help="Create a focused local-launcher bundle with English delivery documentation")
    parser.add_argument("--mac-app", action="store_true", help="Wrap the local source and built UI in a Finder launcher; uses installed Python and FFmpeg")
    parser.add_argument("--expected-commit", help="Reviewed full source SHA; required for a Mac testing candidate")
    parser.add_argument("--include-working-tree", action="store_true", help="Include nonignored source files before committing an integration; review the generated manifest")
    parser.add_argument("--private-reference", type=Path, help="Include an owner-supplied MP4 in a private local API bundle only")
    args = parser.parse_args()
    if args.mac_app:
        args.local_api = True
        if not args.expected_commit:
            parser.error("--mac-app requires --expected-commit with the reviewed full source SHA")
        if args.private_reference:
            parser.error("The Mac classroom app does not bundle private reference videos")
    if args.expected_commit and args.include_working_tree:
        parser.error("A reviewed commit cannot be combined with --include-working-tree")
    if args.output.resolve().is_relative_to(ROOT.resolve()):
        parser.error("Write the archive outside the source checkout to preserve its clean state")
    if args.private_reference and (not args.local_api or not args.private_reference.is_file()
                                   or args.private_reference.suffix.lower() != ".mp4"):
        parser.error("--private-reference requires --local-api and an existing owner-supplied MP4")
    if not (ROOT / "frontend/dist/index.html").is_file():
        parser.error("Build frontend first")
    try:
        commit, clean = source_identity(args.expected_commit,
                                        include_working_tree=args.include_working_tree)
    except (ValueError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    command = ["git", "ls-files", "-z", "--cached"]
    if args.include_working_tree:
        command.extend(["--others", "--exclude-standard"])
    files = subprocess.check_output(command, cwd=ROOT).decode().split("\0")
    paths = [ROOT / name for name in files if name]
    paths.extend((ROOT / "frontend/dist").rglob("*"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bundle_root = (Path("Video Anatomy.app/Contents/Resources/app") if args.mac_app else
                   Path("video-anatomy-local" if args.local_api else "video-anatomy-demo"))
    manifest = {"application_version": VERSION, "source_commit": commit, "source_tree_clean": clean,
        "private_reference_included": bool(args.private_reference), "files": {}, "wrapper_files": {}}
    descriptor, temporary = tempfile.mkstemp(prefix=".video-anatomy-package-", suffix=".tmp",
                                              dir=args.output.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(set(paths)):
                if path.is_file() and not path.is_symlink() and distributable(path, local_api=args.local_api):
                    relative = path.relative_to(ROOT)
                    content = path.read_bytes()
                    info = zipfile.ZipInfo.from_file(path, str(bundle_root / relative))
                    archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED)
                    manifest["files"][relative.as_posix()] = hashlib.sha256(content).hexdigest()
            if args.private_reference:
                target = "samples/guandan-reference.mp4"
                content = args.private_reference.read_bytes()
                archive.writestr(str(bundle_root / target), content)
                manifest["files"][target] = hashlib.sha256(content).hexdigest()
            if args.mac_app:
                from scripts.mac_app_bundle import bundle_entries
                for relative, (content, mode) in bundle_entries().items():
                    info = zipfile.ZipInfo(str(Path("Video Anatomy.app") / relative))
                    info.create_system = 3
                    info.external_attr = (0o100000 | mode) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, content)
                    manifest["wrapper_files"][info.filename] = hashlib.sha256(content).hexdigest()
                readme = (ROOT / "MAC_APP.md").read_bytes()
                archive.writestr("README.txt", readme)
                manifest["wrapper_files"]["README.txt"] = hashlib.sha256(readme).hexdigest()
            archive.writestr(str(bundle_root / "PACKAGE_MANIFEST.json"), json.dumps(manifest, indent=2) + "\n")
        final_commit, final_clean = source_identity(args.expected_commit,
                                                   include_working_tree=args.include_working_tree)
        if final_commit != commit or final_clean != clean:
            raise ValueError("The checkout changed while packaging; rebuild from the reviewed clean commit")
        os.replace(temporary, args.output)
    except (ValueError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    finally:
        Path(temporary).unlink(missing_ok=True)
    print(f"Local workspace bundle: {args.output.resolve()}")
    print("Original media, runtime libraries, API keys and saved tasks are excluded unless an owner-supplied reference was explicitly requested.")


if __name__ == "__main__":
    main()
