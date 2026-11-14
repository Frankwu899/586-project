import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';
const source = await readFile(new URL('../src/project/status.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { coverageMessage, failureMessage, resourceMessage, safeDiagnostic } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('speech failure, silence, absent audio and unprocessed speech remain distinguishable', () => {
  assert.match(coverageMessage('speech', 'failed'), /failed.*Retry transcription/);
  assert.equal(coverageMessage('speech', 'none_found'), 'No speech was detected in this clip.');
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
  assert.equal(failureMessage('Private payload', 'provider_temporarily_unavailable'), 'The service is temporarily busy. Try again shortly.');
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
