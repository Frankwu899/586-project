import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import type { Project } from '../src/project/contracts';

const root = resolve(import.meta.dirname, '../..');
let folder: string; let media: string;
const fixture = (mode = 'valid'): Project => JSON.parse(execFileSync(join(root, '.venv/bin/python'), [join(root, 'frontend/e2e/project-resources-183-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, media, mode], { cwd: root, encoding: 'utf8' }));
async function open(page: Page, project: Project) { await page.goto(`/?project=${project.id}`); await page.getByRole('button', { name: 'Resources', exact: true }).click(); await expect(page.getByRole('heading', { name: 'Media Pool', exact: true })).toBeVisible(); }
async function capture(page: Page, name: string) { const path = process.env.VIDEO_ANATOMY_SCREENSHOT_DIR; if (path) { mkdirSync(path, { recursive: true }); await page.screenshot({ path: join(path, `${name}.png`), fullPage: false }); } }
test.beforeAll(() => { folder = mkdtempSync(join(tmpdir(), 'video-anatomy-b-183-')); media = join(folder, 'synthetic-blue.mp4'); execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=25:d=12', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', media]); });
test.afterAll(() => rmSync(folder, { recursive: true, force: true }));

test('playback failure exports browser diagnostics separately from saved speech failures', async ({ page }) => {
  const project = fixture('playback_failure');
  await page.route('**/file?representation=playback*', route => route.abort('failed'));
  await open(page, project);
  await page.getByRole('button', { name: 'Focus commute-demo.mp4', exact: true }).click();
  await page.getByRole('button', { name: 'Open in timeline', exact: true }).click();
  const failure = page.getByRole('alert').filter({ hasText: 'Playback is unavailable' });
  await expect(failure).toBeVisible();
  await failure.getByText('Support details', { exact: true }).click();
  await expect(failure.locator('pre')).toContainText('stage: playback');
  await expect(failure.locator('pre')).toContainText('media_error_code: 4');
  await expect(failure.locator('pre')).not.toContainText('audio_timestamps_invalid');
  await page.getByText('Coverage, original file and recovery', { exact: true }).click();
  await page.getByText('Support diagnostics', { exact: true }).click();
  await expect(page.locator('.va-source-details pre')).toContainText('audio_timestamps_invalid');
});

test('rebuilding a preview recovers an errored player without leaving Source Review', async ({ page, request }) => {
  const project = fixture(); let unavailable = true;
  await page.route('**/file?representation=playback*', route => unavailable ? route.abort('failed') : route.continue());
  await open(page, project);
  await page.getByRole('button', { name: 'Focus commute-demo.mp4', exact: true }).click();
  await page.getByRole('button', { name: 'Open in timeline', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Playback is unavailable' })).toBeVisible();
  unavailable = false;
  await page.getByText('Coverage, original file and recovery', { exact: true }).click();
  await page.getByRole('button', { name: 'Rebuild media preview', exact: true }).click();
  const video = page.getByLabel('Reference video player');
  await expect.poll(() => video.evaluate(node => (node as HTMLVideoElement).readyState)).toBeGreaterThanOrEqual(1);
  await expect(page.getByRole('alert').filter({ hasText: 'Playback is unavailable' })).toHaveCount(0);
  await page.getByRole('button', { name: /Visual observations at 00:05/ }).click();
  await expect.poll(() => video.evaluate(node => (node as HTMLVideoElement).currentTime)).toBeGreaterThan(4.9);
  const saved: Project = await (await request.get(`/api/projects/${project.id}`)).json();
  expect(saved.resources[0].evidence).toEqual(project.resources[0].evidence);
  expect(saved.resources[0].sha256).toBe(project.resources[0].sha256);
});

test('real folders preserve identity through move, rename, Trash, restore and reload', async ({ page, request }) => {
  const project = fixture(); await open(page, project);
  await expect(page.locator('video,audio')).toHaveCount(0);
  await page.getByRole('checkbox', { name: 'Select commute-demo.mp4', exact: true }).check();
  await page.getByRole('checkbox', { name: 'Select desk-routine.mp4', exact: true }).check();
  await page.getByRole('button', { name: 'Focus commute-demo.mp4', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Focus commute-demo.mp4', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('2 files selected', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Move to', exact: true }).click();
  await page.getByLabel('Destination folder', { exact: true }).selectOption('folder_documents');
  await page.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByRole('button', { name: 'Clear selection', exact: true }).click();
  await page.getByRole('button', { name: 'Rename file', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Name', { exact: true }).fill('renamed-source.mp4');
  await page.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByRole('button', { name: 'Move to Trash', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Move to Trash', exact: true }).click();
  await page.getByRole('navigation', { name: 'Resource folders' }).getByRole('button', { name: 'Trash', exact: true }).click();
  await page.getByRole('button', { name: 'Focus renamed-source.mp4', exact: true }).click();
  await page.getByRole('button', { name: 'Restore file', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Documents', exact: true }).click();
  await page.reload(); await page.getByRole('button', { name: 'Documents', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Focus renamed-source.mp4', exact: true })).toBeVisible();
  const saved: Project = await (await request.get(`/api/projects/${project.id}`)).json();
  expect(saved.resources[0].id).toBe(project.resources[0].id);
  expect(saved.resources[0].sha256).toBe(project.resources[0].sha256);
  expect(saved.resources[0].original_path).toBe(project.resources[0].original_path);
  expect(saved.resources[0].evidence).toEqual(project.resources[0].evidence);
  expect(saved.resources[0].folder_id).toBe('folder_documents');
  await capture(page, 'media-pool-183-documents');
});

test('focus is independent of analysis selection and only confirmed media reach analysis', async ({ page, request }) => {
  const project = fixture(); await open(page, project);
  await page.locator('.va-media-pool input[type=file]').setInputFiles({ name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('Saved document task input.') });
  await expect(page.getByRole('button', { name: 'Focus notes.txt', exact: true })).toBeVisible();
  for (const name of ['commute-demo.mp4', 'desk-routine.mp4', 'notes.txt']) await page.getByRole('checkbox', { name: `Select ${name}`, exact: true }).check();
  await page.getByRole('button', { name: 'Focus notes.txt', exact: true }).click();
  await page.getByRole('button', { name: 'Analyze 2 references', exact: true }).click();
  const confirmation = page.getByRole('dialog', { name: 'Analyze selected references' });
  await expect(confirmation.getByRole('list')).toContainText('commute-demo.mp4');
  await expect(confirmation.getByRole('list')).not.toContainText('notes.txt');
  expect((await (await request.get(`/api/projects/${project.id}`)).json()).jobs.filter((item: { kind: string }) => item.kind === 'analyze')).toEqual([]);
  await confirmation.getByRole('button', { name: 'Cancel', exact: true }).click();
  expect((await (await request.get(`/api/projects/${project.id}`)).json()).active_content_id).toBe(project.active_content_id);
  await capture(page, 'media-pool-183-independent-selection');
});

test('folders can be created, renamed, moved to root, trashed and restored without self-move defaults', async ({ page, request }) => {
  const project = fixture(); await open(page, project);
  await page.getByRole('button', { name: 'References', exact: true }).click();
  await page.getByRole('button', { name: 'New folder', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Name', { exact: true }).fill('A nested folder');
  await page.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByRole('navigation', { name: 'Resource folders' }).getByRole('button', { name: 'A nested folder', exact: true }).click();
  await page.getByLabel('Folder actions', { exact: true }).click();
  await page.getByRole('button', { name: 'Rename folder', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Name', { exact: true }).fill('Renamed folder');
  await page.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByRole('button', { name: 'Move folder', exact: true }).click();
  await expect(page.getByLabel('Destination folder', { exact: true })).toHaveValue('folder_references');
  await page.getByLabel('Destination folder', { exact: true }).selectOption('');
  await page.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByRole('button', { name: 'Move folder to Trash', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Move to Trash', exact: true }).click();
  await page.getByRole('navigation', { name: 'Resource folders' }).getByRole('button', { name: 'Trash', exact: true }).click();
  await page.getByRole('button', { name: 'Renamed folder · Restore folder', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Restore', exact: true }).click();
  const saved: Project = await (await request.get(`/api/projects/${project.id}`)).json();
  const restored = saved.resource_folders.find(item => item.name === 'Renamed folder');
  expect(restored?.parent_id).toBeNull(); expect(restored?.trashed_at).toBeNull();
  expect(saved.resources.map(item => item.id)).toEqual(project.resources.map(item => item.id));
});

test('one Source Review opens exact historical evidence from media and analysis', async ({ page, request }) => {
  const project = fixture(); await open(page, project);
  await page.getByRole('button', { name: 'Focus commute-demo.mp4', exact: true }).click(); await page.getByRole('button', { name: 'Open in timeline', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Evidence timeline', exact: true })).toBeVisible();
  await page.getByRole('button', { name: /Visual observations at 00:05/ }).click();
  await expect(page.getByRole('complementary', { name: 'Selected evidence' })).toContainText('Current corrected observation 0');
  const video = page.getByLabel('Reference video player'); await expect.poll(async () => video.evaluate(node => (node as HTMLVideoElement).currentTime)).toBeGreaterThan(4.9);
  await page.getByLabel('Search transcript', { exact: true }).fill('Current corrected speech');
  await page.getByRole('button', { name: 'Seek to 00:06: Current corrected speech 0', exact: true }).click();
  await expect.poll(async () => video.evaluate(node => (node as HTMLVideoElement).currentTime)).toBeGreaterThan(5.9);
  await page.getByRole('button', { name: 'Analysis', exact: true }).click();
  await page.getByLabel('Analysis scope', { exact: true }).selectOption('');
  await page.getByRole('button', { name: /commute-demo.mp4 · Recorded sample/ }).first().click();
  await expect(page.getByLabel('Evidence revision', { exact: true })).toHaveValue('1');
  await expect(page.getByRole('heading', { name: 'commute-demo.mp4', exact: true })).toBeFocused();
  await expect(page.getByRole('complementary', { name: 'Selected evidence' })).toContainText('Historical observation 0');
  await expect(page.getByRole('complementary', { name: 'Selected evidence' })).not.toContainText('Current corrected observation 0');
  expect((await (await request.get(`/api/projects/${project.id}`)).json()).active_content_id).toBe(project.active_content_id);
  await expect.poll(async () => video.evaluate(node => (node as HTMLVideoElement).seeking)).toBe(false);
  await capture(page, 'source-review-183-historical');
});

for (const mode of ['missing_revision', 'missing_event', 'conflicting_time', 'outside_time']) test(`a ${mode} citation is unavailable without substituted evidence or unsafe seek`, async ({ page }) => {
  const project = fixture(mode); await open(page, project);
  await page.getByRole('button', { name: 'Analysis', exact: true }).click();
  await page.getByLabel('Analysis scope', { exact: true }).selectOption('');
  await page.getByRole('region', { name: 'Key insights', exact: true }).getByRole('button', { name: /commute-demo.mp4 · Recorded sample/ }).click();
  await expect(page.getByRole('alert')).toContainText('No current or approximate event was substituted.');
  await expect(page.getByRole('complementary', { name: 'Selected evidence' })).not.toContainText('Current corrected observation 0');
  const video = page.getByLabel('Reference video player');
  await expect.poll(async () => video.evaluate(node => (node as HTMLVideoElement).readyState)).toBeGreaterThanOrEqual(1);
  expect(await video.evaluate(node => (node as HTMLVideoElement).currentTime)).toBeLessThan(.1);
  await expect(page.getByRole('slider', { name: 'Source playhead', exact: true })).toHaveValue('0');
  await page.getByRole('button', { name: 'View current evidence', exact: true }).click();
  await expect(page.locator('.va-source-evidence-list')).toContainText('Current corrected observation 0');
});

test('a valid unversioned source range plays the original without borrowing current evidence', async ({ page }) => {
  const project = fixture('source_only'); await open(page, project);
  await page.getByRole('button', { name: 'Analysis', exact: true }).click();
  await page.getByRole('region', { name: 'Key insights', exact: true }).getByRole('button', { name: /commute-demo.mp4 · Recorded sample/ }).click();
  await expect(page.getByRole('status').filter({ hasText: 'This link identifies only a source time range.' })).toBeVisible();
  await expect(page.getByLabel('Evidence revision', { exact: true })).toHaveValue('source-only');
  await expect(page.locator('.va-evidence-track')).toHaveCount(0);
  await expect(page.locator('.va-source-evidence-list')).not.toContainText('Current corrected observation 0');
  await expect.poll(async () => page.getByLabel('Reference video player').evaluate(node => (node as HTMLVideoElement).currentTime)).toBeGreaterThan(1.99);
  await page.getByRole('button', { name: 'View current evidence', exact: true }).click();
  await expect(page.locator('.va-source-evidence-list')).toContainText('Current corrected observation 0');
});

for (const [code, diagnosis] of [
  ['provider_authentication', 'The service rejected the API key.'],
  ['provider_credit_balance_exhausted', 'The API account has insufficient credit.'],
  ['provider_network', 'The service could not be reached.'],
]) test(`new ${code} speech retry failure takes precedence over old partial coverage in one action area`, async ({ page }) => {
  const project = fixture(`speech_failure:${code}`); await open(page, project);
  await page.getByRole('button', { name: 'Focus commute-demo.mp4', exact: true }).click();
  await page.getByRole('button', { name: 'Open in timeline', exact: true }).click();
  const action = page.locator('.va-source-speech-status');
  await expect(action.getByRole('alert')).toContainText(diagnosis);
  await expect(action).not.toContainText('Partial transcript available');
  await expect(action).toContainText('Completed observations and corrections are retained.');
  await expect(action.getByRole('button', { name: 'Retry missing speech', exact: true })).toBeEnabled();
  await expect(page.locator('.va-source-player .va-error')).toHaveCount(0);
  await expect(page.getByText('Earlier transcript coverage is incomplete; its completed observations are retained.', { exact: true })).toBeHidden();
  await capture(page, `source-review-183-${code}`);
});

for (const [width, height] of [[1440, 900], [1280, 800], [390, 844], [720, 450]]) test(`Media Pool and timeline remain reachable at ${width}x${height}`, async ({ page }) => {
  const project = fixture(); await page.setViewportSize({ width, height }); await open(page, project);
  await page.getByRole('button', { name: 'Focus commute-demo.mp4', exact: true }).click(); await page.getByRole('button', { name: 'Open in timeline', exact: true }).click();
  await page.getByRole('slider', { name: 'Source playhead', exact: true }).scrollIntoViewIfNeeded();
  await page.getByRole('slider', { name: 'Source playhead', exact: true }).focus(); await page.keyboard.press('ArrowRight');
  await page.getByRole('button', { name: 'Zoom timeline in', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Scrollable source timeline', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
  await capture(page, `source-review-183-${width}x${height}`);
});
