import { expect, test, type Page } from '@playwright/test';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { TaskState } from '../src/generated/contracts';
import { applyInputs, draftSaved, editBrand, fillInputs } from './m2-helpers';

async function area(page: Page, id: 'inputs' | 'reference' | 'directions' | 'production') {
  await page.locator(`#tab-${id}`).click();
  await expect(page.locator(`#area-${id}`)).toBeVisible();
}

async function fullDirection(page: Page) {
  const first = page.locator('article.direction').first();
  const disclosure = first.locator('details.direction-full');
  if (!await disclosure.evaluate((element) => element.hasAttribute('open'))) await disclosure.locator('summary').first().click();
  return first;
}

async function mutation(page: Page, name: string, route: string, within = page.locator('body'), allowAlert = false): Promise<TaskState> {
  const pending = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith(route));
  await within.getByRole('button', { name, exact: true }).click();
  const response = await pending;
  expect(response.ok(), await response.text()).toBeTruthy();
  if (!allowAlert) await expect(page.getByRole('alert')).toHaveCount(0);
  return response.json();
}

test('complete connected sample workflow, playable evidence, edits, exports and outdated history', async ({ page }) => {
  const clientErrors: string[] = [];
  page.on('pageerror', (error) => clientErrors.push(error.message));
  await page.goto('/');
  await page.getByLabel('New task title').fill('Morning sample review');
  await mutation(page, 'Create task', '/tasks');

  await fillInputs(page, {
    'Brand/company': 'Luma team (fictional)', Product: 'LumaCup',
    'Selling points': 'Removable lid\nThree illustrated colors',
    'Approved messages': 'Removable lid\nExplore three colors',
    'Target audience': 'People comparing colorful drinkware',
    'Publishing platform': 'Short-form video',
    'Communication goal': 'Introduce the cup and invite color exploration',
    'Target duration (seconds)': '18',
  });
  await applyInputs(page);
  await area(page, 'reference');
  await mutation(page, 'Load synthetic sample', '/sample');
  await area(page, 'inputs');
  await editBrand(page);
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('LumaCup');
  await area(page, 'reference');
  await page.getByText('Media details and source', { exact: true }).click();
  await expect(page.getByTestId('source-frame-rate')).toHaveText('Reference: 20 fps · 200 frames · Constant frame rate');
  await expect(page.getByRole('button', { name: 'Previous frame', exact: true })).toBeDisabled();

  const video = page.locator('video');
  await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.readyState)).toBeGreaterThanOrEqual(2);
  await video.evaluate(async (element: HTMLVideoElement) => { element.muted = true; await element.play(); });
  await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeGreaterThan(0.1);
  await video.evaluate((element: HTMLVideoElement) => element.pause());

  let state = await mutation(page, 'Run sample analysis', '/recognize');
  const taskId = state.task.task_id;
  const sampleVideoId = state.task.current_video_id!;
  expect(state.videos[0].frame_timing?.fps_numerator).toBe(20);
  expect(state.analyses.at(-1)?.events.find((item) => item.event_id === 'event_intro_text')?.start_frame).toBe(0);
  await page.locator('[data-evidence-id="event_lid_shape"]').getByRole('button', { name: /^Play / }).click();
  await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeCloseTo(3, 1);
  await expect(page.getByTestId('reference-frame-position')).toHaveText('00:00:03:00 · frame 60 / 199');
  const shortChime = page.locator('[data-evidence-id="event_chime_1"]').getByRole('button', { name: /^Play / });
  await expect(shortChime).toHaveAttribute('title', '00:00:03:00–00:00:03:05 · frames [60, 65)');
  await shortChime.click();
  await page.getByRole('button', { name: 'Next frame', exact: true }).click();
  await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeCloseTo(3.05, 2);
  await expect(page.getByTestId('reference-frame-position')).toHaveText('00:00:03:01 · frame 61 / 199');
  await page.getByRole('button', { name: 'Previous frame', exact: true }).click();
  await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeCloseTo(3, 2);
  await expect(page.getByTestId('reference-frame-position')).toHaveText('00:00:03:00 · frame 60 / 199');
  await expect(page.getByText('Sound effect', { exact: true }).last()).toBeVisible();
  await page.locator('[data-evidence-id="event_intro_text"]').getByRole('button', { name: /^Correct visible text/ }).click();
  await page.getByText('Content role interpretations ·', { exact: false }).click();
  await page.getByText('Section 1 ·', { exact: false }).click();
  await page.getByLabel('Recognized text · event_intro_text', { exact: true }).fill('LUMACUP — FICTIONAL SAMPLE (reviewed)');
  await page.getByRole('group', { name: 'Section 1 roles', exact: true }).getByLabel('Product presentation/demo', { exact: true }).check();
  await expect(page.getByRole('button', { name: 'Use this reviewed analysis', exact: true })).toBeDisabled();
  state = await mutation(page, 'Save analysis corrections', '/analysis/correct');
  expect(state.analyses).toHaveLength(2);
  expect(state.analyses[0].events.find((item) => item.event_id === 'event_intro_text')?.text).toBe('LUMACUP\nFICTIONAL SAMPLE');
  expect(state.analyses[1].review.user_confirmed).toBe(false);
  await mutation(page, 'Use this reviewed analysis', '/analysis/confirm');
  await area(page, 'directions');
  await page.getByLabel('Generation language', { exact: true }).selectOption('English');
  await mutation(page, 'Save generation language', '/language');
  state = await mutation(page, 'Generate two sample directions', '/directions/generate');

  const cards = page.locator('article.direction');
  await expect(cards).toHaveCount(2);
  const selection = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/select'));
  // The radio is controlled by persisted server state. Await its mutation before
  // asserting checked state instead of check()'s synchronous post-click assertion.
  await cards.first().getByRole('radio').click();
  const selectionResponse = await selection;
  expect(selectionResponse.ok(), await selectionResponse.text()).toBeTruthy();
  const selectedState: TaskState = await selectionResponse.json();
  expect(selectedState.task.chosen_direction).toEqual({ id: state.directions[0].direction_id, revision: state.directions[0].revision });
  expect(selectedState.task.selected_direction).toBeNull();
  expect(selectedState.directions[0].approval_status).toBe('draft');
  await expect(cards.first().getByRole('radio')).toBeChecked();
  await page.reload();
  await expect(cards.first().getByRole('radio')).toBeChecked();
  await area(page, 'production');
  await expect(page.getByRole('button', { name: 'Generate production materials', exact: true })).toBeDisabled();
  await area(page, 'directions');
  let first = await fullDirection(page);
  await first.getByLabel('Core message', { exact: true }).fill('Removable lid. Explore three colors.');
  await mutation(page, 'Save direction edits', '/edit', first);
  first = await fullDirection(page);
  await first.getByLabel('Refinement instruction', { exact: true }).fill('Make it presenter-free');
  state = await mutation(page, 'Apply instruction', '/refine', first);
  expect(state.feedback.at(-1)?.status).toBe('applied');
  expect(state.feedback.at(-1)?.resulting_direction?.revision).toBeGreaterThan(1);
  first = await fullDirection(page);
  await expect(first.getByLabel('Narrative', { exact: true })).toHaveValue(/presenter.free|no presenter/i);
  await area(page, 'production');
  await expect(page.getByRole('button', { name: 'Generate production materials', exact: true })).toBeDisabled();
  await area(page, 'directions');
  await first.getByLabel('Refinement instruction', { exact: true }).fill('Keep the orange title card as a production note');
  state = await mutation(page, 'Apply instruction', '/refine', first);
  expect(state.feedback.at(-1)?.status).toBe('not_interpreted');
  await page.getByText('Saved refinement instructions (2)', { exact: true }).click();
  await expect(page.getByText('not interpreted', { exact: true })).toBeVisible();
  first = await fullDirection(page);
  await expect(first.getByRole('radio')).toBeChecked();
  await mutation(page, 'Approve this direction', '/approve', first);
  await area(page, 'production');
  state = await mutation(page, 'Generate production materials', '/outputs/generate');
  expect(state.storyboards.at(-1)?.target_duration_seconds).toBe(18);
  expect(state.storyboards.at(-1)?.rows.at(-1)?.end_seconds).toBe(18);
  expect(state.storyboards.at(-1)).not.toHaveProperty('frame_timing');
  await expect(page.getByRole('heading', { name: 'Shot 1', exact: true })).toBeVisible();
  await expect(page.locator('.production-shot-index').first()).toContainText('0s–');
  await expect(page.getByLabel('Shot 1 dialogue', { exact: true })).toHaveValue('');
  await page.getByLabel('Production title', { exact: true }).fill('Morning production plan — reviewed');
  await page.getByLabel('Shot 1 visuals', { exact: true }).fill('Presenter-free close-up of the illustrated blue cup on a dark card.');
  state = await mutation(page, 'Save production edits', '/outputs/edit');
  expect(state.production_briefs).toHaveLength(2);
  expect(state.storyboards).toHaveLength(2);

  const briefDownload = page.waitForEvent('download');
  await page.locator('.production-export-bar').getByRole('button', { name: 'Markdown', exact: true }).click();
  const brief = await briefDownload;
  const briefText = await readFile((await brief.path())!, 'utf8');
  expect(briefText).toContain('Morning production plan — reviewed');
  expect(briefText.toLowerCase()).toContain('sample');
  const csvDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Storyboard CSV', exact: true }).click();
  const csv = await csvDownload;
  const csvText = await readFile((await csv.path())!, 'utf8');
  expect(csvText).toContain('Presenter-free close-up');
  expect(csvText.toLowerCase()).toContain('sample');

  await page.reload();
  await expect(page.getByLabel('Production title', { exact: true })).toHaveValue('Morning production plan — reviewed');
  await expect(page.getByLabel('Shot 1 visuals', { exact: true })).toHaveValue('Presenter-free close-up of the illustrated blue cup on a dark card.');
  await page.getByLabel('New task title').fill('Separate upload task');
  await mutation(page, 'Create task', '/tasks');
  await editBrand(page);
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('');
  await page.locator('.task-list button').filter({ hasText: 'Morning sample review' }).click();
  await expect(page.getByLabel('Production title', { exact: true })).toHaveValue('Morning production plan — reviewed');
  await area(page, 'inputs');
  await editBrand(page);
  await page.getByLabel('Product', { exact: true }).fill('LumaCup campaign revision');
  await draftSaved(page);
  await expect(page.getByTestId('m2-editor')).toContainText('changes not applied');
  await area(page, 'production');
  await expect(page.getByRole('button', { name: 'Regenerate production materials', exact: true })).toBeDisabled();
  const pendingState: TaskState = await (await page.request.get(`/api/tasks/${taskId}`)).json();
  expect(pendingState.production_briefs.at(-1)?.currentness).toBe('current');
  expect(pendingState.task.selected_direction).not.toBeNull();
  await area(page, 'inputs');
  await applyInputs(page);
  await area(page, 'production');
  await expect(page.getByText('These materials are historical because their inputs or approved direction changed.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Regenerate production materials', exact: true })).toBeDisabled();
  await expect(page.getByLabel('Production title', { exact: true })).toHaveValue('Morning production plan — reviewed');
  await area(page, 'reference');
  await page.getByText('Analysis history · 2 saved revisions', { exact: true }).click();
  await page.getByText('Original analysis · revision 1', { exact: false }).click();
  await expect(page.locator('pre').filter({ hasText: 'LUMACUP\\nFICTIONAL SAMPLE' }).first()).toBeVisible();

  await area(page, 'production');
  await expect(page.getByRole('button', { name: 'Export historical CSV', exact: true })).toBeVisible();
  const historicalDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export historical CSV', exact: true }).click();
  await page.getByRole('button', { name: 'Export historical version', exact: true }).click();
  const historicalCsv = await historicalDownload;
  expect(historicalCsv.suggestedFilename()).toContain('historical');
  expect(await readFile((await historicalCsv.path())!, 'utf8')).toMatch(/historical/i);
  await area(page, 'directions');
  state = await mutation(page, 'Generate two new sample directions', '/directions/generate');
  const newSelection = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/select'));
  await cards.first().getByRole('radio').click();
  expect((await newSelection).ok()).toBeTruthy();
  await mutation(page, 'Approve this direction', '/approve', cards.first());
  await area(page, 'production');
  state = await mutation(page, 'Regenerate production materials', '/outputs/generate');
  expect(state.production_briefs).toHaveLength(3);
  expect(state.production_briefs.at(-1)?.brief_ref).toEqual(state.task.current_brief);
  await expect(page.locator('.production-export-bar').getByRole('button', { name: 'Markdown', exact: true })).toBeVisible();

  // Re-upload the same bytes through ordinary intake. It must remain a real upload,
  // never a shortcut into the matching sample's prepared findings.
  const sampleMedia = await page.request.get(`/api/tasks/${taskId}/media/${sampleVideoId}`);
  expect(sampleMedia.ok()).toBeTruthy();
  await page.locator('.task-list button').filter({ hasText: 'Separate upload task' }).click();
  await area(page, 'reference');
  await page.getByLabel('Reference video file', { exact: true }).setInputFiles({ name: 'ordinary-upload.mp4', mimeType: 'video/mp4', buffer: await sampleMedia.body() });
  await mutation(page, 'Upload reference', '/video');
  state = await mutation(page, 'Start analysis', '/recognize', page.locator('body'), true);
  expect(state.task.mode).toBe('real');
  expect(state.analyses.at(-1)?.status).toBe('failed');
  expect(state.analyses.at(-1)?.events).toHaveLength(0);
  await expect(page.getByRole('alert').first()).toContainText(/real.*not configured/i);
  await expect(page.getByText('No recognized words to display.', { exact: false })).toBeVisible();
  expect(clientErrors).toEqual([]);
});

