import type { EvidenceReference, TaskState } from './generated/contracts';

const timestamp = (seconds: number) => {
  const centiseconds = Math.round(seconds * 100);
  const minutes = Math.floor(centiseconds / 6000);
  const remainder = (centiseconds % 6000) / 100;
  return `${String(minutes).padStart(2, '0')}:${remainder.toFixed(2).padStart(5, '0')}`;
};

/** Resolve the cited revision, never substitute the newest observation. */
export function directionEvidence(state: TaskState, citation: EvidenceReference) {
  const analysis = state.analyses.find((item) => item.analysis_id === citation.analysis_id && item.revision === citation.analysis_revision);
  const event = analysis?.events.find((item) => item.event_id === citation.event_id && item.video_id === citation.video_id);
  const video = state.videos.find((item) => item.video_id === citation.video_id);
  const timing = video?.frame_timing;
  const start = event?.start_frame;
  const end = event?.end_frame;
  const startSeconds = start !== null && start !== undefined ? timing?.frame_boundaries_seconds[start] : undefined;
  const endSeconds = end !== null && end !== undefined ? timing?.frame_boundaries_seconds[end] : undefined;
  const timeLabel = startSeconds !== undefined && endSeconds !== undefined
    ? `${timestamp(startSeconds)}–${timestamp(endSeconds)}` : 'Timing unavailable';
  return {
    event,
    observation: event?.text || event?.description || 'The saved observation is unavailable.',
    timeLabel,
    frame: start ?? null,
    // A historical citation must never seek the same index in another video.
    canSeek: Boolean(event && timing && start !== null && start !== undefined && !video?.deleted_at && state.task.current_video_id === citation.video_id),
    mediaDeleted: Boolean(video?.deleted_at),
  };
}
