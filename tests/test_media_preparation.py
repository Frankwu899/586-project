"""Offline source-media preparation, including time offsets and cleanup."""
from array import array
import hashlib
import subprocess
from types import SimpleNamespace
import wave

import pytest

from backend.app.media import MediaError, MediaStore
from backend.app.media_preparation import (
    AudioChunk, PreparationSettings, _prepare_audio, prepare_media, sample_frame_indices,
    validate_audio_chunk,
)
from backend.app.media import MediaSettings
from backend.app.models import FrameTiming


def _upload(path, tmp_path):
    store = MediaStore(tmp_path / "saved")
    with path.open("rb") as stream:
        asset = store.save_upload("task_prepare", path.name, stream)
    return store, asset


def test_sampling_uses_vfr_boundaries_and_keeps_last_source_frame():
    timing = FrameTiming(fps_numerator=10, fps_denominator=1, frame_count=6,
                         frame_boundaries_seconds=[0, .01, .02, .03, .4, .9, 1], rate_mode="variable")
    assert sample_frame_indices(timing, 3) == (0, 4, 5)
    assert sample_frame_indices(timing, 1) == (0,)


def test_sampled_images_use_source_indices_and_are_removed_after_use(tmp_path):
    source = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=128x96:r=24:d=0.5",
                    "-c:v", "libx264", "-output_ts_offset", "2", str(source)], check=True)
    store, video = _upload(source, tmp_path)
    with store.prepare_for_analysis(video, PreparationSettings(max_frames=4, max_image_dimension=64)) as prepared:
        assert prepared.source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
        assert [frame.frame_index for frame in prepared.frames] == [0, 4, 7, 11]
        assert [frame.source_seconds for frame in prepared.frames] == pytest.approx([0, 4/24, 7/24, 11/24], abs=1e-6)
        assert all((frame.width, frame.height) == (64, 48) for frame in prepared.frames)
        assert all(frame.path.read_bytes().startswith(b"\xff\xd8") for frame in prepared.frames)
        assert prepared.audio_chunks == ()
        paths = [frame.path for frame in prepared.frames]
    assert all(not path.exists() for path in paths)


@pytest.mark.parametrize("variable_rate", [False, True])
def test_chunked_audio_preserves_late_track_offset_and_nonzero_source_origin(tmp_path, variable_rate):
    source = tmp_path / "late-audio.mp4"
    # Drop alternating frames only in the latter part while keeping the final
    # frame. The measured video endpoint stays 1.5 s, with unequal frame gaps.
    cadence = (["-vf", "select=lt(n\\,6)+gte(n\\,6)*not(mod(n\\,2))+eq(n\\,17)", "-fps_mode", "vfr"]
               if variable_rate else [])
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x48:r=12:d=1.5",
                    "-itsoffset", "0.5", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    *cadence, "-c:v", "libx264", "-c:a", "aac", "-output_ts_offset", "2", str(source)], check=True)
    store, video = _upload(source, tmp_path)
    assert video.frame_timing.media_start_seconds == 2
    assert video.frame_timing.rate_mode == ("variable" if variable_rate else "constant")
    with prepare_media(store.path_for(video), video,
                       PreparationSettings(max_frames=2, audio_chunk_seconds=.5, max_audio_chunks=3)) as prepared:
        assert [(chunk.start_seconds, chunk.end_seconds) for chunk in prepared.audio_chunks] == [(0, .5), (.5, 1), (1, 1.5)]
        samples = []
        for chunk in prepared.audio_chunks:
            with wave.open(str(chunk.path), "rb") as audio:
                assert (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) == (16000, 1, 2)
                assert audio.getnframes() == 8000
                samples.extend(array("h", audio.readframes(audio.getnframes())))
        # AAC encoder padding may precede the tone slightly; the first .4 s is
        # absent audio and the .65-.85 s source interval contains the tone.
        assert max(abs(sample) for sample in samples[:6400]) < 5
        assert sum(abs(sample) for sample in samples[10400:13600]) / 3200 > 100


def test_audio_chunk_limit_is_explicit_and_never_silently_truncates(tmp_path):
    source = tmp_path / "audio.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x48:r=12:d=1",
                    "-f", "lavfi", "-i", "sine=duration=1", "-c:v", "libx264", "-c:a", "aac", str(source)], check=True)
    store, video = _upload(source, tmp_path)
    with pytest.raises(MediaError) as failure, prepare_media(
        store.path_for(video), video, PreparationSettings(max_frames=1, audio_chunk_seconds=.25, max_audio_chunks=2)
    ):
        pytest.fail("Over-limit audio must not be presented as complete")
    assert failure.value.code == "audio_chunk_limit"


