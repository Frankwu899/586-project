import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/m2DraftSession.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { M2DraftSession } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const draft = () => ({ task_id: 'task_test', draft_version: 1, fields: { brand_company: null, product: null }, claims: [], source_notes: '', has_pending_inputs: false });
const editBrand = (session, text) => session.edit((previous) => ({ ...previous, fields: { ...previous.fields, brand_company: text } }));
const defer = () => { let resolve; let reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };

// These tests model delayed network acknowledgements, rather than asserting implementation steps.
test('typing through a delayed save retains exact newer text and flush waits for both versions', async () => {
  const first = defer();
  const second = defer();
  const sent = [];
  const session = new M2DraftSession(draft(), (input) => { sent.push(input); return sent.length === 1 ? first.promise : second.promise; }, () => {});
  editBrand(session, '早期 wording');
  const complete = session.flush();
  editBrand(session, '更新 · newer wording');
  assert.equal(session.flush(), complete);
  assert.equal(sent.length, 1);
  first.resolve({ ...draft(), draft_version: 2, fields: { ...draft().fields, brand_company: '早期 wording' }, has_pending_inputs: true });
  await Promise.resolve();
  assert.equal(session.current.fields.brand_company, '更新 · newer wording');
  assert.equal(sent.length, 2);
  assert.equal(sent[1].expected_draft_version, 2);
  assert.equal(session.dirty, true);
  second.resolve({ ...draft(), draft_version: 3, fields: { ...draft().fields, brand_company: '更新 · newer wording' }, has_pending_inputs: true });
  const saved = await complete;
  assert.equal(saved.fields.brand_company, '更新 · newer wording');
  assert.equal(saved.draft_version, 3);
  assert.equal(session.dirty, false);
});

test('failed draft persistence retains text and retries with the last acknowledged version', async () => {
  let attempts = 0;
  const session = new M2DraftSession(draft(), async (input) => {
    attempts += 1;
    if (attempts === 1) throw new Error('Storage temporarily unavailable');
    assert.equal(input.expected_draft_version, 1);
    return { ...draft(), ...input, draft_version: 2 };
  }, () => {});
  editBrand(session, 'Retain this');
  await assert.rejects(session.flush(), /temporarily unavailable/);
  assert.equal(session.current.fields.brand_company, 'Retain this');
  assert.equal(session.dirty, true);
  assert.equal(session.saving, false);
  await session.flush();
  assert.equal(session.current.fields.brand_company, 'Retain this');
  assert.equal(session.dirty, false);
  assert.equal(session.error, '');
});

test('editing after a validation error permits a new save without losing unconfirmed draft claims', async () => {
  const session = new M2DraftSession(draft(), async (input) => {
    if (input.claims[0].source_urls[0] === 'https:') throw new Error('Use an http or https source URL');
    return { ...draft(), ...input, draft_version: 2, has_pending_inputs: true };
  }, () => {});
  session.edit((previous) => ({ ...previous, claims: [{ claim_id: 'claim_1', statement: '原文 preserved', source_urls: ['https:'], confirmed_for_use: false }] }));
  await assert.rejects(session.flush(), /source URL/);
  session.edit((previous) => ({ ...previous, claims: [{ ...previous.claims[0], source_urls: ['https://example.com/test'] }] }));
  assert.equal(session.error, '');
  await session.flush();
  assert.equal(session.current.claims[0].confirmed_for_use, false);
  assert.equal(session.current.claims[0].statement, '原文 preserved');
});

test('source notes need persistence but do not create pending formal input changes', async () => {
  const session = new M2DraftSession(draft(), async (input) => ({ ...draft(), ...input, draft_version: 2 }), () => {});
  session.edit((previous) => ({ ...previous, source_notes: 'Pasted text is data, not adopted input.' }));
  assert.equal(session.dirty, true);
  assert.equal(session.pending, false);
  await session.flush();
  assert.equal(session.pending, false);
  editBrand(session, 'An adopted structured value');
  assert.equal(session.pending, true);
});

test('a conflict preserves the local draft until explicit recovery from saved state', async () => {
  const session = new M2DraftSession(draft(), async () => { throw new Error('Draft conflict'); }, () => {});
  editBrand(session, 'My local value');
  await assert.rejects(session.flush(), /Draft conflict/);
  assert.equal(session.current.fields.brand_company, 'My local value');
  session.replace({ ...draft(), draft_version: 5, fields: { ...draft().fields, brand_company: 'Explicitly reloaded value' } });
  assert.equal(session.current.fields.brand_company, 'Explicitly reloaded value');
  assert.equal(session.dirty, false);
  assert.equal(session.error, '');
});
