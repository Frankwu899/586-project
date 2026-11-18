import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { join, resolve } from 'node:path';

const root = resolve(import.meta.dirname, '../..');
function backgroundComplete(id: string) {
  execFileSync(join(root, '.venv/bin/python'), [join(root, 'frontend/e2e/project-concurrency-185-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, id], { cwd: root });
}

test('background completion during autosave and navigation preserves the submitted draft without a false save error', async ({ page, request }) => {
  const project = await (await request.post('/api/projects', { data: { title: 'Synthetic concurrent completion 1.8.5' } })).json();
  await page.goto(`/?project=${project.id}`);
  await expect(page.getByLabel('Describe your assignment')).toBeVisible();
  let reached!: () => void; let release!: () => void;
  const intercepted = new Promise<void>(resolve => { reached = resolve; });
  const held = new Promise<void>(resolve => { release = resolve; });
  let first = true;
  await page.route(`**/api/projects/${project.id}`, async route => {
    if (first && route.request().method() === 'PATCH' && route.request().postDataJSON()?.editor_drafts?.conversation) {
      first = false; reached(); await held;
    }
    await route.continue();
  });
  await page.getByLabel('Describe your assignment').fill('Keep the unsent edit while the saved report arrives.');
  await intercepted;
  backgroundComplete(project.id);
  const navigate = page.getByRole('button', { name: 'Resources', exact: true }).click();
  release(); await navigate;
  await expect.poll(async () => (await (await request.get(`/api/projects/${project.id}`)).json()).editor_drafts?.conversation?.text).toBe('Keep the unsent edit while the saved report arrives.');
  await expect(page.getByRole('heading', { name: 'Media Pool', exact: true })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await page.reload();
  await expect(page.getByLabel('Describe your assignment')).toHaveValue('Keep the unsent edit while the saved report arrives.');
});

test('a real scope conflict retains local text and does not replace a competing saved draft', async ({ page, request }) => {
  const project = await (await request.post('/api/projects', { data: { title: 'Synthetic competing drafts 1.8.5' } })).json();
  await page.goto(`/?project=${project.id}`);
  await expect(page.getByLabel('Describe your assignment')).toBeVisible();
  let reached!: () => void; let release!: () => void;
  const intercepted = new Promise<void>(resolve => { reached = resolve; });
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route(`**/api/projects/${project.id}`, async route => {
    if (route.request().method() === 'PATCH' && route.request().postDataJSON()?.editor_drafts?.conversation) { reached(); await held; }
    await route.continue();
  });
  await page.getByLabel('Describe your assignment').fill('This local competing draft must remain recoverable.');
  await intercepted;
  const competing = await request.patch(`/api/projects/${project.id}`, { data: { expected_version: project.version, expected_editor_versions: { conversation: 0 }, editor_drafts: { conversation: { text: 'Saved in the other window.', resource_ids: [] } } } });
  expect(competing.ok()).toBeTruthy();
  release();
  await expect(page.getByText('A newer draft was saved elsewhere. Your local text is retained for comparison.')).toBeVisible();
  await expect(page.getByLabel('Describe your assignment')).toHaveValue('This local competing draft must remain recoverable.');
  const saved = await (await request.get(`/api/projects/${project.id}`)).json();
  expect(saved.editor_drafts.conversation.text).toBe('Saved in the other window.');
});


test('background completion allows the same reference selection to save once while analysis admission remains explicit', async ({ page, request }) => {
  const project = JSON.parse(execFileSync(join(root, '.venv/bin/python'), [join(root, 'frontend/e2e/project-concurrency-185-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, 'seed'], { cwd: root, encoding: 'utf8' }));
  await page.goto(`/?project=${project.id}`);
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  await page.getByRole('checkbox', { name: 'Select synthetic-reference.mp4', exact: true }).check();
  await page.getByRole('button', { name: 'Analyze 1 reference', exact: true }).click();
  let reached!: () => void; let release!: () => void;
  const intercepted = new Promise<void>(resolve => { reached = resolve; });
  const held = new Promise<void>(resolve => { release = resolve; });
  let once = true; let analyses = 0;
  await page.route(`**/api/projects/${project.id}/selection`, async route => {
    if (once) { once = false; reached(); await held; }
    await route.continue();
  });
  await page.route(`**/api/projects/${project.id}/analyze`, async route => {
    analyses += 1;
    const saved = await (await request.get(`/api/projects/${project.id}`)).json();
    await route.fulfill({ json: saved });
  });
  await page.getByRole('dialog').getByRole('button', { name: 'Start analysis', exact: true }).click();
  await intercepted;
  backgroundComplete(project.id); release();
  await expect.poll(async () => (await (await request.get(`/api/projects/${project.id}`)).json()).selection.resource_ids).toEqual(['video_185']);
  await expect(page.getByRole('heading', { name: 'Reference analysis', exact: true })).toBeVisible();
  expect(analyses).toBe(1);
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('an action precondition is reported without calling it a failed save', async ({ page, request }) => {
  const project = await (await request.post('/api/projects', { data: { title: 'Synthetic action precondition' } })).json();
  await page.goto(`/?project=${project.id}`);
  await expect(page.getByLabel('Describe your assignment')).toBeVisible();
  await page.route(`**/api/projects/${project.id}`, async route => {
    if (route.request().method() === 'PATCH' && route.request().postDataJSON()?.workspace) {
      await route.fulfill({ status: 409, json: { error: { code: 'evidence_pending_changes', message: 'Apply or discard the pending evidence corrections before this action.' } } });
    } else await route.continue();
  });
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Apply or discard');
  await expect(page.locator('.va-save-state')).toHaveText('Action needs attention');
});

test('a changed saved reference selection blocks stale admission and keeps the local checked choice', async ({ page, request }) => {
  const project = JSON.parse(execFileSync(join(root, '.venv/bin/python'), [join(root, 'frontend/e2e/project-concurrency-185-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, 'seed'], { cwd: root, encoding: 'utf8' }));
  await page.goto(`/?project=${project.id}`);
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  const checked = page.getByRole('checkbox', { name: 'Select synthetic-reference.mp4', exact: true });
  await checked.check();
  await page.getByRole('button', { name: 'Analyze 1 reference', exact: true }).click();
  let reached!: () => void; let release!: () => void;
  const intercepted = new Promise<void>(resolve => { reached = resolve; });
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route(`**/api/projects/${project.id}/selection`, async route => { reached(); await held; await route.continue(); });
  let analyses = 0;
  await page.route(`**/api/projects/${project.id}/analyze`, async route => { analyses += 1; await route.abort(); });
  await page.getByRole('dialog').getByRole('button', { name: 'Start analysis', exact: true }).click();
  await intercepted;
  const before = await (await request.get(`/api/projects/${project.id}`)).json();
  const competing = await request.post(`/api/projects/${project.id}/selection`, { data: { expected_version: before.version, resource_ids: ['video_185'] } });
  expect(competing.ok()).toBeTruthy(); release();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('changed');
  await expect(checked).toBeChecked();
  expect(analyses).toBe(0);
});
