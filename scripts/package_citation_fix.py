#!/usr/bin/env python3
"""Build a one-file, hash-guarded Mac update without packaging task data or keys."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = "228d5e768d3da4727a17a815d54e705610a20bcc"
TARGET = "backend/app/providers/creative.py"
INSTALLER = r'''#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
finish() {
  if [ -t 0 ]; then read -r -p '按回车关闭此窗口。' _ || true; fi
}
fail() { echo "$1"; finish; exit 1; }
app_dir="${1:-$HOME/Desktop/video-anatomy-local}"
if [ ! -f "$app_dir/scripts/local_server.py" ]; then
  if command -v osascript >/dev/null; then
    app_dir=$(osascript -e 'POSIX path of (choose folder with prompt "选择原来的 video-anatomy-local 文件夹（保留你现有任务的那个）")') || exit 1
  else
    fail '找不到项目。请将原项目文件夹路径作为参数传入。'
  fi
fi
target="$app_dir/backend/app/providers/creative.py"
[ -f "$app_dir/scripts/local_server.py" ] && [ -f "$target" ] || fail '这不是完整的原项目文件夹，未修改任何内容。'
[ ! -L "$target" ] || fail '目标是符号链接，未自动覆盖。请联系维护者。'
before=$(cat before.sha256)
after=$(cat after.sha256)
current=$(shasum -a 256 "$target" | cut -d ' ' -f 1)
payload=$(shasum -a 256 creative.py | cut -d ' ' -f 1)
[ "$payload" = "$after" ] || fail '更新包校验失败，未修改项目。请重新下载。'
if [ "$current" = "$after" ]; then
  echo '该修复已经安装。请重启原项目，再生成创意方向。'
  finish
  exit 0
fi
[ "$current" = "$before" ] || fail '原文件版本与此补丁不匹配，未覆盖任何修改。请将此提示发给维护者。'
backup=$(mktemp "$target.backup.XXXXXX")
cp -p "$target" "$backup"
temporary=$(mktemp "$target.update.XXXXXX")
trap 'rm -f "$temporary"' EXIT
cp -p creative.py "$temporary"
mv -f "$temporary" "$target"
echo '引用修复已安装。原代码已备份；任务、视频、Brief、已确认分析和草稿均未改动。'
echo '关闭旧项目服务（其终端按 Ctrl+C），然后重新打开原文件夹的 Start Video Anatomy.command。'
echo '重启后进入原任务的 Creative directions，点击一次 Generate two directions；无需重新分析视频。'
finish
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    before = subprocess.check_output(["git", "show", f"{BASE}:{TARGET}"], cwd=ROOT)
    after = (ROOT / TARGET).read_bytes()
    contents = {
        "Apply Citation Fix.command": INSTALLER.encode(), "creative.py": after,
        "before.sha256": hashlib.sha256(before).hexdigest().encode(),
        "after.sha256": hashlib.sha256(after).hexdigest().encode(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            entry = zipfile.ZipInfo(f"video-anatomy-citation-fix/{name}")
            entry.create_system = 3
            entry.external_attr = (0o100755 if name.endswith(".command") else 0o100644) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    print(f"Citation fix: {args.output.resolve()}")


if __name__ == "__main__":
    main()
