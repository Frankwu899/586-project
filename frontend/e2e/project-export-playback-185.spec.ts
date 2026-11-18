import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { Project } from '../src/project/contracts';

const root = resolve(import.meta.dirname, '../..');
const fixture = (mode: string, media = ''): Project => JSON.parse(execFileSync(join(root, '.venv/bin/python'), [join(root, 'frontend/e2e/project-export-playback-185-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, mode, media], { cwd: root, encoding: 'utf8' }));

test('saved historical shot rows render, escape and paginate as an actual printable table', async ({ page }, testInfo) => {
  const project = fixture('export');
  await page.goto(`/api/projects/${project.id}/packs/pack_print/export?revision=1&format=html`);
  await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByRole('row')).toHaveCount(37);
  await expect(page.getByText('Status: Historical revision', { exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'Marker01\n第一行\n第二行 | literal <card>', exact: true })).toBeVisible();
  expect(await page.evaluate(() => 'badExport' in window)).toBeFalsy();
  await expect(page.locator('body')).not.toContainText('obsolete mirrored storyboard');
  await expect(page.locator('body')).not.toContainText('Human-edited r2');
  await expect(page.getByRole('cell', { name: /source_a \/ event_original \/ evidence revision 3/ }).first()).toContainText('1.25s–2.5s');
  await page.emulateMedia({ media: 'print' });
  expect(await page.locator('table').evaluate(table => table.scrollWidth <= table.clientWidth)).toBeTruthy();
  const output = testInfo.outputPath('saved-r1-multipage.pdf');
  await page.pdf({ path: output, printBackground: true, preferCSSPageSize: true });
  const pages: string[] = JSON.parse(execFileSync(join(root, '.venv/bin/python'), ['-c', 'import json,sys; from pypdf import PdfReader; print(json.dumps([p.extract_text() for p in PdfReader(sys.argv[1]).pages]))', output], { cwd: root, encoding: 'utf8' }));
  expect(pages.length).toBeGreaterThan(2);
  const text = pages.join('\n');
  for (let index = 1; index <= 36; index++) expect(text.split(`Marker${String(index).padStart(2, '0')}`).length - 1).toBe(1);
  const sheetPages = pages.filter(text => /Marker\d/.test(text));
  expect(sheetPages.length).toBeGreaterThan(1);
  for (const text of sheetPages) expect(text).toContain('Framing / Camera');
  expect(text).not.toContain('Human-edited r2');
});

test('corrupt cached preview rebuilds and supports play, pause, historical seek and exact-original relink', async ({ page, request }) => {
  const folder = mkdtempSync(join(tmpdir(), 'video-anatomy-185-playback-'));
  try {
    const original = join(folder, 'original.mov');
    execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=10:d=8', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', original]);
    const project = fixture('playback', original);
    await page.goto(`/?project=${project.id}`);
    await page.getByRole('button', { name: 'Resources', exact: true }).click();
    await page.getByRole('button', { name: 'Focus cache-recovery.mov', exact: true }).click();
    await page.getByRole('button', { name: 'Open in timeline', exact: true }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'Playback is unavailable' })).toBeVisible();
    await page.getByText('Coverage, original file and recovery', { exact: true }).click();
    await page.getByRole('button', { name: 'Rebuild media preview', exact: true }).click();
    const media = page.getByLabel('Reference video player');
    await expect.poll(() => media.evaluate(node => (node as HTMLVideoElement).readyState)).toBeGreaterThanOrEqual(1);
    await expect(page.getByRole('alert').filter({ hasText: 'Playback is unavailable' })).toHaveCount(0);
    await media.evaluate(async node => { const video = node as HTMLVideoElement; video.muted = true; await video.play(); });
    await expect.poll(() => media.evaluate(node => (node as HTMLVideoElement).currentTime)).toBeGreaterThan(0.1);
    await media.evaluate(node => (node as HTMLVideoElement).pause());
    expect(await media.evaluate(node => (node as HTMLVideoElement).paused)).toBeTruthy();
    await page.getByLabel('Evidence revision', { exact: true }).selectOption('1');
    await page.getByRole('button', { name: /Visual observations at 00:02.*Historical blue sample/ }).click();
    await expect.poll(() => media.evaluate(node => (node as HTMLVideoElement).currentTime)).toBeGreaterThanOrEqual(2);
    await expect(page.getByText('Historical blue sample', { exact: true }).first()).toBeVisible();
    const beforeRelink = await media.getAttribute('src');
    const relinkResponse = page.waitForResponse(response => response.url().endsWith('/relink') && response.request().method() === 'POST');
    const chooser = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: 'Relink original', exact: true }).click();
    await (await chooser).setFiles({ name: 'original.mov', mimeType: 'video/quicktime', buffer: readFileSync(original) });
    expect((await relinkResponse).ok()).toBeTruthy();
    await expect.poll(() => media.getAttribute('src')).not.toBe(beforeRelink);
    await expect.poll(() => media.evaluate(node => (node as HTMLVideoElement).readyState)).toBeGreaterThanOrEqual(1);
    const saved: Project = await (await request.get(`/api/projects/${project.id}`)).json();
    expect(saved.resources[0].evidence).toEqual(project.resources[0].evidence);
    expect(saved.resources[0].sha256).toBe(project.resources[0].sha256);
    expect(saved.jobs.filter(job => job.kind !== 'extract')).toEqual([]);
  } finally { rmSync(folder, { recursive: true, force: true }); }
});
