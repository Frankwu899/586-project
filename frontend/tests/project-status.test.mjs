import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';
const source = await readFile(new URL('../src/project/status.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { coverageMessage, failureMessage, resourceMessage, safeDiagnostic, supportText, evidenceOrigin, isClaimKey } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('playback support identifies source and preview formats without source paths or URLs', () => {
  const details = supportText({ stage: 'playback', media_representation: 'preview', format_name: 'mov,mp4', pixel_format: 'yuv444p', video_profile: 'High 4:4:4 Predictive', playback_video_codec: 'h264', playback_pixel_format: 'yuv420p', playback_audio_codec: 'aac', playback_format_name: 'mp4', original_path: '/private/source.mov', media_url: 'https://private.example/source', source_text: 'PRIVATE' });
  for (const line of ['media_representation: preview', 'format_name: mov,mp4', 'pixel_format: yuv444p', 'video_profile: High 4:4:4 Predictive', 'playback_video_codec: h264', 'playback_pixel_format: yuv420p', 'playback_audio_codec: aac', 'playback_format_name: mp4']) assert.ok(details.includes(line), line);
  assert.doesNotMatch(details, /private|PRIVATE|source_text/);
});

test('speech failure, silence, absent audio and unprocessed speech remain distinguishable', () => {
  assert.match(coverageMessage('speech', 'failed'), /failed.*Retry transcription/);
  assert.equal(coverageMessage('speech', 'none_found'), 'No speech was detected by this transcription attempt. Check the audio if speech was expected.');
  assert.equal(coverageMessage('speech', 'no_audio'), 'This clip has no audio track.');
  assert.equal(coverageMessage('speech', 'not_analyzed'), 'Speech has not been analyzed.');
  assert.equal(coverageMessage('visual_action', 'observations'), 'Visual observations available.');
  assert.equal(coverageMessage('sfx', 'not_analyzed'), 'Music analysis is not available in this version.');
});
test('media availability never presents failed speech as complete analysis', () => {
  const resource = { status: 'ready', kind: 'video', evidence: [{ coverage: { speech: 'failed', visual_action: 'observations' } }] };
  assert.equal(resourceMessage(resource), 'Media saved · evidence incomplete');
  resource.evidence[0].coverage.speech = 'none_found';
  assert.equal(resourceMessage(resource), 'Media available');
});
test('only an actual classified quota code provides a billing diagnosis', () => {
  assert.match(failureMessage('Private payload', 'provider_quota'), /billing limit/);
  assert.equal(failureMessage('Private payload', 'provider_temporarily_unavailable'), 'The service could not complete this request. Wait and retry; check support details if it persists.');
  assert.doesNotMatch(failureMessage('{"message":"billing unavailable", "key":"sk-private-value"}'), /billing|sk-private|payload/);
});
test('support text removes credential and raw payload material', () => {
  const text = safeDiagnostic('Operation failed Authorization: Bearer sk-private-value https://provider.test/private?key=secret {"token":"private"}');
  assert.doesNotMatch(text, /sk-private|provider\.test|"token"/);
});

test('corrected speech overlap requests review rather than falsely reporting provider failure', () => {
  const expected = 'New transcription overlaps saved corrections. Review speech and timing against playback, then retry.';
  assert.equal(coverageMessage('speech', 'partial', true, 'speech_merge_conflict'), expected);
  assert.equal(failureMessage('Speech transcription failed.', 'speech_merge_conflict'), expected);
  assert.equal(coverageMessage('speech', 'failed', false, 'provider_busy'), 'Speech transcription failed. Retry transcription.');
});

test('transcript coverage separates incomplete evidence, disabled and checked absence', () => {
  assert.match(coverageMessage('speech', 'partial', true), /Partial transcript/);
  assert.match(coverageMessage('speech', 'disabled'), /disabled/);
  assert.match(coverageMessage('speech', 'complete', false), /does not establish/);
  assert.match(coverageMessage('speech', 'none_found'), /this transcription attempt/);
  assert.match(coverageMessage('speech', 'no_audio'), /no audio track/);
});

