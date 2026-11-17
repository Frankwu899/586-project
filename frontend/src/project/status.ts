import type { Resource } from './contracts';

export const channelLabel: Record<string, string> = { speech: 'Speech', on_screen_text: 'On-screen text', visual: 'Visual observations', vision: 'Visual observations', sound: 'Music and sound', music: 'Music', sfx: 'Sound effects', visual_action: 'Visual observations' };
const speechConflict = 'New transcription overlaps saved corrections. Review speech and timing against playback, then retry.';
export function coverageMessage(channel: string, value: string, hasEvents = false, diagnostic?: string) {
  if (channel === 'speech' && diagnostic === 'speech_merge_conflict') return speechConflict;
  if (channel === 'sound' || channel === 'music' || channel === 'sfx') return 'Music analysis is not available in this version.';
  if (value === 'partial' && channel === 'speech') return 'Partial transcript available. Retry missing speech; saved results are retained.';
  if (['failed', 'error', 'partial'].includes(value)) return channel === 'speech' ? 'Speech transcription failed. Retry transcription.' : `${channelLabel[channel] ?? 'Source evidence'} is incomplete. Retry recognition.`;
  if (['no_audio', 'no_audio_track', 'not_applicable'].includes(value) && channel === 'speech') return 'This clip has no audio track.';
  if (channel === 'speech' && value === 'disabled') return 'Transcription is disabled in the current configuration.';
  if (channel === 'speech' && !hasEvents && ['complete', 'available', 'succeeded', 'analyzed'].includes(value)) return 'No transcript was returned. Review the audio and processing details; this does not establish that the source has no speech.';
  if (['no_speech', 'no_speech_detected', 'none_found', 'empty'].includes(value) || (!hasEvents && ['complete', 'available', 'succeeded', 'analyzed'].includes(value))) return channel === 'speech' ? 'No speech was detected by this transcription attempt. Check the audio if speech was expected.' : `No ${channel === 'on_screen_text' ? 'on-screen text was detected' : 'observations were detected'}.`;
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
export const jobStatus: Record<string, string> = { queued: 'Waiting to start', running: 'Processing', succeeded: 'Saved', partial: 'Saved with limitations', stopped: 'Stopped', failed: 'Needs attention' };
export function safeDiagnostic(value: unknown) {
  const raw = typeof value === 'string' ? value : value instanceof Error ? value.message : '';
  return raw.replace(/(?:sk-|sess-)[A-Za-z0-9_-]+/g, '[redacted]').replace(/Bearer\s+\S+/gi, 'Bearer [redacted]').replace(/(?:api[_ -]?key|authorization)\s*[:=]\s*[^\s,}]+/gi, '[credential redacted]').replace(/https?:\/\/[^\s]+/g, '[service URL]').replace(/Traceback[\s\S]*/gi, '[technical traceback omitted]').replace(/\{[\s\S]*\}/g, '[provider payload omitted]').slice(0, 500);
}
const failureCodes: Record<string, string> = {
  speech_merge_conflict: speechConflict,
  provider_credit_balance_exhausted: 'The API account has insufficient credit. Check the account’s API billing before retrying.',
  provider_project_spend_limit: 'The API project’s spending limit was reached. Check the project limit before retrying.',
  provider_organization_spend_limit: 'The API organization’s spending limit was reached. Check the organization limit before retrying.',
  provider_organization_usage_limit: 'The API organization’s usage limit was reached. Check the organization limit before retrying.',
  provider_rate_limit: 'The service is temporarily throttling requests. Wait, then retry.',
  provider_refusal: 'The service declined this request. Rephrase the request before retrying.',
  provider_incomplete: 'The service returned an incomplete response. Your message is saved; retry this turn.',
  conversation_context_changed: 'The brief changed while this reply was being prepared. Your newer edits are saved; retry using the current context.',
  conversation_stale_context: 'The brief changed while this reply was being prepared. Your newer edits are saved; retry using the current context.',
  audio_timestamps_invalid: 'Some speech timing is invalid. Valid transcript segments are saved; retry missing speech.',
  audio_timestamps_missing: 'The transcription response omitted speech timing. Retry transcription.',
  audio_preparation_failed: 'The audio could not be prepared for transcription. Check the source or rebuild the media preview.',
  media_preparation_failed: 'Media preparation failed before transcription. Check the source or rebuild the media preview.',
  provider_quota: 'The provider reports insufficient credit or a billing limit. Check billing for the project that owns this key.',
  provider_authentication: 'The service rejected the API key. Check the saved key in Settings.',
  provider_not_configured: 'Connect your API key in Settings, then retry.',
  provider_permission: 'The key lacks permission for this request. Check model and Audio Transcriptions access.',
  provider_model_access: 'The configured model is unavailable to this key. Check project model access.',
  provider_temporarily_unavailable: 'The service could not complete this request. Wait and retry; check support details if it persists.',
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

// Export only operational metadata. Source text, prompts and arbitrary provider
// payloads are intentionally excluded even when a future backend adds them.
const supportKeys = new Set([
  'application_version', 'source_commit', 'operation', 'stage', 'timestamp', 'started_at', 'ended_at',
  'project_id', 'resource_id', 'job_id', 'message_id', 'conversation_turn_id', 'reply_to_message_id',
  'requested_model', 'model', 'attempts', 'attempt_count', 'cache_status', 'elapsed_ms', 'elapsed_seconds',
  'http_status', 'provider_code', 'provider_type', 'provider_request_id', 'validation_outcome',
  'validation_rule', 'validation_field', 'failure_category', 'failure_code', 'error_code', 'status', 'speech',
  'chunk_start_seconds', 'chunk_end_seconds', 'chunk_start', 'chunk_end', 'chunk_index', 'total_chunks', 'retry_after_seconds', 'coverage', 'coverage_status',
  'valid_segments', 'invalid_segments', 'rejected_segments', 'rounded_boundaries', 'sample_rate', 'sample_count', 'channels', 'duration_seconds', 'prepared_duration_seconds', 'source_start_seconds', 'source_end_seconds', 'completed_chunks', 'failed_chunks', 'missing_chunks',
  'accepted_proposals', 'rejected_proposals', 'rejected_proposal_count', 'reply_validation',
  'proposal_validation', 'outcome', 'validation_issues', 'attempt', 'retry', 'operation_mode', 'result_origin', 'evidence_revision',
]);
export function supportText(records: Record<string, unknown> | Record<string, unknown>[] = {}) {
  return (Array.isArray(records) ? records : [records]).map(record => Object.entries(record)
    .filter(([key, value]) => (supportKeys.has(key) || /^proposal_\d+_(?:rule|field)$/.test(key)) && ['string', 'number', 'boolean'].includes(typeof value))
    .map(([key, value]) => `${key}: ${safeDiagnostic(String(value))}`).join('\n'))
    .filter(Boolean).join('\n\n');
}
export function evidenceOrigin(records: Record<string, unknown>[] = []) {
  if (records.some(item => item.stage === 'saved_evidence_reuse')) return 'Reused saved evidence · no new recognition request';
  const caches = records.map(item => item.cache_status);
  if (!caches.length) return '';
  if (caches.every(value => value === 'hit' || value === 'cached')) return 'Reused saved transcription · no new speech request';
  if (caches.some(value => value === 'hit' || value === 'partial_hit')) return 'Saved transcription reused · missing speech retried';
  if (caches.some(value => value === 'miss' || value === 'new')) return records.some(item => item.operation_mode === 'retry') ? 'Transcription retry attempt' : 'New transcription attempt';
  return '';
}

// Keep aligned with project_workspace.conversation.CLAIM_KEYS. Restrictions such
// as prohibited_claim remain separate from permission to use a product claim.
const claimKeys = new Set(['claim', 'claims', 'product_claim', 'selling_point', 'selling_points', 'approved_message', 'approved_messages', 'benefit', 'benefits', 'product_benefit', 'product_benefits', 'efficacy', 'health_claim', 'product_claims', '卖点', '产品卖点', '功效', '产品功效', '产品声明', '产品优势', '优势']);
export function isClaimKey(key: string) {
  return claimKeys.has(key.trim().toLowerCase().replaceAll(/[\s-]+/g, '_'));
}
