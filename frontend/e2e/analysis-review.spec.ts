import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import type { TaskState } from '../src/generated/contracts';

async function update(api: APIRequestContext, state: TaskState, path: string, body: Record<string, unknown> = {}): Promise<TaskState> {
  const response = await api.post(`/api/tasks/${state.task.task_id}${path}`, { data: { expected_version: state.task.version, ...body } });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function sample(api: APIRequestContext) {
  const created = await api.post('/api/tasks', { data: { title: 'Reference corrections recovery' } });
  let state: TaskState = await created.json();
  state = await update(api, state, '/sample');
  state = await update(api, state, '/recognize');
  state = await update(api, state, '/analysis/confirm', { analysis_ref: state.task.current_analysis });
  state = await update(api, state, '/language', { generation_language: 'English' });
  return state;
}

async function open(page: Page, state: TaskState) {
  await page.addInitScript((id) => {
    localStorage.setItem('video-anatomy-task', id);
    localStorage.setItem(`video-anatomy-area:${id}`, 'reference');
  }, state.task.task_id);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Read the reference.', exact: true })).toBeVisible();
}

const observation = (page: Page) => page.locator('[data-evidence-id="event_intro_text"]');
const correction = (page: Page) => page.getByLabel('Recognized text · event_intro_text', { exact: true });

async function edit(page: Page, text: string) {
  if (!await correction(page).isVisible()) await observation(page).getByRole('button', { name: /^Correct visible text/ }).click();
  await correction(page).fill(text);
}

test('reference corrections restore after refresh/task switches, gate new work, and apply separately from confirmation', async ({ page, request }) => {
  const state = await sample(request);
  const taskId = state.task.task_id;
  const otherResponse = await request.post('/api/tasks', { data: { title: 'Another reference task' } });
  const other: TaskState = await otherResponse.json();
  await open(page, state);
  await expect(page.locator('.m5 textarea')).toHaveCount(0);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 960 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.locator('.m5').screenshot({ path: `/tmp/m5-evidence-${width}.png` });
  }
  await page.setViewportSize({ width: 1440, height: 960 });
  await expect(page.locator('[data-evidence-id="event_footer"]')).toHaveCount(1);
  await expect(page.locator('.m5-coverage-note')).toContainText('not every shot');
  await edit(page, 'LUMACUP · 保留的纠正草稿');
  await page.locator('#tab-directions').click();
  await expect(page.getByRole('button', { name: 'Generate two sample directions', exact: true })).toBeDisabled();
  const saved = await request.get(`/api/tasks/${taskId}/editors/analysis`);
  expect((await saved.json()).has_pending_changes).toBe(true);
  const preserved: TaskState = await (await request.get(`/api/tasks/${taskId}`)).json();
  expect(preserved.task.version).toBe(state.task.version);
  expect(preserved.analyses.at(-1)?.review.user_confirmed).toBe(true);
  const blocked = await request.post(`/api/tasks/${taskId}/recognize`, { data: { expected_version: state.task.version } });
  expect(blocked.ok()).toBe(false);
  expect((await blocked.json()).error.code).toBe('editor_pending_changes');
  await page.locator('#tab-reference').click();
  await page.reload();
  await edit(page, 'LUMACUP · 保留的纠正草稿');
  await expect(correction(page)).toHaveValue('LUMACUP · 保留的纠正草稿');
  await page.getByRole('complementary', { name: 'Saved tasks' }).getByRole('button', { name: new RegExp(other.task.title) }).click();
  await expect(page.getByRole('heading', { name: other.task.title, exact: true })).toBeVisible();
  await page.getByRole('complementary', { name: 'Saved tasks' }).getByRole('button', { name: new RegExp(state.task.title) }).click();
  await observation(page).getByRole('button', { name: /^Correct visible text/ }).click();
  await expect(correction(page)).toHaveValue('LUMACUP · 保留的纠正草稿');
  await page.getByRole('button', { name: 'Discard corrections', exact: true }).click();
  await page.getByRole('button', { name: 'Discard draft changes', exact: true }).click();
  await expect(observation(page).locator('.m5-observation-copy')).toHaveText('LUMACUP\nFICTIONAL SAMPLE');
  await expect(page.locator('.m5-review-status')).toContainText('Review confirmed');
  await edit(page, 'LUMACUP · 已应用的纠正');
  const response = page.waitForResponse((item) => item.request().method() === 'POST' && new URL(item.url()).pathname.endsWith('/analysis/correct'));
  await page.getByRole('button', { name: 'Save analysis corrections', exact: true }).click();
  const appliedResponse = await response;
  expect(appliedResponse.ok(), await appliedResponse.text()).toBeTruthy();
  const applied: TaskState = await appliedResponse.json();
  expect(applied.analyses).toHaveLength(2);
  expect(applied.analyses[0]).toEqual(state.analyses[0]);
  expect(applied.analyses[1].review.user_confirmed).toBe(false);
  await expect(page.getByRole('button', { name: 'Use this reviewed analysis', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Use this reviewed analysis', exact: true }).click();
  await expect(page.locator('.m5-review-status')).toContainText('Review confirmed');
});

test('a failed correction autosave retains local wording and can retry without changing formal analysis', async ({ page, request }) => {
  const state = await sample(request);
  await open(page, state);
  let fail = true;
  await page.route(`**/api/tasks/${state.task.task_id}/editors/analysis`, async (route) => {
    if (route.request().method() === 'POST' && fail) await route.fulfill({ status: 503, json: { error: { code: 'fixture_unavailable', message: 'Save unavailable in this test. Retry your draft.', retryable: true } } });
    else await route.continue();
  });
  await edit(page, 'Draft remains after temporary failure');
  await expect(page.locator('.m5').getByRole('alert')).toContainText('Save unavailable');
  await expect(correction(page)).toHaveValue('Draft remains after temporary failure');
  fail = false;
  await page.getByRole('button', { name: 'Retry draft save', exact: true }).click();
  await expect(page.locator('.m5').getByRole('alert')).toHaveCount(0);
  await expect.poll(async () => (await (await request.get(`/api/tasks/${state.task.task_id}/editors/analysis`)).json()).content.events.find((event: {event_id: string}) => event.event_id === 'event_intro_text').text).toBe('Draft remains after temporary failure');
  const formal: TaskState = await (await request.get(`/api/tasks/${state.task.task_id}`)).json();
  expect(formal.analyses).toEqual(state.analyses);
});
