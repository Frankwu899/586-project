"""Constrained local MP4 intake. Filenames never become storage identifiers."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
import hashlib
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import BinaryIO
from uuid import uuid4

from .models import FrameTiming, Origin, PlaybackRepresentation, VideoAsset

SAMPLE_KEY = "lumacup_shapes_v1"
SAMPLE_DESCRIPTION = "Fictional generated LumaCup shapes/cards/tones; lumacup_shapes_v1; no human speech or real product evidence."


class MediaError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class MediaSettings:
    max_bytes: int = 50 * 1024 * 1024
    max_duration_seconds: float = 180
    max_width: int = 1920
    max_height: int = 1920
    probe_timeout_seconds: float = 15
    decode_timeout_seconds: float = 60
    transcode_timeout_seconds: float = 180
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"

    def __post_init__(self) -> None:
        for key in ("max_bytes", "max_duration_seconds", "max_width", "max_height", "probe_timeout_seconds", "decode_timeout_seconds", "transcode_timeout_seconds"):
            value = getattr(self, key)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be finite and positive")

    @classmethod
    def from_env(cls) -> "MediaSettings":
        return cls(
            max_bytes=int(os.getenv("VIDEO_MAX_BYTES", str(50*1024*1024))),
            max_duration_seconds=float(os.getenv("VIDEO_MAX_DURATION_SECONDS", "180")),
            max_width=int(os.getenv("VIDEO_MAX_WIDTH", "1920")),
            max_height=int(os.getenv("VIDEO_MAX_HEIGHT", "1920")),
            probe_timeout_seconds=float(os.getenv("VIDEO_PROBE_TIMEOUT_SECONDS", "15")),
            decode_timeout_seconds=float(os.getenv("VIDEO_DECODE_TIMEOUT_SECONDS", "60")),
            transcode_timeout_seconds=float(os.getenv("VIDEO_TRANSCODE_TIMEOUT_SECONDS", "180")),
            ffmpeg=os.getenv("FFMPEG_BIN", "ffmpeg"),
            ffprobe=os.getenv("FFPROBE_BIN", "ffprobe"),
        )


def _run_media(command: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise MediaError("media_tool_unavailable", "Install ffmpeg and ffprobe to inspect local video files.") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaError("media_inspection_timeout", "Media inspection exceeded the configured time limit; try a smaller clip.") from exc
    if result.returncode:
        raise MediaError("unreadable_media", "The file could not be decoded as supported MP4 video. Export a complete H.264 or SDR HEVC MP4 with optional AAC audio and try again.")
    return result


def _positive_number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def probe_frame_timing(path: Path, settings: MediaSettings | None = None) -> FrameTiming:
    """Index decoded video presentation timestamps without extracting images.

    The first presented frame is reference time zero; its original timestamp is
    retained as media_start_seconds for the browser's playback clock. Stream duration supplies
    the exclusive final boundary, so a longer AAC track cannot add video frames.
    If duration is absent, use the final decoded frame's duration, then the last
    observed interval. Average/rational FPS is only display metadata; seeks and
    quantization always use the actual boundary map, including for VFR input.
    """
    settings = settings or MediaSettings.from_env()
    path = Path(path)
    if not path.is_file():
        raise MediaError("missing_media", "The saved media file is missing; upload it again.")
    result = _run_media([
        settings.ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe",
        "-select_streams", "v:0", "-show_frames", "-show_streams", "-show_entries",
        "stream=avg_frame_rate,r_frame_rate,duration,start_time:frame=best_effort_timestamp_time,duration_time,pkt_duration_time",
        "-of", "json", str(path),
    ], settings.decode_timeout_seconds)
    try:
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        # ffprobe emits decoded presentation order. Sorting would hide a broken
        # timestamp sequence and make frame indices disagree with extraction.
        frames = data["frames"]
        timestamps = [float(frame["best_effort_timestamp_time"]) for frame in frames]
        if not timestamps or not all(math.isfinite(value) for value in timestamps):
            raise ValueError("missing/nonfinite frame timestamps")
        if any(after <= before for before, after in zip(timestamps, timestamps[1:])):
            raise ValueError("ambiguous frame timestamps")
        origin = timestamps[0]
        starts = [round(value - origin, 9) for value in timestamps]
        rate = None
        for key in ("avg_frame_rate", "r_frame_rate"):
            try:
                candidate = Fraction(stream.get(key, "0/1"))
                if candidate > 0:
                    rate = candidate
                    break
            except (TypeError, ValueError, ZeroDivisionError):
                continue
        duration = _positive_number(stream.get("duration"))
        stream_start = float(stream.get("start_time", origin))
        endpoint = stream_start + duration - origin if duration is not None else None
        if endpoint is None or not math.isfinite(endpoint) or endpoint <= starts[-1]:
            last_duration = (_positive_number(frames[-1].get("duration_time"))
                             or _positive_number(frames[-1].get("pkt_duration_time")))
            if last_duration is None:
                last_duration = starts[-1] - starts[-2] if len(starts) > 1 else float(1 / rate) if rate else None
            if last_duration is None:
                raise ValueError("missing final frame duration")
            endpoint = starts[-1] + last_duration
        endpoint = round(endpoint, 9)
        if endpoint > settings.max_duration_seconds:
            raise MediaError("media_too_long", f"Video exceeds the configured {settings.max_duration_seconds:g}-second limit.")
        if rate is None:
            rate = (Fraction(len(frames)) / Fraction(str(endpoint))).limit_denominator(1_000_000)
        boundaries = [*starts, endpoint]
        intervals = [after - before for before, after in zip(boundaries, boundaries[1:])]
        tolerance = max(0.000002, float(1 / rate) * 0.005)
        variable = max(intervals) - min(intervals) > tolerance
        return FrameTiming(
            fps_numerator=rate.numerator, fps_denominator=rate.denominator,
            frame_count=len(frames), frame_boundaries_seconds=boundaries,
            media_start_seconds=origin, rate_mode="variable" if variable else "constant", source="probed",
        )
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, MediaError):
            raise
        raise MediaError("invalid_frame_timing", "Video frame timing could not be read. Export a complete H.264 MP4 and try again.") from exc


def inspect_media(path: Path, settings: MediaSettings | None = None) -> dict:
    settings = settings or MediaSettings.from_env()
    path = Path(path)
    if not path.is_file():
        raise MediaError("missing_media", "The saved media file is missing; upload it again.")
    size = path.stat().st_size
    if size == 0:
        raise MediaError("empty_media", "The uploaded file is empty.")
    if size > settings.max_bytes:
        raise MediaError("media_too_large", f"Video exceeds the configured {settings.max_bytes}-byte limit.")
    result = _run_media([settings.ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe",
                         "-show_format", "-show_streams", "-of", "json", str(path)], settings.probe_timeout_seconds)
    try:
        data = json.loads(result.stdout)
        streams = data["streams"]
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        if len(video_streams) != 1:
            raise MediaError("unsupported_streams", "Use an MP4 containing exactly one video stream.")
        video = video_streams[0]
        if "mp4" not in data["format"].get("format_name", "").split(","):
            raise MediaError("unsupported_format", "Use MP4 containing H.264 or SDR HEVC video and optional AAC audio.")
        if video.get("codec_name") not in {"h264", "hevc"} or any(s.get("codec_name") != "aac" for s in audio_streams):
            raise MediaError("unsupported_codec", "Use H.264 or SDR HEVC video with AAC audio, or without an audio track.")
        if video.get("codec_name") == "hevc" and (
            video.get("pix_fmt") != "yuv420p" or video.get("profile") != "Main"
            or video.get("color_transfer") in {"smpte2084", "arib-std-b67"}
        ):
            raise MediaError("unsupported_hevc_profile", "HEVC intake supports SDR Main 8-bit 4:2:0. Export HDR, 10-bit or other profiles to SDR H.264 first.")
        if len(audio_streams) > 1:
            raise MediaError("unsupported_streams", "Use a video with at most one AAC audio stream.")
        # Video duration takes precedence over container duration (which can
        # include an audio tail). The frame probe below supplies the final value.
        duration = float(video.get("duration", data["format"].get("duration", "nan")))
        if not math.isfinite(duration) or duration <= 0:
            raise MediaError("invalid_duration", "A finite positive video duration could not be measured.")
        if duration > settings.max_duration_seconds:
            raise MediaError("media_too_long", f"Video exceeds the configured {settings.max_duration_seconds:g}-second limit.")
        width, height = int(video["width"]), int(video["height"])
        if width <= 0 or height <= 0 or width > settings.max_width or height > settings.max_height:
            raise MediaError("unsupported_dimensions", f"Video dimensions must be positive and at most {settings.max_width} by {settings.max_height} pixels.")
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, MediaError):
            raise
        raise MediaError("unreadable_media", "Media properties could not be read; export a standard H.264/AAC MP4.") from exc
    # Probe metadata alone can accept truncated files. Decode every stream before accepting.
    _run_media([settings.ffmpeg, "-hide_banner", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
                "-i", str(path), "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-"], settings.decode_timeout_seconds)
    timing = probe_frame_timing(path, settings)
    return {"duration_seconds": timing.frame_boundaries_seconds[-1], "frame_timing": timing,
            "width": width, "height": height,
            "video_codec": video["codec_name"], "audio_codec": "aac" if audio_streams else None,
            "has_audio": bool(audio_streams)}


def validate_frame_correspondence(source: Path, derivative: Path, source_timing: FrameTiming,
                                  derivative_timing: FrameTiming, settings: MediaSettings) -> None:
    """Verify presentation order/count and decoded appearance, not just duration.

    The encoder uses passthrough sync (no frame dropping/duplication). Independently
    decode both sequences with the same autorotation and compare every 32px RGB
    thumbnail, allowing modest lossy-codec error. This is a bounded-memory guard
    against reorder/drop/rotation mistakes, not a claim of lossless color fidelity.
    """
    if source_timing.frame_count != derivative_timing.frame_count:
        raise MediaError("playback_frame_mismatch", "Playback conversion changed the source frame count; export SDR H.264 and try again.")
    with tempfile.TemporaryDirectory(prefix="video-anatomy-correspondence-") as temporary:
        paths = []
        for index, media in enumerate((source, derivative)):
            raw = Path(temporary) / f"{index}.rgb"
            _run_media([
                settings.ffmpeg, "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
                "-i", str(media), "-map", "0:v:0", "-an", "-sn", "-dn",
                "-vf", "scale=32:32:flags=area", "-fps_mode", "passthrough",
                "-pix_fmt", "rgb24", "-f", "rawvideo", str(raw),
            ], settings.decode_timeout_seconds)
            paths.append(raw)
        frame_bytes = 32 * 32 * 3
        if any(path.stat().st_size != source_timing.frame_count * frame_bytes for path in paths):
            raise MediaError("playback_frame_mismatch", "Playback conversion could not preserve every source frame.")
        with paths[0].open("rb") as original, paths[1].open("rb") as proxy:
            for _ in range(source_timing.frame_count):
                left, right = original.read(frame_bytes), proxy.read(frame_bytes)
                difference = sum(abs(a - b) for a, b in zip(left, right)) / frame_bytes
                if difference > 12:
                    raise MediaError("playback_frame_mismatch", "Playback frame order or appearance could not be validated; export SDR H.264 and try again.")


def create_playback(source: Path, target: Path, properties: dict, settings: MediaSettings) -> PlaybackRepresentation:
    """Produce an independently clocked H.264 derivative; never modify source."""
    try:
        _run_media([
            settings.ffmpeg, "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
            "-copyts", "-start_at_zero", "-i", str(source), "-map", "0:v:0", "-map", "0:a?",
            "-map_metadata", "-1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-fps_mode", "passthrough", "-c:a", "aac",
            "-movflags", "+faststart", "-f", "mp4", str(target),
        ], settings.transcode_timeout_seconds)
        # A derivative may be larger than its uploaded source; the input size
        # cap remains an intake limit, not a reason to skip derivative probing.
        from dataclasses import replace
        playback = inspect_media(target, replace(settings, max_bytes=max(settings.max_bytes, target.stat().st_size)))
        if playback["video_codec"] != "h264" or playback["has_audio"] != properties["has_audio"]:
            raise MediaError("playback_conversion_failed", "Playback conversion did not preserve the supported video/audio streams.")
        validate_frame_correspondence(source, target, properties["frame_timing"], playback["frame_timing"], settings)
        return PlaybackRepresentation(storage_id=target.name, video_codec="h264",
                                      audio_codec=playback["audio_codec"], duration_seconds=playback["duration_seconds"],
                                      frame_timing=playback["frame_timing"])
    except BaseException:
        target.unlink(missing_ok=True)
        raise


class MediaStore:
    def __init__(self, root: Path, settings: MediaSettings | None = None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings = settings or MediaSettings.from_env()

    def path_for(self, video: VideoAsset) -> Path:
        """Original bytes for recognition, hashing and source timing."""
        return self._path_for_id(video.storage_id)

    def playback_path_for(self, video: VideoAsset) -> Path:
        """Browser media uses the derivative and its own frame_timing if present."""
        return self._path_for_id(video.playback.storage_id if video.playback else video.storage_id)

    def _path_for_id(self, storage_id: str | None) -> Path:
        if storage_id is None or not re.fullmatch(r"[a-f0-9]{32}\.mp4", storage_id):
            raise MediaError("missing_media", "This record has no playable saved media; upload a video or load the generated sample.")
        path = self.root / storage_id
        if not path.is_file() or path.resolve().parent != self.root:
            raise MediaError("missing_media", "The saved media file is missing; upload it again.")
        return path

    def prepare_for_analysis(self, video: VideoAsset, settings=None):
        from .media_preparation import prepare_media
        return prepare_media(self.path_for(video), video, settings=settings, media_settings=self.settings)

    def save_upload(self, task_id: str, original_name: str, stream: BinaryIO, source_url: str | None = None) -> VideoAsset:
        if Path(original_name).suffix.lower() != ".mp4":
            raise MediaError("unsupported_format", "Choose an .mp4 file with H.264 or SDR HEVC video and optional AAC audio.")
        storage_id = f"{uuid4().hex}.mp4"
        target = self.root / storage_id
        partial = self.root / f"{storage_id}.part"
        playback_target = self.root / f"{uuid4().hex}.mp4"
        try:
            size = 0
            digest = hashlib.sha256()
            with partial.open("xb") as destination:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.settings.max_bytes:
                        raise MediaError("media_too_large", f"Video exceeds the configured {self.settings.max_bytes}-byte limit.")
                    digest.update(chunk)
                    destination.write(chunk)
            properties = inspect_media(partial, self.settings)
            playback = create_playback(partial, playback_target, properties, self.settings) if properties["video_codec"] == "hevc" else None
            partial.rename(target)
            return VideoAsset(video_id=f"video_{uuid4().hex}", task_id=task_id, input_method="file",
                              storage_id=storage_id, content_sha256=digest.hexdigest(), original_file_name=Path(original_name.replace("\\", "/")).name,
                              source_url=source_url, intake_status="ready", playback=playback, **properties,
                              origin=Origin(kind="manual", description="User uploaded media; recognition has not been performed."))
        except BaseException:
            partial.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            playback_target.unlink(missing_ok=True)
            raise

    def create_sample(self, task_id: str) -> VideoAsset:
        from scripts.generate_sample_media import generate_sample_media
        with tempfile.TemporaryDirectory(prefix="video-anatomy-sample-") as temporary:
            path = generate_sample_media(Path(temporary) / f"{SAMPLE_KEY}.mp4", self.settings.ffmpeg)
            with path.open("rb") as stream:
                video = self.save_upload(task_id, path.name, stream)
        return VideoAsset.model_validate({**video.model_dump(), "input_method": "sample", "sample_key": SAMPLE_KEY,
                                         "origin": Origin(kind="sample", description=SAMPLE_DESCRIPTION)})
