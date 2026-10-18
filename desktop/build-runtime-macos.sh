#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(uname -s)" != Darwin ]; then
  echo 'The native runtime and DMG must be built and tested on macOS.' >&2
  exit 1
fi
if [ -z "${VIDEO_ANATOMY_FFMPEG_DIR:-}" ] || [ -z "${VIDEO_ANATOMY_FFMPEG_NOTICES:-}" ]; then
  echo 'Set VIDEO_ANATOMY_FFMPEG_DIR to a vetted portable ffmpeg/ffprobe build and VIDEO_ANATOMY_FFMPEG_NOTICES to its license/source-offer notices.' >&2
  exit 1
fi
for tool in ffmpeg ffprobe; do
  test -x "$VIDEO_ANATOMY_FFMPEG_DIR/$tool" || { echo "Missing executable: $tool" >&2; exit 1; }
  # A Homebrew binary may reference libraries outside the app. Fail closed until
  # its runtime dependencies have actually been bundled, rather than shipping it.
  python3 - "$VIDEO_ANATOMY_FFMPEG_DIR/$tool" <<'PY'
import platform, subprocess, sys
binary = sys.argv[1]
architectures = subprocess.check_output(["lipo", "-archs", binary], text=True).split()
if platform.machine() not in architectures:
    raise SystemExit("Media-tool architecture does not match this Mac.")
lines = subprocess.check_output(["otool", "-L", binary], text=True).splitlines()[1:]
external = [line.strip().split(" (")[0] for line in lines if not line.strip().startswith(("/usr/lib/", "/System/Library/"))]
if external:
    raise SystemExit("Portable media tools are required; external libraries found: " + ", ".join(external))
PY
done
test -f "$VIDEO_ANATOMY_FFMPEG_NOTICES" || { echo 'Media-tool license notices are missing.' >&2; exit 1; }
test -f frontend/dist/index.html || { echo 'Build the frontend first: npm --prefix frontend ci && npm --prefix frontend run build' >&2; exit 1; }
python3.12 -m venv desktop/build/venv
desktop/build/venv/bin/python -m pip install -r requirements.lock 'pyinstaller==6.16.0'
desktop/build/venv/bin/python -m PyInstaller --noconfirm --clean --onedir --name video-anatomy-backend --distpath desktop/runtime --workpath desktop/build/pyinstaller --specpath desktop/build --paths . --collect-submodules backend --collect-submodules uvicorn --add-data 'frontend/dist:frontend/dist' --add-data 'data:data' --add-data 'contracts:contracts' scripts/desktop_backend.py
mkdir -p desktop/runtime/media-bin desktop/runtime/notices
cp "$VIDEO_ANATOMY_FFMPEG_DIR/ffmpeg" "$VIDEO_ANATOMY_FFMPEG_DIR/ffprobe" desktop/runtime/media-bin/
cp "$VIDEO_ANATOMY_FFMPEG_NOTICES" desktop/runtime/notices/FFmpeg.txt
desktop/build/venv/bin/python - <<'PY'
from pathlib import Path
import hashlib, json, platform
root = Path('desktop/runtime')
files = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob('*') if path.is_file() and path.name != 'manifest.json'}
(root / 'manifest.json').write_text(json.dumps({'platform': 'darwin', 'architecture': platform.machine(), 'files': files}, indent=2) + '\n')
PY
echo 'Native runtime assembled. Test it on this Mac before producing or distributing an installer.'
