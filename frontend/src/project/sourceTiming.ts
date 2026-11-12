import { frameAtTime, frameSeekTime } from '../timing';
import type { FrameTiming } from '../generated/contracts';
import type { Resource } from './contracts';

function timing(value: unknown): FrameTiming | null {
  if (!value || typeof value !== 'object') return null;
  const data = value as Partial<FrameTiming>;
  return Array.isArray(data.frame_boundaries_seconds) && typeof data.frame_count === 'number' && typeof data.media_start_seconds === 'number' ? data as FrameTiming : null;
}

/** Evidence uses source-relative seconds; playback may have an independent clock. */
export function playbackSeconds(resource: Resource, seconds: number): number {
  const source = timing(resource.media_metadata.frame_timing);
  if (!source) return Math.max(0, seconds);
  const proxyActive = resource.playback_path && resource.playback_path !== resource.original_path;
  const playback = (proxyActive ? timing(resource.media_metadata.playback_frame_timing) : null) ?? source;
  return frameSeekTime(frameAtTime(seconds + source.media_start_seconds, source), playback);
}
