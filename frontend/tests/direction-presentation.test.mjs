import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/directionPresentation.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { directionEvidence } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const citation = { analysis_id: 'a', analysis_revision: 1, video_id: 'v', event_id: 'e', reason: 'Opening idea' };
const state = () => ({
  task: { current_video_id: 'v' },
  videos: [{ video_id: 'v', deleted_at: null, frame_timing: { frame_boundaries_seconds: [0, 0.03, 0.09, 0.2] } }],
  analyses: [
    { analysis_id: 'a', revision: 1, events: [{ event_id: 'e', video_id: 'v', start_frame: 1, end_frame: 3, text: '原文 / original', description: 'A saved observation' }] },
    { analysis_id: 'a', revision: 2, events: [{ event_id: 'e', video_id: 'v', start_frame: 1, end_frame: 3, text: 'Later correction', description: 'Changed' }] },
  ],
});

test('direction citations resolve the exact revision and measured variable-rate timestamps', () => {
  const evidence = directionEvidence(state(), citation);
  assert.equal(evidence.observation, '原文 / original');
  assert.equal(evidence.timeLabel, '00:00.03–00:00.20');
  assert.equal(evidence.frame, 1);
  assert.equal(evidence.canSeek, true);
});

test('deleted or replaced reference never seeks the current player with a historical frame', () => {
  const deleted = state();
  deleted.videos[0].deleted_at = '2026-10-17T00:00:00Z';
  assert.equal(directionEvidence(deleted, citation).canSeek, false);
  assert.equal(directionEvidence(deleted, citation).mediaDeleted, true);
  assert.equal(directionEvidence(deleted, citation).observation, '原文 / original');
  const replaced = state();
  replaced.task.current_video_id = 'another-video';
  assert.equal(directionEvidence(replaced, citation).canSeek, false);
});

test('missing or wrong-video event does not borrow another revision or fabricate timing', () => {
  const missing = directionEvidence(state(), { ...citation, analysis_revision: 3 });
  assert.equal(missing.timeLabel, 'Timing unavailable');
  assert.equal(missing.canSeek, false);
  assert.equal(missing.frame, null);
  const wrongVideo = state();
  wrongVideo.analyses[0].events[0].video_id = 'other';
  assert.equal(directionEvidence(wrongVideo, citation).canSeek, false);
});
