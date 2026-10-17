"""Bounded provider inputs from original media, with explicit source time maps.

Files are temporary and must be consumed inside ``with prepare_media(...)``.
Only sampled JPEGs and video-aligned PCM chunks are provider inputs. Neither
the playback derivative nor its timestamps are used for recognition.
"""
from __future__ import annotations

from bisect import bisect_left
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import struct
import tempfile
import wave

from .media import MediaError, MediaSettings, _run_media
from .models import FrameTiming, VideoAsset

PREPARATION_VERSION = "source-jpeg-pcm-v1"


@dataclass(frozen=True)
class PreparationSettings:
    max_frames: int = 12
    max_image_dimension: int = 1024
    audio_chunk_seconds: float = 60
    max_audio_chunks: int = 3

    def __post_init__(self):
        if type(self.max_frames) is not int or not 1 <= self.max_frames <= 64:
            raise ValueError("max_frames must be an integer between 1 and 64")
        if type(self.max_image_dimension) is not int or not 32 <= self.max_image_dimension <= 1024:
            raise ValueError("max_image_dimension must be an integer between 32 and 1024")
        if not math.isfinite(self.audio_chunk_seconds) or not 0 < self.audio_chunk_seconds <= 120:
            raise ValueError("audio_chunk_seconds must be finite, positive and at most 120")
        if type(self.max_audio_chunks) is not int or not 1 <= self.max_audio_chunks <= 24:
            raise ValueError("max_audio_chunks must be an integer between 1 and 24")


@dataclass(frozen=True)
class PreparedFrame:
    frame_index: int
    source_seconds: float
    path: Path
    width: int
    height: int


@dataclass(frozen=True)
class AudioChunk:
    path: Path
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True)
class PreparedMedia:
    frames: tuple[PreparedFrame, ...]
    audio_chunks: tuple[AudioChunk, ...]
    source_sha256: str
    preparation_version: str = PREPARATION_VERSION


def sample_frame_indices(timing: FrameTiming, maximum: int) -> tuple[int, ...]:
    """Cover source time including first/last frame, never assume constant FPS."""
    if type(maximum) is not int or maximum < 1:
        raise ValueError("maximum must be a positive integer")
    count = min(maximum, timing.frame_count)
    if count == 1:
        return (0,)
    starts = timing.frame_boundaries_seconds[:-1]
    selected = set()
    for index in range(count):
        target = starts[-1] * index / (count - 1)
        after = min(timing.frame_count - 1, bisect_left(starts, target))
        before = max(0, after - 1)
        selected.add(before if target - starts[before] < starts[after] - target else after)
    return tuple(sorted(selected))


def _jpeg_dimensions(path: Path) -> tuple[int, int]:
    # Parse JPEG SOF headers without adding a runtime image-library dependency.
    data = path.read_bytes()
    offset = 2
    while offset < len(data):
        if data[offset] != 0xFF:
            break
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        marker = data[offset]
        offset += 1
        size = int.from_bytes(data[offset:offset + 2], "big")
        if marker in {0xC0, 0xC1, 0xC2}:
            height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
            return width, height
        if size < 2:
            break
        offset += size
    raise MediaError("media_preparation_failed", "A sampled frame could not be read as JPEG.")


def _prepare_audio(path: Path, video: VideoAsset, directory: Path,
                   settings: PreparationSettings, media_settings: MediaSettings) -> tuple[AudioChunk, ...]:
    if video.has_audio is False:
        return ()
    if video.has_audio is not True or video.frame_timing is None:
        raise MediaError("missing_audio_metadata", "Audio presence must be established during media intake before transcription.")
    duration = video.frame_timing.frame_boundaries_seconds[-1]
    if math.ceil(duration / settings.audio_chunk_seconds) > settings.max_audio_chunks:
        raise MediaError("audio_chunk_limit", "The source exceeds the configured audio-chunk limit; increase the limit or use a shorter clip.")
    origin = video.frame_timing.media_start_seconds
    aligned = directory / "aligned.wav"
    # Preserve source PTS until after trimming. Anchor to video frame zero,
    # rather than the first audio sample, so late audio retains its offset.
    _run_media([
        media_settings.ffmpeg, "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
        "-copyts", "-i", str(path), "-map", "0:a:0", "-vn",
        "-af", f"atrim=start={origin:.9f}:end={origin + duration:.9f},asetpts=PTS-({origin:.9f})/TB,aresample=16000:async=1:first_pts=0",
        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", str(aligned),
    ], media_settings.decode_timeout_seconds)
    sample_rate = 16000
    with wave.open(str(aligned), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, sample_rate):
            raise MediaError("media_preparation_failed", "Audio extraction did not produce the required mono 16 kHz PCM.")
        pcm = source.readframes(source.getnframes())
    # Pad absent samples at the tail to the video interval; these are measured
    # track gaps, not claimed silence outside the video or a substitute for ASR.
    total_samples = math.ceil(duration * sample_rate)
    pcm = pcm[:total_samples * 2].ljust(total_samples * 2, b"\0")
    samples_per_chunk = max(1, round(settings.audio_chunk_seconds * sample_rate))
    chunks = []
    for index, first in enumerate(range(0, total_samples, samples_per_chunk)):
        stop = min(total_samples, first + samples_per_chunk)
        target = directory / f"audio-{index:03d}.wav"
        with wave.open(str(target), "wb") as output:
            output.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
            output.writeframes(pcm[first * 2:stop * 2])
        chunks.append(AudioChunk(target, first / sample_rate, min(duration, stop / sample_rate)))
    return tuple(chunks)


@contextmanager
def prepare_media(media_path: Path, video: VideoAsset, settings: PreparationSettings | None = None,
                  media_settings: MediaSettings | None = None):
    settings = settings or PreparationSettings()
    media_settings = media_settings or MediaSettings.from_env()
    path = Path(media_path)
    if video.frame_timing is None or video.intake_status != "ready":
        raise MediaError("missing_frame_timing", "Recognition requires the measured original frame map.")
    try:
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
    except OSError as exc:
        raise MediaError("missing_media", "The saved original media is missing; upload it again.") from exc
    if video.content_sha256 is None or digest != video.content_sha256:
        raise MediaError("source_media_mismatch", "The saved original media no longer matches its intake hash; upload it again.")
    indices = sample_frame_indices(video.frame_timing, settings.max_frames)
    with tempfile.TemporaryDirectory(prefix="video-anatomy-prepared-") as temporary:
        directory = Path(temporary)
        select = "+".join(f"eq(n\\,{index})" for index in indices)
        dimension = settings.max_image_dimension
        _run_media([
            media_settings.ffmpeg, "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
            "-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn",
            "-vf", f"select={select},scale=w='min({dimension},iw)':h='min({dimension},ih)':force_original_aspect_ratio=decrease",
            "-fps_mode", "passthrough", "-frames:v", str(len(indices)), "-q:v", "2",
            str(directory / "frame-%03d.jpg"),
        ], media_settings.decode_timeout_seconds)
        images = sorted(directory.glob("frame-*.jpg"))
        if len(images) != len(indices):
            raise MediaError("media_preparation_failed", "Could not extract every selected source frame.")
        frames = tuple(PreparedFrame(index, video.frame_timing.frame_boundaries_seconds[index], image,
                                     *_jpeg_dimensions(image)) for index, image in zip(indices, images))
        chunks = _prepare_audio(path, video, directory, settings, media_settings)
        yield PreparedMedia(frames, chunks, digest)
