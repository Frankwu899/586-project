"""Deterministic Finder launcher files for the dependency-assisted macOS app."""
from __future__ import annotations

import hashlib
from pathlib import Path
import plistlib

EXECUTABLE = '''#!/bin/bash
set -euo pipefail
launcher_dir="$(cd "$(dirname "$0")" && pwd)"
app_root="$(cd "$launcher_dir/../Resources/app" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
for candidate in python3.12 /opt/homebrew/opt/python@3.12/bin/python3.12 /usr/local/opt/python@3.12/bin/python3.12; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert sys.version_info[:2] == (3, 12)' 2>/dev/null; then
    exec "$candidate" "$app_root/scripts/mac_launcher.py" "$@"
  fi
done
/usr/bin/osascript <<'APPLESCRIPT'
display dialog "Python 3.12 is required. Install Homebrew, then run this once in Terminal: brew install python@3.12 ffmpeg. Reopen Video Anatomy afterwards." with title "Video Anatomy setup" buttons {"OK"} default button "OK" with icon caution
APPLESCRIPT
'''


def package_fingerprint(root: Path) -> str:
    """Identify installed contents, including replacement at the same app path.

    Release archives carry a manifest of source and UI bytes. Development
    checkouts have no manifest, so hash relevant source/build files directly.
    Runtime data, credentials, caches and virtual environments are excluded.
    """
    manifest = root / "PACKAGE_MANIFEST.json"
    if manifest.is_file():
        return hashlib.sha256(manifest.read_bytes()).hexdigest()
    digest = hashlib.sha256()
    candidates = [root / "requirements.lock"]
    for directory in (root / "backend", root / "scripts"):
        candidates.extend(directory.rglob("*.py"))
    candidates.extend((root / "frontend" / "dist").rglob("*"))
    for path in sorted(set(candidates)):
        if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode() + b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def bundle_entries() -> dict[str, tuple[bytes, int]]:
    """Return app-relative files and permission modes; no app/data/key is bundled."""
    info = {
        "CFBundleName": "Video Anatomy",
        "CFBundleDisplayName": "Video Anatomy",
        "CFBundleIdentifier": "dev.video-anatomy.local-launcher",
        "CFBundleExecutable": "VideoAnatomy",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.7.5",
        "CFBundleVersion": "75",
        "LSUIElement": True,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    }
    return {
        "Contents/Info.plist": (plistlib.dumps(info, sort_keys=True), 0o644),
        "Contents/MacOS/VideoAnatomy": (EXECUTABLE.encode(), 0o755),
        "Contents/PkgInfo": (b"APPL????", 0o644),
    }
