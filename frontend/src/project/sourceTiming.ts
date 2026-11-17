import { frameAtTime, frameSeekTime } from '../timing';
import type { FrameTiming } from '../generated/contracts';
import type { Resource } from './contracts';

export function timing(value: unknown): FrameTiming | null {
  if (!value || typeof value !== 'object') return null;
  const data = value as Partial<FrameTiming>;
  return Array.isArray(data.frame_boundaries_seconds) && typeof data.frame_count === 'number' && data.frame_count > 0 && data.frame_boundaries_seconds.length === data.frame_count + 1 && data.frame_boundaries_seconds.every(Number.isFinite) && typeof data.media_start_seconds === 'number' ? data as FrameTiming : null;
}

export function sourceMapping(resource: Resource): 'frames' | 'seconds' | 'unavailable' {
  const source = timing(resource.media_metadata.frame_timing);
  const proxy = resource.playback_path && resource.playback_path !== resource.original_path;
  if (!proxy) return source ? 'frames' : 'seconds';
  const playback = timing(resource.media_metadata.playback_frame_timing);
  return source && playback && source.frame_count === playback.frame_count ? 'frames' : 'unavailable';
}

/** Evidence uses source-relative seconds; playback may have an independent clock. */
export function playbackSeconds(resource: Resource, seconds: number): number {
  const source = timing(resource.media_metadata.frame_timing);
  if (!source) return Math.max(0, seconds);
  const proxyActive = resource.playback_path && resource.playback_path !== resource.original_path;
  const playback = (proxyActive ? timing(resource.media_metadata.playback_frame_timing) : null) ?? source;
  return frameSeekTime(frameAtTime(seconds + source.media_start_seconds, source), playback);
}

/** Convert the selected player's clock back to source-relative seconds. */
export function sourceSeconds(resource: Resource, seconds: number): number | null {
  const mapping = sourceMapping(resource);
  if (mapping === 'unavailable') return null;
  const source = timing(resource.media_metadata.frame_timing);
  if (!source) return Math.max(0, seconds);
  const proxy = resource.playback_path && resource.playback_path !== resource.original_path;
  const playback = (proxy ? timing(resource.media_metadata.playback_frame_timing) : null) ?? source;
  return source.frame_boundaries_seconds[frameAtTime(seconds, playback)];
}
