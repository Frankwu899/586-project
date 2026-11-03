import { expect, test, type Page } from '@playwright/test';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { EvidenceEvent, TaskState } from '../src/generated/contracts';
import { applyInputs, area, editBrand, fillInputs } from './m2-helpers';

async function mutation(page: Page, name: string, route: string, within = page.locator('body')): Promise<TaskState> {
  const operation = route === '/recognize' ? 'recognize' : route === '/directions/generate' ? 'directions' : route === '/refine' ? 'refine' : route === '/outputs/generate' ? 'production' : null;
  const pending = page.waitForResponse((response) => response.request().method() === 'POST' && (operation
    ? new URL(response.url()).pathname.endsWith('/operations') && response.request().postDataJSON()?.operation === operation
    : new URL(response.url()).pathname.endsWith(route)));
  await within.getByRole('button', { name: name === 'Create task' ? /^(Create task|New project)$/ : name, exact: true }).click();
  const response = await pending;
  expect(response.ok(), await response.text()).toBeTruthy();
  let result = await response.json();
  if (operation) {
    if (result.status === 'queued' || result.status === 'running') {
      const completed = await page.waitForResponse(async (item) => {
        if (item.request().method() !== 'GET' || !new URL(item.url()).pathname.endsWith(`/operations/${result.operation_id}`)) return false;
        const ticket = await item.json();
        return ticket.status === 'succeeded' || ticket.status === 'failed';
      });
      expect(completed.ok(), await completed.text()).toBeTruthy();
      result = await completed.json();
    }
    expect(result.status, JSON.stringify(result.error)).toBe('succeeded');
    expect(result.result).toBeTruthy();
    result = result.result;
  }
  await expect(page.getByRole('alert')).toHaveCount(0);
  return result;
}

async function selectEvidence(page: Page, event: EvidenceEvent, events: EvidenceEvent[]) {
  let candidates = events.filter((item) => item.kind === event.kind);
  if (event.kind === 'on_screen_text') candidates = candidates.filter((item, index) => !candidates.slice(0, index).some((prior) => prior.start_frame === item.start_frame && prior.legacy_seconds?.start_seconds === item.legacy_seconds?.start_seconds));
  const pointIndex = candidates.findIndex((item) => event.kind === 'on_screen_text' ? item.start_frame === event.start_frame && item.legacy_seconds?.start_seconds === event.legacy_seconds?.start_seconds : item.event_id === event.event_id);
  await page.getByRole('region', { name: 'Video evidence timeline', exact: true }).locator(`.timeline-mark.${event.kind}`).nth(pointIndex).click();
  const words = page.getByLabel('Visible text at selected sample', { exact: true });
  if (event.kind === 'on_screen_text' && await words.isVisible()) await words.selectOption(event.event_id);
  await expect(page.locator(`[data-evidence-id="${event.event_id}"]`)).toBeVisible();
}

async function correctEvidence(page: Page, event: EvidenceEvent, events: EvidenceEvent[]) {
  await selectEvidence(page, event, events);
  const inspector = page.locator(`[data-evidence-id="${event.event_id}"]`);
  const open = inspector.getByRole('button', { name: /^Correct / });
  if (await open.isVisible()) await open.click();
  return inspector;
}