def test_original_hash_is_verified_before_any_provider_preparation(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x48:r=12:d=0.25",
                    "-c:v", "libx264", str(source)], check=True)
    store, video = _upload(source, tmp_path)
    path = store.path_for(video)
    path.write_bytes(b"changed source")
    def fail(*_args):
        pytest.fail("Hash mismatch must stop decoding")
    monkeypatch.setattr("backend.app.media_preparation._run_media", fail)
    with pytest.raises(MediaError) as failure, prepare_media(path, video):
        pytest.fail("Changed source must not be sent to a provider")
    assert failure.value.code == "source_media_mismatch"


def test_sampled_jpegs_are_cleaned_up_if_provider_raises(tmp_path):
    source = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x48:r=12:d=0.25",
                    "-c:v", "libx264", str(source)], check=True)
    store, video = _upload(source, tmp_path)
    with pytest.raises(RuntimeError, match="provider failure"):
        with prepare_media(store.path_for(video), video) as prepared:
            directory = prepared.frames[0].path.parent
            raise RuntimeError("provider failure")
    assert not directory.exists()


def _pcm(path, *, channels=1, rate=16000, count=1600):
    with wave.open(str(path), "wb") as audio:
        audio.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * count * channels)


def test_prepared_silence_is_valid_audio_not_proof_of_no_speech(tmp_path):
    path = tmp_path / "silence.wav"
    _pcm(path)
    details = validate_audio_chunk(AudioChunk(path, 4, 4.1), source_duration=5)
    assert details == {"sample_rate": 16000, "channels": 1, "sample_width": 2,
                       "sample_count": 1600, "duration_seconds": .1}


@pytest.mark.parametrize("case", ["empty", "truncated", "stereo", "rate", "duration", "source_bounds"])
def test_invalid_prepared_audio_is_rejected_before_transcription(tmp_path, case):
    path = tmp_path / "invalid.wav"
    _pcm(path, channels=2 if case == "stereo" else 1,
         rate=8000 if case == "rate" else 16000, count=0 if case == "empty" else 1600)
    if case == "truncated":
        path.write_bytes(path.read_bytes()[:-100])
    chunk = AudioChunk(path, 0, .3 if case == "duration" else .1)
    with pytest.raises(MediaError) as error:
        validate_audio_chunk(chunk, source_duration=.05 if case == "source_bounds" else 1)
    assert error.value.code == "audio_preparation_invalid"


@pytest.mark.parametrize("truncated", [False, True])
def test_empty_or_truncated_decoded_pcm_is_never_padded_into_apparent_success(tmp_path, monkeypatch, truncated):
    def decode(_command, _timeout):
        target = tmp_path / "aligned.wav"
        _pcm(target, count=1600 if truncated else 0)
        if truncated:
            target.write_bytes(target.read_bytes()[:-100])
    monkeypatch.setattr("backend.app.media_preparation._run_media", decode)
    video = SimpleNamespace(has_audio=True, frame_timing=SimpleNamespace(
        frame_boundaries_seconds=[0, 1], media_start_seconds=0))
    with pytest.raises(MediaError) as error:
        _prepare_audio(tmp_path / "source.mp4", video, tmp_path, PreparationSettings(), MediaSettings())
    assert error.value.code == "audio_preparation_invalid"


@pytest.mark.parametrize("audio_filter, audible", [
    ("anullsrc=r=16000:cl=mono:d=1.25", False),
    ("aevalsrc=0.12*sin(2*PI*440*t)+0.08*sin(2*PI*880*t):s=16000:d=1.25", True),
])
def test_real_preparation_preserves_synthetic_waveforms_and_short_final_chunk(tmp_path, audio_filter, audible):
    # These are controlled silence/tone fixtures, not a claim about ASR accuracy.
    source = tmp_path / "waveform.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x48:r=12:d=1.25",
                    "-f", "lavfi", "-i", audio_filter, "-c:v", "libx264", "-c:a", "aac", str(source)], check=True)
    store, video = _upload(source, tmp_path)
    with prepare_media(store.path_for(video), video,
                       PreparationSettings(max_frames=1, audio_chunk_seconds=.5, max_audio_chunks=3)) as prepared:
        assert [(chunk.start_seconds, chunk.end_seconds) for chunk in prepared.audio_chunks] == [(0, .5), (.5, 1), (1, 1.25)]
        assert [validate_audio_chunk(chunk, source_duration=1.25)["sample_count"]
                for chunk in prepared.audio_chunks] == [8000, 8000, 4000]
        with wave.open(str(prepared.audio_chunks[-1].path), "rb") as audio:
            samples = array("h", audio.readframes(audio.getnframes()))
        assert (max(abs(sample) for sample in samples) > 100) is audible
