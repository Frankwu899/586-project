import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { Project } from '../src/project/contracts';

const root = resolve(import.meta.dirname, '../..');
const seed = (mode = 'multiple'): Project => JSON.parse(execFileSync(join(root, '.venv/bin/python'), [join(root, 'frontend/e2e/project-planning-184-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, mode], { cwd: root, encoding: 'utf8' }));
const load = async (request: APIRequestContext, id: string): Promise<Project> => (await request.get(`/api/projects/${id}`)).json();
const video = (page: Page, id: string) => page.locator(`[data-plan-video="${id}"]`);
const series = (page: Page, id: string) => page.locator(`[data-plan-series="${id}"]`);
async function action(page: Page, kind: 'video' | 'series', id: string, label: string) {
  const row = kind === 'video' ? video(page, id) : series(page, id);
  await row.locator(':scope > .va-planning-actions > button').click();
  await row.getByRole('button', { name: label, exact: true }).click();
}
async function move(page: Page, id: string, destination: string) {
  const row = video(page, id);
  await row.locator(':scope > .va-planning-actions > button').click();
  await row.getByRole('button', { name: /Move video \/ make standalone|Move to a series/ }).click();
  const dialog = page.getByRole('dialog', { name: 'Move video', exact: true });
  await dialog.getByLabel('Destination series', { exact: true }).selectOption(destination);
  await dialog.getByRole('button', { name: 'Move video', exact: true }).click();
  await expect(dialog).not.toBeVisible();
}
async function screenshot(page: Page, name: string) {
  const directory = process.env.VIDEO_ANATOMY_SCREENSHOT_DIR;
  if (directory) { mkdirSync(directory, { recursive: true }); await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: join(directory, name), fullPage: true }); }
}

test('standalone and in-series creation are discoverable and searchable without switching the selected Video', async ({ page, request }) => {
  const project = seed();
  await page.goto(`/?project=${project.id}`);
  await page.getByRole('button', { name: 'Plan a video', exact: true }).click();
  const create = page.getByRole('dialog', { name: 'Plan a video', exact: true });
  await expect(create.getByLabel('Series', { exact: true })).toHaveValue('');
  await create.getByLabel('Title', { exact: true }).fill('A new standalone idea');
  await create.getByRole('button', { name: 'Create video', exact: true }).click();
  await expect(create).not.toBeVisible();
  let saved = await load(request, project.id);
  const standalone = saved.contents.find(item => item.title === 'A new standalone idea')!;
  expect(standalone.series_id).toBeNull(); expect(saved.active_content_id).toBe(standalone.id);
  await page.getByRole('button', { name: 'Create series', exact: true }).click();
  const group = page.getByRole('dialog', { name: 'Create series', exact: true });
  await group.getByLabel('Title', { exact: true }).fill('A new optional Series');
  await group.getByRole('button', { name: 'Create series', exact: true }).click();
  await expect(group).not.toBeVisible();
  saved = await load(request, project.id);
  const createdSeries = saved.series.find(item => item.title === 'A new optional Series')!;
  expect(saved.active_content_id).toBe(standalone.id);
  await page.getByRole('button', { name: 'Add video to A new optional Series', exact: true }).click();
  await expect(create.getByLabel('Series', { exact: true })).toHaveValue(createdSeries.id);
  await create.getByLabel('Title', { exact: true }).fill('An episode inside the Series');
  await create.getByRole('button', { name: 'Create video', exact: true }).click();
  await expect(create).not.toBeVisible();
  saved = await load(request, project.id);
  const episode = saved.contents.find(item => item.title === 'An episode inside the Series')!;
  expect(episode.series_id).toBe(createdSeries.id);
  await page.getByLabel('Search videos and series', { exact: true }).fill('commuter');
  await expect(series(page, 'series_managed')).toBeVisible();
  await expect(video(page, standalone.id)).toHaveCount(0);
  expect((await load(request, project.id)).active_content_id).toBe(episode.id);
  await page.getByLabel('Search videos and series', { exact: true }).fill('no matching title');
  await expect(page.getByText('No matching series.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Clear search', exact: true }).click();
  await expect(video(page, standalone.id)).toBeVisible();
  expect((await load(request, project.id)).jobs).toEqual([]);
});

test('renaming a Video and its Series preserves approval, historical packs, and the Production selection', async ({ page, request }) => {
  const project = seed(); const original = project.contents[0];
  await page.goto(`/?project=${project.id}`);
  await action(page, 'video', original.id, 'Rename video');
  const rename = page.getByRole('dialog', { name: 'Rename video', exact: true });
  await expect(rename.getByLabel('Name', { exact: true })).toBeFocused();
  await rename.getByLabel('Name', { exact: true }).fill('The renamed planned Video');
  await rename.getByRole('button', { name: 'Save name', exact: true }).click();
  await action(page, 'series', 'series_managed', 'Rename series');
  const renameSeries = page.getByRole('dialog', { name: 'Rename series', exact: true });
  await renameSeries.getByLabel('Name', { exact: true }).fill('The renamed Series');
  await renameSeries.getByRole('button', { name: 'Save name', exact: true }).click();
  const saved = await load(request, project.id); const current = saved.contents.find(item => item.id === original.id)!;
  expect(saved.active_content_id).toBe(original.id); expect(current.approved_direction_id).toBe(original.approved_direction_id);
  expect(current.directions).toEqual(original.directions); expect(saved.packs).toEqual(project.packs);
  await page.getByRole('button', { name: 'Open Production', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'The renamed planned Video', exact: true })).toBeVisible();
  await expect(page.getByLabel('Video', { exact: true })).toHaveValue(original.id);
  await page.reload(); await expect(page.getByLabel('Video', { exact: true })).toHaveValue(original.id);
  await page.getByRole('button', { name: 'Content plan', exact: true }).click();
  await expect(video(page, original.id).getByRole('button', { name: 'The renamed planned Video', exact: true })).toHaveAttribute('aria-current', 'true');
  await screenshot(page, 'content-plan-management-desktop.png');
});

test('moving the same Video out of and into grouping-only Series preserves its identity and saved work', async ({ page, request }) => {
  const project = seed(); const original = project.contents[0];
  await page.goto(`/?project=${project.id}`);
  await move(page, original.id, '');
  let saved = await load(request, project.id);
  expect(saved.contents.find(item => item.id === original.id)?.series_id).toBeNull();
  await move(page, original.id, 'series_other');
  saved = await load(request, project.id);
  const current = saved.contents.find(item => item.id === original.id)!;
  expect(current.series_id).toBe('series_other'); expect(current.approved_direction_id).toBe(original.approved_direction_id);
  expect(current.directions).toEqual(original.directions); expect(saved.packs).toEqual(project.packs);
  expect(saved.active_content_id).toBe(original.id); expect(saved.contents).toHaveLength(project.contents.length);
  await expect(page.locator('.va-video-group').getByLabel('Series', { exact: true })).toHaveValue('series_other');
});

test('Video Trash retains history, chooses a remaining active Video, and restores without stealing selection', async ({ page, request }) => {
  const project = seed(); const original = project.contents[0];
  await page.goto(`/?project=${project.id}`);
  await action(page, 'video', original.id, 'Move video to Trash');
  const trash = page.getByRole('dialog', { name: 'Move video to Trash', exact: true });
  await expect(trash.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused();
  await expect(trash).toContainText('2 direction revisions · 1 production revision');
  await trash.getByRole('button', { name: 'Move video to Trash', exact: true }).click();
  let saved = await load(request, project.id); const retained = saved.contents.find(item => item.id === original.id)!;
  expect(retained.trashed_at).toBeTruthy(); expect(retained.directions).toEqual(original.directions); expect(saved.packs).toEqual(project.packs);
  expect(saved.active_content_id).not.toBe(original.id);
  const selected = saved.active_content_id;
  await page.getByRole('button', { name: /^Trash \(/ }).click();
  expect((await load(request, project.id)).active_content_id).toBe(selected);
  await page.getByRole('button', { name: 'Restore video The planned Video', exact: true }).click();
  const restore = page.getByRole('dialog', { name: 'Restore video', exact: true });
  await restore.getByRole('button', { name: 'Restore', exact: true }).click();
  saved = await load(request, project.id);
  expect(saved.contents.find(item => item.id === original.id)?.trashed_at).toBeNull(); expect(saved.active_content_id).toBe(selected);
  expect(saved.packs).toEqual(project.packs);
  await page.getByRole('button', { name: 'Back to active plan', exact: true }).click();
  await video(page, original.id).getByRole('button', { name: original.title, exact: true }).click();
  await expect(page.getByRole('button', { name: 'Open Production', exact: true })).toBeVisible();
});

test('Series Trash previews kept videos and restores only unchanged standalone members', async ({ page, request }) => {
  const project = seed();
  await page.goto(`/?project=${project.id}`);
  await action(page, 'series', 'series_managed', 'Move series to Trash');
  const trash = page.getByRole('dialog', { name: 'Move series to Trash', exact: true });
  await expect(trash).toContainText('keep its 2 active videos as standalone');
  await expect(trash.getByText('The planned Video', { exact: true })).toBeVisible();
  await expect(trash.getByText('A second series Video', { exact: true })).toBeVisible();
  await expect(trash.getByText('Previously trashed Video', { exact: true })).toHaveCount(0);
  await trash.getByRole('button', { name: 'Keep videos and trash series', exact: true }).click();
  let saved = await load(request, project.id);
  expect(saved.series.find(item => item.id === 'series_managed')?.trashed_at).toBeTruthy();
  expect(saved.contents.find(item => item.id === 'content_active_video')?.series_id).toBeNull();
  expect(saved.contents.find(item => item.id === 'content_pretrashed')?.trashed_at).toBeTruthy();
  await move(page, 'content_active_video', 'series_other');
  const selected = (await load(request, project.id)).active_content_id;
  await page.getByRole('button', { name: /^Trash \(/ }).click();
  await page.getByRole('button', { name: 'Restore series Commuter tests', exact: true }).click();
  const restore = page.getByRole('dialog', { name: 'Restore series', exact: true });
  await expect(restore).toContainText('1 video below will rejoin');
  await expect(restore.getByText('A second series Video', { exact: true })).toBeVisible();
  await expect(restore.getByText('The planned Video', { exact: true })).toHaveCount(0);
  const restoredResponse = page.waitForResponse(response => response.request().method() === 'POST'
    && response.url().endsWith(`/api/projects/${project.id}/series/series_managed/restore`));
  await restore.getByRole('button', { name: 'Restore', exact: true }).click();
  expect((await restoredResponse).ok()).toBeTruthy();
  saved = await load(request, project.id);
  expect(saved.contents.find(item => item.id === 'content_active_video')?.series_id).toBe('series_other');
  expect(saved.contents.find(item => item.id === 'content_series_second')?.series_id).toBe('series_managed');
  expect(saved.contents.find(item => item.id === 'content_pretrashed')?.trashed_at).toBeTruthy();
  expect(saved.active_content_id).toBe(selected); expect(saved.packs).toEqual(project.packs); expect(saved.jobs).toEqual([]);
});

test('inline actions and native dialogs keep keyboard focus and fit narrow and short windows', async ({ page }) => {
  const project = seed(); await page.goto(`/?project=${project.id}`);
  const row = video(page, 'content_active_video');
  const trigger = row.getByRole('button', { name: 'Actions for The planned Video', exact: true });
  await trigger.focus(); await page.keyboard.press('Enter');
  await page.keyboard.press('Tab');
  await expect(row.getByRole('button', { name: 'Rename video', exact: true })).toBeFocused();
  await page.keyboard.press('Escape'); await expect(trigger).toBeFocused();
  await page.keyboard.press('Enter'); await page.keyboard.press('Tab'); await page.keyboard.press('Enter');
  const rename = page.getByRole('dialog', { name: 'Rename video', exact: true });
  await expect(rename.getByLabel('Name', { exact: true })).toBeFocused();
  await page.keyboard.press('Escape'); await expect(trigger).toBeFocused();
  for (const viewport of [{ width: 720, height: 450 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await action(page, 'video', 'content_active_video', 'Move video to Trash');
    const dialog = page.getByRole('dialog', { name: 'Move video to Trash', exact: true });
    await dialog.getByRole('button', { name: 'Move video to Trash', exact: true }).scrollIntoViewIfNeeded();
    await dialog.getByRole('button', { name: 'Move video to Trash', exact: true }).click({ trial: true });
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(trigger).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await screenshot(page, `content-plan-management-${viewport.width}.png`);
  }
  const library = page.locator('.va-planning-library');
  await library.locator(':scope > summary').click();
  await expect(page.getByLabel('Search videos and series', { exact: true })).not.toBeVisible();
  await expect(page.getByRole('heading', { name: 'The planned Video', exact: true })).toBeVisible();
  await library.locator(':scope > summary').click();
  await expect(page.getByLabel('Search videos and series', { exact: true })).toBeVisible();
});


test('restoring the last Video leaves an explicit choice in Content plan and Production', async ({ page, request }) => {
  const project = seed('single');
  await page.goto(`/?project=${project.id}`);
  await action(page, 'video', 'content_active_video', 'Move video to Trash');
  await page.getByRole('dialog', { name: 'Move video to Trash', exact: true }).getByRole('button', { name: 'Move video to Trash', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Start with one video', exact: true })).toBeVisible();
  expect((await load(request, project.id)).active_content_id).toBeNull();
  await page.getByRole('button', { name: /^Trash \(/ }).click();
  await page.getByRole('button', { name: 'Restore video The planned Video', exact: true }).click();
  await page.getByRole('dialog', { name: 'Restore video', exact: true }).getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Back to active plan', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Choose a video', exact: true })).toBeVisible();
  expect((await load(request, project.id)).active_content_id).toBeNull();
  await page.getByRole('button', { name: 'Production', exact: true }).click();
  await expect(page.getByLabel('Video', { exact: true })).toHaveValue('');
  await expect(page.getByRole('heading', { name: 'Legacy production documents', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Content plan', exact: true }).click();
  await video(page, 'content_active_video').getByRole('button', { name: 'The planned Video', exact: true }).click();
  await page.getByRole('button', { name: 'Open Production', exact: true }).click();
  await expect(page.getByLabel('Video', { exact: true })).toHaveValue('content_active_video');
  expect((await load(request, project.id)).packs).toEqual(project.packs);
});


test('busy generation and invalid creation errors stay inside native dialogs with entries retained', async ({ page, request }) => {
  const project = seed('busy');
  await page.goto(`/?project=${project.id}`);
  await action(page, 'video', 'content_active_video', 'Move video to Trash');
  const trash = page.getByRole('dialog', { name: 'Move video to Trash', exact: true });
  await trash.getByRole('button', { name: 'Move video to Trash', exact: true }).click();
  await expect(trash.getByRole('alert')).toContainText("Wait for this video's current operation before moving it to Trash.");
  await expect(trash).toContainText('The planned Video');
  await expect(trash).toBeVisible();
  await screenshot(page, 'content-plan-busy-trash-error.png');
  await expect(page.locator('.va-global-error')).toHaveCount(0);
  const unchanged = await load(request, project.id);
  expect(unchanged.contents[0].trashed_at).toBeNull(); expect(unchanged.active_content_id).toBe('content_active_video');
  expect(unchanged.packs).toEqual(project.packs);
  await trash.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Plan a video', exact: true }).click();
  const create = page.getByRole('dialog', { name: 'Plan a video', exact: true });
  await create.getByLabel('Title', { exact: true }).fill('   ');
  await create.getByLabel('Topic / creative starting point (optional)', { exact: true }).fill('A retained starting point.');
  await create.getByRole('button', { name: 'Create video', exact: true }).click();
  await expect(create.getByRole('alert')).toContainText('Enter a name between 1 and 200 characters.');
  await expect(create.getByLabel('Title', { exact: true })).toHaveValue('   ');
  await expect(create.getByLabel('Topic / creative starting point (optional)', { exact: true })).toHaveValue('A retained starting point.');
  await expect(page.locator('.va-global-error')).toHaveCount(0);
});


test('creative Series Trash requires input review while exact restoration recovers the original formal approval', async ({ page, request }) => {
  const project = seed('concept');
  const original = project.contents.find(item => item.id === 'content_active_video')!;
  const sheet = project.packs.at(-1)!;
  expect(original.directions).toHaveLength(2);
  expect(original.approved_direction_revision).toBe(2);
  expect(sheet.sheet_format).toBe('storyboard_sheet'); expect(sheet.shots).toHaveLength(1);
  const readiness = async () => (await request.get(`/api/projects/${project.id}/contents/${original.id}/readiness`)).json();
  const ready = await readiness(); expect(ready.direction_current).toBe(true);
  expect((await load(request, project.id)).version).toBe(project.version);
  const csvBefore = await request.get(`/api/projects/${project.id}/packs/${sheet.id}/export?revision=${sheet.revision}&format=csv`);
  expect(csvBefore.ok()).toBeTruthy(); const csv = await csvBefore.text();
  await page.goto(`/?project=${project.id}`);
  await action(page, 'series', 'series_managed', 'Move series to Trash');
  await page.getByRole('dialog', { name: 'Move series to Trash', exact: true }).getByRole('button', { name: 'Keep videos and trash series', exact: true }).click();
  let saved = await load(request, project.id);
  const stale = await readiness(); expect(stale.direction_current).toBe(false); expect(stale.code).toBe('direction_inputs_outdated');
  expect((await load(request, project.id)).version).toBe(saved.version);
  expect(saved.contents.find(item => item.id === original.id)?.directions).toEqual(original.directions);
  expect(saved.packs).toEqual(project.packs); expect(saved.jobs).toEqual([]);
  const direction = page.locator('.va-direction-card');
  await expect(direction.getByText('Needs review', { exact: true })).toBeVisible();
  await expect(direction.getByRole('button', { name: 'Approve direction', exact: true })).toBeDisabled();
  await expect(direction).toContainText('Edit and save a current direction revision');
  await direction.getByRole('button', { name: 'Open saved Production', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Storyboard sheet', exact: true })).toBeVisible();
  await expect(page.getByLabel('Shot 01 Visual / Action', { exact: true })).toHaveValue(sheet.shots[0].visual);
  await expect(page.getByRole('button', { name: 'Export sheet', exact: true })).toBeEnabled();
  await expect(page.getByRole('button', { name: /Generate (a new|storyboard) sheet/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Start a (new )?blank sheet/ })).toHaveCount(0);
  const csvDuring = await request.get(`/api/projects/${project.id}/packs/${sheet.id}/export?revision=${sheet.revision}&format=csv`);
  expect(csvDuring.ok()).toBeTruthy(); expect(await csvDuring.text()).toBe(csv);
  await page.getByRole('button', { name: 'Content plan', exact: true }).click();
  await page.getByRole('button', { name: /^Trash \(/ }).click();
  await page.getByRole('button', { name: 'Restore series Commuter tests', exact: true }).click();
  await page.getByRole('dialog', { name: 'Restore series', exact: true }).getByRole('button', { name: 'Restore', exact: true }).click();
  await page.getByRole('button', { name: 'Back to active plan', exact: true }).click();
  expect((await readiness()).direction_current).toBe(true);
  await expect(page.locator('.va-direction-card').getByText('Approved', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Open Production', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Generate a new sheet', exact: true })).toBeEnabled();
  saved = await load(request, project.id);
  const restored = saved.contents.find(item => item.id === original.id)!;
  expect(restored.approved_direction_id).toBe(original.approved_direction_id);
  expect(restored.approved_direction_revision).toBe(original.approved_direction_revision);
  expect(restored.directions).toEqual(original.directions); expect(saved.packs).toEqual(project.packs); expect(saved.jobs).toEqual([]);
  const csvAfter = await request.get(`/api/projects/${project.id}/packs/${sheet.id}/export?revision=${sheet.revision}&format=csv`);
  expect(csvAfter.ok()).toBeTruthy(); expect(await csvAfter.text()).toBe(csv);
});
