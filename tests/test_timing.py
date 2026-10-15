"""Reference conversion behavior, including short observations and VFR gaps."""
import pytest

from backend.app.models import FrameTiming
from backend.app.timing import frame_to_seconds, seconds_to_frame_range


@pytest.fixture
def timing():
    return FrameTiming(fps_numerator=25, fps_denominator=1, frame_count=4,
                       frame_boundaries_seconds=[0, 0.04, 0.08, 0.2, 0.3], rate_mode="variable")


def test_quantization_preserves_contiguous_boundaries_and_subsecond_observations(timing):
    assert seconds_to_frame_range(0, 0.07, timing) == (0, 2)
    assert seconds_to_frame_range(0.07, 0.3, timing) == (2, 4)
    assert seconds_to_frame_range(0.041, 0.045, timing) == (1, 2)
    assert seconds_to_frame_range(0.12, 0.125, timing) == (2, 3)
    assert frame_to_seconds(2, timing) == 0.08
    assert frame_to_seconds(4, timing) == 0.3


def test_quantization_clamps_provider_rounding_at_video_edges(timing):
    assert seconds_to_frame_range(-0.001, 0.301, timing) == (0, 4)
    assert seconds_to_frame_range(-0.02, -0.01, timing) == (0, 1)
    assert seconds_to_frame_range(0.3, 0.301, timing) == (3, 4)


@pytest.mark.parametrize("interval", [(0.1, 0.1), (0.2, 0.1), (float("nan"), 1), (0, float("inf"))])
def test_invalid_seconds_intervals_are_rejected(interval, timing):
    with pytest.raises(ValueError, match="finite and start before end"):
        seconds_to_frame_range(*interval, timing)


@pytest.mark.parametrize("frame", [-1, 5, 1.5, True])
def test_frame_boundary_requires_a_real_integer_in_range(frame, timing):
    with pytest.raises(ValueError, match="integer"):
        frame_to_seconds(frame, timing)
