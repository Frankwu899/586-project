import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import type { Project } from '../src/project/contracts';

test.afterEach(async ({ context }) => {
  // Drain intercepted polling requests before Playwright closes their contexts.
  for (const page of context.pages()) await page.unrouteAll({ behavior: 'wait' });
});

const root = resolve(import.meta.dirname, '../..');
let folder: string;
let media: string;
const fixture = (): Project => JSON.parse(execFileSync(join(root, '.venv/bin/python'), [join(root, 'frontend/e2e/project-resources-183-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, media], { cwd: root, encoding: 'utf8' }));

async function report(page: Page, project: Project, update: (state: Project) => void) {
  await page.route(`**/api/projects/${project.id}`, async route => {
    if (route.request().method() !== 'GET') { await route.continue(); return; }
    const response = await route.fetch();
    const state = await response.json();
    update(state);
    await route.fulfill({ response, json: state });
  });
  await page.goto(`/?project=${project.id}`);
  await page.getByRole('button', { name: 'Analysis', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Key insights', exact: true })).toBeVisible();
}

test.beforeAll(() => {
  folder = mkdtempSync(join(tmpdir(), 'video-anatomy-analysis-185-'));
  media = join(folder, 'synthetic.mp4');
  execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=25:d=12', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', media]);
});
test.afterAll(() => rmSync(folder, { recursive: true, force: true }));

test('compact report keeps limits visible and expands exact observations and graphs on request', async ({ page }) => {
  const project = fixture();
  const completeLimit = 'Sparse samples cover isolated moments only. '.repeat(18)
    + 'Required condition: no audience response or outcome has been observed.';
  await report(page, project, state => {
    const saved = state.analyses[0];
    saved.report_version = '1.8.5';
    saved.key_insights[0] = { ...saved.key_insights[0], title: 'Demonstrate first', scope: 'observation', support_resource_ids: [state.resources[0].id], observation: 'The sample shows the test before its explanation, within a sparse visual sample only.', application: 'Open with a visible demonstration, if the new product can show equivalent evidence.' };
    saved.structures[0] = { ...saved.structures[0], method: 'Visible demonstration', flow: 'Test → explanation', borrowable: 'Show the evidence before describing it.' };
    saved.structures.push({ ...saved.structures[0], resource_id: state.resources[1].id, method: 'Routine contrast', flow: 'Routine → contrast', borrowable: 'Compare a familiar moment with a supported alternative.', nodes: [], edges: [] });
    saved.limitations = ['Only sampled visuals are supported. Audio and the closing CTA are unknown.', completeLimit];
  });
  await expect(page.getByRole('heading', { name: 'Demonstrate first', exact: true })).toBeVisible();
  await expect(page.getByText('Open with a visible demonstration, if the new product can show equivalent evidence.', { exact: true })).toBeVisible();
  await expect(page.getByText('Only sampled visuals are supported. Audio and the closing CTA are unknown.', { exact: true })).toBeVisible();
  await expect(page.getByText(completeLimit, { exact: true })).toBeVisible();
  const summary = page.getByRole('table', { name: 'Structure summary', exact: true });
  await expect(summary.getByRole('row')).toHaveCount(3);
  await expect(summary).toContainText('Visible demonstration');
  await expect(summary).toContainText('Test → explanation');
  await expect(summary).toContainText('Routine contrast');
  await expect(page.getByRole('region', { name: /Video logic graph/ })).toBeHidden();
  await expect(page.getByText('The sample shows the test before its explanation, within a sparse visual sample only.', { exact: true })).toBeHidden();
  await page.getByText('Observation and support', { exact: true }).click();
  await expect(page.getByText('The sample shows the test before its explanation, within a sparse visual sample only.', { exact: true })).toBeVisible();
  await page.getByText('Detailed structures and comparison', { exact: true }).click();
  await expect(page.getByRole('region', { name: /Video logic graph/ })).toBeVisible();
});

test('commonality states distinct-video support while a single-source insight stays an observation', async ({ page }) => {
  const project = fixture();
  await report(page, project, state => {
    const saved = state.analyses[0]; const first = saved.key_insights[0];
    saved.report_version = '1.8.5';
    const secondSource = { ...first.sources[0], resource_id: state.resources[1].id, event_id: 'visual_1', excerpt: 'Historical observation 1' };
    saved.key_insights = [
      { ...first, id: 'common', title: 'Show a test', scope: 'commonality', support_resource_ids: state.resources.map((item: { id: string }) => item.id), sources: [...first.sources, secondSource] },
      { ...first, id: 'single', title: 'One source only', observation: 'A single reference shows a routine.', application: 'Consider this routine only when relevant.', scope: 'observation', support_resource_ids: [state.resources[0].id] },
    ];
  });
  const insights = page.getByRole('region', { name: 'Key insights', exact: true });
  await expect(insights.getByText('Commonality · 2 of 2 videos', { exact: true })).toBeVisible();
  await expect(insights.getByText('Single-video observation · 1 of 2 videos', { exact: true })).toBeVisible();
  await expect(insights.getByRole('heading', { name: 'One source only', exact: true })).toBeVisible();
  await insights.getByRole('button', { name: /commute-demo.mp4 · Recorded sample/ }).first().click();
  await expect(page.getByLabel('Evidence revision', { exact: true })).toHaveValue('1');
  await expect(page.getByRole('complementary', { name: 'Selected evidence', exact: true })).toContainText('Historical observation 0');
});

test('legacy reports preserve every saved insight and leave absent structure fields unknown', async ({ page }) => {
  const project = fixture();
  await report(page, project, state => {
    const saved = state.analyses[0];
    saved.key_insights = Array.from({ length: 6 }, (_, index) => ({ ...saved.key_insights[0], id: `legacy_${index}`, observation: `Saved observation ${index + 1}`, application: `Saved condition ${index + 1}` }));
    saved.limitations = ['The legacy report did not record per-video analysis provenance.'];
  });
  await expect(page.getByRole('heading', { name: 'Saved observation 6', exact: true })).toBeVisible();
  const summary = page.getByRole('table', { name: 'Structure summary', exact: true });
  await expect(summary.getByRole('row')).toHaveCount(3);
  await expect(summary).toContainText('Recorded structure interpretation');
  await expect(summary).toContainText('Not recorded');
  await expect(page.getByText('The legacy report did not record per-video analysis provenance.', { exact: true })).toBeVisible();
});

for (const missing of ['identity', 'time range']) test(`citations missing ${missing} cannot turn an insight into a verified commonality`, async ({ page }) => {
  const project = fixture();
  await report(page, project, state => {
    const saved = state.analyses[0]; const insight = saved.key_insights[0];
    saved.report_version = '1.8.5';
    Object.assign(insight, { title: 'Check recorded support', scope: 'commonality', support_resource_ids: state.resources.map(item => item.id) });
    insight.sources.push({ ...insight.sources[0], resource_id: state.resources[1].id, ...(missing === 'identity' ? { evidence_revision: null, event_id: null } : { event_id: 'visual_1', start_seconds: null, end_seconds: null }) });
  });
  const insights = page.getByRole('region', { name: 'Key insights', exact: true });
  await expect(insights.getByText('Single-video observation · 1 of 2 videos', { exact: true })).toBeVisible();
  await expect(insights.getByText('Commonality · 2 of 2 videos', { exact: true })).toHaveCount(0);
  await insights.getByText('Observation and support', { exact: true }).click();
  await expect(insights).toContainText('lacks linked support from two different videos');
});

test('consolidating repeated insight wording preserves the exact support from both videos', async ({ page }) => {
  const project = fixture();
  await report(page, project, state => {
    const saved = state.analyses[0]; const first = saved.key_insights[0];
    saved.report_version = '1.8.5';
    Object.assign(first, { title: 'A repeated observation', scope: 'observation' });
    saved.key_insights.push({ ...first, id: 'duplicate_wording', sources: [{ ...first.sources[0], resource_id: state.resources[1].id, event_id: 'visual_1', excerpt: 'Historical observation 1' }] });
  });
  const insights = page.getByRole('region', { name: 'Key insights', exact: true });
  await expect(insights.getByRole('heading', { name: 'A repeated observation', exact: true })).toHaveCount(1);
  await expect(insights.getByRole('button', { name: /commute-demo.mp4 · Recorded sample/ })).toHaveCount(1);
  await expect(insights.getByRole('button', { name: /desk-routine.mp4 · Recorded sample/ })).toHaveCount(1);
  await expect(insights.getByText('Commonality · 2 of 2 videos', { exact: true })).toHaveCount(0);
});

test('production requirements are visible before direction approval without blocking a manual direction', async ({ page, request }) => {
  const project = fixture(); const content = project.contents[0];
  const draft = await request.post(`/api/projects/${project.id}/brief/draft`, { data: { expected_version: project.version, expected_draft_version: project.brief_draft_version, facts: [{ key: 'assignment', value: 'Introduce a user-authored everyday routine.', origin: 'manual', status: 'confirmed' }] } });
  expect(draft.ok()).toBeTruthy();
  const drafted: Project = await draft.json();
  const applied = await request.post(`/api/projects/${project.id}/brief/apply`, { data: { expected_version: drafted.version, expected_draft_version: drafted.brief_draft_version, facts: drafted.brief_draft } });
  expect(applied.ok()).toBeTruthy();
  const confirmed: Project = await applied.json();
  const created = await request.post(`/api/projects/${project.id}/contents/${content.id}/directions`, { data: { expected_version: confirmed.version, title: 'Untimed manual direction', concept: 'A user-authored concept.' } });
  expect(created.ok()).toBeTruthy();
  await page.route(`**/api/projects/${project.id}/contents/${content.id}/readiness`, async route => {
    const response = await route.fetch(); const saved = await response.json();
    await route.fulfill({ response, json: { ...saved, production_ready: false, production_requirements: ['Confirm one target duration before generating a timed production plan.'] } });
  });
  await page.goto(`/?project=${project.id}`);
  await page.getByRole('button', { name: 'Content plan', exact: true }).click();
  await expect(page.getByText('Confirm one target duration before generating a timed production plan.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve direction', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Approve direction', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Open Production', exact: true })).toBeVisible();
});
