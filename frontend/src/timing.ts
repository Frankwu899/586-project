import type { FrameTiming } from './generated/contracts';

/** Readable non-drop-frame timecode; frame IDs remain authoritative. */
export function frameTimecode(frame: number, timing: FrameTiming): string {
  const nominalFps = Math.max(1, Math.round(timing.fps_numerator / timing.fps_denominator));
  const wholeSeconds = Math.floor(frame / nominalFps);
  const parts = [Math.floor(wholeSeconds / 3600), Math.floor(wholeSeconds / 60) % 60, wholeSeconds % 60, frame % nominalFps];
  return parts.map((part) => String(part).padStart(2, '0')).join(':');
}

export function frameRateLabel(timing: FrameTiming): string {
  const fps = timing.fps_numerator / timing.fps_denominator;
  const rate = Number(fps.toFixed(3));
  return `${rate} fps${timing.fps_denominator === 1 ? '' : ` (${timing.fps_numerator}/${timing.fps_denominator})`}`;
}

export function frameRangeLabel(start: number, end: number, timing: FrameTiming): string {
  return `${frameTimecode(start, timing)}–${frameTimecode(end, timing)} · frames [${start}, ${end})`;
}

/** Find the presentation-order frame containing a browser playback timestamp. */
export function frameAtTime(time: number, timing: FrameTiming): number {
  const boundaries = timing.frame_boundaries_seconds;
  const relativeTime = time - timing.media_start_seconds;
  let low = 0;
  let high = timing.frame_count;
  while (low < high) {
    const middle = Math.floor((low + high + 1) / 2);
    if (boundaries[middle] <= relativeTime) low = middle;
    else high = middle - 1;
  }
  return Math.min(low, timing.frame_count - 1);
}

/** Seek just inside the chosen frame, avoiding boundary rounding in browsers. */
export function frameSeekTime(frame: number, timing: FrameTiming): number {
  const index = Math.min(Math.max(0, frame), timing.frame_count - 1);
  const start = timing.frame_boundaries_seconds[index];
  const end = timing.frame_boundaries_seconds[index + 1];
  return Math.max(0, timing.media_start_seconds + start + Math.min(0.001, (end - start) / 4));
}