test('uploaded video with a nonzero source timestamp steps through zero-based frames', async ({ page }) => {
  const directory = await mkdtemp(join(tmpdir(), 'video-anatomy-shifted-'));
  const mediaPath = join(directory, 'shifted-24fps.mp4');
  try {
    execFileSync('ffmpeg', ['-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=64x64:r=24:d=0.5', '-c:v', 'libx264', '-output_ts_offset', '2', mediaPath]);
    await page.goto('/');
    await page.getByLabel('New task title').fill('Shifted reference frame review');
    await mutation(page, 'Create task', '/tasks');
    await area(page, 'reference');
    await page.getByLabel('Reference video file', { exact: true }).setInputFiles(mediaPath);
    const state = await mutation(page, 'Upload reference', '/video');
    expect(state.videos[0].frame_timing?.media_start_seconds).toBe(2);
    expect(state.videos[0].duration_seconds).toBeCloseTo(0.5);
    await page.getByText('Media details and source', { exact: true }).click();
    await expect(page.getByTestId('source-frame-rate')).toHaveText('Reference: 24 fps · 12 frames · Constant frame rate');
    const video = page.locator('video');
    await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.readyState)).toBeGreaterThanOrEqual(2);
    await expect(page.getByTestId('reference-frame-position')).toHaveText('00:00:00:00 · frame 0 / 11');
    await expect(page.getByRole('button', { name: 'Previous frame', exact: true })).toBeDisabled();
    for (let frame = 1; frame <= 6; frame += 1) {
      await page.getByRole('button', { name: 'Next frame', exact: true }).click();
      await expect(page.getByTestId('reference-frame-position')).toHaveText(`00:00:00:0${frame} · frame ${frame} / 11`);
    }
    await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeCloseTo(2.25, 2);
    await page.getByRole('button', { name: 'Previous frame', exact: true }).click();
    await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeCloseTo(2 + 5 / 24, 2);
    await expect(page.getByTestId('reference-frame-position')).toHaveText('00:00:00:05 · frame 5 / 11');
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
