import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const compile = source => ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
const moduleUrl = source => `data:text/javascript;base64,${Buffer.from(compile(source)).toString('base64')}`;
const timingUrl = moduleUrl(await readFile(new URL('../src/timing.ts', import.meta.url), 'utf8'));
const source = (await readFile(new URL('../src/project/sourceTiming.ts', import.meta.url), 'utf8')).replace("from '../timing'", `from '${timingUrl}'`);
const { playbackSeconds, sourceSeconds, sourceMapping } = await import(moduleUrl(source));
const frames = (origin, boundaries) => ({ media_start_seconds: origin, frame_count: boundaries.length - 1, frame_boundaries_seconds: boundaries });
const resource = metadata => ({ original_path: 'sources/original.mp4', playback_path: 'sources/original.mp4', media_metadata: metadata });

test('source and browser clocks round-trip measured variable-rate frame identities', () => {
  const source = resource({ frame_timing: frames(2, [0, .04, .1, .17]) });
  assert.equal(sourceMapping(source), 'frames');
  for (const value of [0, .04, .1]) assert.ok(Math.abs(sourceSeconds(source, playbackSeconds(source, value)) - value) < 1e-9);
  assert.ok(playbackSeconds(source, .1) > 2.1);
});

test('a validated proxy clock maps the corresponding frame without borrowing the source origin', () => {
  const source = { ...resource({ frame_timing: frames(2, [0, .04, .1, .17]), playback_frame_timing: frames(0, [0, .03, .08, .2]) }), playback_path: 'cache/proxy.mp4' };
  assert.equal(sourceMapping(source), 'frames');
  assert.equal(playbackSeconds(source, .1), .081);
  assert.equal(sourceSeconds(source, .081), .1);
});

test('unmapped or mismatched proxies never claim a usable source clock', () => {
  for (const metadata of [{}, { frame_timing: frames(0, [0, .04, .1]) }, { frame_timing: frames(0, [0, .04, .1]), playback_frame_timing: frames(0, [0, .1]) }]) {
    const source = { ...resource(metadata), playback_path: 'cache/proxy.mp4' };
    assert.equal(sourceMapping(source), 'unavailable');
    assert.equal(sourceSeconds(source, 5), null);
  }
  assert.equal(sourceMapping(resource({})), 'seconds');
  assert.equal(sourceSeconds(resource({}), 5), 5);
});
