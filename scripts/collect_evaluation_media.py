#!/usr/bin/env python3
"""Prepare the reviewed evaluation corpus without credentials or model calls.

Network download is opt-in and restricted to the pinned public GitHub asset.
Derived files are test controls, not claims of automatic media cleaning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evaluation/manifests/workspace-redesign-v1.json"
PINNED_ROOT = (
    "https://raw.githubusercontent.com/IDPF/epub3-samples/"
    "7651e2002b631e6577fadf7e9e0692fa6efb8746/30/cc-shared-culture/EPUB/"
)
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT / ".local-data/evaluation"):
        raise ValueError("Media outputs must stay in .local-data/evaluation")
    return path


def probe(path: Path) -> dict:
    result = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ], timeout=30))
    video = next(s for s in result["streams"] if s["codec_type"] == "video")
    return {
        "duration_seconds": float(result["format"]["duration"]),
        "width": video["width"], "height": video["height"],
        "fps": video["r_frame_rate"], "average_fps": video["avg_frame_rate"],
        "frame_count": int(video["nb_frames"]) if video.get("nb_frames", "").isdigit() else None,
        "video_codec": video["codec_name"],
        "audio": any(s["codec_type"] == "audio" for s in result["streams"]),
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected source redirect; review provenance before downloading")


def fetch_asset(url: str, target: Path, expected_sha256: str) -> None:
    if not url.startswith(PINNED_ROOT):
        raise ValueError("Only the reviewed, commit-pinned GitHub source is supported")
    target.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(NoRedirect)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            with opener.open(url, timeout=30) as response:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise ValueError("Source exceeds the 32 MiB per-file limit")
                    handle.write(chunk)
            handle.flush()
            if sha256(temporary) != expected_sha256:
                raise ValueError("Source digest does not match the reviewed asset")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


def derive_asset(asset: dict, assets: dict[str, dict], target: Path) -> None:
    parent = assets[asset["derived_from"]]
    source = local_path(parent["path"])
    if not source.exists():
        raise FileNotFoundError("Parent asset is not prepared")
    if parent.get("sha256") and sha256(source) != parent["sha256"]:
        raise ValueError("Parent digest mismatch; refusing to derive from unreviewed bytes")
    recipe = asset["derivation"]
    args = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(source)]
    if recipe["kind"] == "manual_ui_masks":
        filters = [
            f"drawbox=x={box['x']}:y={box['y']}:w={box['width']}:h={box['height']}:color=black:t=fill"
            for box in recipe["rectangles_pixels"]
        ]
        args += ["-vf", ",".join(filters), "-fps_mode", "vfr"]
    elif recipe["kind"] == "excerpt":
        args += ["-ss", str(recipe["start_seconds"]), "-t", str(recipe["duration_seconds"])]
    else:
        raise ValueError("Unknown reviewed derivation")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.stem + ".preparing.mp4")
    try:
        subprocess.run(args + [
            "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "fast",
            "-crf", "18", "-c:a", "aac", "-movflags", "+faststart", str(temporary)
        ], check=True, timeout=120)
        probe(temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-public", action="store_true", help="Download the one reviewed public campaign source")
    parser.add_argument("--derive", action="store_true", help="Prepare the labeled manual-mask and excerpt controls")
    parser.add_argument("--attachments-root", type=Path, default=Path("/workspace/attachments"))
    args = parser.parse_args()
    corpus = json.loads(MANIFEST.read_text())
    assets = {asset["id"]: asset for asset in corpus["assets"]}
    checks = []
    for asset in corpus["assets"]:
        target = local_path(asset["path"])
        check = {"id": asset["id"], "path": asset["path"]}
        try:
            if not target.exists() and asset.get("attachment_filename"):
                matches = list(args.attachments_root.rglob(asset["attachment_filename"]))
                match = next((p for p in matches if sha256(p) == asset["sha256"]), None)
                if match:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(match, target)
            if not target.exists() and asset.get("download_url") and args.fetch_public:
                fetch_asset(asset["download_url"], target, asset["sha256"])
            if not target.exists() and asset.get("derived_from") and args.derive:
                derive_asset(asset, assets, target)
            if not target.exists():
                check["status"] = "missing"
            else:
                digest = sha256(target)
                check.update(status="ready", sha256=digest, size_bytes=target.stat().st_size, media=probe(target))
                if not asset.get("derived_from") and digest != asset["sha256"]:
                    raise ValueError("Digest mismatch; existing media was preserved, not overwritten")
                if asset.get("derived_from"):
                    check["note"] = "Derived control bytes may vary by FFmpeg version; not an original export"
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            check.update(status="failed", error=str(error))
        checks.append(check)
    report = ROOT / ".local-data/evaluation/corpus-readiness.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"assets": checks, "api_calls": 0, "paid_cost_usd": 0}, indent=2) + "\n")
    print(json.dumps({"report": str(report), "assets": [{"id": c["id"], "status": c["status"]} for c in checks]}, indent=2))
    return 1 if any(c["status"] == "failed" for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
