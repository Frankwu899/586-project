import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/productionReadiness.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { productionBlocker } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const fixture = JSON.parse(await readFile(new URL('../../examples/v0.6.sample-task.json', import.meta.url), 'utf8'));
const context = { pending: false, unsaved: false, loading: false, legacyReviewRequired: false, missing: [] };
const ready = () => { const state = structuredClone(fixture); state.task.generation_language = 'English'; return state; };
const selected = (state) => state.directions.find((item) => item.direction_id === state.task.selected_direction.id && item.revision === state.task.selected_direction.revision);

test('Production distinguishes missing, unsaved, unapplied and loading context', () => {
  const state = ready();
  assert.equal(productionBlocker(state, context, false, false), null);
  assert.deepEqual(productionBlocker(state, { ...context, loading: true }, false, false), { message: 'Loading project context…' });
  assert.deepEqual(productionBlocker(state, { ...context, loading: true, error: 'Unavailable' }, false, false), { message: 'Project context could not be loaded.', action: 'Review project context', destination: 'context' });
  assert.equal(productionBlocker(state, { ...context, error: 'Save failed', unsaved: true }, false, false).message, 'Project context changes could not be saved.');
  assert.equal(productionBlocker(state, { ...context, unsaved: true }, false, false).action, 'Review project context');
  assert.equal(productionBlocker(state, { ...context, pending: true }, false, false).action, 'Apply context changes');
  assert.equal(productionBlocker(state, { ...context, pending: true, missing: ['Product'] }, false, false).action, 'Complete project context');
  state.task.current_brief = null;
  assert.equal(productionBlocker(state, context, false, false).action, 'Complete project context');
});

test('reference corrections and missing source review route to Timeline without blocking an original idea', () => {
  const state = ready();
  assert.equal(productionBlocker(state, context, true, false).destination, 'timeline');
  const analysis = state.analyses.find((item) => item.analysis_id === state.task.current_analysis.id && item.revision === state.task.current_analysis.revision);
  analysis.review.user_confirmed = false;
  assert.match(productionBlocker(state, context, false, false).message, /Confirm the reference/);
  selected(state).analysis_ref = null;
  assert.equal(productionBlocker(state, context, true, false), null);
});

test('approval must match the selected revision and context; idea drafts remain a visible prerequisite', () => {
  const state = ready();
  assert.equal(productionBlocker(state, context, false, true).action, 'Review idea draft');
  selected(state).approval_status = 'draft';
  assert.equal(productionBlocker(state, context, false, false).action, 'Choose and approve an idea');
  selected(state).approval_status = 'approved';
  selected(state).brief_ref.revision += 1;
  assert.equal(productionBlocker(state, context, false, false).action, 'Choose and approve an idea');
});

test('legacy claim review, missing language and stale references have distinct recovery destinations', () => {
  const state = ready();
  assert.equal(productionBlocker(state, { ...context, legacyReviewRequired: true }, false, false).action, 'Review product claims');
  state.task.generation_language = null;
  assert.equal(productionBlocker(state, context, false, false).action, 'Choose generation language');
  state.task.generation_language = 'English';
  state.task.current_analysis = null;
  assert.equal(productionBlocker(state, context, false, false).action, 'Review and approve an idea');
});
