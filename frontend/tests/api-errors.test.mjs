import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/api.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { ApiError, operationErrorMessage, request } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('background authentication failures retain their cause without a false draft-conflict instruction', async (context) => {
  const message = 'Provider authentication failed; check your API key.';
  context.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => ({ status: 'failed', result: null, error: { code: 'provider_authentication_failed', message } }) }));
  let failure;
  try { await request('/tasks/task_demo/recognize', { video_id: 'video_demo' }); } catch (error) { failure = error; }
  assert.ok(failure instanceof ApiError);
  assert.equal(failure.code, 'provider_authentication_failed');
  assert.equal(operationErrorMessage(failure), message);
});

test('only actual version conflicts suggest reopening a retained draft', () => {
  assert.match(operationErrorMessage(new ApiError('Task changed.', 409, 'version_conflict')), /Reopen the saved project/);
  assert.equal(operationErrorMessage(new ApiError('Provider is busy.', 409, 'provider_connection_busy')), 'Provider is busy.');
  assert.equal(operationErrorMessage(new ApiError('No account credit.', 409, 'provider_quota_exceeded')), 'No account credit.');
});
