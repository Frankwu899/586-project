#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# macOS Finder may not inherit a shell's Homebrew PATH.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
local_python=""
for candidate in python3.12 /opt/homebrew/opt/python@3.12/bin/python3.12 /usr/local/opt/python@3.12/bin/python3.12 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert sys.version_info[:2] == (3, 12)' 2>/dev/null; then
    local_python="$candidate"
    break
  fi
done

if [ -z "$local_python" ] || ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  if [ "$(uname -s)" = Darwin ] && command -v brew >/dev/null; then
    echo 'Installing Python 3.12 and FFmpeg. The first run may take a few minutes...'
    brew install python@3.12 ffmpeg
    local_python="$(brew --prefix python@3.12)/bin/python3.12"
  else
    echo 'Python 3.12 and FFmpeg are required. On macOS, install Homebrew, then run: brew install python@3.12 ffmpeg'
    echo 'Homebrew: https://brew.sh/ . Reopen this launcher after installation. On Linux, use your package manager.'
    exit 1
  fi
fi

if [ ! -x .venv/bin/python ]; then
  "$local_python" -m venv .venv
fi
.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 12), "Existing .venv needs Python 3.12; use a fresh extracted bundle."'
local_lock_hash=$(.venv/bin/python -c 'import hashlib; print(hashlib.sha256(open("requirements.lock", "rb").read()).hexdigest())')
if [ ! -f .venv/local-install.sha256 ] || [ "$(cat .venv/local-install.sha256)" != "$local_lock_hash" ]; then
  .venv/bin/python -m pip install -r requirements.lock
  printf '%s' "$local_lock_hash" > .venv/local-install.sha256
fi
if [ ! -f frontend/dist/index.html ]; then
  npm --prefix frontend ci
  npm --prefix frontend run build
fi
exec .venv/bin/python scripts/local_server.py "$@"