test('mocked real providers: HEVC playback, bilingual corrections, approval, export and stale outputs', async ({ page }) => {
  const directory = await mkdtemp(join(tmpdir(), 'video-anatomy-hevc-browser-'));
  const mediaPath = join(directory, 'bilingual-fixture.mp4');
  const clientErrors: string[] = [];
  page.on('pageerror', (error) => clientErrors.push(error.message));
  try {
    // Synthetic media and deterministic provider responses verify plumbing only.
    execFileSync('ffmpeg', ['-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=96x64:r=24:d=4', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=4', '-c:v', 'libx265', '-x265-params', 'log-level=error:pools=1:frame-threads=1', '-tag:v', 'hvc1', '-c:a', 'aac', '-output_ts_offset', '2', mediaPath]);
    await page.goto('/');
    await page.getByLabel('New task title').fill('中英混合 provider integration');
    await mutation(page, 'Create task', '/tasks');
    const briefFields = {
      'Brand/company': 'Luma 乐玛', Product: 'LumaCup 随行杯',
      'Selling points': '可拆卸杯盖\n蓝色杯身', 'Approved messages': '探索 LumaCup 三种颜色',
      'Target audience': '中文与 English 用户', 'Publishing platform': '短视频',
      'Communication goal': '介绍产品并邀请查看颜色', 'Target duration (seconds)': '12',
    };
    await fillInputs(page, briefFields);
    await applyInputs(page);
    await area(page, 'reference');
    await page.getByRole('button', { name: 'Import video', exact: true }).click();
    await page.getByLabel('Reference video file', { exact: true }).setInputFiles(mediaPath);
    let state = await mutation(page, 'Upload reference', '/video');
    const source = state.videos[0];
    expect(source.video_codec).toBe('hevc');
    expect(source.frame_timing?.media_start_seconds).toBe(2);
    expect(source.playback?.video_codec).toBe('h264');
    expect(source.playback?.frame_timing.frame_count).toBe(source.frame_timing?.frame_count);
    const playbackTiming = source.playback!.frame_timing;
    expect(playbackTiming.media_start_seconds).not.toBe(source.frame_timing!.media_start_seconds);
    const video = page.locator('video');
    await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.readyState)).toBeGreaterThanOrEqual(2);
    await video.evaluate(async (element: HTMLVideoElement) => { element.muted = true; await element.play(); });
    await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeGreaterThan(0.1);
    await video.evaluate((element: HTMLVideoElement) => { element.pause(); element.currentTime = 0; });
    await expect(page.getByTestId('reference-frame-position')).toContainText('· 0 /');
    await page.getByRole('button', { name: 'Next frame', exact: true }).click();
    await expect(page.getByTestId('reference-frame-position')).toContainText('· 1 /');
    await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeCloseTo(playbackTiming.media_start_seconds + playbackTiming.frame_boundaries_seconds[1], 2);

    state = await mutation(page, 'Start analysis', '/recognize');
    const original = state.analyses.at(-1)!;
    expect(original.status).toBe('succeeded');
    expect(original.origin.kind).toBe('provider');
    const visual = original.events.find((event) => event.visual_details?.subjects.items.some((subject) => subject.roles?.includes('product')))!;
    const product = visual.visual_details!.subjects.items.find((subject) => subject.roles?.includes('product'))!;
    const ocr = original.events.find((event) => event.kind === 'on_screen_text')!;
    const speech = original.events.find((event) => event.kind === 'speech')!;
    expect(ocr.text).not.toBe(speech.text);
    await correctEvidence(page, visual, original.events);
    await page.locator(`[data-evidence-id="${visual.event_id}"]`).getByText('Correct subjects, actions or product labels', { exact: true }).click();
    const subjectLabel = `Subject label · ${visual.event_id} · ${product.subject_id}`;
    const actionLabel = `Action type · ${visual.event_id} · 1`;
    const presentationLabel = `Presentation type · ${visual.event_id} · 1`;
    await page.getByLabel(subjectLabel, { exact: true }).first().fill('蓝色 LumaCup 杯子');
    await page.getByLabel(`Subject kind · ${visual.event_id} · ${product.subject_id}`, { exact: true }).first().selectOption('physical_object');
    await page.getByLabel(actionLabel, { exact: true }).first().selectOption('hold');
    await page.getByLabel(presentationLabel, { exact: true }).first().selectOption('appearance');
    await correctEvidence(page, ocr, original.events);
    await page.getByLabel(`Recognized text · ${ocr.event_id}`, { exact: true }).first().fill('LumaCup 随行杯 · 350 mL · ¥99');
    await correctEvidence(page, speech, original.events);
    await page.getByLabel(`Recognized text · ${speech.event_id}`, { exact: true }).first().fill('试试 LumaCup，choose your color。');
    await expect(page.getByRole('button', { name: 'Use this reviewed analysis', exact: true })).toBeDisabled();
    // An atomic label edit must not silently break a product relationship.
    await selectEvidence(page, visual, original.events);
    await page.locator(`[data-evidence-id="${visual.event_id}"]`).getByText('Correct subjects, actions or product labels', { exact: true }).click();
    const roles = page.getByRole('group', { name: `Subject roles · ${visual.event_id} · ${product.subject_id}`, exact: true }).first();
    const rejected = page.waitForResponse((response) => response.request().method() === 'POST' && ['/editors/analysis', '/analysis/correct'].some((path) => new URL(response.url()).pathname.endsWith(path)) && !response.ok());
    await roles.getByLabel('product', { exact: true }).uncheck();
    await page.getByRole('button', { name: 'Save analysis corrections', exact: true }).click();
    expect((await rejected).ok()).toBe(false);
    await expect(page.getByRole('alert').first()).toContainText(/product/i);
    await roles.getByLabel('product', { exact: true }).check();
    state = await mutation(page, 'Save analysis corrections', '/analysis/correct');
    expect(state.analyses[0]).toEqual(original);
    const corrected = state.analyses.at(-1)!;
    expect(corrected.revision).toBe(original.revision + 1);
    expect(corrected.review.user_confirmed).toBe(false);
    expect(corrected.corrections.some((correction) => correction.field === 'visual_details')).toBe(true);
    const savedVisual = corrected.events.find((event) => event.event_id === visual.event_id)!;
    expect(savedVisual.start_frame).toBe(visual.start_frame);
    expect(savedVisual.end_frame).toBe(visual.end_frame);
    expect(savedVisual.visual_details!.actions.items[0].actor_subject_ids).toEqual(visual.visual_details!.actions.items[0].actor_subject_ids);
    expect(savedVisual.visual_details!.subjects.items.find((subject) => subject.subject_id === product.subject_id)?.label).toBe('蓝色 LumaCup 杯子');
    await mutation(page, 'Use this reviewed analysis', '/analysis/confirm');
    await area(page, 'directions');
    await page.getByLabel('Generation language', { exact: true }).selectOption('Chinese');
    await mutation(page, 'Save generation language', '/language');
    await page.getByRole('checkbox', { name: 'Use reviewed reference evidence', exact: true }).check();
    await mutation(page, 'Generate two directions', '/directions/generate');
    const cards = page.locator('article.direction');
    await expect(cards).toHaveCount(2);
    const selection = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/select'));
    await cards.first().getByRole('radio').click();
    expect((await selection).ok()).toBeTruthy();
    await cards.first().getByText('Read full direction and edit', { exact: true }).click();
    await cards.first().getByLabel('Refinement instruction', { exact: true }).fill('请保留 LumaCup 品牌名，使用中英混合字幕。');
    state = await mutation(page, 'Apply instruction', '/refine', cards.first());
    expect(state.feedback.at(-1)?.instruction).toBe('请保留 LumaCup 品牌名，使用中英混合字幕。');
    expect(state.feedback.at(-1)?.status).toBe('applied');
    await mutation(page, 'Approve this direction', '/approve', cards.first());
    await area(page, 'production');
    state = await mutation(page, 'Generate production materials', '/outputs/generate');
    expect(state.storyboards.at(-1)?.target_duration_seconds).toBe(12);
    await page.getByLabel('Production title', { exact: true }).fill('LumaCup 创意简报 — 中英双语');
    await page.getByLabel('Shot 1 visuals', { exact: true }).fill('蓝色杯身 close-up；保留 350 mL 字样。');
    state = await mutation(page, 'Save production edits', '/outputs/edit');
    for (const [name, content] of [['Markdown', 'LumaCup 创意简报'], ['Storyboard CSV', '蓝色杯身 close-up']] as const) {
      const pending = page.waitForEvent('download');
      await page.locator('.production-export-bar > summary').click();
      await page.locator('.production-export-bar').getByRole('button', { name, exact: true }).click();
      expect(await readFile((await (await pending).path())!, 'utf8')).toContain(content);
    }
    await page.reload();
    await editBrand(page);
    await expect(page.getByLabel('Brand/company', { exact: true })).toHaveValue('Luma 乐玛');
    await area(page, 'production');
    await expect(page.getByLabel('Production title', { exact: true })).toHaveValue('LumaCup 创意简报 — 中英双语');
    await area(page, 'reference');
    await correctEvidence(page, visual, corrected.events);
    await page.locator(`[data-evidence-id="${visual.event_id}"]`).getByText('Correct subjects, actions or product labels', { exact: true }).click();
    await expect(page.getByLabel(subjectLabel, { exact: true }).first()).toHaveValue('蓝色 LumaCup 杯子');
    await page.getByLabel(subjectLabel, { exact: true }).first().fill('蓝色 LumaCup 杯子（再次核对）');
    state = await mutation(page, 'Save analysis corrections', '/analysis/correct');
    expect(state.task.selected_direction).toBeNull();
    expect(state.production_briefs.at(-1)?.currentness).toBe('outdated');
    expect(state.storyboards.at(-1)?.currentness).toBe('outdated');
    expect(state.analyses.at(-1)?.review.user_confirmed).toBe(false);
    await area(page, 'production');
    await expect(page.locator('.production-toolbar').getByText('Historical version', { exact: true })).toBeVisible();
    await expect(page.locator('.production-prerequisite').getByRole('button', { name: 'Choose and approve an idea', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Regenerate production materials', exact: true })).toBeDisabled();
    await expect(page.getByLabel('Production title', { exact: true })).toHaveValue('LumaCup 创意简报 — 中英双语');
    await area(page, 'directions');
    await expect(page.getByRole('button', { name: 'Generate two new directions', exact: true })).toBeDisabled();
    expect(clientErrors).toEqual([]);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('partial and legacy structured coverage stays visible without editable extraction status', async ({ page }) => {
  let response = await page.request.post('/api/tasks', { data: { title: 'UI coverage state fixture' } });
  expect(response.ok()).toBeTruthy();
  let state: TaskState = await response.json();
  const taskId = state.task.task_id;
  response = await page.request.post(`/api/tasks/${taskId}/sample`, { data: { expected_version: state.task.version } });
  expect(response.ok()).toBeTruthy();
  state = await response.json();
  response = await page.request.post(`/api/tasks/${taskId}/recognize`, { data: { expected_version: state.task.version } });
  expect(response.ok()).toBeTruthy();
  state = await response.json();
  // Browser-only fixture checks presentation of a preserved successful event
  // alongside a failed structured group; no provider or accuracy claim is made.
  const analysis = state.analyses.at(-1)!;
  analysis.status = 'partial';
  const visual = analysis.events.find((event) => event.kind === 'visual_action')!;
  visual.visual_details = {
    subjects: { status: 'failed', items: [], error: { code: 'fixture_extraction_failed', message: 'Subject extraction failed in this UI fixture.', retryable: true } },
    actions: { status: 'not_analyzed', items: [], error: null },
    product_presentations: { status: 'none_found', items: [], error: null },
  };
  await page.route('**/api/tasks', async (route) => {
    if (route.request().method() === 'GET') await route.fulfill({ json: [state] });
    else await route.continue();
  });
  await page.route(`**/api/tasks/${taskId}/editors/analysis`, async (route) => {
    const response = await route.fetch();
    const draft = await response.json();
    await route.fulfill({ json: { ...draft, content: { events: analysis.events, segments: analysis.segments } } });
  });
  await page.addInitScript((id) => localStorage.setItem('video-anatomy-task', id), taskId);
  await page.goto('/');
  await area(page, 'reference');
  await selectEvidence(page, visual, analysis.events);
  await page.getByText('Observed details', { exact: true }).click();
  await expect(page.getByText('Subject extraction failed in this UI fixture.', { exact: true })).toBeVisible();
  await expect(page.getByText('Not analyzed', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Checked; none found', { exact: true }).first()).toBeVisible();
  const legacy = analysis.events.find((event) => event.kind === 'visual_action' && event.event_id !== visual.event_id && !event.visual_details)!;
  expect(legacy).toBeTruthy();
  await selectEvidence(page, legacy, analysis.events);
  await page.getByText('Observed details', { exact: true }).click();
  await expect(page.getByText('Structured visual details were not analyzed for this observation.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Use this reviewed analysis', exact: true })).toBeDisabled();
  await area(page, 'directions');
  await expect(page.getByRole('button', { name: 'Generate two sample directions', exact: true })).toBeDisabled();
  await area(page, 'reference');
  await selectEvidence(page, visual, analysis.events);
  await expect(page.getByLabel(`Structured visual details · ${visual.event_id}`, { exact: true }).getByRole('combobox')).toHaveCount(0);
});

test('M2 proposals preserve mixed notes, show replacements and adopt a selected batch only once', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await page.getByLabel('New task title', { exact: true }).fill('Mixed-language proposal review');
  const initial = await mutation(page, 'Create task', '/tasks');
  await editBrand(page);
  await page.getByLabel('Brand/company', { exact: true }).fill('Existing supplied brand');
  await page.getByText('Paste your notes', { exact: true }).click();
  const notes = 'Brand: Luma 乐玛\nProduct: LumaCup 随行杯\nSelling point: Removable lid';
  await page.getByLabel('Source notes', { exact: true }).fill(notes);
  const response = page.waitForResponse((item) => new URL(item.url()).pathname.endsWith('/m2/assist'));
  await page.getByRole('button', { name: 'Extract details', exact: true }).click();
  expect((await response).ok()).toBeTruthy();
  const review = page.getByRole('region', { name: 'Review proposed details', exact: true });
  await expect(review.locator('article')).toHaveCount(3);
  await expect(review).toContainText('Deterministic test assistance');
  await expect(review).toContainText('Current: Existing supplied brand');
  await expect(review.getByLabel('Proposed Brand/company 1', { exact: true })).toHaveValue('Luma 乐玛');
  await expect(review.locator('blockquote').first()).toContainText('Brand: Luma 乐玛');
  await expect(page.getByLabel('Brand/company', { exact: true })).toHaveValue('Existing supplied brand');
  await expect(page.getByRole('button', { name: 'Use selected details', exact: true })).toBeDisabled();
  const before = await (await page.request.get(`/api/tasks/${initial.task.task_id}/m2/draft`)).json();
  // Selecting and editing rows are local; keyboard activation also exercises proposal review.
  for (const label of ['Select Brand/company proposal 1', 'Select Product proposal 2']) {
    await review.getByRole('checkbox', { name: label, exact: true }).focus();
    await page.keyboard.press('Space');
  }
  await review.getByLabel('Proposed Product 2', { exact: true }).fill('LumaCup 随行杯 — explicitly edited');
  await review.getByRole('button', { name: 'Dismiss Selling point proposal 3', exact: true }).click();
  const untouched = await (await page.request.get(`/api/tasks/${initial.task.task_id}/m2/draft`)).json();
  expect(untouched.draft_version).toBe(before.draft_version);
  expect(untouched.claims).toEqual([]);
  await page.screenshot({ path: '../.local-data/m2-ui-evidence/proposal-review-1440.png', fullPage: true });
  await review.screenshot({ path: '../.local-data/m2-ui-evidence/proposal-details-1440.png' });
  const adoption = page.waitForResponse((item) => new URL(item.url()).pathname.endsWith('/m2/adopt'));
  await page.getByRole('button', { name: 'Use selected details', exact: true }).focus();
  await page.keyboard.press('Enter');
  const adoptedResponse = await adoption;
  expect(adoptedResponse.ok(), await adoptedResponse.text()).toBeTruthy();
  const adopted = await adoptedResponse.json();
  expect(adopted.draft_version).toBe(before.draft_version + 1);
  expect(adopted.fields.brand_company).toBe('Luma 乐玛');
  expect(adopted.fields.product).toBe('LumaCup 随行杯 — explicitly edited');
  expect(adopted.fields.target_audience).toBeNull();
  expect(adopted.source_notes).toBe(notes);
  expect(adopted.claims).toEqual([]);
  const state: TaskState = await (await page.request.get(`/api/tasks/${initial.task.task_id}`)).json();
  expect(state.task.version).toBe(initial.task.version);
  expect(state.briefs).toEqual([]);
});

test('M2 stale assistance and provider errors keep newer manual text and offer an honest retry', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('New task title', { exact: true }).fill('Stale assistance does not overwrite');
  const initial = await mutation(page, 'Create task', '/tasks');
  await editBrand(page);
  await page.getByText('Paste your notes', { exact: true }).click();
  await page.getByLabel('Source notes', { exact: true }).fill('Brand: Luma 乐玛\nProduct: LumaCup 随行杯\nSelling point: Removable lid');
  let release!: () => void;
  const hold = new Promise<void>((resolveHold) => { release = resolveHold; });
  let received!: () => void;
  const ready = new Promise<void>((resolveReady) => { received = resolveReady; });
  await page.route('**/m2/assist', async (route) => {
    const response = await route.fetch();
    received();
    await hold;
    await route.fulfill({ response });
  });
  await page.getByRole('button', { name: 'Extract details', exact: true }).click();
  await ready;
  await page.getByLabel('Product', { exact: true }).fill('My newer product text 新');
  await expect(page.getByTestId('m2-save-status')).toContainText('Draft saved');
  release();
  await expect(page.getByRole('alert')).toContainText('Your inputs changed. Run extraction again.');
  await expect(page.getByRole('button', { name: 'Use selected details', exact: true })).toBeDisabled();
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('My newer product text 新');
  await page.setViewportSize({ width: 390, height: 960 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../.local-data/m2-ui-evidence/stale-proposal-390.png', fullPage: true });
  await page.unroute('**/m2/assist');
  await page.route('**/m2/assist', (route) => route.fulfill({ status: 502, json: { error: { code: 'm2_invalid_assistance', message: 'Couldn’t extract usable details. Retry or continue editing manually.', retryable: true } } }));
  await page.getByRole('button', { name: 'Run extraction again', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Couldn’t extract details. You can continue editing.');
  await expect(page.getByRole('region', { name: 'Review proposed details', exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Product', { exact: true })).toHaveValue('My newer product text 新');
  await expect(page.getByRole('button', { name: 'Try again', exact: true })).toBeVisible();
  const state: TaskState = await (await page.request.get(`/api/tasks/${initial.task.task_id}`)).json();
  expect(state.briefs).toEqual([]);
  expect(state.task.version).toBe(initial.task.version);
});
