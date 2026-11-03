import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import type { TaskState } from '../src/generated/contracts';

async function update(api: APIRequestContext, state: TaskState, path: string, body: Record<string, unknown> = {}): Promise<TaskState> {
  const response = await api.post(`/api/tasks/${state.task.task_id}${path}`, { data: { expected_version: state.task.version, ...body } });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}
async function sample(api: APIRequestContext) {
  let state: TaskState = await (await api.post('/api/tasks', { data: { title: 'Timeline corrections recovery' } })).json();
  state = await update(api, state, '/sample');
  state = await update(api, state, '/recognize');
  return state;
}
async function open(page: Page, state: TaskState) {
  await page.addInitScript((id) => { localStorage.setItem('video-anatomy-task', id); localStorage.setItem(`video-anatomy-area:${id}`, 'reference'); }, state.task.task_id);
  await page.goto('/');
  await expect(page.getByRole('region', { name: 'Video evidence timeline' })).toBeVisible();
}
async function selectText(page: Page) {
  await page.locator('.timeline-mark.on_screen_text').first().click();
  const dropdown = page.getByLabel('Visible text at selected sample');
  if (await dropdown.isVisible()) await dropdown.selectOption('event_intro_text');
}
async function edit(page: Page, text: string) {
  await selectText(page);
  const correction = page.getByLabel('Recognized text · event_intro_text', { exact: true });
  if (!await correction.isVisible()) await page.locator('[data-evidence-id="event_intro_text"]').getByRole('button', { name: /^Correct visible text/ }).click();
  await correction.fill(text);
  return correction;
}

