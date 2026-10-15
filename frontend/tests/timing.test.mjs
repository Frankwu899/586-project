import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

// Use the project's compiler to run the real helper on all supported Node 22+
// versions without depending on Node's later native TypeScript support.
const source = await readFile(new URL('../src/timing.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { frameAtTime, frameRateLabel, frameRangeLabel, frameSeekTime, frameTimecode } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

const constant = (numerator, denominator = 1, count = 120) => ({
  fps_numerator: numerator, fps_denominator: denominator, frame_count: count,
  media_start_seconds: 0,
  frame_boundaries_seconds: Array.from({ length: count + 1 }, (_, frame) => frame * denominator / numerator),
  rate_mode: 'constant', source: 'probed',
});

test('timecode and frame labels distinguish brief events at common source rates', () => {
  for (const fps of [20, 24, 25, 30, 50, 60]) {
    const timing = constant(fps);
    assert.equal(frameTimecode(fps * 3 + 5, timing), '00:00:03:05');
    assert.equal(frameTimecode(fps * 3661 + 2, timing), '01:01:01:02');
    assert.equal(frameRateLabel(timing), `${fps} fps`);
  }
  assert.equal(frameRangeLabel(60, 65, constant(20)), '00:00:03:00–00:00:03:05 · frames [60, 65)');
});

test('fractional rates retain exact rational metadata while timecode is non-drop-frame', () => {
  assert.equal(frameRateLabel(constant(24000, 1001)), '23.976 fps (24000/1001)');
  assert.equal(frameRateLabel(constant(30000, 1001)), '29.97 fps (30000/1001)');
  assert.equal(frameRateLabel(constant(60000, 1001)), '59.94 fps (60000/1001)');
  assert.equal(frameTimecode(30, constant(30000, 1001)), '00:00:01:00');
  const timing = constant(30000, 1001, 30000);
  const time = frameSeekTime(17982, timing);
  assert.equal(frameAtTime(time, timing), 17982);
  assert.ok(Math.abs(time - 599.9994) < 0.002);
});

test('variable-rate seeks and neighboring frames use measured timestamps, not average fps', () => {
  const timing = { ...constant(30, 1, 4), rate_mode: 'variable', frame_boundaries_seconds: [0, 0.02, 0.09, 0.12, 0.2] };
  assert.equal(frameAtTime(0.08, timing), 1);
  assert.equal(frameAtTime(0.09, timing), 2);
  assert.equal(frameAtTime(0.119, timing), 2);
  assert.equal(frameSeekTime(2, timing), 0.091);
  for (let frame = 0; frame < timing.frame_count; frame += 1) {
    assert.equal(frameAtTime(frameSeekTime(frame, timing), timing), frame);
  }
});

test('frame stepping clamps at both ends and seeks within even very short frames', () => {
  const timing = constant(20, 1, 200);
  assert.equal(frameAtTime(-1, timing), 0);
  assert.equal(frameAtTime(10, timing), 199);
  assert.equal(frameAtTime(100, timing), 199);
  assert.equal(frameAtTime(frameSeekTime(-1, timing), timing), 0);
  assert.equal(frameAtTime(frameSeekTime(200, timing), timing), 199);
  const short = { ...constant(10000, 1, 1), frame_boundaries_seconds: [0, 0.0001] };
  assert.ok(frameSeekTime(0, short) > 0 && frameSeekTime(0, short) < 0.0001);
});

test('source timestamp offsets map browser time to zero-based frames and back', () => {
  const timing = { ...constant(24, 1, 12), media_start_seconds: 2 };
  assert.equal(frameAtTime(2, timing), 0);
  assert.equal(frameAtTime(2.25, timing), 6);
  assert.equal(frameSeekTime(6, timing), 2.251);
  assert.equal(frameTimecode(6, timing), '00:00:00:06');
  for (let frame = 0; frame < timing.frame_count; frame += 1) {
    assert.equal(frameAtTime(frameSeekTime(frame, timing), timing), frame);
  }
  const negativeOrigin = { ...timing, media_start_seconds: -0.125 };
  assert.equal(frameAtTime(0, negativeOrigin), 3);
  assert.equal(frameSeekTime(0, negativeOrigin), 0);
  assert.equal(frameAtTime(frameSeekTime(6, negativeOrigin), negativeOrigin), 6);
});
