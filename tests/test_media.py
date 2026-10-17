"""Real media validation, not merely extension/MIME checks."""
from io import BytesIO
from fractions import Fraction
import hashlib
import subprocess

import pytest

from backend.app.media import (MediaError, MediaSettings, MediaStore, inspect_media, probe_frame_timing,
                               validate_frame_correspondence)
from backend.app.timing import frame_to_seconds, seconds_to_frame_range
from backend.app.media_preparation import PreparationSettings
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


def make_hevc_fixture(path, *, audio=False, variable=False, rotation=False):
    """Small SDR Main fixture with a unique color and left marker per frame."""
    colors = [(220, 15, 15), (15, 220, 15), (15, 15, 220), (220, 220, 15),
              (220, 15, 220), (15, 220, 220), (120, 35, 220), (220, 120, 35)]
    pixels = bytearray()
    for color in colors:
        for _ in range(48):
            for x in range(64):
                pixels.extend((240, 240, 240) if x < 8 else color)
    command = ["ffmpeg", "-v", "error", "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "64x48",
               "-framerate", "12", "-i", "pipe:0"]
    if audio:
        command += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1.2", "-c:a", "aac"]
    if variable:
        command += ["-vf", "setpts=if(lt(N\\,4)\\,N\\,4+(N-4)*2)/(12*TB)", "-fps_mode", "vfr"]
    command += ["-c:v", "libx265", "-x265-params", "pools=1:frame-threads=1:log-level=error", "-crf", "12",
                "-pix_fmt", "yuv420p", "-output_ts_offset", "2", str(path)]
    subprocess.run(command, input=bytes(pixels), check=True, capture_output=True)
    if rotation:
        rotated = path.with_name("rotated.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-display_rotation:v:0", "90", "-i", str(path),
                        "-c", "copy", "-copyts", str(rotated)], check=True)
        rotated.replace(path)
    return path


@pytest.mark.parametrize(("audio", "variable", "rotation"), [(False, False, False), (True, True, False), (False, True, True)])
def test_hevc_original_and_independent_proxy_preserve_frame_identity(tmp_path, audio, variable, rotation):
    source = make_hevc_fixture(tmp_path / "source.mp4", audio=audio, variable=variable, rotation=rotation)
    original = source.read_bytes()
    before = inspect_media(source)
    store = MediaStore(tmp_path / "saved")
    with source.open("rb") as stream:
        asset = store.save_upload("task_hevc", "source.mp4", stream)
    assert asset.video_codec == "hevc"
    assert asset.content_sha256 == hashlib.sha256(original).hexdigest()
    assert store.path_for(asset).read_bytes() == original
    assert asset.frame_timing == before["frame_timing"]
    assert asset.frame_timing.frame_count == 8
    assert asset.frame_timing.rate_mode == ("variable" if variable else "constant")
    assert asset.playback is not None and asset.playback.storage_id != asset.storage_id
    assert asset.playback.video_codec == "h264"
    assert asset.playback.audio_codec == ("aac" if audio else None)
    proxy = inspect_media(store.playback_path_for(asset))
    assert proxy["video_codec"] == "h264"
    assert proxy["frame_timing"] == asset.playback.frame_timing
    assert asset.playback.frame_timing.frame_count == asset.frame_timing.frame_count
    assert asset.playback.frame_timing.media_start_seconds != asset.frame_timing.media_start_seconds
    # Same count/duration is insufficient: validate the visibly distinct frame
    # sequence and automatic rotation independently of intake's own check.
    validate_frame_correspondence(source, store.playback_path_for(asset), asset.frame_timing,
                                  asset.playback.frame_timing, store.settings)
    with store.prepare_for_analysis(asset, PreparationSettings(max_frames=2)) as prepared:
        assert [frame.frame_index for frame in prepared.frames] == [0, 7]
        assert prepared.frames[-1].source_seconds == asset.frame_timing.frame_boundaries_seconds[7]
        assert (prepared.frames[0].width, prepared.frames[0].height) == ((48, 64) if rotation else (64, 48))
        assert bool(prepared.audio_chunks) == audio


def test_repeated_hevc_uploads_keep_independent_original_and_proxy_storage(tmp_path):
    source = make_hevc_fixture(tmp_path / "source.mp4")
    store = MediaStore(tmp_path / "saved")
    assets = [store.save_upload("task_hevc", source.name, BytesIO(source.read_bytes())) for _ in range(2)]
    assert assets[0].content_sha256 == assets[1].content_sha256
    assert len({asset.storage_id for asset in assets} | {asset.playback.storage_id for asset in assets}) == 4
    assert all(store.path_for(asset).is_file() and store.playback_path_for(asset).is_file() for asset in assets)


def test_same_count_reordered_proxy_is_rejected(tmp_path):
    source = make_hevc_fixture(tmp_path / "source.mp4")
    reversed_path = tmp_path / "reversed.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(source), "-vf", "reverse", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(reversed_path)], check=True)
    source_timing, proxy_timing = probe_frame_timing(source), probe_frame_timing(reversed_path)
    assert source_timing.frame_count == proxy_timing.frame_count
    with pytest.raises(MediaError) as failure:
        validate_frame_correspondence(source, reversed_path, source_timing, proxy_timing, MediaSettings())
    assert failure.value.code == "playback_frame_mismatch"


def test_proxy_validation_failure_removes_both_original_and_derivative(tmp_path, monkeypatch):
    source = make_hevc_fixture(tmp_path / "source.mp4")
    store = MediaStore(tmp_path / "saved")
    def fail(*_args):
        raise MediaError("playback_frame_mismatch", "Synthetic correspondence failure")
    monkeypatch.setattr("backend.app.media.validate_frame_correspondence", fail)
    with source.open("rb") as stream, pytest.raises(MediaError):
        store.save_upload("task_hevc", "source.mp4", stream)
    assert list(store.root.iterdir()) == []


def test_hevc_10bit_is_explicitly_outside_supported_profile(tmp_path):
    path = tmp_path / "ten-bit.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x48:r=12:d=0.25",
                    "-c:v", "libx265", "-x265-params", "pools=1:frame-threads=1:log-level=error",
                    "-pix_fmt", "yuv420p10le", str(path)], check=True, capture_output=True)
    with pytest.raises(MediaError) as failure:
        inspect_media(path)
    assert failure.value.code == "unsupported_hevc_profile"
