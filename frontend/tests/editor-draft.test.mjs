import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/editorDraftSession.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { EditorDraftSession } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const draft = (content = { text: 'Applied text' }) => ({ task_id: 'task_one', scope: 'analysis', draft_version: 1, base_refs: { analysis: { id: 'analysis_one', revision: 1 } }, content, has_pending_changes: false, conflict: false, updated_at: '2026-10-17T00:00:00Z' });
const defer = () => { let resolve; let reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };

test('switching tasks waits for newer typing entered during an in-flight save', async () => {
  const first = defer();
  const second = defer();
  const sent = [];
  const session = new EditorDraftSession(draft(), (input) => { sent.push(input); return sent.length === 1 ? first.promise : second.promise; }, () => {});
  session.edit({ text: 'First correction' });
  const complete = session.flush();
  session.edit({ text: '保温六小时 · with qualification' });
  assert.equal(session.flush(), complete);
  first.resolve({ ...draft(sent[0].content), draft_version: 2, has_pending_changes: true });
  await Promise.resolve();
  assert.equal(session.current.content.text, '保温六小时 · with qualification');
  assert.equal(sent[1].expected_draft_version, 2);
  second.resolve({ ...draft(sent[1].content), draft_version: 3, has_pending_changes: true });
  await complete;
  assert.equal(session.dirty, false);
  assert.equal(session.pending, true);
  assert.equal(session.current.content.text, '保温六小时 · with qualification');
});

test('failed persistence retains exact text and uses last acknowledged version when retried', async () => {
  let attempts = 0;
  const session = new EditorDraftSession(draft(), async (input) => {
    assert.equal(input.expected_draft_version, 1);
    if (++attempts === 1) throw new Error('Temporary network failure');
    return { ...draft(input.content), draft_version: 2, has_pending_changes: true };
  }, () => {});
  session.edit({ text: 'Unsaved 中文 correction' });
  await assert.rejects(session.flush(), /network failure/);
  assert.equal(session.current.content.text, 'Unsaved 中文 correction');
  assert.equal(session.dirty, true);
  await session.flush();
  assert.equal(session.dirty, false);
  assert.equal(session.error, '');
});

test('interrupted save recovered on the same server version can be safely flushed', async () => {
  const session = new EditorDraftSession(draft(), async (input) => ({ ...draft(input.content), draft_version: 2, has_pending_changes: true }), () => {});
  session.recover({ text: 'Recovered after browser close' }, false);
  assert.equal(session.pending, true);
  await session.flush();
  assert.equal(session.current.content.text, 'Recovered after browser close');
  assert.equal(session.dirty, false);
});

test('recovered work never overwrites a newer server version', async () => {
  let writes = 0;
  const session = new EditorDraftSession({ ...draft({ text: 'Other tab saved this' }), draft_version: 4 }, async () => { writes += 1; return draft(); }, () => {});
  session.recover({ text: 'My interrupted local draft' }, true);
  await assert.rejects(session.flush(), /newer saved draft/);
  assert.equal(writes, 0);
  assert.equal(session.current.content.text, 'My interrupted local draft');
  assert.equal(session.current.conflict, true);
});

test('formal checkpoint clears pending work without pretending content was auto-approved', () => {
  const session = new EditorDraftSession(draft(), async () => draft(), () => {});
  session.edit({ text: 'Saved correction' });
  assert.equal(session.pending, true);
  session.replace({ ...draft({ text: 'Saved correction' }), draft_version: 3, base_refs: { analysis: { id: 'analysis_one', revision: 2 } } });
  assert.equal(session.pending, false);
  assert.equal(session.dirty, false);
  assert.equal(session.current.base_refs.analysis.revision, 2);
});

test('reverting all local changes does not require a formal revision', async () => {
  const session = new EditorDraftSession(draft(), async (input) => ({ ...draft(input.content), draft_version: 2 }), () => {});
  session.edit({ text: 'Temporary edit' });
  session.edit({ text: 'Applied text' });
  assert.equal(session.pending, false);
  await session.flush();
  assert.equal(session.current.has_pending_changes, false);
});

test('a competing tab save marks the retained local draft conflicted instead of retrying stale versions forever', async () => {
  let writes = 0;
  const session = new EditorDraftSession(draft(), async () => {
    writes += 1;
    throw Object.assign(new Error('Another tab saved a newer draft.'), { status: 409, code: 'editor_draft_conflict' });
  }, () => {});
  session.edit({ text: 'Keep my competing edit for comparison' });
  await assert.rejects(session.flush(), /newer draft/);
  assert.equal(session.current.conflict, true);
  assert.equal(session.current.content.text, 'Keep my competing edit for comparison');
  await assert.rejects(session.flush(), /retained/);
  assert.equal(writes, 1);
  session.replace({ ...draft({ text: 'Latest saved content from another tab' }), draft_version: 3, has_pending_changes: true });
  assert.equal(session.current.conflict, false);
  assert.equal(session.current.draft_version, 3);
  assert.equal(session.dirty, false);
});
