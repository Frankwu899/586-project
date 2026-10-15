"""Real media validation, not merely extension/MIME checks."""
from io import BytesIO
from fractions import Fraction
import subprocess

import pytest

from backend.app.media import MediaError, MediaSettings, MediaStore, inspect_media, probe_frame_timing
from backend.app.timing import frame_to_seconds, seconds_to_frame_range
from scripts.generate_sample_media import generate_sample_media


@pytest.fixture(scope="module")
def sample_path(tmp_path_factory):
    return generate_sample_media(tmp_path_factory.mktemp("actual-media") / "sample.mp4")


def test_generated_sample_is_probeable_and_upload_name_is_never_storage_id(sample_path, tmp_path):
    store = MediaStore(tmp_path / "media")
    with sample_path.open("rb") as source:
        asset = store.save_upload("task_media", "../../private.mp4", source)
    assert asset.duration_seconds == 10
    assert (asset.width, asset.height, asset.video_codec, asset.audio_codec) == (640, 360, "h264", "aac")
    assert asset.has_audio is True
    assert asset.frame_timing.frame_count == 200
    assert asset.frame_timing.frame_boundaries_seconds[-1] == asset.duration_seconds
    assert asset.original_file_name == "private.mp4"
    assert asset.input_method == "file" and asset.sample_key is None
    assert asset.origin.kind == "manual"
    assert asset.public_metrics is None
    assert len(asset.content_sha256) == 64
    assert store.path_for(asset).parent == (tmp_path / "media").resolve()
    assert store.path_for(asset).name != "private.mp4"
    store.path_for(asset).unlink()
    with pytest.raises(MediaError, match="missing"):
        store.path_for(asset)


def test_no_audio_is_reported_as_absent_not_failed(sample_path, tmp_path):
    silent = tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(sample_path), "-map", "0:v:0", "-c:v", "copy", "-an", str(silent)], check=True)
    props = inspect_media(silent)
    assert props["has_audio"] is False
    assert props["audio_codec"] is None


@pytest.mark.parametrize(("payload", "filename", "code"), [
    (b"", "empty.mp4", "empty_media"),
    (b"not a movie", "bad.mp4", "unreadable_media"),
    (b"not a movie", "bad.mov", "unsupported_format"),
])
def test_bad_media_has_actionable_errors_without_persisting_files(payload, filename, code, tmp_path):
    store = MediaStore(tmp_path)
    with pytest.raises(MediaError) as error:
        store.save_upload("task_bad", filename, BytesIO(payload))
    assert error.value.code == code
    assert list(tmp_path.iterdir()) == []


def test_configured_size_duration_and_dimensions_are_enforced(sample_path, tmp_path):
    with pytest.raises(MediaError) as size:
        MediaStore(tmp_path / "size", MediaSettings(max_bytes=4)).save_upload("task_bad", "large.mp4", BytesIO(b"12345"))
    assert size.value.code == "media_too_large"
    assert list((tmp_path / "size").iterdir()) == []
    with pytest.raises(MediaError) as duration:
        inspect_media(sample_path, MediaSettings(max_duration_seconds=9))
    assert duration.value.code == "media_too_long"
    with pytest.raises(MediaError) as dimensions:
        inspect_media(sample_path, MediaSettings(max_width=320))
    assert dimensions.value.code == "unsupported_dimensions"


def test_actual_codec_is_checked_even_with_mp4_extension(tmp_path):
    unsupported = tmp_path / "mpeg4.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=64x64:d=1", "-c:v", "mpeg4", str(unsupported)], check=True)
    with pytest.raises(MediaError) as error:
        inspect_media(unsupported)
    assert error.value.code == "unsupported_codec"


def test_sample_provenance_is_only_stamped_on_generated_media(tmp_path):
    store = MediaStore(tmp_path)
    sample = store.create_sample("task_sample")
    assert sample.input_method == "sample"
    assert sample.sample_key == "lumacup_shapes_v1"
    assert sample.origin.kind == "sample"
    assert store.path_for(sample).is_file()


@pytest.mark.parametrize("rate", ["24", "25", "30", "60", "24000/1001", "30000/1001", "60000/1001"])
def test_different_integer_and_fractional_rates_index_actual_frames(rate, tmp_path):
    path = tmp_path / "rate.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=64x64:r={rate}",
        "-frames:v", "12", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ], check=True)
    properties = inspect_media(path)
    timing = properties["frame_timing"]
    expected_rate = Fraction(rate)
    assert Fraction(timing.fps_numerator, timing.fps_denominator) == expected_rate
    assert timing.frame_count == 12
    assert timing.rate_mode == "constant"
    assert timing.source == "probed"
    assert timing.frame_boundaries_seconds == pytest.approx(
        [float(frame / expected_rate) for frame in range(13)], abs=0.000001,
    )
    assert properties["duration_seconds"] == timing.frame_boundaries_seconds[-1]
    assert seconds_to_frame_range(*timing.frame_boundaries_seconds[5:7], timing) == (5, 6)


def test_variable_frame_rate_uses_actual_presentations_not_average_rate(tmp_path):
    path = tmp_path / "variable.mp4"
    # Ten consecutive frames, then every other frame: 30 fps followed by 15 fps.
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x64:r=30:d=1",
        "-vf", "select='lt(n,10)+gte(n,10)*not(mod(n,2))'", "-fps_mode", "vfr",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ], check=True)
    timing = inspect_media(path)["frame_timing"]
    expected_starts = [frame / 30 for frame in [*range(10), *range(10, 30, 2)]]
    assert timing.frame_count == 20
    assert timing.rate_mode == "variable"
    assert timing.frame_boundaries_seconds[:-1] == pytest.approx(expected_starts, abs=0.000001)
    assert frame_to_seconds(10, timing) == pytest.approx(10 / 30, abs=0.000001)
    assert frame_to_seconds(15, timing) == pytest.approx(20 / 30, abs=0.000001)
    assert seconds_to_frame_range(10 / 30, 12 / 30, timing) == (10, 11)
    assert abs(frame_to_seconds(10, timing) - 10 * timing.fps_denominator / timing.fps_numerator) > 0.05
    assert timing.frame_boundaries_seconds[-1] > expected_starts[-1]


def test_nonzero_stream_origin_is_normalized_and_audio_tail_is_not_video_duration(tmp_path):
    shifted = tmp_path / "shifted.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x64:r=24:d=0.5",
        "-c:v", "libx264", "-output_ts_offset", "2", str(shifted),
    ], check=True)
    timing = probe_frame_timing(shifted)
    assert timing.frame_count == 12
    assert timing.frame_boundaries_seconds[0] == 0
    assert timing.frame_boundaries_seconds[-1] == 0.5
    assert timing.media_start_seconds == 2

    audio_tail = tmp_path / "audio-tail.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x64:r=24:d=0.5",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1.5", "-c:v", "libx264",
        "-c:a", "aac", str(audio_tail),
    ], check=True)
    properties = inspect_media(audio_tail, MediaSettings(max_duration_seconds=0.75))
    assert properties["has_audio"] is True
    assert properties["duration_seconds"] == 0.5
    assert properties["frame_timing"].frame_count == 12
