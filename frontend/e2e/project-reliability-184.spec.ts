import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { Project } from '../src/project/contracts';

// Synthetic authored records and real generated WAV bytes. No live provider calls.
const root = resolve(import.meta.dirname, '../..');
const seed = (mode = 'base'): Project => JSON.parse(execFileSync(join(root, '.venv/bin/python'), [
  join(root, 'frontend/e2e/project-reliability-184-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, mode,
], { cwd: root, encoding: 'utf8' }));
const load = async (request: APIRequestContext, id: string): Promise<Project> => (await request.get(`/api/projects/${id}`)).json();
async function open(page: Page, project: Project) {
  await page.goto(`/?project=${project.id}`);
  await expect(page.getByRole('heading', { name: 'Media Pool', exact: true })).toBeVisible();
}
async function source(page: Page, name = 'Alpha partial.wav') {
  await page.getByRole('button', { name: `Focus ${name}`, exact: true }).dblclick();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
}
async function capture(page: Page, name: string) {
  const folder = process.env.VIDEO_ANATOMY_SCREENSHOT_DIR;
  if (folder) { mkdirSync(folder, { recursive: true }); await page.screenshot({ path: join(folder, `${name}.png`), fullPage: true }); }
}

test('Activity shows exact parent and source tasks, partial diagnostics without error, and saved source revision', async ({ page }) => {
  const project = seed();
  expect(project.jobs.find(job => job.id === 'child_alpha')?.error).toBeNull();
  await open(page, project);
  const toggle = page.getByRole('button', { name: 'Activity', exact: true });
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  const activity = page.getByRole('complementary', { name: 'Activity', exact: true });
  const report = activity.getByRole('article', { name: 'Reference analysis Needs attention', exact: true });
  await expect(report).toContainText('The earlier report remains saved. This attempt did not replace it. Saved source evidence is retained.');
  await expect(report.getByText('Source recognition · 3 of 3 finished', { exact: true })).toBeVisible();
  for (const name of ['Alpha partial.wav', 'Beta partial.wav', 'Gamma chunk.wav']) {
    await expect(report.getByRole('article', { name: new RegExp(`^${name.replaceAll('.', '\\.')}`) })).toHaveCount(1);
  }
  const child = report.getByRole('article', { name: 'Alpha partial.wav Saved with limitations', exact: true });
  await expect(child).toContainText('Speech incomplete. Other valid source observations were saved.');
  await child.getByText('Processing details', { exact: true }).click();
  await expect(child.locator('pre')).toContainText('parent_job_id: failed_summary');
  await expect(child.locator('pre')).toContainText('evidence_revision: 1');
  await expect(child.locator('pre')).toContainText('audio_timestamps_invalid');
  await capture(page, 'activity-parent-source-partial-diagnostics');
  await child.getByRole('button', { name: 'Open saved evidence v1 · Alpha partial.wav', exact: true }).click();
  await expect(page.getByText(/Showing exact historical evidence revision 1/)).toBeVisible();
  await expect(page.locator('.va-transcript')).toContainText('Authored alpha saved text');
  await expect(page.locator('.va-transcript')).not.toContainText('Authored newer Alpha text');
  await page.getByText('Coverage, original file and recovery', { exact: true }).click();
  await page.getByText('Support diagnostics', { exact: true }).click();
  await expect(page.locator('.va-source-details pre')).toContainText('evidence_revision: 1');
  await expect(page.locator('.va-source-details pre')).toContainText('audio_timestamps_invalid');
  await expect(page.locator('.va-source-details pre')).not.toContainText('provider_authentication');
  await expect(page.getByText('Latest attempt details', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'View current evidence', exact: true }).click();
  const current = page.locator('.va-source-speech-status');
  await expect(current).toContainText('The service rejected the API key. Check the saved key in Settings.');
  await expect(current.getByRole('alert')).toHaveCount(1);
  await current.getByText('Latest attempt details', { exact: true }).click();
  await expect(current.locator('pre')).toContainText('gpt-transcribe');
  await expect(current.locator('pre')).toContainText('provider_authentication');
  await capture(page, 'source-current-auth-failure-after-historical-review');
});

test('report retry uses the frozen original scope and real API failure never creates extraction or replaces saved evidence', async ({ page, request }) => {
  const project = seed();
  const capabilities = await (await request.get('/api/projects/capabilities')).json();
  expect(capabilities.configured, 'Offline regression must not use a saved or environment API key').toBe(false);
  await open(page, project);
  await page.getByRole('button', { name: 'Activity', exact: true }).click();
  const report = page.getByRole('article', { name: 'Reference analysis Needs attention', exact: true });
  const sent = page.waitForRequest(item => item.method() === 'POST' && item.url().endsWith(`/api/projects/${project.id}/analyze`));
  await report.getByRole('button', { name: 'Retry report synthesis', exact: true }).click();
  const payload = (await sent).postDataJSON();
  expect(payload).toMatchObject({ resource_ids: ['resource_alpha', 'resource_beta', 'resource_gamma'], content_id: 'content_target', synthesis_only: true, visual_only: false });
  expect(payload).not.toHaveProperty('transcription_model');
  await expect.poll(async () => (await load(request, project.id)).jobs.filter(job => job.kind === 'analyze').length).toBe(2);
  await expect.poll(async () => (await load(request, project.id)).jobs.filter(job => job.kind === 'analyze').at(-1)?.status).toBe('failed');
  const after = await load(request, project.id);
  expect(after.jobs.filter(job => job.kind === 'reference_extraction')).toEqual(project.jobs.filter(job => job.kind === 'reference_extraction'));
  expect(after.jobs.filter(job => job.kind === 'recognize')).toEqual(project.jobs.filter(job => job.kind === 'recognize'));
  expect(after.jobs.at(-1)?.error_code).toBe('provider_not_configured');
  expect(after.resources.map(item => item.evidence)).toEqual(project.resources.map(item => item.evidence));
  expect(after.analyses).toEqual(project.analyses);
  expect(after.active_content_id).toBe(project.active_content_id);
  expect(after.selection).toEqual(project.selection);
  await expect(page.getByRole('complementary', { name: 'Activity' })).toContainText('Saved source evidence is retained.');
  await capture(page, 'report-retry-offline-failure-preserves-sources');
});

test('speech model preference persists without recognition and an explicit action sends its selected profile', async ({ page, request }) => {
  const project = seed(); let processing = 0;
  page.on('request', item => { if (item.method() === 'POST' && /\/(?:recognize|analyze)$/.test(new URL(item.url()).pathname)) processing += 1; });
  await open(page, project); await source(page);
  await page.getByLabel('Speech model', { exact: true }).selectOption('gpt-transcribe');
  await expect(page.getByText(/GPT Transcribe returns text\. Evidence uses the actual audio-chunk range/)).toBeVisible();
  await expect.poll(async () => (await load(request, project.id)).editor_drafts['recognition-settings']?.transcription_model).toBe('gpt-transcribe');
  expect(processing).toBe(0);
  await page.reload();
  await expect(page.getByLabel('Speech model', { exact: true })).toHaveValue('gpt-transcribe');
  expect(processing).toBe(0);
  let profile: Record<string, unknown> | undefined;
  await page.route(`**/api/projects/${project.id}/resources/resource_alpha/recognize`, async route => {
    profile = route.request().postDataJSON();
    // Transport assertion only: prevent a paid provider attempt and return saved state.
    await route.fulfill({ status: 202, json: await load(request, project.id) });
  });
  await page.getByRole('button', { name: 'Transcribe with selected model', exact: true }).click();
  await expect.poll(() => profile?.transcription_model).toBe('gpt-transcribe');
  expect(processing).toBe(1);
  await page.getByRole('button', { name: 'Back to Media Pool', exact: true }).click();
  await source(page, 'Gamma chunk.wav');
  await expect(page.getByText('New speech blocks use audio-chunk ranges, without word or sentence timestamps. Preserved events keep their recorded precision.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /^Speech at 00:00\.0:/ }).click();
  await expect(page.getByText('Whole audio-chunk range; sentence and word timing are unavailable.', { exact: true })).toBeVisible();
  await capture(page, 'gpt-authored-chunk-precision');
});

test('report retry cannot restore an older reference selection after its saved scope changes', async ({ page, request }) => {
  const project = seed('changed_scope');
  await open(page, project);
  await page.getByRole('button', { name: 'Activity', exact: true }).click();
  const report = page.getByRole('article', { name: 'Reference analysis Needs attention', exact: true });
  await expect(report.getByRole('button', { name: 'Retry report synthesis', exact: true })).toBeDisabled();
  await expect(report.locator('.va-report-retry')).toContainText(/selection.*changed|references.*changed|scope.*changed/i);
  const before = await load(request, project.id);
  const response = await request.post(`/api/projects/${project.id}/analyze`, { data: {
    expected_version: before.version, resource_ids: ['resource_alpha', 'resource_beta', 'resource_gamma'],
    content_id: 'content_target', synthesis_only: true, visual_only: false,
  } });
  expect(response.status(), await response.text()).toBe(409);
  expect((await response.json()).error.code).toBe('analysis_inputs_changed');
  const after = await load(request, project.id);
  expect(after.jobs).toEqual(before.jobs);
  expect(after.contents.find(item => item.id === 'content_target')?.selection).toEqual(before.contents.find(item => item.id === 'content_target')?.selection);
  expect(after.resources.map(item => item.evidence)).toEqual(before.resources.map(item => item.evidence));
  expect(after.active_content_id).toBe(before.active_content_id);
});

test('Media Pool model choice is passive until explicit Analyze and sends the exact selected scope', async ({ page, request }) => {
  const project = seed(); let analyzed: Record<string, unknown> | undefined;
  await page.route(`**/api/projects/${project.id}/analyze`, async route => {
    analyzed = route.request().postDataJSON();
    await route.fulfill({ status: 202, json: await load(request, project.id) });
  });
  await open(page, project);
  await page.getByRole('button', { name: 'Analyze 1 reference', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Analyze selected references', exact: true });
  await dialog.getByLabel('Speech model', { exact: true }).selectOption('gpt-transcribe');
  await expect.poll(async () => (await load(request, project.id)).editor_drafts['recognition-settings']?.transcription_model).toBe('gpt-transcribe');
  expect(analyzed).toBeUndefined();
  await dialog.getByLabel('Analysis for', { exact: true }).selectOption('content_target');
  await dialog.getByRole('button', { name: 'Start analysis', exact: true }).click();
  await expect.poll(() => analyzed?.transcription_model).toBe('gpt-transcribe');
  expect(analyzed).toMatchObject({ resource_ids: ['resource_gamma'], content_id: 'content_target', visual_only: false });
  expect((await load(request, project.id)).active_content_id).toBe(project.active_content_id);
});

test('complete saved evidence still exposes a newer failed model attempt and its requested profile', async ({ page }) => {
  const project = seed('complete_failure');
  await open(page, project); await source(page);
  await expect(page.locator('.va-transcript')).toContainText('Authored newer Alpha text');
  await expect(page.locator('.va-source-speech-status')).toContainText('Apply or discard the pending evidence corrections before retrying recognition.');
  await page.getByText('Latest attempt details', { exact: true }).click();
  await expect(page.locator('.va-source-speech-status pre')).toContainText('gpt-transcribe');
  await expect(page.locator('.va-source-speech-status pre')).toContainText('evidence_pending_changes');
});

test('Media Pool advertises 500 MiB and reports per-file success, local failure and configured-size preflight', async ({ page, request }) => {
  const project = seed('empty');
  const capabilities = await (await request.get('/api/projects/capabilities')).json();
  expect(capabilities.media_limits.max_bytes).toBe(500 * 1024 * 1024);
  await open(page, project);
  await expect(page.getByText(/^Per file: 500 MiB maximum;/)).toBeVisible();
  // Parameterized client boundary, not a claim that 500 MiB was uploaded.
  await page.route('**/api/projects/capabilities', route => route.fulfill({ json: { ...capabilities, media_limits: { ...capabilities.media_limits, max_bytes: 2 * 1024 * 1024 } } }));
  await page.reload();
  await expect(page.getByText(/^Per file: 2 MiB maximum;/)).toBeVisible();
  const uploads: string[] = [];
  await page.route(`**/api/projects/${project.id}/resources`, async route => {
    if (route.request().method() !== 'POST') { await route.continue(); return; }
    const body = route.request().postDataBuffer()?.toString('utf8') ?? '';
    uploads.push(body);
    if (body.includes('authored-failure.txt')) {
      await route.fulfill({ status: 422, json: { error: { code: 'invalid_document', message: 'Authored local import failure: the document could not be read.' } } });
    } else if (body.includes('real-note.txt')) {
      // Preserve the real admission response until its own local preparation
      // finishes, exposing an actual aggregate-version race deterministically.
      const response = await route.fetch();
      const admitted = await response.json() as Project;
      const resourceId = admitted.resources.at(-1)?.id;
      await expect.poll(async () => (await load(request, project.id)).jobs.some(job => job.kind === 'extract' && job.resource_id === resourceId && !['queued', 'running'].includes(job.status))).toBe(true);
      await route.fulfill({ response, json: admitted });
    } else await route.continue();
  });
  await page.locator('.va-page-heading input[type="file"]').setInputFiles([
    { name: 'real-note.txt', mimeType: 'text/plain', buffer: Buffer.from('Real generated local text file. Synthetic test content.') },
    { name: 'authored-failure.txt', mimeType: 'text/plain', buffer: Buffer.from('Authored response fixture.') },
    { name: 'over-limit.txt', mimeType: 'text/plain', buffer: Buffer.alloc(2 * 1024 * 1024 + 1, 65) },
    { name: 'last-note.txt', mimeType: 'text/plain', buffer: Buffer.from('Later files still import after an earlier failure.') },
  ]);
  const results = page.locator('.va-upload-results');
  await expect(results.getByText('Upload results · 4 files checked', { exact: true })).toBeVisible();
  await expect(results.locator('li').filter({ hasText: 'real-note.txt' })).toContainText('Imported.');
  await expect(results.locator('li').filter({ hasText: 'authored-failure.txt' })).toContainText('Authored local import failure');
  await expect(results.locator('li').filter({ hasText: 'over-limit.txt' })).toContainText('exceeds the configured 2 MiB limit');
  await expect(results.locator('li').filter({ hasText: 'last-note.txt' })).toContainText('Imported.');
  expect(uploads.filter(body => body.includes('real-note.txt'))).toHaveLength(1);
  expect(uploads.filter(body => body.includes('authored-failure.txt'))).toHaveLength(1);
  expect(uploads.filter(body => body.includes('last-note.txt')).length).toBeGreaterThanOrEqual(1);
  expect(uploads.filter(body => body.includes('last-note.txt')).length).toBeLessThanOrEqual(2);
  expect(uploads.some(body => body.includes('over-limit.txt'))).toBe(false);
  await expect(page.getByRole('button', { name: 'Upload files', exact: true })).toBeEnabled();
  expect((await load(request, project.id)).resources.map(item => item.name)).toEqual(['real-note.txt', 'last-note.txt']);
  await capture(page, 'media-pool-import-results-and-parameterized-size-limit');
});

test('legacy tasks with unknown request scope can explicitly generate a new report from checked saved evidence only', async ({ page, request }) => {
  const project = seed('legacy_job');
  expect(project.jobs.find(job => job.id === 'failed_summary')?.resource_ids).toEqual([]);
  const capabilities = await (await request.get('/api/projects/capabilities')).json();
  expect(capabilities.configured, 'This regression must never call a paid provider').toBe(false);
  await open(page, project);
  await page.getByRole('button', { name: 'Activity', exact: true }).click();
  const oldReport = page.getByRole('article', { name: 'Reference analysis Needs attention', exact: true });
  await expect(oldReport.getByRole('button', { name: 'Retry report synthesis', exact: true })).toBeDisabled();
  await expect(oldReport).toContainText('Choose references in Resources and select Use saved evidence only to create a new report.');
  await page.getByRole('button', { name: 'Close activity', exact: true }).click();
  const names = ['Alpha partial.wav', 'Beta partial.wav', 'Gamma chunk.wav'];
  for (const name of names) await page.getByRole('checkbox', { name: `Select ${name}`, exact: true }).check();
  await page.getByRole('button', { name: 'Analyze 3 references', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Analyze selected references', exact: true });
  await expect(dialog.locator('ul li')).toHaveText(names);
  const savedOnly = dialog.getByRole('checkbox', { name: 'Use saved evidence only — skip visual and speech recognition.', exact: true });
  await expect(savedOnly).toBeEnabled();
  await expect(savedOnly).not.toBeChecked();
  await expect(dialog.getByLabel('Speech model', { exact: true })).toBeEnabled();
  await savedOnly.check();
  await expect(dialog.getByLabel('Speech model', { exact: true })).toBeDisabled();
  await expect(dialog).toContainText('The report uses available saved observations and keeps coverage gaps explicit.');
  await capture(page, 'legacy-explicit-saved-evidence-only-confirmation');
  const selected = page.waitForRequest(item => item.method() === 'POST' && item.url().endsWith(`/api/projects/${project.id}/selection`));
  const analyzed = page.waitForRequest(item => item.method() === 'POST' && item.url().endsWith(`/api/projects/${project.id}/analyze`));
  await dialog.getByRole('button', { name: 'Generate from saved evidence', exact: true }).click();
  const ids = ['resource_alpha', 'resource_beta', 'resource_gamma'];
  expect((await selected).postDataJSON()).toMatchObject({ resource_ids: ids, content_id: null });
  const payload = (await analyzed).postDataJSON();
  expect(payload).toMatchObject({ resource_ids: ids, content_id: null, synthesis_only: true, visual_only: false });
  expect(payload).not.toHaveProperty('transcription_model');
  await expect.poll(async () => (await load(request, project.id)).jobs.filter(job => job.kind === 'analyze').length).toBe(2);
  await expect.poll(async () => (await load(request, project.id)).jobs.filter(job => job.kind === 'analyze').at(-1)?.status).toBe('failed');
  const after = await load(request, project.id);
  const parent = after.jobs.filter(job => job.kind === 'analyze').at(-1)!;
  expect(parent.resource_ids).toEqual(ids);
  expect(parent.content_id).toBeNull();
  expect(parent.error_code).toBe('provider_not_configured');
  expect(parent.diagnostics.synthesis_only).toBe('true');
  expect(after.jobs.filter(job => ['reference_extraction', 'recognize'].includes(job.kind))).toEqual(project.jobs.filter(job => ['reference_extraction', 'recognize'].includes(job.kind)));
  expect(after.resources.map(item => item.evidence)).toEqual(project.resources.map(item => item.evidence));
  // The user's explicit selection may mark older reports for review; their
  // content and saved input manifests must still remain intact.
  expect(after.analyses.map(item => ({ ...item, needs_review: false }))).toEqual(project.analyses.map(item => ({ ...item, needs_review: false })));
  expect(after.active_content_id).toBe(project.active_content_id);
  expect(after.selection.resource_ids).toEqual(ids);
});