test('timeline stays reachable, selects one inspector, and supports keyboard seeking', async ({ page, request }) => {
  const state = await sample(request);
  await open(page, state);
  for (const viewport of [{ width: 1440, height: 900 }, { width: 1280, height: 800 }, { width: 1024, height: 768 }]) {
    await page.setViewportSize(viewport);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/video-anatomy-timeline-${viewport.width}.png` });
    await page.locator('.reference-timeline-slot').scrollIntoViewIfNeeded();
    const timeline = await page.locator('.reference-timeline-slot').boundingBox();
    expect(timeline!.y + timeline!.height).toBeLessThanOrEqual(viewport.height);
    await expect(page.locator('.m5-observation')).toHaveCount(1);
  }
  await page.locator('.timeline-mark.visual_action').first().focus();
  await page.keyboard.press('ArrowRight');
  const selected = state.analyses[0].events.filter((event) => event.kind === 'visual_action')[1];
  await expect(page.locator(`[data-evidence-id="${selected.event_id}"]`)).toBeVisible();
  await expect(page.getByTestId('reference-frame-position')).toContainText(`· ${selected.start_frame} /`);
  await page.locator('#tab-directions').click();
  await expect(page.locator('#area-directions')).toBeVisible();
  await page.locator('#tab-reference').click();
  await expect(page.locator(`[data-evidence-id="${selected.event_id}"]`)).toBeVisible();
});

test('selected correction draft survives reload and applies separately from confirmation', async ({ page, request }) => {
  const state = await sample(request);
  await open(page, state);
  await edit(page, 'LUMACUP · retained correction');
  await expect.poll(async () => (await (await request.get(`/api/tasks/${state.task.task_id}/editors/analysis`)).json()).has_pending_changes).toBe(true);
  await page.reload();
  await selectText(page);
  await page.locator('[data-evidence-id="event_intro_text"]').getByRole('button', { name: /^Correct visible text/ }).click();
  await expect(page.getByLabel('Recognized text · event_intro_text')).toHaveValue('LUMACUP · retained correction');
  await page.getByRole('button', { name: 'Save analysis corrections', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Use this reviewed analysis', exact: true })).toBeEnabled();
  const saved: TaskState = await (await request.get(`/api/tasks/${state.task.task_id}`)).json();
  expect(saved.analyses).toHaveLength(2);
  expect(saved.analyses[0]).toEqual(state.analyses[0]);
  expect(saved.analyses[1].review.user_confirmed).toBe(false);
  await page.getByRole('button', { name: 'Use this reviewed analysis', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Analysis reviewed', exact: true })).toBeDisabled();
});

test('failed correction save stays in inspector and retries without losing wording', async ({ page, request }) => {
  const state = await sample(request);
  await open(page, state);
  let fail = true;
  await page.route(`**/api/tasks/${state.task.task_id}/editors/analysis`, async (route) => {
    if (route.request().method() === 'POST' && fail) await route.fulfill({ status: 503, json: { error: { code: 'fixture_unavailable', message: 'Save unavailable in this test.', retryable: true } } });
    else await route.continue();
  });
  const correction = await edit(page, 'Draft retained after failure');
  await expect(page.locator('.reference-inspector').getByRole('alert')).toContainText('Save unavailable');
  await expect(correction).toHaveValue('Draft retained after failure');
  fail = false;
  await page.getByRole('button', { name: 'Retry draft save' }).click();
  await expect(page.locator('.reference-inspector').getByRole('alert')).toHaveCount(0);
  const formal: TaskState = await (await request.get(`/api/tasks/${state.task.task_id}`)).json();
  expect(formal.analyses).toEqual(state.analyses);
});

test('content-area preview saves a reversible source-coordinate crop without recognition calls', async ({ page, request }) => {
  const fixture = await sample(request);
  const media = await request.get(`/api/tasks/${fixture.task.task_id}/media/${fixture.task.current_video_id}`);
  let state: TaskState = await (await request.post('/api/tasks', { data: { title: 'Content area preview' } })).json();
  const upload = await request.post(`/api/tasks/${state.task.task_id}/video`, { multipart: { expected_version: String(state.task.version), file: { name: 'local-fixture.mp4', mimeType: 'video/mp4', buffer: await media.body() } } });
  expect(upload.ok(), await upload.text()).toBeTruthy(); state = await upload.json();
  await page.addInitScript((id) => localStorage.setItem('video-anatomy-task', id), state.task.task_id);
  await page.goto('/');
  await page.getByRole('button', { name: 'Content area', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Content area', exact: true });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel('Trim top percent').fill('10');
  await page.screenshot({ path: '/tmp/video-anatomy-content-area.png' });
  await dialog.getByRole('button', { name: 'Save content area' }).click();
  await expect(dialog).toHaveCount(0);
  const region = await (await request.get(`/api/tasks/${state.task.task_id}/videos/${state.task.current_video_id}/content-region`)).json();
  expect(region.crop.y).toBe(.1); expect(region.revision).toBe(1);
  const saved: TaskState = await (await request.get(`/api/tasks/${state.task.task_id}`)).json();
  expect(saved.jobs).toHaveLength(0);
  expect(saved.videos[0].content_sha256).toBe(state.videos[0].content_sha256);
});


test('empty and importing Timeline share dark surfaces and one progress announcement', async ({ page, request }) => {
  const fixture = await sample(request);
  const media = await request.get(`/api/tasks/${fixture.task.task_id}/media/${fixture.task.current_video_id}`);
  const state: TaskState = await (await request.post('/api/tasks', { data: { title: 'Timeline empty and import states' } })).json();
  await page.addInitScript((id) => localStorage.setItem('video-anatomy-task', id), state.task.task_id);
  await page.goto('/');
  const placeholder = page.locator('.media-placeholder');
  await expect(placeholder.getByRole('button', { name: 'Import video', exact: true })).toBeVisible();
  const contrast = await placeholder.evaluate((element) => {
    const luminance = (color: string) => color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map((component) => {
      const value = component / 255;
      return value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4;
    }).reduce((total, value, index) => total + value * [.2126, .7152, .0722][index], 0);
    const style = getComputedStyle(element);
    const a = luminance(style.color); const b = luminance(style.backgroundColor);
    return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
  });
  expect(contrast).toBeGreaterThanOrEqual(4.5);
  let releaseImport!: () => void;
  const importing = new Promise<void>((resolve) => { releaseImport = resolve; });
  await page.route(`**/api/tasks/${state.task.task_id}/video`, async (route) => { await importing; await route.continue(); });
  await placeholder.getByRole('button', { name: 'Import video', exact: true }).click();
  await page.getByLabel('Reference video file', { exact: true }).setInputFiles({ name: 'import-state-fixture.mp4', mimeType: 'video/mp4', buffer: await media.body() });
  await page.getByRole('button', { name: 'Upload reference', exact: true }).click();
  try {
    await expect(page.getByRole('status').filter({ hasText: 'Importing video…' })).toHaveCount(1);
    await expect(page.getByText('Importing video…', { exact: true })).toHaveCount(1);
    await expect(page.locator('.reference-operation-feedback')).toHaveCSS('overflow-y', 'visible');
  } finally { releaseImport(); }
  await expect(page.getByLabel('Reference video player', { exact: true })).toBeVisible();
  await expect(page.getByText('Importing video…', { exact: true })).toHaveCount(0);
});

test('analysis retry keeps evidence visible and a failed result exposes previous evidence read only', async ({ page, request }) => {
  const state = await sample(request);
  const failed = structuredClone(state);
  const error = { code: 'fixture_unavailable', message: 'Analysis unavailable in this test.', retryable: true };
  const previous = failed.analyses[0];
  failed.analyses.push({ ...previous, analysis_id: 'failed-analysis-fixture', status: 'failed', events: [], segments: [], error });
  failed.task.current_analysis = { id: 'failed-analysis-fixture', revision: previous.revision };
  failed.task.version += 1;
  failed.jobs.push({ ...failed.jobs[failed.jobs.length - 1], job_id: 'failed-job-fixture', status: 'failed', error });
  let finished = false;
  await page.route(`**/api/tasks/${state.task.task_id}`, async (route) => route.fulfill({ json: finished ? failed : state }));
  await page.route(`**/api/tasks/${state.task.task_id}/operations`, async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({ json: { operation_id: 'retry-visibility-fixture', status: 'running', result: null, error: null } });
  });
  await page.route(`**/api/tasks/${state.task.task_id}/operations/retry-visibility-fixture`, async (route) => route.fulfill({ json: { operation_id: 'retry-visibility-fixture', status: finished ? 'succeeded' : 'running', result: finished ? failed : null, error: null } }));
  await open(page, state);
  await expect(page.getByRole('button', { name: 'Use this reviewed analysis', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Analyze again', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm new analysis', exact: true }).click();
  await expect(page.getByText('Analyzing video…', { exact: true })).toHaveCount(1);
  await expect(page.locator('.m5-observation-copy')).toHaveText(previous.events[0].description!);
  finished = true;
  await expect(page.getByRole('alert').filter({ hasText: error.message })).toHaveCount(1);
  await expect(page.getByText('Showing previous analysis · read only', { exact: true })).toBeVisible();
  await expect(page.locator('.m5-observation-copy')).toHaveText(previous.events[0].description!);
  await expect(page.getByRole('button', { name: 'Use this reviewed analysis', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^Correct visual observation/ })).toHaveCount(0);
  await expect(page.getByText('Analyzing video…', { exact: true })).toHaveCount(0);
});

test('evidence panel resizes, reopens from a selected mark, and joins narrow reading flow', async ({ page, request }) => {
  const state = await sample(request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, state);
  const divider = page.getByRole('separator', { name: 'Resize evidence panel', exact: true });
  await divider.focus();
  await page.keyboard.press('ArrowLeft');
  await expect(divider).toHaveAttribute('aria-valuenow', '380');
  await page.keyboard.press('Home');
  await expect(divider).toHaveAttribute('aria-valuenow', '360');
  await page.getByRole('button', { name: 'Hide details', exact: true }).click();
  await expect(page.locator('#reference-inspector')).not.toBeVisible();
  await page.locator('.timeline-mark.visual_action').first().click();
  await expect(page.locator('#reference-inspector')).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('.reference-inspector-content')).toHaveCSS('overflow-y', 'visible');
  await expect(page.locator('.reference-inspector-content')).toHaveCSS('max-height', 'none');
  await expect(divider).not.toBeVisible();
  const order = await page.locator('.reference-editor-grid').evaluate((element) => {
    const video = element.querySelector('.reference-viewer')!.getBoundingClientRect();
    const timeline = element.querySelector('.reference-timeline-slot')!.getBoundingClientRect();
    const evidence = element.querySelector('.reference-inspector')!.getBoundingClientRect();
    return video.bottom <= timeline.top && timeline.bottom <= evidence.top;
  });
  expect(order).toBe(true);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
