"""Reversible source-coordinate capture regions, separate from evidence and originals.

Suggestions are deliberately conservative edge-bar heuristics, not semantic UI
recognition. They never become active without the user's explicit save.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .media import MediaError, _run_media
from .models import TaskState, validate_state
from .storage import WorkflowError


class Rect(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def inside(self):
        if self.x + self.width > 1.0000001 or self.y + self.height > 1.0000001:
            raise ValueError("The rectangle must stay inside the original frame.")
        return self


class ContentRegion(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    revision: int = Field(default=0, ge=0)
    source_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    crop: Rect = Field(default_factory=lambda: Rect(x=0, y=0, width=1, height=1))
    exclusions: list[Rect] = Field(default_factory=list, max_length=8)

    @property
    def fingerprint(self):
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class RegionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    expected_version: int = Field(ge=1)
    expected_revision: int = Field(ge=0)
    crop: Rect
    exclusions: list[Rect] = Field(default_factory=list, max_length=8)


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS content_regions (
        task_id TEXT NOT NULL, video_id TEXT NOT NULL, revision INTEGER NOT NULL,
        payload TEXT NOT NULL, PRIMARY KEY(task_id, video_id))""")


def get_content_region(store, task_id, video) -> ContentRegion:
    with store._connect() as db:
        _table(db)
        row = db.execute("SELECT payload FROM content_regions WHERE task_id=? AND video_id=?", (task_id, video.video_id)).fetchone()
    region = ContentRegion.model_validate_json(row[0]) if row else ContentRegion(source_sha256=video.content_sha256)
    if region.source_sha256 != video.content_sha256:
        raise WorkflowError("region_source_changed", "The content area belongs to different source bytes. Restore the original video.", 409)
    return region


def region_from_database(store, task_id, video) -> ContentRegion:
    """Read an already-created table without opening a write transaction."""
    with store._connect() as db:
        row = db.execute("SELECT payload FROM content_regions WHERE task_id=? AND video_id=?", (task_id, video.video_id)).fetchone()
    region = ContentRegion.model_validate_json(row[0]) if row else ContentRegion(source_sha256=video.content_sha256)
    if region.source_sha256 != video.content_sha256:
        raise WorkflowError("region_source_changed", "The content area belongs to different source bytes.", 409)
    return region


def _video(state, video_id):
    video = next((v for v in state.videos if v.video_id == video_id), None)
    if video is None:
        raise WorkflowError("video_not_found", "This video does not belong to the task.", 404)
    if video.deleted_at is not None or video.intake_status != "ready":
        raise WorkflowError("video_unavailable", "This source is unavailable. Its history remains saved.", 409)
    return video


