"""Restore exact missing originals without changing their evidence identity."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import tempfile
from typing import Annotated, BinaryIO

from fastapi import APIRouter, File, Form, UploadFile

from .media import MediaError, create_playback, inspect_media
from .models import TaskState
from .workflow_errors import WorkflowError


def _asset(state, video_id):
    video = next((item for item in state.videos if item.video_id == video_id), None)
    if video is None:
        raise WorkflowError("video_not_found", "This video does not belong to the task.", 404)
    if video.deleted_at is not None:
        raise WorkflowError("video_deleted", "This reference was deliberately removed. Upload it as a new reference instead.", 410)
    if not video.content_sha256 or not video.storage_id or video.frame_timing is None:
        raise WorkflowError("media_relink_unavailable", "This older record has no verifiable original fingerprint. Upload the file as a new reference.", 422)
    return video


def _target(root: Path, storage_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}\.mp4", storage_id):
        raise WorkflowError("media_relink_unavailable", "This record has no valid managed file location.", 422)
    target = root / storage_id
    if target.is_symlink() or target.resolve().parent != root or (target.exists() and not target.is_file()):
        raise WorkflowError("media_path_conflict", "The managed media location is not a regular file. Restore your library backup or choose a new library.", 422)
    return target


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relink_media(service, task_id: str, expected_version: int, video_id: str,
                 stream: BinaryIO) -> TaskState:
    state = service.store.get(task_id)
    if state.task.version != expected_version:
        raise WorkflowError("version_conflict", "This task changed. Reopen it before restoring its media.")
    video = _asset(state, video_id)
    root = service.media.root.resolve()
    original = _target(root, video.storage_id)
    playback = _target(root, video.playback.storage_id) if video.playback else None
    installed = []
    with tempfile.TemporaryDirectory(prefix=".relink-", dir=root) as temporary:
        staged = Path(temporary) / "original.mp4"
        size, digest = 0, hashlib.sha256()
        with staged.open("xb") as destination:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > service.media.settings.max_bytes:
                    raise MediaError("media_too_large", "The file exceeds the configured upload size limit.")
                digest.update(chunk)
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        if digest.hexdigest() != video.content_sha256:
            raise WorkflowError("media_hash_mismatch", "This file differs from the original. Upload it as a new reference; existing evidence cannot be attached to different video bytes.", 422)
        if original.is_file() and _digest(original) != video.content_sha256:
            raise WorkflowError("media_path_conflict", "A different file occupies the managed location. It was not overwritten. Restore the library from backup or upload a new reference.", 422)
        rebuilt = None
        if playback is not None and not playback.exists():
            properties = inspect_media(staged, service.media.settings)
            if properties["frame_timing"] != video.frame_timing:
                raise WorkflowError("media_relink_timing_mismatch", "The current decoder cannot reproduce the stored frame timing. The saved evidence was not changed.", 422)
            rebuilt = Path(temporary) / video.playback.storage_id
            representation = create_playback(staged, rebuilt, properties, service.media.settings)
            if representation.model_dump(exclude={"storage_id"}) != video.playback.model_dump(exclude={"storage_id"}):
                raise WorkflowError("media_relink_playback_mismatch", "Playback could not be rebuilt with the stored frame mapping. No saved media or evidence was replaced.", 422)
        try:
            def restore(current):
                current_video = _asset(current, video_id)
                if current_video != video:
                    raise WorkflowError("version_conflict", "This reference changed while its file was being checked. Retry from the current task.")
                additions = [(staged, _target(root, video.storage_id))]
                if rebuilt is not None:
                    additions.append((rebuilt, _target(root, video.playback.storage_id)))
                for source, destination in additions:
                    # Hard-link installation is atomic and refuses an existing
                    # path. Temp files share the destination filesystem.
                    try:
                        os.link(source, destination)
                        stat = destination.stat()
                        installed.append((destination, stat.st_dev, stat.st_ino))
                    except FileExistsError:
                        if destination == original and _digest(destination) == video.content_sha256:
                            continue
                        raise WorkflowError("media_path_conflict", "The media location changed while restoring. Nothing was overwritten.", 409) from None
                return bool(installed)
            return service._update(task_id, expected_version, restore)
        except BaseException:
            for path, device, inode in installed:
                if path.is_file() and not path.is_symlink():
                    stat = path.stat()
                    if (stat.st_dev, stat.st_ino) == (device, inode):
                        path.unlink()
            raise


def create_media_repair_router(service) -> APIRouter:
    router = APIRouter()

    @router.post("/api/tasks/{task_id}/videos/{video_id}/relink", response_model=TaskState)
    def relink(task_id: str, video_id: str, file: Annotated[UploadFile, File()],
               expected_version: Annotated[int, Form(ge=1)]):
        return relink_media(service, task_id, expected_version, video_id, file.file)

    return router
