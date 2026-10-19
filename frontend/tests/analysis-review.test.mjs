import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/analysisReviewModel.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { analysisCorrections, evidenceLanes, repeatedTextGroups } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const event = (event_id, kind, start_frame, extra = {}) => ({ event_id, kind, start_frame, end_frame: start_frame + 1, text: null, description: 'Observed action', visual_details: null, ...extra });

test('every speech/text event remains in chronological reading order without section membership', () => {
  const events = [event('unlinked-speech', 'speech', 90, { text: '未关联，still visible' }), event('visual', 'visual_action', 10), event('ocr', 'on_screen_text', 20, { text: '品牌 Brand' }), event('early-speech', 'speech', 5, { text: 'hello' }), event('music', 'music', 0)];
  const originalOrder = events.map((item) => item.event_id);
  const lanes = evidenceLanes(events);
  assert.deepEqual(lanes.words.map((item) => item.event_id), ['early-speech', 'ocr', 'unlinked-speech']);
  assert.deepEqual(lanes.visuals.map((item) => item.event_id), ['visual']);
  assert.deepEqual(lanes.sounds.map((item) => item.event_id), ['music']);
  assert.equal(Object.values(lanes).flat().length, events.length);
  assert.deepEqual(events.map((item) => item.event_id), originalOrder, 'reading order must not reorder saved evidence');
});

test('legacy events retain their original seconds ordering without inventing frame positions', () => {
  const events = [event('late', 'speech', null, { end_frame: null, legacy_seconds: { start_seconds: 4, end_seconds: 5 } }), event('early', 'on_screen_text', null, { end_frame: null, legacy_seconds: { start_seconds: 1, end_seconds: 2 } })];
  assert.deepEqual(evidenceLanes(events).words.map((item) => item.event_id), ['early', 'late']);
  assert.equal(events[0].start_frame, null);
});

test('correction patches match stable IDs and never submit timing, sources or section identity', () => {
  const original = { events: [event('visual', 'visual_action', 10), event('speech', 'speech', 20, { text: 'unreviewed' })], segments: [{ segment_id: 'section', roles: ['hook'], evidence_ids: ['visual'], start_frame: 0 }] };
  const edited = { events: [{ ...original.events[1], text: '经确认 reviewed', start_frame: 0 }, { ...original.events[0], description: 'Hand holds the cup', source: 'should not be editable' }], segments: [{ ...original.segments[0], roles: ['product_demo'], evidence_ids: [], start_frame: 8 }] };
  assert.deepEqual(analysisCorrections(original, edited), { event_edits: [{ event_id: 'speech', text: '经确认 reviewed' }, { event_id: 'visual', description: 'Hand holds the cup' }], segment_edits: [{ segment_id: 'section', roles: ['product_demo'] }] });
  assert.equal(original.events[1].text, 'unreviewed');
});

test('unchanged drafts and noneditable music descriptions do not create correction revisions', () => {
  const original = { events: [event('music', 'music', 2)], segments: [] };
  assert.deepEqual(analysisCorrections(original, structuredClone(original)), { event_edits: [], segment_edits: [] });
  const edited = { events: [{ ...original.events[0], description: 'This is not an allowed field' }], segments: [] };
  assert.deepEqual(analysisCorrections(original, edited), { event_edits: [], segment_edits: [] });
});


test('repeated OCR groups retain every sampled point without discarding stationary price content', () => {
  const records = [event('price-a', 'on_screen_text', 10, { text: '$49' }), event('speech', 'speech', 12, { text: '$49' }), event('price-b', 'on_screen_text', 20, { text: '$49' }), event('price-different', 'on_screen_text', 30, { text: '$59' })];
  const original = structuredClone(records);
  const groups = repeatedTextGroups(records);
  assert.equal(groups.size, 2);
  assert.deepEqual(groups.get('$49').map((item) => [item.event_id, item.start_frame, item.end_frame]), [['price-a', 10, 11], ['price-b', 20, 21]]);
  assert.deepEqual(records, original);
});
