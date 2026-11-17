import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import type { Project } from '../src/project/contracts';

const root = resolve(import.meta.dirname, '../..');
let folder: string; let media: string;
const fixture = (): Project => JSON.parse(execFileSync(join(root, '.venv/bin/python'), [join(root, 'frontend/e2e/project-resources-183-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, media], { cwd: root, encoding: 'utf8' }));
async function open(page: Page, project: Project) {
  await page.goto(`/?project=${project.id}`);
  await page.getByRole('button', { name: 'Analysis', exact: true }).click();
  // The latest project report must be visible even while a planned Video with
  // no per-Video report remains selected for Production.
  await expect(page.getByLabel('Analysis scope', { exact: true })).toHaveValue('');
  await expect(page.getByRole('heading', { name: 'Key insights', exact: true })).toBeVisible();
}
async function capture(page: Page, name: string) {
  const path = process.env.VIDEO_ANATOMY_SCREENSHOT_DIR;
  if (path) { mkdirSync(path, { recursive: true }); await page.screenshot({ path: join(path, `${name}.png`), fullPage: false }); }
}
test.beforeAll(() => {
  folder = mkdtempSync(join(tmpdir(), 'video-anatomy-analysis-183-'));
  media = join(folder, 'synthetic-blue.mp4');
  execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=25:d=12', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', media]);
});
test.afterAll(() => rmSync(folder, { recursive: true, force: true }));

test('source-linked insights lead the report and a citation opens its exact historical evidence', async ({ page, request }) => {
  const project = fixture(); await open(page, project);
  const insights = page.getByRole('region', { name: 'Key insights', exact: true });
  await expect(insights).toContainText('Show the evidence before explaining.');
  await expect(insights).toContainText('Open with a visible demonstration.');
  await expect(page.getByText('Historical report context retained once.', { exact: true })).toBeHidden();
  const insightBounds = await insights.boundingBox();
  const graphBounds = await page.getByRole('heading', { name: 'Structure flow', exact: true }).boundingBox();
  expect(insightBounds!.y).toBeLessThan(graphBounds!.y);
  await expect(page.getByRole('heading', { name: 'Comparison', exact: true })).toBeVisible();
  const sources = project.analyses[0].key_insights[0].sources;
  await insights.getByRole('button', { name: /commute-demo.mp4 · Recorded sample/ }).click();
  await expect(page.getByLabel('Evidence revision', { exact: true })).toHaveValue(String(sources[0].evidence_revision));
  const evidence = page.getByRole('complementary', { name: 'Selected evidence', exact: true });
  await expect(evidence).toContainText('Historical observation 0');
  await expect(evidence).not.toContainText('Current corrected observation 0');
  const video = page.getByLabel('Reference video player');
  await expect.poll(async () => video.evaluate(node => (node as HTMLVideoElement).currentTime)).toBeGreaterThanOrEqual(1.99);
  expect((await (await request.get(`/api/projects/${project.id}`)).json()).active_content_id).toBe(project.active_content_id);
});

test('browsing report scopes never writes the selected production Video', async ({ page, request }) => {
  const project = fixture(); await open(page, project);
  const writes: unknown[] = [];
  page.on('request', call => {
    if (call.method() === 'PATCH' && call.url().endsWith(`/api/projects/${project.id}`) && Object.hasOwn(call.postDataJSON() ?? {}, 'active_content_id')) writes.push(call.postDataJSON());
  });
  await page.getByLabel('Analysis scope', { exact: true }).selectOption(project.contents[0].id);
  await expect(page.getByRole('heading', { name: 'A conclusion grounded in your references' })).toBeVisible();
  await page.getByLabel('Analysis scope', { exact: true }).selectOption('');
  await expect(page.getByRole('heading', { name: 'Key insights', exact: true })).toBeVisible();
  expect(writes).toEqual([]);
  const saved: Project = await (await request.get(`/api/projects/${project.id}`)).json();
  expect(saved.active_content_id).toBe(project.active_content_id);
});

test('using an insight creates reviewable inspiration without creating or approving a direction', async ({ page, request }) => {
  const project = fixture(); await open(page, project);
  const insight = project.analyses[0].key_insights[0];
  await page.getByRole('button', { name: 'Use insight in Content plan', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Reference inspiration', exact: true })).toBeVisible();
  await expect(page.getByText('It has not changed your direction or approved brief.', { exact: false })).toBeVisible();
  const saved: Project = await (await request.get(`/api/projects/${project.id}`)).json();
  expect(saved.editor_drafts['content-inspiration']).toEqual({ analysis_id: project.analyses[0].id, insight_id: insight.id, observation: insight.observation, application: insight.application, sources: insight.sources });
  expect(saved.editor_draft_versions['content-inspiration']).toBe(1);
  expect(saved.active_content_id).toBe(project.active_content_id);
  expect(saved.contents[0].directions).toEqual(project.contents[0].directions);
  expect(saved.contents[0].approved_direction_id).toBeNull();
  expect(saved.briefs).toEqual(project.briefs);
});

test('old unlinked findings stay readable without fabricated per-insight citations', async ({ page }) => {
  const project = fixture();
  await page.route(`**/api/projects/${project.id}`, async route => {
    if (route.request().method() !== 'GET') { await route.continue(); return; }
    const response = await route.fetch(); const state = await response.json();
    state.analyses[0].key_insights = [];
    await route.fulfill({ response, json: state });
  });
  await open(page, project);
  const insights = page.getByRole('region', { name: 'Key insights', exact: true });
  await expect(insights).toContainText('An unlinked legacy finding.');
  await expect(insights.locator('.va-sources')).toHaveCount(0);
  await expect(insights.getByRole('button', { name: 'Use insight in Content plan', exact: true })).toHaveCount(0);
  await page.getByText('Saved report context', { exact: true }).click();
  await expect(page.getByText('Historical report context retained once.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'View as list', exact: true }).click();
  const list = page.getByRole('list', { name: 'Structure as list', exact: true });
  await expect(list).toContainText('Make the test visible');
  await expect(list).toContainText('A saved interpretation of this exact sample.');
  await expect(list.getByRole('button', { name: /commute-demo.mp4 · Recorded sample/ })).toHaveCount(1);
});

test('graph kinds remain readable through hover, selection and keyboard focus with a list alternative', async ({ page }) => {
  const project = fixture();
  // Authored UI fixture exercises all semantic styles; it does not assert that
  // these mechanisms were produced by recognition or a live model.
  await page.route(`**/api/projects/${project.id}`, async route => {
    if (route.request().method() !== 'GET') { await route.continue(); return; }
    const response = await route.fetch(); const state = await response.json();
    const structure = state.analyses[0].structures[0]; const source = structure.nodes[0].sources;
    structure.nodes = ['observation', 'interpretation', 'source_claim', 'user_context'].map((kind, index) => ({ id: `style_${index}`, kind, label: `Readable ${kind}`, detail: `Saved ${kind} detail`, sources: source }));
    structure.edges = [{ source: 'style_0', target: 'style_1', label: 'supports interpretation', explanation: 'Authored edge for style validation.', sources: source }];
    await route.fulfill({ response, json: state });
  });
  await open(page, project);
  const graph = page.getByRole('region', { name: /Video logic graph/ });
  await graph.scrollIntoViewIfNeeded(); await graph.focus(); await page.keyboard.press('ArrowRight');
  const contrast = async (id: string) => page.locator(`[data-node-id="${id}"]`).evaluate(node => {
    const foreground = getComputedStyle(node.querySelector('strong')!).color.match(/[\d.]+/g)!.slice(0, 3).map(Number);
    const background = getComputedStyle(node).backgroundColor.match(/[\d.]+/g)!.slice(0, 3).map(Number);
    const luminance = (rgb: number[]) => rgb.map(value => value / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4).reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
    const first = luminance(foreground); const second = luminance(background);
    return (Math.max(first, second) + .05) / (Math.min(first, second) + .05);
  });
  for (const id of ['style_0', 'style_1', 'style_2', 'style_3']) {
    const node = page.locator(`[data-node-id="${id}"]`);
    expect(await contrast(id)).toBeGreaterThanOrEqual(4.5);
    await node.hover(); expect(await contrast(id)).toBeGreaterThanOrEqual(4.5);
    await node.click(); await expect(node).toHaveAttribute('aria-pressed', 'true');
    await node.focus(); await expect(node).toBeFocused(); expect(await contrast(id)).toBeGreaterThanOrEqual(4.5);
  }
  await page.getByRole('button', { name: 'View as list', exact: true }).click();
  await expect(page.getByRole('list', { name: 'Structure as list', exact: true }).getByRole('listitem')).toHaveCount(4);
  await page.getByRole('button', { name: 'View as graph', exact: true }).click();
  await expect(graph).toBeVisible();
  await capture(page, 'analysis-183-readable-graph');
});

for (const [width, height] of [[1440, 900], [1280, 800], [390, 844], [720, 450]]) test(`insights and graph stay within their container at ${width}x${height}`, async ({ page }) => {
  const project = fixture(); await page.setViewportSize({ width, height }); await open(page, project);
  await expect(page.getByRole('region', { name: 'Key insights', exact: true })).toBeVisible();
  const graph = page.getByRole('region', { name: /Video logic graph/ });
  await graph.scrollIntoViewIfNeeded(); await graph.focus(); await page.keyboard.press('ArrowRight');
  await page.getByRole('button', { name: 'View as list', exact: true }).click();
  await expect(page.getByRole('list', { name: 'Structure as list', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
  await capture(page, `analysis-183-${width}x${height}`);
});
