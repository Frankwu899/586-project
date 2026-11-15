#!/usr/bin/env python3
"""Verify a team ZIP and smoke-test its extracted Linux runtime without API calls.

This is not a macOS installation, signing, Keychain, or model-quality test.
Run with the repository's dependency-complete Python 3.12 virtual environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile


FORBIDDEN_PARTS = {".git", ".venv", "node_modules", ".local-data", "__pycache__",
                   "provider-cache", "projects", "runtime", "test-results"}
FORBIDDEN_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".sqlite3", ".db", ".pyc",
                      ".mp4", ".mov", ".webm", ".mkv", ".mp3", ".wav", ".m4a",
                      ".aac", ".flac", ".ogg", ".zip"}
SECRET_PATTERN = re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b")


def _safe_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (not name or "\\" in name or path.is_absolute()
            or any(part in {"", ".", ".."} for part in name.rstrip("/").split("/"))):
        raise ValueError("The archive contains an unsafe path")
    return path


def verify_archive(archive_path: Path, expected_version: str, expected_commit: str | None = None):
    """Validate every member before extraction, including unmanifested wrappers."""
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)):
            raise ValueError("The archive contains duplicate paths")
        for entry in entries:
            path = _safe_path(entry.filename)
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}):
                raise ValueError("The archive contains a linked or special file")
            if (set(path.parts) & FORBIDDEN_PARTS or path.suffix.lower() in FORBIDDEN_SUFFIXES
                    or (path.name.startswith(".env") and path.name != ".env.example")):
                raise ValueError(f"The archive contains an excluded private/runtime file: {entry.filename}")
            if not entry.is_dir() and SECRET_PATTERN.search(archive.read(entry)):
                raise ValueError(f"The archive contains a possible credential in {entry.filename}")
        if archive.testzip() is not None:
            raise ValueError("The archive failed its CRC check")
        manifests = [name for name in names if name.endswith("/PACKAGE_MANIFEST.json")]
        if len(manifests) != 1:
            raise ValueError("Exactly one package manifest is required")
        manifest_name = manifests[0]
        root = PurePosixPath(manifest_name).parent
        mac = str(root) == "Video Anatomy.app/Contents/Resources/app"
        if not mac and str(root) != "video-anatomy-local":
            raise ValueError("Use a local-launcher or Mac team package")
        manifest = json.loads(archive.read(manifest_name))
        commit = manifest.get("source_commit")
        if manifest.get("application_version") != expected_version:
            raise ValueError("The package version differs from the expected release")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("The source commit is missing or malformed")
        if expected_commit is not None and commit != expected_commit:
            raise ValueError("The package source differs from the expected commit")
        if manifest.get("private_reference_included") is not False:
            raise ValueError("Team packages must not contain private reference media")
        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError("The package manifest has no file inventory")
        for relative, digest in files.items():
            _safe_path(relative)
            member = str(root / relative)
            if member not in names or hashlib.sha256(archive.read(member)).hexdigest() != digest:
                raise ValueError(f"Manifest hash mismatch or missing file: {relative}")
        payload = {name[len(str(root)) + 1:] for name in names
                   if name.startswith(str(root) + "/") and not name.endswith("/")}
        if payload != set(files) | {"PACKAGE_MANIFEST.json"}:
            raise ValueError("The package has unmanifested application files")
        required = {"backend/app/release.py", "scripts/local_server.py", "scripts/start-local.sh",
                    "scripts/mac_launcher.py", "requirements.lock", "frontend/dist/index.html",
                    "MAC_APP.md", "LOCAL_API.md", f"docs/releases/{expected_version}.md",
                    f"docs/handoff/project-workspace-{expected_version}.md"}
        skill = "skills/video-anatomy-professional-generation/"
        required |= {skill + item for item in ("SKILL.md", "references/PROFESSIONAL_METHOD.md",
                     "references/EDITORIAL.md", "references/QUALITY.md", "references/IDEAS.md",
                     "references/STORYBOARD.md", "references/STRUCTURE.md")}
        if not required.issubset(files):
            raise ValueError(f"Missing runtime files: {sorted(required - set(files))}")
        wrappers = {name for name in names if not name.startswith(str(root) + "/") and not name.endswith("/")}
        expected_wrappers = {"Video Anatomy.app/Contents/Info.plist", "Video Anatomy.app/Contents/PkgInfo",
                             "Video Anatomy.app/Contents/MacOS/VideoAnatomy", "READ ME FIRST.md",
                             "RELEASE NOTES.md"} if mac else set()
        if wrappers != expected_wrappers:
            raise ValueError("Unexpected or missing package wrapper files")
        if mac:
            info = plistlib.loads(archive.read("Video Anatomy.app/Contents/Info.plist"))
            if (info.get("CFBundleShortVersionString") != expected_version
                    or info.get("CFBundleVersion") != expected_version.replace(".", "")):
                raise ValueError("The Finder application version is inconsistent")
            launcher = archive.getinfo("Video Anatomy.app/Contents/MacOS/VideoAnatomy")
            if not ((launcher.external_attr >> 16) & 0o111):
                raise ValueError("The Finder launcher is not executable")
            if archive.read("READ ME FIRST.md") != archive.read(str(root / "MAC_APP.md")):
                raise ValueError("Finder launch instructions differ from the package")
            if archive.read("RELEASE NOTES.md") != archive.read(str(root / f"docs/releases/{expected_version}.md")):
                raise ValueError("Finder release notes differ from the package")
    return {"application_version": expected_version, "source_commit": commit, "files_verified": len(files),
            "variant": "mac-launcher" if mac else "local-launcher", "payload_root": str(root)}


SMOKE = r'''
import json
import re
import sys
import time
from pathlib import Path

root, data, phase, version, commit = sys.argv[1:]
root, data = Path(root), Path(data)
sys.path.insert(0, str(root))
from fastapi.testclient import TestClient
from backend.app.project_workspace.models import Analysis, InputManifest
from backend.app.project_workspace.planning import load_instructions
from backend.app.providers.transport import OpenAITransport
from scripts.local_server import ROOT, local_app, local_settings

assert ROOT.resolve() == root.resolve(), "The smoke test imported a development checkout"
def prohibit(*args, **kwargs):
    raise AssertionError("The package smoke test must never request a provider")
OpenAITransport._request = prohibit
settings = local_settings(data, "", allow_empty=True)
assert settings.vision_model == settings.m2_model == settings.creative_model == "gpt-6.1-sol"
assert settings.transcription_model == "whisper-1"
app = local_app(data, settings)
with TestClient(app) as client:
    page = client.get("/")
    assert page.status_code == 200 and "<html" in page.text.lower()
    for asset in re.findall(r'(?:src|href)="(/assets/[^"]+)"', page.text):
        assert client.get(asset).status_code == 200, "A built frontend asset is missing"
    identity = client.get("/api/projects/capabilities").json()
    assert identity["version"] == version and identity["source_commit"] == commit
    assert identity["configured"] is False
    assert identity["discovery"] == "Reserved — awaiting Frank’s specification."
    for module in ("IDEAS", "STORYBOARD", "STRUCTURE"):
        instructions, digest = load_instructions(module)
        assert instructions and len(digest) == 64
    snapshot = data.parent / "expected-project.json"
    if phase == "create":
        response = client.post("/api/projects", json={"title": "Synthetic package smoke fixture"})
        assert response.status_code == 201
        project = response.json()
        endpoint = "/api/projects/" + project["id"]
        response = client.post(endpoint + "/messages", json={"expected_version": project["version"],
                               "text": "Synthetic fixture: retain this saved conversation without an API key."})
        assert response.status_code == 202
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            project = client.get(endpoint).json()
            if all(job["status"] not in {"running", "queued"} for job in project["jobs"]):
                break
            time.sleep(0.01)
        assert project["jobs"][-1]["status"] == "failed"
        assert len([m for m in project["messages"] if m["role"] == "user"]) == 1
        assert project["messages"][-1]["status"] == "failed"
        def fixture(state):
            state.analyses.append(Analysis(inputs=InputManifest(),
                conclusion="Synthetic saved analysis for package persistence; not provider output."))
            state.conversation_draft = "Synthetic unsent draft retained across restart."
            state.workspace = "resources"
        saved = app.state.project_workspace.store.update(project["id"], project["version"], fixture)
        snapshot.write_text(saved.model_dump_json(), encoding="utf-8")
    else:
        expected = json.loads(snapshot.read_text(encoding="utf-8"))
        restored = client.get("/api/projects/" + expected["id"]).json()
        assert restored == expected, "Saved work changed after package relocation/restart"
        assert client.get("/api/projects").json() == [expected]
print(json.dumps({"phase": phase, "static_ui": "passed", "provider_requests": 0,
                  "runtime_instructions": "passed", "persistence": "passed"}))
'''


def smoke_archive(archive_path: Path, report: dict):
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("OPENAI_", "VIDEO_", "ANALYSIS_", "CREATIVE_", "STRUCTURE_", "PYTHON"))}
    environment.update({"RUN_LIVE_MODEL_TESTS": "0", "PYTHONDONTWRITEBYTECODE": "1"})
    with tempfile.TemporaryDirectory(prefix="video-anatomy-package-check-") as temporary:
        folder = Path(temporary)
        installation = folder / "installation"
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(installation)
        data = folder / "library"
        environment["VIDEO_ANATOMY_DATA_DIR"] = str(data)
        phases = []
        for phase in ("create", "reopen"):
            if phase == "reopen":
                relocated = folder / "relocated-installation"
                shutil.move(installation, relocated)
                installation = relocated
            root = installation / report["payload_root"]
            completed = subprocess.run([sys.executable, "-I", "-B", "-c", SMOKE, str(root), str(data), phase,
                                        report["application_version"], report["source_commit"]],
                                       cwd=root, env=environment, capture_output=True, text=True, timeout=60)
            if completed.returncode:
                raise RuntimeError(f"Extracted-package {phase} smoke failed:\n{completed.stderr[-6000:]}")
            phases.append(json.loads(completed.stdout.strip().splitlines()[-1]))
        return phases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expected-commit")
    parser.add_argument("--integrity-only", action="store_true", help="Skip the extracted runtime smoke")
    args = parser.parse_args()
    report = verify_archive(args.archive, args.version, args.expected_commit)
    report["sha256"] = hashlib.sha256(args.archive.read_bytes()).hexdigest()
    report["crc"] = "passed"
    report["smoke"] = "not run" if args.integrity_only else smoke_archive(args.archive, report)
    report["macos_installation"] = "not run"
    report["live_api"] = "not run"
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
