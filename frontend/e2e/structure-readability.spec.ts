import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import type { TaskState } from '../src/generated/contracts';
import type { StructureGraph, StructureState } from '../src/structureApi';

async function fixture(page: Page, api: APIRequestContext, cyclic = false) {
  let state: TaskState = await (await api.post('/api/tasks', { data: { title: 'Synthetic graph readability fixture' } })).json();
  for (const path of ['/sample', '/recognize']) {
    const response = await api.post(`/api/tasks/${state.task.task_id}${path}`, { data: { expected_version: state.task.version } });
    expect(response.ok(), await response.text()).toBeTruthy(); state = await response.json();
  }
  const graph: StructureGraph = {
    title: 'Synthetic relationships', summary: 'Synthetic UI fixture, not model output.', methods: [], research_gaps: [],
    nodes: Array.from({ length: cyclic ? 20 : 7 }, (_, index) => ({ id: `node-${index}`, label: index === 1 ? 'A deliberately long observation whose full title must remain readable without its own scrollbar' : `Observation ${index + 1}`, explanation: `Synthetic explanation for observation ${index + 1}.`, kind: index % 2 ? 'inference' : 'observation', event_ids: [], source_ids: [], context_ids: [], moments: [] })),
    edges: [],
  };
  for (let index = 1; index < graph.nodes.length; index++) graph.edges.push({ id: `edge-${index}`, from_node: graph.nodes[index - 1].id, to_node: graph.nodes[index].id, relation: index % 2 ? 'The visible demonstration provides concrete support for this attributed product claim' : '这些可见细节解释产品主张与演示之间的具体关系', explanation: 'A synthetic explanatory connection.' });
  if (cyclic) {
    graph.edges.push({ id: 'cycle', from_node: 'node-19', to_node: 'node-0', relation: 'Returns to the original question', explanation: 'Synthetic cycle.' });
    for (let index = 2; index < 12; index++) graph.edges.push({ id: `cross-${index}`, from_node: 'node-0', to_node: `node-${index}`, relation: 'Supplies context for a later claim', explanation: 'Synthetic long connection.' });
  }
  const result: StructureState = { output_language: 'English', structure_id: 'readability-fixture', task_id: state.task.task_id, video_id: state.task.current_video_id!, analysis_ref: state.task.current_analysis!, version: 1, graph_revision: 1, status: 'ready', origin: 'sample', graph, sources: [], contexts: [], proposals: [], answers: [], feedback_status: 'idle', error: null, research_note: null, outdated: false, source_deleted: false, created_at: '2026-11-03T00:00:00Z', updated_at: '2026-11-03T00:00:00Z' };
  await page.route(`**/api/tasks/${state.task.task_id}/structure`, route => route.fulfill({ json: result }));
  await page.addInitScript(id => localStorage.setItem('video-anatomy-task', id), state.task.task_id);
  await page.goto('/');
  await page.getByRole('tab', { name: 'Structure', exact: true }).click();
  await expect(page.locator('.logic-node')).toHaveCount(graph.nodes.length);
  return graph;
}

test('full relationship labels, readable Fit, navigation and resizable details survive desktop resize', async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const graph = await fixture(page, request);
  await expect(page.locator('.structure-inspector')).toHaveCount(0);
  const labels = page.locator('.logic-edge-label');
  for (let index = 0; index < graph.edges.length; index++) {
    expect((await labels.nth(index).innerText()).replace(/\s/gu, '')).toBe(graph.edges[index].relation.replace(/\s/gu, ''));
    expect(await labels.nth(index).evaluate(element => getComputedStyle(element).fontSize)).toBe('14px');
  }
  await page.getByRole('button', { name: 'Zoom out', exact: true }).click();
  await expect(page.locator('.logic-zoom')).toHaveText('90%');
  await page.getByRole('button', { name: 'Fit', exact: true }).click();
  await expect(page.locator('.logic-zoom')).toHaveText('100%');
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  await page.locator('.logic-node').first().click();
  const inspector = page.getByRole('complementary', { name: 'Selected structure node' });
  await expect(inspector).toBeVisible();
  const grip = page.getByRole('separator', { name: 'Resize node details' });
  await grip.focus(); await page.keyboard.press('ArrowLeft');
  await expect(grip).toHaveAttribute('aria-valuenow', '360');
  await page.setViewportSize({ width: 1024, height: 768 });
  await expect(page.locator('.logic-zoom')).toHaveText('110%');
  await expect(page.locator('.logic-node').first()).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Close details', exact: true }).click();
  await expect(page.locator('.logic-node').first()).toBeFocused();
  const canvas = page.locator('.logic-viewport');
  await canvas.focus();
  const before = await canvas.evaluate(element => element.scrollLeft);
  await page.keyboard.press('ArrowRight');
  await expect.poll(() => canvas.evaluate(element => element.scrollLeft)).toBeGreaterThan(before);
  await page.getByRole('button', { name: 'Reset view', exact: true }).click();
  await expect(page.locator('.logic-zoom')).toHaveText('100%');
  await page.locator('.logic-relationships summary').click();
  await expect(page.locator('.logic-relationships li')).toHaveCount(graph.edges.length);
  await expect(page.locator('.logic-relationships li').first()).toContainText(graph.edges[0].relation);
  expect(await page.evaluate(() => document.body.scrollWidth <= innerWidth)).toBe(true);
});

test('maximum cyclic graph stays readable on a narrow screen and details close with Escape', async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const graph = await fixture(page, request, true);
  await expect(page.locator('.logic-edge-label')).toHaveCount(30);
  await page.getByRole('button', { name: 'Fit', exact: true }).click();
  await expect(page.locator('.logic-zoom')).toHaveText('100%');
  await page.locator('.logic-node').nth(1).click();
  const dialog = page.getByRole('dialog', { name: 'Selected structure node' });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText(graph.nodes[1].label);
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(page.locator('.logic-node').nth(1)).toBeFocused();
  await page.locator('.logic-relationships summary').click();
  await expect(page.locator('.logic-relationships li')).toHaveCount(30);
  await page.locator('.logic-relationships li').last().scrollIntoViewIfNeeded();
  await expect(page.locator('.logic-relationships li').last()).toBeVisible();
  expect(await page.evaluate(() => document.body.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath('structure-narrow.png') });
});
