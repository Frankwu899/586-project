import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { Project } from '../src/project/contracts';

const root = resolve(import.meta.dirname, '../..');
const fixture = (mode: string, id = ''): Project => JSON.parse(execFileSync(join(root, '.venv/bin/python'), [join(root, 'frontend/e2e/project-reliability-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, mode, id], { cwd: root, encoding: 'utf8' }));
async function open(page: Page, project: Project) {
  await page.goto(`/?project=${project.id}`);
  await expect(page.getByRole('button', { name: 'All projects', exact: true })).toBeVisible();
}
async function capture(page: Page, name: string) {
  const folder = process.env.VIDEO_ANATOMY_SCREENSHOT_DIR;
  if (!folder) return;
  mkdirSync(folder, { recursive: true });
  await page.screenshot({ path: join(folder, `${name}.png`), fullPage: true });
}
const wellPath = 'WellPath is a personalized preventive health platform preparing to launch in the US. It brings personal health and wellness information into an understandable dashboard and helps users set wellness goals and track progress. No clinical benefits or disease-prevention capabilities have been established.\n\nI want this campaign to make more people know WellPath, but I also want people to sign up after watching the video. I’m not sure which one should be the main goal.';

test('saved failed WellPath turn has explicit retry without duplicating its message', async ({ page, request }) => {
  const project = await (await request.post('/api/projects', { data: { title: '1.8.2 failed turn recovery' } })).json() as Project;
  await open(page, project);
  await page.getByLabel('Describe your assignment').fill(wellPath);
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Retry assistance', exact: true })).toBeVisible();
  await expect(page.locator('.va-message.user')).toHaveCount(1);
  await page.getByText('Support details', { exact: true }).click();
  await expect(page.locator('.va-message .va-support pre')).toContainText('provider_not_configured');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export support details', exact: true }).click();
  const download = await downloadPromise;
  const diagnostic = readFileSync((await download.path())!, 'utf8');
  expect(diagnostic).toContain('conversation_turn_id:');
  expect(diagnostic).not.toContain('WellPath');
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await page.reload();
  await expect(page.locator('.va-message.user')).toHaveCount(1);
  await page.getByRole('button', { name: 'Retry assistance', exact: true }).click();
  await expect.poll(async () => (await (await request.get(`/api/projects/${project.id}`)).json()).messages.filter((message: { role: string }) => message.role === 'assistant').length).toBe(2);
  await expect(page.getByRole('button', { name: 'Retry assistance', exact: true })).toHaveCount(1);
  await expect(page.locator('.va-message.user')).toHaveCount(1);
  await expect(page.locator('.va-assistant-working')).toHaveCount(0);
  const saved = await (await request.get(`/api/projects/${project.id}`)).json() as Project;
  expect(saved.messages.filter(message => message.role === 'user').map(message => message.text)).toEqual([wellPath]);
  expect(saved.briefs).toEqual([]);
  await capture(page, 'overview-retry-support');
});

test('persisted running assistance survives navigation and restart exposes explicit recovery', async ({ page, request }) => {
  const project = fixture('pending');
  await open(page, project);
  await expect(page.locator('.va-assistant-working')).toContainText('Preparing a reply');
  await page.getByLabel('Describe your assignment').fill('A later message stays in the composer.');
  await expect(page.getByRole('button', { name: 'Send message', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Stop response', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await page.reload();
  await expect(page.locator('.va-assistant-working')).toBeVisible();
  await page.getByRole('button', { name: 'Review brief', exact: true }).click();
  await page.getByRole('button', { name: 'Add information', exact: true }).click();
  await page.getByLabel('Information', { exact: true }).fill('objective');
  await page.getByLabel('Correction', { exact: true }).fill('Keep my newer objective.');
  await page.getByRole('button', { name: 'Save suggestion', exact: true }).click();
  await expect(page.locator('.va-fact-editor')).toBeHidden();
  await expect(page.getByText('Keep my newer objective.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Close review', exact: true }).click();
  fixture('restart', project.id);
  await expect(page.locator('.va-assistant-working')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Retry assistance', exact: true })).toBeVisible();
  await expect(page.getByLabel('Describe your assignment')).toHaveValue('A later message stays in the composer.');
  expect((await (await request.get(`/api/projects/${project.id}`)).json()).brief_draft[0].value).toBe('Keep my newer objective.');
});

test('partial assistance preserves useful discussion and unresolved brief review', async ({ page }) => {
  const project = fixture('partial');
  await open(page, project);
  await expect(page.locator('.va-message.assistant')).toContainText('Which outcome matters most');
  await expect(page.locator('.va-message.assistant')).toContainText('Some information could not be added');
  await page.getByRole('button', { name: /^Review changes/ }).click();
  await expect(page.locator('.va-fact.unresolved')).toContainText('Awareness or sign-ups?');
  await expect(page.getByText('Suggested', { exact: true })).toHaveCount(3);
  await expect(page.getByRole('button', { name: 'Apply updates', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Retry assistance', exact: true })).toHaveCount(0);
  await expect(page.locator('.va-fact').filter({ hasText: 'No clinical benefits have been established.' }).getByLabel('Permit this claim’s use. This does not verify its truth.')).toHaveCount(0);
  await expect(page.getByLabel('Permit this claim’s use. This does not verify its truth.')).toHaveCount(2);
  await page.getByRole('button', { name: 'Close review', exact: true }).click();
  await page.getByText('Support details', { exact: true }).click();
  await expect(page.locator('.va-support pre')).toContainText('proposals[1].excerpt');
  await expect(page.locator('.va-support pre')).toContainText('source_mismatch');
  await page.reload();
  await page.getByRole('button', { name: /^Review changes/ }).click();
  await expect(page.locator('.va-fact')).toContainText(['Awareness or sign-ups?', 'No clinical benefits have been established.']);
  // English and Chinese product-claim aliases must both remain adoptable only
  // after the user grants permission and explicitly confirms the fact.
  for (const text of ['WellPath brings wellness information together.', '健康信息集中展示。']) {
    const fact = page.locator('.va-fact').filter({ hasText: text });
    await fact.getByLabel('Permit this claim’s use. This does not verify its truth.').check();
    await fact.getByLabel('Use this update').check();
  }
  await page.getByRole('button', { name: 'Apply updates', exact: true }).click();
  await expect(page.locator('.va-overview-inspector').getByText('In use · v1', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator('.va-overview-inspector').getByText('In use · v1', { exact: true })).toBeVisible();
  // Permission lives in the adopted snapshot; unchanged claims are omitted
  // from the changes-only review instead of reappearing as pending inputs.
  const saved = await page.request.get(`/api/projects/${project.id}`);
  const adopted = (await saved.json()).briefs.at(-1).facts;
  expect(adopted.filter((fact: { permitted_for_use: boolean }) => fact.permitted_for_use)).toHaveLength(2);
  await capture(page, 'overview-partial-proposals');
});

test('partial speech exposes coverage, reuse and sanitized chunk diagnostics', async ({ page }) => {
  const project = fixture('speech');
  await open(page, project);
  await page.getByRole('button', { name: 'Focus Synthetic silent audio.wav', exact: true }).click();
  await page.getByRole('button', { name: 'Open in timeline', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Synthetic silent audio.wav' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Retry missing speech', exact: true })).toBeVisible();
  const saved = await (await page.request.get(`/api/projects/${project.id}`)).json() as Project;
  const evidence = saved.resources.find(item => item.id === project.resources[0].id)!.evidence.at(-1)!;
  expect(evidence.coverage.speech).toBe('partial');
  expect(evidence.diagnostics.speech).toBe('audio_timestamps_invalid');
  await expect(page.getByLabel('Recognition summary')).toContainText('Some speech timing is invalid. Valid transcript segments are saved; retry missing speech.');
  await expect(page.getByLabel('Recognition summary')).toContainText('Saved transcription reused');
  await expect(page.locator('.va-transcript')).toContainText('User-corrected original-language wording 中文.');
  await page.getByText('Coverage, original file and recovery', { exact: true }).click();
  await page.getByText('Support diagnostics', { exact: true }).click();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export support details', exact: true }).click();
  const download = await downloadPromise;
  const diagnostic = readFileSync((await download.path())!, 'utf8');
  expect(diagnostic).toContain('chunk_start_seconds: 1');
  expect(diagnostic).toContain('audio_timestamps_invalid');
  expect(diagnostic).not.toContain('User-corrected');
  await capture(page, 'resources-partial-transcription');
  let release!: () => void;
  let requests = 0;
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route(`**/api/projects/${project.id}/resources/${project.resources[0].id}/recognize`, async route => {
    requests += 1;
    const response = await route.fetch();
    await held;
    await route.fulfill({ response });
  });
  await page.getByRole('button', { name: 'Retry missing speech', exact: true }).click();
  try {
    await expect(page.getByRole('button', { name: 'Recognizing…', exact: true })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Rebuild media preview', exact: true })).toBeDisabled();
    await expect(page.getByRole('status').filter({ hasText: 'Processing missing evidence' })).toBeVisible();
    expect(requests).toBe(1);
  } finally { release(); }
  await expect(page.getByRole('button', { name: 'Retry missing speech', exact: true })).toBeEnabled();
  await expect(page.locator('.va-transcript')).toContainText('User-corrected original-language wording 中文.');
  await page.reload();
  await expect(page.locator('.va-transcript')).toContainText('User-corrected original-language wording 中文.');
});
