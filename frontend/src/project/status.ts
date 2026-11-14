import type { Resource } from './contracts';

export const channelLabel: Record<string, string> = { speech: 'Speech', on_screen_text: 'On-screen text', visual: 'Visual observations', vision: 'Visual observations', sound: 'Music and sound', music: 'Music', sfx: 'Sound effects', visual_action: 'Visual observations' };
const speechConflict = 'New transcription overlaps saved corrections. Review speech and timing against playback, then retry.';
export function coverageMessage(channel: string, value: string, hasEvents = false, diagnostic?: string) {
  if (channel === 'speech' && diagnostic === 'speech_merge_conflict') return speechConflict;
  if (channel === 'sound' || channel === 'music' || channel === 'sfx') return 'Music analysis is not available in this version.';
  if (['failed', 'error', 'partial'].includes(value)) return channel === 'speech' ? 'Speech transcription failed. Retry transcription.' : `${channelLabel[channel] ?? 'Source evidence'} is incomplete. Retry recognition.`;
  if (['no_audio', 'no_audio_track', 'not_applicable'].includes(value) && channel === 'speech') return 'This clip has no audio track.';
  if (['no_speech', 'no_speech_detected', 'none_found', 'empty'].includes(value) || (!hasEvents && ['complete', 'available', 'succeeded', 'analyzed'].includes(value))) return channel === 'speech' ? 'No speech was detected in this clip.' : `No ${channel === 'on_screen_text' ? 'on-screen text was detected' : 'observations were detected'}.`;
  if (['not_analyzed', 'not_requested', 'skipped', 'disabled', 'unavailable', 'unknown'].includes(value)) return channel === 'speech' ? 'Speech has not been analyzed.' : `${channelLabel[channel] ?? 'This evidence'} has not been analyzed.`;
  if (hasEvents || ['complete', 'available', 'succeeded', 'analyzed', 'sampled', 'observations'].includes(value)) return channel === 'speech' ? 'Speech transcript available.' : channel === 'on_screen_text' ? 'On-screen text detected.' : 'Visual observations available.';
  return `${channelLabel[channel] ?? 'Evidence'} needs review.`;
}
export function resourceMessage(resource: Resource) {
  const evidence = resource.evidence.at(-1);
  if (resource.status === 'missing') return 'Original file missing';
  if (resource.status === 'unsupported') return 'File needs conversion';
  if (resource.status === 'processing') return 'Preparing file';
  if (resource.status === 'stored') return 'File saved locally';
  if (evidence && Object.values(evidence.coverage).some(value => ['failed', 'partial', 'error'].includes(value))) return 'Media saved · evidence incomplete';
  if (resource.status === 'failed') return 'Processing needs attention';
  if (resource.status === 'partial') return 'Some results available';
  return ['audio', 'video'].includes(resource.kind) ? 'Media available' : 'File available';
}
export const jobLabel: Record<string, string> = { analyze: 'Reference analysis', recognize: 'Reference recognition', reference_extraction: 'Reference recognition', extract: 'File preparation', conversation: 'Project conversation', concepts: 'Series and topic suggestions', directions: 'Creative directions', production: 'Production documents' };
export const jobStatus: Record<string, string> = { queued: 'Waiting to start', running: 'Processing', succeeded: 'Saved', partial: 'Saved with limitations', failed: 'Needs attention' };
export function safeDiagnostic(value: unknown) {
  const raw = typeof value === 'string' ? value : value instanceof Error ? value.message : '';
  return raw.replace(/(?:sk-|sess-)[A-Za-z0-9_-]+/g, '[redacted]').replace(/Bearer\s+\S+/gi, 'Bearer [redacted]').replace(/(?:api[_ -]?key|authorization)\s*[:=]\s*[^\s,}]+/gi, '[credential redacted]').replace(/https?:\/\/[^\s]+/g, '[service URL]').replace(/Traceback[\s\S]*/gi, '[technical traceback omitted]').replace(/\{[\s\S]*\}/g, '[provider payload omitted]').slice(0, 500);
}
const failureCodes: Record<string, string> = {
  speech_merge_conflict: speechConflict,
  provider_quota: 'The provider reports insufficient credit or a billing limit. Check billing for the project that owns this key.',
  provider_authentication: 'The service rejected the API key. Check the saved key in Settings.',
  provider_not_configured: 'Connect your API key in Settings, then retry.',
  provider_permission: 'The key lacks permission for this request. Check model and Audio Transcriptions access.',
  provider_model_access: 'The configured model is unavailable to this key. Check project model access.',
  provider_temporarily_unavailable: 'The service is temporarily busy. Try again shortly.',
  provider_busy: 'The service is temporarily busy. Try again shortly.',
  provider_timeout: 'The service took too long to respond. Check the connection and retry.',
  provider_network: 'The service could not be reached. Check your network and try again.',
  provider_invalid_output: 'The response could not be read as valid evidence. Retry this operation.',
  provider_invalid_json: 'The response could not be read as valid evidence. Retry this operation.',
  missing_prepared_audio: 'The audio track could not be prepared. Rebuild the media preview and retry transcription.',
};
export function failureMessage(value: unknown, code?: string | null) {
  const raw = typeof value === 'string' ? value : value instanceof Error ? value.message : '';
  if (code && failureCodes[code]) return failureCodes[code];
  if (failureCodes[raw]) return failureCodes[raw];
  if (/\{|Traceback|Exception|Error:|\bHTTP\b|^[a-z]+(?:_[a-z]+)+$/i.test(raw)) return 'This operation could not finish. Your saved work is retained; retry or review the support details.';
  return safeDiagnostic(raw) || 'This operation could not finish. Your saved work is retained; retry it.';
}
