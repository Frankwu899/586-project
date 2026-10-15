"""Map reference-video frames to the probed media clock.

Frames are zero based. Intervals use an exclusive end frame, so frame_count is
the boundary after the last frame. Seconds here are an adapter/playback bridge;
reference observations store frame intervals, while storyboard plans use seconds.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
import math

from .models import FrameTiming


def frame_to_seconds(frame: int, timing: FrameTiming) -> float:
    """Return a boundary's media time, including the exclusive final boundary."""
    if type(frame) is not int or not 0 <= frame <= timing.frame_count:
        raise ValueError("frame must be an integer between zero and frame_count")
    return timing.frame_boundaries_seconds[frame]


def seconds_to_frame_range(start_seconds: float, end_seconds: float,
                           timing: FrameTiming) -> tuple[int, int]:
    """Quantize an interval to its nearest actual presentation boundaries.

    Out-of-range finite times are clamped to the video. Equidistant boundaries
    round upward. A subframe interval that would collapse gets the frame containing
    its midpoint. This deliberately allows a minor frame error; an adapter must
    still validate section/evidence overlap after quantization.
    """
    if (not math.isfinite(start_seconds) or not math.isfinite(end_seconds)
            or start_seconds >= end_seconds):
        raise ValueError("seconds interval must be finite and start before end")
    boundaries = timing.frame_boundaries_seconds
    duration = boundaries[-1]
    start = min(duration, max(0.0, start_seconds))
    end = min(duration, max(0.0, end_seconds))

    def nearest(seconds: float) -> int:
        after = bisect_left(boundaries, seconds)
        if after == 0:
            return 0
        if after == len(boundaries):
            return timing.frame_count
        before = after - 1
        return before if seconds - boundaries[before] < boundaries[after] - seconds else after

    first, stop = nearest(start), nearest(end)
    if first == stop:
        first = min(timing.frame_count - 1, max(0, bisect_right(boundaries, (start + end) / 2) - 1))
        stop = first + 1
    return first, stop
