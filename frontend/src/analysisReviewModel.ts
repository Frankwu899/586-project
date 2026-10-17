import type { AnalysisResult, ContentSegment, EvidenceEvent } from './generated/contracts';

export interface AnalysisEditorContent {
  events: EvidenceEvent[];
  segments: ContentSegment[];
}

/** Evidence is listed once, independently of overlapping or missing role sections. */
export function evidenceLanes(events: EvidenceEvent[]) {
  const ordered = [...events].sort((left, right) => {
    const leftTime = left.start_frame ?? left.legacy_seconds?.start_seconds ?? Number.MAX_SAFE_INTEGER;
    const rightTime = right.start_frame ?? right.legacy_seconds?.start_seconds ?? Number.MAX_SAFE_INTEGER;
    return leftTime - rightTime;
  });
  return {
    visuals: ordered.filter((event) => event.kind === 'visual_action'),
    words: ordered.filter((event) => event.kind === 'speech' || event.kind === 'on_screen_text'),
    sounds: ordered.filter((event) => event.kind === 'music' || event.kind === 'sfx'),
  };
}

/** Generate only the server's allowlisted correction leaves, keyed by stable ID. */
export function analysisCorrections(analysis: AnalysisResult, content: AnalysisEditorContent) {
  const originals = new Map(analysis.events.map((event) => [event.event_id, event]));
  const event_edits = content.events.flatMap((event) => {
    const previous = originals.get(event.event_id);
    if (!previous) return [];
    const patch: { event_id: string; text?: string | null; description?: string | null; visual_details?: EvidenceEvent['visual_details'] } = { event_id: event.event_id };
    if ((event.kind === 'speech' || event.kind === 'on_screen_text') && event.text !== previous.text) patch.text = event.text;
    if (event.kind === 'visual_action' && event.description !== previous.description) patch.description = event.description;
    if (event.kind === 'visual_action' && JSON.stringify(event.visual_details) !== JSON.stringify(previous.visual_details)) patch.visual_details = event.visual_details;
    return Object.keys(patch).length > 1 ? [patch] : [];
  });
  const originalSegments = new Map(analysis.segments.map((segment) => [segment.segment_id, segment]));
  const segment_edits = content.segments.filter((segment) => {
    const previous = originalSegments.get(segment.segment_id);
    return previous && JSON.stringify(segment.roles) !== JSON.stringify(previous.roles);
  }).map(({ segment_id, roles }) => ({ segment_id, roles }));
  return { event_edits, segment_edits };
}