test('billing and timing messages identify a useful next action', () => {
  for (const code of ['provider_project_spend_limit', 'provider_organization_spend_limit', 'provider_organization_usage_limit']) assert.match(failureMessage('', code), /Check.*limit before retrying/);
  assert.match(failureMessage('', 'provider_credit_balance_exhausted'), /API billing/);
  assert.match(failureMessage('', 'provider_rate_limit'), /Wait, then retry/);
  assert.match(failureMessage('', 'audio_timestamps_invalid'), /Valid transcript segments are saved/);
});

test('default support exports include operational outcomes but exclude private payloads and secrets', () => {
  const exported = supportText([{ project_id: 'project_test', validation_field: 'proposals[0].excerpt', validation_rule: 'source_mismatch', requested_model: 'whisper-1', chunk_start_seconds: '60', prompt: 'PRIVATE PROMPT', text: 'PRIVATE TRANSCRIPT', audio: 'PRIVATE MEDIA', api_key: 'sk-private', authorization: 'Bearer secret', provider_request_id: 'Bearer sk-secret' }]);
  assert.match(exported, /validation_field: proposals\[0\].excerpt/);
  assert.match(exported, /chunk_start_seconds: 60/);
  assert.doesNotMatch(exported, /PRIVATE|sk-secret|sk-private|Bearer secret/);
});

test('speech reuse is distinct from requests for missing chunks', () => {
  assert.match(evidenceOrigin([{ cache_status: 'hit' }]), /no new speech request/);
  assert.match(evidenceOrigin([{ cache_status: 'hit' }, { cache_status: 'miss' }]), /missing speech retried/);
  assert.match(evidenceOrigin([{ cache_status: 'miss' }]), /New transcription attempt/);
});

test('grounded product-claim aliases offer permission while prohibited claims stay separate', () => {
  for (const key of [' benefit ', 'BENEFITS', 'product benefit', 'product-benefits', 'efficacy', 'health_claim', 'product_claims', '卖点', '产品卖点', '功效', '产品功效', '产品声明', '产品优势', '优势']) assert.equal(isClaimKey(key), true, key);
  for (const key of ['prohibited_claim', 'prohibited claims', 'clinical_restriction', 'avoid_benefit_claims']) assert.equal(isClaimKey(key), false, key);
});

test('phase durations and actual timeout stay available without exporting source payloads', () => {
  const exported = supportText({ phase_queued_ms: '20', phase_extracting_ms: '31', phase_single_video_analysis_ms: '45', phase_synthesizing_ms: '60', phase_validating_ms: '4', phase_saving_ms: '2', network_timeout_seconds: '45', max_network_attempts: '3', input_tokens: '150', output_tokens: '70', prompt: 'PRIVATE', response: 'PRIVATE', phase_prompt_ms: 'PRIVATE' });
  for (const line of ['phase_queued_ms: 20', 'phase_extracting_ms: 31', 'phase_single_video_analysis_ms: 45', 'phase_synthesizing_ms: 60', 'phase_validating_ms: 4', 'phase_saving_ms: 2', 'network_timeout_seconds: 45', 'max_network_attempts: 3', 'input_tokens: 150', 'output_tokens: 70']) assert.ok(exported.includes(line), line);
  assert.doesNotMatch(exported, /PRIVATE|phase_prompt_ms/);
});

test('per-attempt core reuse counts export without changing original run provenance', () => {
  assert.equal(supportText({ single_cache_hits: '2', single_cache_misses: '1' }), 'single_cache_hits: 2\nsingle_cache_misses: 1');
});

test('saved stage input manifests remain private in operational support exports', () => {
  const exported = supportText({ stage: 'synthesizing', provider_request_id: 'offline-request',
    inputs: { brief_revision: 1, selection_revision: 2, limitations: ['PRIVATE SOURCE CONDITION'],
      single_analysis_ids: { resource_test: 'single_test' } },
    prompt: 'PRIVATE PROMPT', confirmed_brief: { facts: [{ value: 'PRIVATE BRIEF' }] } });
  assert.equal(exported, 'stage: synthesizing\nprovider_request_id: offline-request');
});
