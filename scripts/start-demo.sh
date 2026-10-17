#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v ffmpeg >/dev/null || { echo 'Install FFmpeg (including ffprobe) first. See DEMO.md.'; exit 1; }
command -v ffprobe >/dev/null || { echo 'ffprobe is required. See DEMO.md.'; exit 1; }
if [ ! -x .venv/bin/python ]; then
  if command -v python3.12 >/dev/null; then
    demo_python=python3.12
  else
    demo_python=python3
  fi
  "$demo_python" -c 'import sys; assert sys.version_info >= (3, 12), "Install Python 3.12 or later first. See DEMO.md."'
  "$demo_python" -m venv .venv
  .venv/bin/python -m pip install -r requirements.lock
fi
if [ ! -f frontend/dist/index.html ]; then
  npm --prefix frontend ci
  npm --prefix frontend run build
fi
exec .venv/bin/python scripts/demo_server.py --open "$@"
