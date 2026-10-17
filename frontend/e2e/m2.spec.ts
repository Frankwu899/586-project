import { expect, test, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import type { TaskState } from '../src/generated/contracts';
import { area, applyInputs, draftSaved, editBrand, editTask, fillInputs } from './m2-helpers';

const evidence = resolve(import.meta.dirname, '../../.local-data/m2-ui-evidence');
const minimum = {
  'Brand/company': 'Luma team (fictional)', Product: 'LumaCup 随行杯',
  'Selling points': 'Keeps drinks warm for up to 6 hours',
  'Target audience': 'Office commuters', 'Publishing platform': 'TikTok',
  'Communication goal': 'Demonstrate everyday usefulness', 'Target duration (seconds)': '20',
};

async function create(page: Page, title: string): Promise<TaskState> {
  await page.goto('/');
  await page.getByLabel('New task title', { exact: true }).fill(title);
  const response = page.waitForResponse((item) => item.request().method() === 'POST' && new URL(item.url()).pathname === '/api/tasks');
  await page.getByRole('button', { name: 'Create task', exact: true }).click();
  const result = await response;
  expect(result.ok()).toBeTruthy();
  await expect(page.getByTestId('m2-editor')).toBeVisible();
  return result.json();
}

async function savedState(page: Page, id: string): Promise<TaskState> {
  const response = await page.request.get(`/api/tasks/${id}`);
  expect(response.ok()).toBeTruthy();
  return response.json();
}

test('empty and partial inputs have no defaults, survive reopening, and fit desktop and narrow screens', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const initial = await create(page, 'Partial bilingual M2 draft');
  await expect(page.getByRole('heading', { name: 'Shape the work.', exact: true })).toBeVisible();
  await area(page, 'reference');
  await expect(page.getByLabel('Reference video file', { exact: true })).toBeEnabled();
  await area(page, 'inputs');
  for (const width of [1440, 1024, 390, 320]) {
    await page.setViewportSize({ width, height: 960 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `${evidence}/empty-${width}.png`, fullPage: true });
    if (width === 1440 || width === 390) await page.getByTestId('m2-editor').screenshot({ path: `${evidence}/empty-inputs-${width}.png` });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await editTask(page);
  for (const label of ['Target audience', 'Publishing platform', 'Communication goal', 'Target duration (seconds)']) {
    await expect(page.getByLabel(label, { exact: true })).toHaveValue('');
  }
  for (const [question, heading, answerLabel] of [
    ['target_audience', 'Who should this speak to?', 'Target audience'],
    ['communication_goal', 'What should viewers take away?', 'Communication goal'],
    ['target_duration_seconds', 'How much time do you have?', 'Target duration (seconds)'],
  ]) {
    await page.getByLabel('Choose another question', { exact: true }).selectOption(question);
    await expect(page.locator('#m2-question-heading')).toHaveText(heading);
    await expect(page.getByLabel(`Your answer — ${answerLabel}`, { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Decide later', exact: true }).click();
  }
  await editBrand(page);
  await page.getByLabel('Brand/company', { exact: true }).fill('Luma 乐玛');
  await page.getByLabel('Product', { exact: true }).fill('随行杯 — keep original text');
  await expect(page.getByLabel('Choose another question', { exact: true })).toHaveValue('brand_company');
  await expect(page.locator('#m2-question-heading')).toHaveText('What is the brand or company?');
  await expect(page.getByLabel('Your answer — Brand/company', { exact: true })).toBeVisible();
  for (const label of ['Target audience', 'Communication goal', 'Target duration (seconds)']) {
    await expect(page.getByLabel(label, { exact: true })).toHaveValue('');
  }
  await draftSaved(page);
  let state = await savedState(page, initial.task.task_id);
  expect(state.task.version).toBe(initial.task.version);
  expect(state.briefs).toEqual([]);
  await page.screenshot({ path: `${evidence}/partial-1440.png`, fullPage: true });
  await page.reload();
  await editBrand(page);
  await expect(page.getByLabel('Brand/company', { exact: true })).toHaveValue('Luma 乐玛');
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('随行杯 — keep original text');
  await editTask(page);
  await expect(page.getByLabel('Target duration (seconds)', { exact: true })).toHaveValue('');
  await expect(page.getByTestId('m2-editor')).toContainText(/audience|selling point/i);
  state = await savedState(page, initial.task.task_id);
  expect(state.task.current_brief).toBeNull();
});

test('review includes only confirmed claims and wording edits clear permission without changing applied input', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const initial = await create(page, 'M2 exact claim review');
  await fillInputs(page, minimum);
  await page.getByRole('checkbox', { name: /^Confirmed for use\s*: selling point/ }).first().uncheck();
  await page.getByRole('button', { name: 'Review inputs', exact: true }).last().click();
  await expect(page.getByRole('button', { name: 'Apply inputs', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Apply inputs', exact: true })).toHaveAttribute('aria-describedby', 'm2-missing');
  await expect(page.getByRole('alert')).toContainText('Confirmed selling point');
  await page.getByRole('button', { name: 'Back to editing', exact: true }).click();
  await page.getByRole('checkbox', { name: /^Confirmed for use\s*: selling point/ }).first().check();
  await page.getByText('Support and conditions', { exact: true }).click();
  await page.getByLabel('Qualification for selling point 1', { exact: true }).fill('Up to 6 hours, indoor test only.');
  await expect(page.getByRole('checkbox', { name: /^Confirmed for use\s*: selling point/ }).first()).not.toBeChecked();
  await page.getByLabel('Supporting notes for selling point 1', { exact: true }).fill('Supplied internal test note; not independently verified.');
  await page.getByRole('checkbox', { name: /^Confirmed for use\s*: selling point/ }).first().check();
  await page.getByRole('button', { name: 'Add selling point', exact: true }).click();
  await page.getByLabel('Selling point 2', { exact: true }).fill('Unconfirmed alternative — all day');
  const applied = await applyInputs(page, `${evidence}/review-inputs-1440.png`);
  expect(applied.briefs).toHaveLength(1);
  expect(applied.briefs[0].selling_points).toEqual([minimum['Selling points']]);
  expect(applied.briefs[0].claim_details[0].confirmation_origin).toBe('user_confirmed');
  expect(applied.briefs[0].target_duration_seconds).toBe(20);
  expect(applied.briefs[0].claim_details[0].qualification).toBe('Up to 6 hours, indoor test only.');
  expect(applied.briefs[0].claim_details[0].supporting_notes).toContain('not independently verified');
  await expect(page.getByTestId('m2-editor')).toContainText('excluded');
  await page.screenshot({ path: `${evidence}/applied-1440.png`, fullPage: true });
  await editBrand(page);
  await page.getByLabel('Selling point 1', { exact: true }).fill('Keeps drinks warm for up to 5 hours');
  await expect(page.getByRole('checkbox', { name: /^Confirmed for use\s*: selling point/ }).first()).not.toBeChecked();
  await draftSaved(page);
  await expect(page.getByTestId('m2-editor')).toContainText(/not applied|unapplied/i);
  const current = await savedState(page, initial.task.task_id);
  expect(current.task.current_brief).toEqual(applied.task.current_brief);
  expect(current.task.version).toBe(applied.task.version);
  expect(current.briefs[0].selling_points).toEqual([minimum['Selling points']]);
});

test('a delayed autosave acknowledgement never overwrites text typed during the request', async ({ page }) => {
  const initial = await create(page, 'Serialized draft saves');
  await editBrand(page);
  let release!: () => void;
  const held = new Promise<void>((resolveHeld) => { release = resolveHeld; });
  let received!: () => void;
  const firstReceived = new Promise<void>((resolveReceived) => { received = resolveReceived; });
  let writes = 0;
  await page.route('**/m2/draft', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    writes += 1;
    const response = await route.fetch();
    if (writes === 1) { received(); await held; }
    await route.fulfill({ response });
  });
  await page.getByLabel('Product', { exact: true }).fill('Older product text');
  await firstReceived;
  await expect(page.getByTestId('m2-save-status')).toContainText('Saving');
  await page.getByLabel('Product', { exact: true }).fill('Newer product text 中文');
  release();
  await draftSaved(page);
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('Newer product text 中文');
  expect(writes).toBe(2);
  expect((await savedState(page, initial.task.task_id)).task.version).toBe(initial.task.version);
  await page.reload();
  await editBrand(page);
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('Newer product text 中文');
});

test('failed saving keeps text, reports unsaved state and recovers with an explicit retry', async ({ page }) => {
  const initial = await create(page, 'Recoverable save failure');
  await editBrand(page);
  let fail = true;
  await page.route('**/m2/draft', async (route) => {
    if (route.request().method() === 'POST' && fail) {
      await route.fulfill({ status: 503, json: { error: { code: 'test_storage_unavailable', message: 'Test storage temporarily unavailable.', retryable: true } } });
    } else await route.continue();
  });
  await page.getByLabel('Product', { exact: true }).fill('Retain my unsaved 随行杯');
  await expect(page.getByTestId('m2-editor').getByRole('alert')).toContainText('Test storage temporarily unavailable');
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('Retain my unsaved 随行杯');
  await expect(page.getByTestId('m2-save-status')).toContainText(/not saved|aren.t saved/);
  await page.setViewportSize({ width: 390, height: 960 });
  await page.screenshot({ path: `${evidence}/save-error-390.png`, fullPage: true });
  expect((await savedState(page, initial.task.task_id)).briefs).toEqual([]);
  fail = false;
  await page.getByRole('button', { name: 'Retry save', exact: true }).click();
  await draftSaved(page);
  await page.reload();
  await editBrand(page);
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('Retain my unsaved 随行杯');
});

test('manual input, confirmation, disclosure and Apply are operable by keyboard with visible focus', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 960 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await create(page, 'Keyboard-only M2 editing');
  const edit = page.getByRole('button', { name: 'Edit brand & product', exact: true });
  await edit.focus();
  await page.keyboard.press('Tab');
  await page.keyboard.press('Shift+Tab');
  await expect(edit).toBeFocused();
  expect(await edit.evaluate((element) => getComputedStyle(element).outlineStyle)).not.toBe('none');
  await page.keyboard.press('Enter');
  for (const label of ['Brand/company', 'Product']) {
    await page.getByLabel(label, { exact: true }).focus();
    await page.keyboard.insertText(minimum[label as keyof typeof minimum]);
  }
  if (!await page.getByLabel('Selling point 1', { exact: true }).isVisible()) {
    await page.getByRole('button', { name: 'Add selling point', exact: true }).focus();
    await page.keyboard.press('Enter');
  }
  await page.getByLabel('Selling point 1', { exact: true }).focus();
  await page.keyboard.insertText(minimum['Selling points']);
  await page.getByRole('checkbox', { name: /^Confirmed for use\s*: selling point/ }).focus();
  await page.keyboard.press('Space');
  await page.getByRole('button', { name: 'Edit task details', exact: true }).focus();
  await page.keyboard.press('Enter');
  for (const label of ['Target audience', 'Publishing platform', 'Communication goal', 'Target duration (seconds)']) {
    await page.getByLabel(label, { exact: true }).focus();
    await page.keyboard.insertText(minimum[label as keyof typeof minimum]);
  }
  await page.getByText('Production details and restrictions', { exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByLabel('Prohibited claims', { exact: true })).toBeVisible();
  await page.getByLabel('Prohibited claims', { exact: true }).focus();
  await page.keyboard.insertText('Do not claim dishwasher safety.');
  await page.getByRole('button', { name: 'Review inputs', exact: true }).last().focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Review your inputs.', exact: true })).toBeFocused();
  await page.getByTestId('m2-editor').screenshot({ path: `${evidence}/review-inputs-keyboard-390.png` });
  await page.getByRole('button', { name: 'Apply inputs', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('m2-editor')).toContainText('Inputs applied');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `${evidence}/applied-keyboard-390.png`, fullPage: true });
});

test('reference processing response does not block editing or replace independently saved draft text', async ({ page }) => {
  await create(page, 'Reference and inputs in parallel');
  await area(page, 'reference');
  const sampleResponse = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/sample'));
  await page.getByRole('button', { name: 'Load synthetic sample', exact: true }).click();
  const sample = await sampleResponse;
  expect(sample.ok()).toBeTruthy();
  const sampleState: TaskState = await sample.json();
  await editBrand(page);
  let release!: () => void;
  const held = new Promise<void>((resolveHeld) => { release = resolveHeld; });
  let received!: (state: TaskState) => void;
  const ready = new Promise<TaskState>((resolveReady) => { received = resolveReady; });
  await page.route('**/recognize', async (route) => {
    const response = await route.fetch();
    received(await response.json());
    await held;
    await route.fulfill({ response });
  });
  await area(page, 'reference');
  await page.getByRole('button', { name: 'Run sample analysis', exact: true }).click();
  const recognized = await ready;
  expect(recognized.analyses.at(-1)?.status).toBe('succeeded');
  await area(page, 'inputs');
  await expect(page.getByLabel('Product', { exact: true })).toBeEnabled();
  await page.getByLabel('Product', { exact: true }).fill('Typed while recognition response pending');
  await draftSaved(page);
  const whilePending = await savedState(page, sampleState.task.task_id);
  expect(whilePending.task.version).toBe(recognized.task.version);
  const response = page.waitForResponse((item) => new URL(item.url()).pathname.endsWith('/recognize'));
  release();
  expect((await response).ok()).toBeTruthy();
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('Typed while recognition response pending');
  await area(page, 'reference');
  await expect(page.getByRole('button', { name: 'Use this reviewed analysis', exact: true })).toBeEnabled();
  await page.reload();
  await editBrand(page);
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('Typed while recognition response pending');
});

test('discard is explicit and restores applied values or clears only a new input draft', async ({ page }) => {
  const initial = await create(page, 'M2 discard review');
  await fillInputs(page, minimum);
  const applied = await applyInputs(page);
  await editBrand(page);
  await page.getByLabel('Product', { exact: true }).fill('Draft to discard');
  await draftSaved(page);
  await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await expect(page.getByRole('group', { name: 'Confirm discard changes', exact: true })).toContainText('task, reference and history will stay');
  await page.getByRole('button', { name: 'Confirm discard changes', exact: true }).click();
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue(minimum.Product);
  const restored = await savedState(page, initial.task.task_id);
  expect(restored.task.version).toBe(applied.task.version);
  expect(restored.briefs).toEqual(applied.briefs);
  await page.getByLabel('New task title', { exact: true }).fill('Discard new draft only');
  const newResponse = page.waitForResponse((item) => item.request().method() === 'POST' && new URL(item.url()).pathname === '/api/tasks');
  await page.getByRole('button', { name: 'Create task', exact: true }).click();
  const newTask: TaskState = await (await newResponse).json();
  await editBrand(page);
  await page.getByLabel('Product', { exact: true }).fill('Temporary draft');
  await draftSaved(page);
  await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm discard changes', exact: true }).click();
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('');
  expect((await savedState(page, newTask.task.task_id)).briefs).toEqual([]);
});

test('switching tasks flushes text entered while the next task is loading before leaving the editor', async ({ page }) => {
  const source = await create(page, 'Switch race source');
  const targetResponse = await page.request.post('/api/tasks', { data: { title: 'Switch race target' } });
  const target: TaskState = await targetResponse.json();
  await page.reload();
  await editBrand(page);
  let releaseRead!: () => void;
  const readHold = new Promise<void>((resolveHold) => { releaseRead = resolveHold; });
  let readStarted!: () => void;
  const reading = new Promise<void>((resolveReading) => { readStarted = resolveReading; });
  await page.route(`**/api/tasks/${target.task.task_id}`, async (route) => {
    const response = await route.fetch();
    readStarted();
    await readHold;
    await route.fulfill({ response });
  });
  let releaseSave!: () => void;
  const saveHold = new Promise<void>((resolveHold) => { releaseSave = resolveHold; });
  let saves = 0;
  await page.route('**/m2/draft', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    const response = await route.fetch();
    saves += 1;
    await saveHold;
    await route.fulfill({ response });
  });
  await page.getByRole('button', { name: /^Switch race target/ }).click();
  await reading;
  await expect(page.getByLabel('Product', { exact: true })).toBeEnabled();
  await page.getByLabel('Product', { exact: true }).fill('Last-moment product text 最后编辑');
  releaseRead();
  await expect.poll(() => saves).toBe(1);
  await expect(page.getByRole('heading', { name: 'Switch race source', exact: true })).toBeVisible();
  releaseSave();
  await expect(page.getByRole('heading', { name: 'Switch race target', exact: true })).toBeVisible();
  await page.getByRole('button', { name: /^Switch race source/ }).click();
  await editBrand(page);
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('Last-moment product text 最后编辑');
  expect((await savedState(page, source.task.task_id)).task.version).toBe(source.task.version);
});

test('a delayed Apply response cannot return the user to a task they have left', async ({ page }) => {
  const source = await create(page, 'Apply race source');
  const targetResponse = await page.request.post('/api/tasks', { data: { title: 'Apply race target' } });
  const target: TaskState = await targetResponse.json();
  await page.reload();
  await fillInputs(page, minimum);
  await page.getByRole('button', { name: 'Review inputs', exact: true }).last().click();
  let release!: () => void;
  const held = new Promise<void>((resolveHold) => { release = resolveHold; });
  let received!: () => void;
  const ready = new Promise<void>((resolveReady) => { received = resolveReady; });
  await page.route('**/m2/apply', async (route) => {
    const response = await route.fetch();
    expect(response.ok()).toBeTruthy();
    received();
    await held;
    await route.fulfill({ response });
  });
  await page.getByRole('button', { name: 'Apply inputs', exact: true }).click();
  await ready;
  await page.getByRole('button', { name: /^Apply race target/ }).click();
  await expect(page.getByRole('heading', { name: 'Apply race target', exact: true })).toBeVisible();
  const response = page.waitForResponse((item) => new URL(item.url()).pathname.endsWith('/m2/apply'));
  release();
  await (await response).finished();
  await page.evaluate(() => new Promise((resolveFrame) => requestAnimationFrame(() => requestAnimationFrame(resolveFrame))));
  await expect(page.getByRole('heading', { name: 'Apply race target', exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('video-anatomy-task'))).toBe(target.task.task_id);
  await page.getByRole('button', { name: /^Apply race source/ }).click();
  await expect(page.getByTestId('m2-editor')).toContainText('Inputs applied');
  expect((await savedState(page, source.task.task_id)).briefs).toHaveLength(1);
});

test('saved tasks restore their own last work area after switching and browser refresh', async ({ page }) => {
  await create(page, 'Workspace position source');
  await area(page, 'reference');
  await expect(page.getByLabel('Reference video file', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator('#area-reference')).toBeVisible();
  await page.getByLabel('New task title', { exact: true }).fill('Workspace position target');
  await page.getByRole('button', { name: 'Create task', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Workspace position target', exact: true })).toBeVisible();
  await expect(page.locator('#area-inputs')).toBeVisible();
  await area(page, 'production');
  await page.getByRole('button', { name: /^Workspace position source/ }).click();
  await expect(page.locator('#area-reference')).toBeVisible();
  await page.getByRole('button', { name: /^Workspace position target/ }).click();
  await expect(page.locator('#area-production')).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Workspace position target', exact: true })).toBeVisible();
  await expect(page.locator('#area-production')).toBeVisible();
});

test('deleting reference media keeps historical work and pending brand inputs; replacement upload never starts analysis', async ({ page }) => {
  let state = await create(page, 'Reference lifecycle workspace');
  const update = async (path: string, body: Record<string, unknown> = {}) => {
    const response = await page.request.post(`/api/tasks/${state.task.task_id}${path}`, { data: { expected_version: state.task.version, ...body } });
    expect(response.ok(), await response.text()).toBeTruthy();
    state = await response.json();
  };
  await update('/sample');
  const oldVideo = state.task.current_video_id!;
  const media = await page.request.get(`/api/tasks/${state.task.task_id}/media/${oldVideo}`);
  expect(media.ok()).toBeTruthy();
  const mediaBytes = await media.body();
  await update('/recognize', { video_id: oldVideo });
  await update('/analysis/confirm', { analysis_ref: state.task.current_analysis });
  await update('/language', { generation_language: 'English' });
  await update('/directions/generate', { brief_ref: state.task.current_brief, analysis_ref: state.task.current_analysis });
  await update(`/directions/${state.directions[0].direction_id}/approve`, { direction_revision: state.directions[0].revision, brief_ref: state.task.current_brief, analysis_ref: state.task.current_analysis });
  await update('/outputs/generate', { direction_ref: state.task.selected_direction, brief_ref: state.task.current_brief, analysis_ref: state.task.current_analysis });
  const beforeDelete = state;
  await page.reload();
  await editBrand(page);
  await page.getByLabel('Product', { exact: true }).fill('Pending brand input survives reference deletion');
  await draftSaved(page);
  await area(page, 'reference');
  await expect(page.getByLabel('Reference video player', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Delete media', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Confirm reference deletion' })).toContainText('Historical analysis and creative work stay saved');
  expect((await savedState(page, state.task.task_id)).videos[0].deleted_at).toBeNull();
  const deletedResponse = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith(`/videos/${oldVideo}/delete`));
  await page.getByRole('button', { name: 'Delete reference media', exact: true }).click();
  const deleted = await deletedResponse;
  expect(deleted.ok(), await deleted.text()).toBeTruthy();
  state = await deleted.json();
  await expect(page.getByLabel('Reference video player', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Source media deleted · history retained', { exact: true })).toBeVisible();
  expect(state.task.current_video_id).toBeNull();
  expect(state.task.current_analysis).toBeNull();
  expect(state.task.selected_direction).toBeNull();
  expect(state.briefs).toEqual(beforeDelete.briefs);
  expect(state.analyses).toEqual(beforeDelete.analyses);
  expect(state.directions).toHaveLength(beforeDelete.directions.length);
  expect(state.production_briefs).toHaveLength(beforeDelete.production_briefs.length);
  expect(state.production_briefs.every((item) => item.currentness === 'outdated')).toBe(true);
  expect((await page.request.get(`/api/tasks/${state.task.task_id}/media/${oldVideo}`)).ok()).toBe(false);
  await editBrand(page);
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('Pending brand input survives reference deletion');
  await area(page, 'reference');
  await page.getByLabel('Reference video file', { exact: true }).setInputFiles({ name: 'replacement-reference.mp4', mimeType: 'video/mp4', buffer: mediaBytes });
  let uploaded = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/video'));
  await page.getByRole('button', { name: 'Upload reference', exact: true }).click();
  let uploadedResponse = await uploaded;
  expect(uploadedResponse.ok(), await uploadedResponse.text()).toBeTruthy();
  state = await uploadedResponse.json();
  await expect(page.getByLabel('Reference video player', { exact: true })).toBeVisible();
  expect(state.videos).toHaveLength(2);
  expect(state.videos[0].deleted_at).not.toBeNull();
  expect(state.task.current_analysis).toBeNull();
  expect(state.analyses).toEqual(beforeDelete.analyses);
  expect(state.task.mode).toBe('real');
  await expect(page.getByRole('button', { name: 'Start analysis', exact: true })).toBeEnabled();
  const uploadDetails = page.locator('.reference-sources details').last();
  if (!await uploadDetails.evaluate((element) => element.hasAttribute('open'))) await uploadDetails.locator('summary').click();
  await page.getByLabel('Reference video file', { exact: true }).setInputFiles({ name: 'second-reference.mp4', mimeType: 'video/mp4', buffer: mediaBytes });
  await page.getByRole('button', { name: 'Upload reference', exact: true }).click();
  await expect(page.getByText('This file becomes the current reference.', { exact: false })).toBeVisible();
  expect((await savedState(page, state.task.task_id)).videos).toHaveLength(2);
  uploaded = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/video'));
  await page.getByRole('button', { name: 'Confirm replacement upload', exact: true }).click();
  uploadedResponse = await uploaded;
  expect(uploadedResponse.ok(), await uploadedResponse.text()).toBeTruthy();
  state = await uploadedResponse.json();
  expect(state.videos).toHaveLength(3);
  expect(state.task.current_video_id).toBe(state.videos[2].video_id);
  expect(state.task.current_analysis).toBeNull();
  expect(state.analyses).toEqual(beforeDelete.analyses);
});