def save_content_region(svc, task_id, video_id, body: RegionUpdate) -> TaskState:
    # Region and invalidation share one SQLite transaction, so recognition cannot
    # observe new settings with an old task version or a partially saved region.
    from .service import invalidate_references
    with svc.store._connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _table(db)
        row = db.execute("SELECT payload FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise WorkflowError("task_not_found", "This task does not exist.", 404)
        state = svc.store._read_state(db, task_id, row[0])
        if state.task.version != body.expected_version:
            raise WorkflowError("version_conflict", "This task changed. Reopen the content-area editor and retry.")
        video = _video(state, video_id)
        row = db.execute("SELECT payload FROM content_regions WHERE task_id=? AND video_id=?", (task_id, video_id)).fetchone()
        old = ContentRegion.model_validate_json(row[0]) if row else ContentRegion(source_sha256=video.content_sha256)
        if old.revision != body.expected_revision:
            raise WorkflowError("region_conflict", "The content area changed in another window. Reopen it before saving.")
        new = ContentRegion(revision=old.revision + 1, source_sha256=video.content_sha256,
                            crop=body.crop, exclusions=body.exclusions)
        if new.crop == old.crop and new.exclusions == old.exclusions:
            return state
        svc.store._require_editors_clear(db, state, ("analysis",), None)
        if state.task.mode == "sample":
            raise WorkflowError("sample_region_unavailable", "The fictional sample has fixed evidence. Import your own video to analyze a content area.", 422)
        db.execute("INSERT OR REPLACE INTO content_regions VALUES (?,?,?,?)", (task_id, video_id, new.revision, new.model_dump_json()))
        if state.task.current_video_id == video_id:
            state.task.current_analysis = None
            state.task.progress = "analysis"
            invalidate_references(state)
        state.task.version += 1
        state = validate_state(state)
        db.execute("UPDATE tasks SET version=?,payload=? WHERE id=?", (state.task.version, state.model_dump_json(), task_id))
        return state


def region_filters(region: ContentRegion) -> list[str]:
    """Apply normalized display coordinates after FFmpeg's source autorotation.

    Encoded width/height can be swapped by display metadata. Expressions use the
    actual decoded input dimensions, matching the browser's presented video.
    """
    filters = []
    for rect in region.exclusions:
        filters.append(f"drawbox=x=iw*{rect.x:.9f}:y=ih*{rect.y:.9f}:"
                       f"w=iw*{rect.width:.9f}:h=ih*{rect.height:.9f}:color=black:t=fill")
    rect = region.crop
    if rect != Rect(x=0, y=0, width=1, height=1):
        # Crop keeps at least two output pixels, with an unchanged source clock.
        filters.append(f"crop=w='max(2,ceil(iw*{rect.x + rect.width:.9f})-floor(iw*{rect.x:.9f}))':"
                       f"h='max(2,ceil(ih*{rect.y + rect.height:.9f})-floor(ih*{rect.y:.9f}))':"
                       f"x='floor(iw*{rect.x:.9f})':y='floor(ih*{rect.y:.9f})':exact=1")
    return filters


def suggest_content_region(path: Path, video, media_settings) -> dict:
    """Inspect five downsampled frames for persistent near-flat edge bars.

    Only edge-connected rows/columns qualify; static logos and internal price
    panels are not used as a reason to exclude anything. Suggestions are advisory.
    """
    from .media_preparation import sample_frame_indices
    if not video.frame_timing:
        raise MediaError("missing_frame_timing", "Measured source timing is required.")
    with path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != video.content_sha256:
            raise MediaError("source_media_mismatch", "Saved source bytes no longer match intake.")
    indices = sample_frame_indices(video.frame_timing, 5)
    width, height = 96, 160
    with tempfile.TemporaryDirectory(prefix="video-anatomy-region-") as folder:
        output = Path(folder) / "samples.gray"
        select = "+".join(f"eq(n\\,{i})" for i in indices)
        _run_media([media_settings.ffmpeg, "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
                    "-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn", "-vf",
                    f"select={select},scale={width}:{height},format=gray", "-fps_mode", "passthrough",
                    "-frames:v", str(len(indices)), "-f", "rawvideo", str(output)], media_settings.decode_timeout_seconds)
        data = output.read_bytes()
    size = width * height
    if len(data) != size * len(indices):
        raise MediaError("region_suggestion_failed", "Not all source frames could be checked.")
    frames = [data[i*size:(i+1)*size] for i in range(len(indices))]
    def flat(values):
        # Sparse icons/text may sit on a uniform edge bar. Neither temporal
        # stillness alone nor an interior rectangle is treated as platform UI.
        return max(sum(p < 28 for p in values), sum(p > 228 for p in values)) / len(values) >= .88
    rows = [all(flat(frame[y*width:(y+1)*width]) for frame in frames) for y in range(height)]
    cols = [all(flat(frame[x::width]) for frame in frames) for x in range(width)]
    def edge_count(values, limit):
        count = 0
        for item in values[:limit]:
            if not item:
                break
            count += 1
        return count
    top = edge_count(rows, int(height * .24))
    bottom = edge_count(rows[::-1], int(height * .28))
    left = edge_count(cols, int(width * .16))
    right = edge_count(cols[::-1], int(width * .16))
    # Fewer than three scaled pixels is too little to distinguish codec padding.
    top, bottom, left, right = [v if v >= 3 else 0 for v in (top, bottom, left, right)]
    crop = Rect(x=left/width, y=top/height, width=(width-left-right)/width, height=(height-top-bottom)/height)
    found = any((top, bottom, left, right))
    return {"crop": crop.model_dump(), "exclusions": [], "method": "conservative_edge_bars_v1", "sample_frames": list(indices),
            "requires_review": True, "suggestion_found": found,
            "message": "Possible edge bars found. Check the start, middle and end before saving; captions, logos and prices may be valid content." if found else "No reliable edge bars found. Keep the full frame or adjust the content area manually. Static content is not automatically removed."}


def create_content_region_router(svc):
    router = APIRouter()
    prefix = "/api/tasks/{task_id}/videos/{video_id}/content-region"
    @router.get(prefix, response_model=ContentRegion)
    def get_region(task_id: str, video_id: str):
        video = _video(svc.store.get(task_id), video_id)
        return get_content_region(svc.store, task_id, video)
    @router.post(prefix, response_model=TaskState)
    def save_region(task_id: str, video_id: str, body: RegionUpdate):
        return save_content_region(svc, task_id, video_id, body)
    @router.post(prefix + "/suggest")
    def suggest_region(task_id: str, video_id: str):
        video = _video(svc.store.get(task_id), video_id)
        return suggest_content_region(svc.media.path_for(video), video, svc.media.settings)
    return router
