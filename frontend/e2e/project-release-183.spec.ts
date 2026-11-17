import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { Project } from '../src/project/contracts';

// Real local files plus authored historical records. No provider requests.
const root = resolve(import.meta.dirname, '../..');
type Receipt = { project: Project; media_sha256: string };
const seed = (mode = 'seed'): Receipt => JSON.parse(execFileSync(join(root, '.venv/bin/python'), [
  join(root, 'frontend/e2e/project-release-183-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!,
  mode,
], { cwd: root, encoding: 'utf8' }));
const load = async (request: APIRequestContext, id: string): Promise<Project> => (await request.get(`/api/projects/${id}`)).json();
async function change(request: APIRequestContext, id: string, path: string, fields: Record<string, unknown>) {
  const project = await load(request, id);
  const response = await request.post(`/api/projects/${id}${path}`, { data: { expected_version: project.version, ...fields } });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json() as Promise<Project>;
}
async function open(page: Page, id: string) { await page.goto(`/?project=${id}`); await expect(page.getByRole('heading', { name: 'Media Pool', exact: true })).toBeVisible(); }
async function capture(page: Page, name: string) {
  const folder = process.env.VIDEO_ANATOMY_SCREENSHOT_DIR;
  if (folder) { mkdirSync(folder, { recursive: true }); await page.screenshot({ path: join(folder, `${name}.png`), fullPage: true }); }
}
function csvRows(contents: string): string[][] {
  return JSON.parse(execFileSync(join(root, '.venv/bin/python'), ['-c',
    'import csv,io,json,sys; print(json.dumps(list(csv.reader(io.StringIO(sys.stdin.read().lstrip("\\ufeff"))))))'],
  { input: contents, encoding: 'utf8' }));
}

test('old source moves, renames, trashes and restores without changing evidence or analysis selection', async ({ page, request }) => {
  const receipt = seed(); const original = receipt.project; const rid = 'resource_legacy_reference';
  await open(page, original.id);
  await expect(page.locator('video')).toHaveCount(0);
  const selected = page.getByRole('checkbox', { name: 'Select Legacy reference.mp4', exact: true });
  await expect(selected).toBeChecked();
  await page.getByRole('button', { name: 'Focus Legacy notes.txt', exact: true }).click();
  await expect(selected).toBeChecked();
  await page.getByRole('navigation', { name: 'Resource folders' }).getByRole('button', { name: 'Documents', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Analyze 1 reference', exact: true })).toBeVisible();
  await page.getByRole('navigation', { name: 'Resource folders' }).getByRole('button', { name: 'All files', exact: true }).click();
  await page.getByRole('button', { name: 'Focus Legacy reference.mp4', exact: true }).click();
  await page.getByRole('button', { name: 'Move to', exact: true }).click();
  const move = page.getByRole('dialog', { name: 'Move files', exact: true });
  await move.getByLabel('Destination folder').selectOption('folder_documents');
  await move.getByRole('button', { name: 'Save', exact: true }).click();
  await expect.poll(async () => (await load(request, original.id)).resources.find(resource => resource.id === rid)?.folder_id).toBe('folder_documents');
  await page.getByRole('button', { name: 'Rename file', exact: true }).click();
  const rename = page.getByRole('dialog', { name: 'Rename file', exact: true });
  await rename.getByLabel('Name', { exact: true }).fill('Moved reference.mp4');
  await rename.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Focus Moved reference.mp4', exact: true })).toBeVisible();
  const moved = await load(request, original.id);
  expect(moved.resources.find(resource => resource.id === rid)?.original_path).toBe(original.resources[0].original_path);
  expect(moved.resources[0].evidence.map(revision => revision.events.map(event => event.text))).toEqual(original.resources[0].evidence.map(revision => revision.events.map(event => event.text)));
  expect(moved.analyses[0].sources).toEqual(original.analyses[0].sources);
  expect(moved.active_content_id).toBe(original.active_content_id);
  expect(moved.jobs).toEqual([]);
  await page.getByRole('button', { name: 'Move to Trash', exact: true }).click();
  await page.getByRole('dialog', { name: 'Move to Trash', exact: true }).getByRole('button', { name: 'Move to Trash', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Focus Moved reference.mp4', exact: true })).toHaveCount(0);
  await page.getByRole('navigation', { name: 'Resource folders' }).getByRole('button', { name: 'Trash', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Focus Moved reference.mp4', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Restore file', exact: true }).click();
  await page.getByRole('dialog', { name: 'Restore from Trash', exact: true }).getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('navigation', { name: 'Resource folders' }).getByRole('button', { name: 'All files', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Focus Moved reference.mp4', exact: true })).toBeVisible();
  const media = await request.get(`/api/projects/${original.id}/resources/${rid}/file`);
  expect(createHash('sha256').update(await media.body()).digest('hex')).toBe(receipt.media_sha256);
  await capture(page, 'release-183-media-pool-restored');
});

test('sheet human edits reopen and export the same saved revision while legacy documents stay readable', async ({ page, request }) => {
  const receipt = seed(); const id = receipt.project.id;
  const withDirection = await change(request, id, '/contents/content_active_video/directions', {
    title: 'The exact approved sheet direction', concept: 'A six-second introduction.', hook: '', narrative: 'A simple authored plan.', cta: '',
  });
  const direction = withDirection.contents[0].directions.at(-1)!;
  await change(request, id, `/contents/content_active_video/directions/${direction.id}/approve`, { revision: direction.revision });
  const created = await change(request, id, '/contents/content_active_video/production/manual', {});
  const pack = created.packs.at(-1)!;
  await change(request, id, `/packs/${pack.id}`, { revision: 1, production_brief: 'A concise saved production brief.', shots: [{
    id: 'shot_browser', start_seconds: 0, end_seconds: 6, framing_camera: 'Medium shot',
    visual: 'An initial planned visual.', dialogue: 'Initial dialogue.', on_screen_text: 'Introduction', sound: 'Ambient', notes: '', sources: [],
  }] });
  await open(page, id);
  await page.getByRole('button', { name: 'Production', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'The planned Video', exact: true })).toBeVisible();
  await page.getByLabel('Shot 01 Framing / Camera', { exact: true }).fill('Close-up / handheld');
  await page.getByLabel('Shot 01 Visual / Action', { exact: true }).fill('Human revised visual.');
  const dialogue = 'Human dialogue, with "quotes".\n第二行台词。';
  await page.getByLabel('Shot 01 Dialogue / VO', { exact: true }).fill(dialogue);
  await page.getByRole('button', { name: 'Save sheet', exact: true }).click();
  await expect(page.getByText('Current · v3', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Shot 01 Dialogue / VO', { exact: true })).toHaveValue(dialogue);
  await expect(page.getByLabel('Shot 01 Framing / Camera', { exact: true })).toHaveValue('Close-up / handheld');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export sheet', exact: true }).click();
  const file = await download;
  const rows = csvRows(readFileSync((await file.path())!, 'utf8'));
  expect(rows).toHaveLength(2);
  expect(rows[0]).toEqual(['Shot', 'Start', 'End', 'Framing / Camera', 'Visual / Action', 'Dialogue / VO', 'On-screen Text', 'Music / SFX', 'Production Notes']);
  expect(rows[1].slice(1, 6)).toEqual(['0.0', '6.0', 'Close-up / handheld', 'Human revised visual.', dialogue]);
  const saved = await load(request, id);
  const latest = saved.packs.filter(item => item.id === pack.id).at(-1)!;
  expect(latest.revision).toBe(3);
  expect(latest.shots[0].dialogue).toBe(rows[1][5]);
  expect(saved.active_content_id).toBe('content_active_video');
  await capture(page, 'release-183-authoritative-storyboard-sheet');
  for (const [width, height] of [[720, 450], [390, 844]]) {
    await page.setViewportSize({ width, height });
    const notes = page.getByLabel('Shot 01 Production Notes', { exact: true });
    await notes.scrollIntoViewIfNeeded(); await notes.focus();
    await expect(notes).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    const table = page.getByRole('region', { name: 'Storyboard sheet', exact: true });
    expect(await table.evaluate(element => {
      const bounds = element.getBoundingClientRect();
      return bounds.left >= 0 && bounds.right <= innerWidth + 1 && element.scrollWidth > element.clientWidth;
    })).toBeTruthy();
    const exportButton = page.getByRole('button', { name: 'Export sheet', exact: true });
    await exportButton.scrollIntoViewIfNeeded(); await exportButton.click({ trial: true });
    const reader = page.locator('details.va-sheet-reader');
    if (!await reader.evaluate(element => (element as HTMLDetailsElement).open)) await reader.locator('summary').click();
    const spokenText = reader.locator('dd').filter({ hasText: 'Human dialogue,' });
    await expect(spokenText).toBeVisible(); await expect(spokenText).toContainText('第二行台词。');
  }
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.getByLabel('Saved revision', { exact: true }).selectOption('pack_legacy_text:1');
  await expect(page.getByRole('heading', { name: 'Legacy production documents', exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Storyboard', exact: true }).click();
  await expect(page.getByLabel('Storyboard', { exact: true })).toHaveValue(receipt.project.packs[0].storyboard);
  expect((await load(request, id)).packs.find(item => item.id === 'pack_legacy_text')?.shots).toEqual([]);
});

async function openHistoricalSource(page: Page, project: Project) {
  await open(page, project.id);
  await page.getByRole('button', { name: 'Analysis', exact: true }).click();
  await page.getByLabel('Analysis scope', { exact: true }).selectOption('content_browsed_video');
  await page.getByText('Evidence and source moments', { exact: true }).click();
  await page.locator('.va-analysis-evidence').getByRole('button', { name: /Legacy reference\.mp4.*00:0[15]/ }).click();
  await expect(page.getByRole('region', { name: 'Source Review', exact: true })).toBeVisible();
  const player = page.getByLabel('Reference video player', { exact: true });
  await expect.poll(async () => player.evaluate(element => (element as HTMLVideoElement).readyState)).toBeGreaterThanOrEqual(2);
  return player;
}

test('historical source review and report browsing keep the same planned Video and exact evidence', async ({ page, request }) => {
  const receipt = seed(); const project = receipt.project;
  const player = await openHistoricalSource(page, project);
  await expect(page.getByLabel('Evidence revision', { exact: true })).toHaveValue('1');
  await expect(page.locator('.va-source-selected-text')).toHaveText('Original observation at one second.');
  await expect(page.getByText('Timing precision is not recorded for this legacy event.', { exact: true })).toBeVisible();
  await expect(page.getByText('Verified frame timing', { exact: true })).toHaveCount(0);
  await expect.poll(async () => player.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeGreaterThanOrEqual(.95);
  expect(await player.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeLessThan(1.1);
  expect((await load(request, project.id)).active_content_id).toBe('content_active_video');
  await expect.poll(async () => player.evaluate(element => (element as HTMLVideoElement).seeking)).toBe(false);
  await capture(page, 'release-183-exact-historical-evidence');
  await page.getByLabel('Evidence revision', { exact: true }).selectOption('2');
  await page.getByRole('button', { name: 'Seek to 00:03: Human-corrected observation at three seconds.', exact: true }).click();
  await expect(page.locator('.va-source-selected-text')).toHaveText('Human-corrected observation at three seconds.');
  await expect.poll(async () => player.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeGreaterThanOrEqual(2.95);
  await expect.poll(async () => player.evaluate(element => (element as HTMLVideoElement).seeking)).toBe(false);
  expect((await load(request, project.id)).analyses[0].sources).toEqual(project.analyses[0].sources);
  await capture(page, 'release-183-current-evidence-after-explicit-switch');
  await page.locator('.va-back-to-pool').click();
  await expect(page.getByRole('heading', { name: 'Reference analysis', exact: true })).toBeVisible();
  await expect(page.getByLabel('Analysis scope', { exact: true })).toHaveValue('content_browsed_video');
  await page.getByRole('button', { name: 'Production', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'The planned Video', exact: true })).toBeVisible();
  await expect(page.getByLabel('Video', { exact: true })).toHaveValue('content_active_video');
});

for (const mode of ['missing_revision', 'unversioned_time']) test(`${mode} never substitutes current evidence for the historical link`, async ({ page }) => {
  const receipt = seed(mode);
  const player = await openHistoricalSource(page, receipt.project);
  if (mode === 'missing_revision') {
    await expect(page.getByRole('alert')).toContainText('Requested evidence revision 99 is unavailable.');
    expect(await player.evaluate(element => (element as HTMLVideoElement).currentTime)).toBe(0);
  } else {
    await expect(page.getByLabel('Evidence revision', { exact: true })).toHaveValue('source-only');
    await expect(page.getByRole('status').filter({ hasText: 'This link identifies only a source time range.' })).toContainText('Its saved evidence revision is unavailable; current evidence was not substituted.');
    await expect.poll(async () => player.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeGreaterThanOrEqual(.95);
    expect(await player.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeLessThan(1.1);
  }
  await expect(page.locator('.va-source-selected-text')).toHaveCount(0);
  await expect(page.locator('.va-source-evidence-list ol > li')).toHaveCount(0);
  await page.getByRole('button', { name: 'View current evidence', exact: true }).click();
  await page.getByRole('button', { name: 'Seek to 00:03: Human-corrected observation at three seconds.', exact: true }).click();
  await expect(page.locator('.va-source-selected-text')).toHaveText('Human-corrected observation at three seconds.');
});

test('a corrupted citation timestamp cannot send the player to another moment', async ({ page }) => {
  const receipt = seed('mismatched_time');
  const player = await openHistoricalSource(page, receipt.project);
  // Either resolve the exact saved event's authoritative time, or explain that
  // the conflicting reference is unavailable. Never trust its cached five seconds.
  if (await page.getByRole('alert').count()) {
    await expect(page.getByRole('alert')).toContainText(/unavailable|timestamp|time range|timing conflicts/i);
    expect(await player.evaluate(element => (element as HTMLVideoElement).currentTime)).toBe(0);
    await expect(page.getByRole('slider', { name: 'Source playhead', exact: true })).toHaveValue('0');
  } else {
    await expect.poll(async () => player.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeGreaterThanOrEqual(.95);
    expect(await player.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeLessThan(1.1);
    await expect(page.locator('.va-source-selected-text')).toHaveText('Original observation at one second.');
  }
});

test('late media metadata cannot restore a citation after an explicit playback choice', async ({ page }) => {
  const receipt = seed();
  // A second authored event in the same saved revision exercises a deliberate
  // event change independently of the current/historical revision controls.
  execFileSync(join(root, '.venv/bin/python'), ['-c', [
    'from pathlib import Path',
    'import sys',
    'from backend.app.project_workspace.models import EvidenceEvent',
    'from backend.app.project_workspace.store import ProjectStore',
    'store = ProjectStore(Path(sys.argv[1]))',
    'project = store.get(sys.argv[2])',
    'def add_event(state):',
    '    state.resources[0].evidence[0].events.append(EvidenceEvent(id="visual_second", kind="visual", text="Another historical observation at two seconds.", start_seconds=2, end_seconds=2))',
    'store.update(project.id, project.version, add_event)',
  ].join('\n'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, receipt.project.id], { cwd: root });
  const player = await openHistoricalSource(page, receipt.project);
  const at = async (seconds: number) => {
    await expect.poll(async () => player.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeGreaterThanOrEqual(seconds - .05);
    expect(await player.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeLessThan(seconds + .05);
  };
  const lateMetadata = async () => {
    await player.dispatchEvent('loadedmetadata');
    await expect.poll(async () => player.evaluate(element => (element as HTMLVideoElement).seeking)).toBe(false);
  };
  await at(1);
  await page.getByRole('button', { name: 'Seek to 00:02: Another historical observation at two seconds.', exact: true }).click();
  await at(2);
  await lateMetadata();
  await at(2);
  await expect(page.locator('.va-source-selected-text')).toHaveText('Another historical observation at two seconds.');

  await page.getByRole('button', { name: 'View current evidence', exact: true }).click();
  await lateMetadata();
  await at(2);
  await expect(page.getByLabel('Evidence revision', { exact: true })).toHaveValue('current');
  await expect(page.locator('.va-source-selected-text')).toHaveCount(0);

  await page.getByLabel('Evidence revision', { exact: true }).selectOption('2');
  await page.getByRole('button', { name: 'Seek to 00:03: Human-corrected observation at three seconds.', exact: true }).click();
  await at(3);
  await lateMetadata();
  await at(3);
  await expect(page.locator('.va-source-selected-text')).toHaveText('Human-corrected observation at three seconds.');
});
