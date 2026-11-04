import { expect, test, type APIRequestContext } from '@playwright/test';
import type { TaskState } from '../src/generated/contracts';

async function sampleTask(api: APIRequestContext, title: string) {
  const create = await api.post('/api/tasks', { data: { title } });
  expect(create.ok()).toBeTruthy();
  const initial: TaskState = await create.json();
  const sample = await api.post(`/api/tasks/${initial.task.task_id}/sample`, { data: { expected_version: initial.task.version } });
  expect(sample.ok(), await sample.text()).toBeTruthy();
  return await sample.json() as TaskState;
}

test('research scrolls within its reader and Structure analyzes without a separate Timeline step', async ({ page, request }) => {
  const state = await sampleTask(request, 'Structure workspace smoke');
  await page.addInitScript((id) => localStorage.setItem('video-anatomy-task', id), state.task.task_id);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: state.task.title, exact: true })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Workspaces' }).getByRole('button', { name: 'Ideas', exact: true })).toBeEnabled();
  await page.getByRole('tab', { name: 'Structure', exact: true }).click();
  await page.getByRole('button', { name: 'Analyze structure', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Video logic graph.', exact: false })).toBeVisible();
  await expect(page.locator('.logic-node')).toHaveCount(3);
  await expect(page.getByText('Fictional sample', { exact: true }).last()).toBeVisible();
  const heights = await page.evaluate(() => ({ body: document.body.scrollHeight, viewport: window.innerHeight }));
  expect(heights.body).toBeLessThanOrEqual(heights.viewport);
  await expect(page.getByRole('complementary', { name: 'Selected structure node' })).toHaveCount(0);
  await page.locator('.logic-node').last().click();
  await expect(page.getByRole('complementary', { name: 'Selected structure node' }).getByText('Inference', { exact: true })).toBeVisible();
  await expect(page.getByText('An interpretation of the available evidence, not a verified intent or measured effect.')).toHaveCount(0);
  await page.getByRole('button', { name: 'Close details', exact: true }).click();
  await page.getByRole('button', { name: /Transferable methods/ }).click();
  await page.locator('.method-choice input').check();
  await page.getByRole('button', { name: 'Use in Ideas · 1', exact: true }).click();
  await expect(page.locator('#area-directions')).toBeVisible();
  const handoff = await (await request.get(`/api/tasks/${state.task.task_id}/structure/handoff`)).json();
  expect(handoff.methods).toHaveLength(1);
  expect(handoff.nodes.length).toBeGreaterThan(0);
  expect(handoff.analysis_ref.id).toBeTruthy();
  await page.getByRole('button', { name: 'Research', exact: true }).click();
  await expect(page.getByRole('tab', { name: 'Structure', exact: true })).toHaveAttribute('aria-selected', 'true');
  await page.reload();
  await expect(page.getByRole('tab', { name: 'Structure', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('.method-choice input')).toBeChecked();
  await page.setViewportSize({ width: 1440, height: 900 });
  expect(await page.evaluate(() => document.body.scrollHeight <= innerHeight)).toBe(true);
  await page.getByRole('button', { name: 'Logic map', exact: true }).click();
  await page.screenshot({ path: test.info().outputPath('workspace-structure.png') });
  await page.setViewportSize({ width: 1024, height: 800 });
  expect(await page.evaluate(() => document.body.scrollHeight <= innerHeight && document.body.scrollWidth <= innerWidth)).toBe(true);
});

test('Structure failures stay local and never prevent project or workspace navigation', async ({ page, request }) => {
  const state = await sampleTask(request, 'Research failure source');
  const otherResponse = await request.post('/api/tasks', { data: { title: 'Research failure destination' } });
  const other: TaskState = await otherResponse.json();
  await page.addInitScript((id) => localStorage.setItem('video-anatomy-task', id), state.task.task_id);
  await page.route(`**/api/tasks/${state.task.task_id}/structure/analyze`, (route) => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: { code: 'research_unavailable', message: 'Research service is temporarily unavailable.' } }) }));
  await page.goto('/');
  await page.getByRole('tab', { name: 'Structure', exact: true }).click();
  await page.getByRole('button', { name: 'Analyze structure', exact: true }).click();
  await expect(page.locator('.structure-workspace').getByRole('alert')).toContainText('Research service is temporarily unavailable.');
  await page.getByRole('button', { name: 'Production', exact: true }).click();
  await expect(page.locator('#area-production')).toBeVisible();
  await page.getByRole('complementary', { name: 'Saved tasks' }).getByRole('button', { name: new RegExp(other.task.title) }).click();
  await expect(page.getByRole('heading', { name: other.task.title, exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Ideas', exact: true }).click();
  await expect(page.locator('#area-directions')).toBeVisible();
});

test('context opens as a focused drawer and retains a draft when switching workspaces', async ({ page, request }) => {
  const created = await request.post('/api/tasks', { data: { title: 'Independent context drawer' } });
  const state: TaskState = await created.json();
  await page.addInitScript((id) => localStorage.setItem('video-anatomy-task', id), state.task.task_id);
  await page.goto('/');
  await page.getByRole('button', { name: 'Project context', exact: true }).click();
  const drawer = page.getByRole('dialog', { name: 'Project context' });
  await expect(drawer).toBeVisible();
  await drawer.getByRole('button', { name: 'Edit brand & product', exact: true }).click();
  await drawer.getByLabel('Brand/company', { exact: true }).fill('Retained brand');
  await page.getByRole('button', { name: 'Close context', exact: true }).click();
  await expect(drawer).not.toBeVisible();
  await page.getByRole('button', { name: 'Ideas', exact: true }).click();
  await page.getByRole('button', { name: /^Project context/ }).click();
  await expect(drawer.getByLabel('Brand/company', { exact: true })).toHaveValue('Retained brand');
  await page.keyboard.press('Escape');
  await expect(drawer).not.toBeVisible();
});

test('an original idea can be written and approved without a reference analysis', async ({ page, request }) => {
  let state = await sampleTask(request, 'Original idea without reference');
  const removed = await request.post(`/api/tasks/${state.task.task_id}/videos/${state.task.current_video_id}/delete`, { data: { expected_version: state.task.version } });
  expect(removed.ok(), await removed.text()).toBeTruthy();
  state = await removed.json();
  const language = await request.post(`/api/tasks/${state.task.task_id}/language`, { data: { expected_version: state.task.version, generation_language: 'English' } });
  expect(language.ok()).toBeTruthy(); state = await language.json();
  await page.addInitScript((id) => { localStorage.setItem('video-anatomy-task', id); localStorage.setItem(`video-anatomy-area:${id}`, 'directions'); }, state.task.task_id);
  await page.goto('/');
  const notebook = page.locator('.idea-notebook');
  await notebook.getByLabel('Idea', { exact: true }).fill('An everyday pause with LumaCup');
  await notebook.getByLabel('Opening', { exact: true }).fill('A busy desk, then a quiet sip.');
  await notebook.getByLabel('Story', { exact: true }).fill('Show one person making space for a moment between meetings.');
  await notebook.getByLabel('Call to action', { exact: true }).fill('Choose your next quiet moment.');
  await page.getByRole('button', { name: 'Research', exact: true }).click();
  await page.getByRole('button', { name: 'Ideas', exact: true }).click();
  await expect(notebook.getByLabel('Idea', { exact: true })).toHaveValue('An everyday pause with LumaCup');
  await notebook.getByRole('button', { name: 'Use as a direction', exact: true }).click();
  const card = page.getByRole('article', { name: 'Direction A', exact: true });
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: 'Approve this direction', exact: true }).click();
  await expect(card.getByRole('button', { name: 'Approve this direction', exact: true })).toBeDisabled();
  const saved: TaskState = await (await request.get(`/api/tasks/${state.task.task_id}`)).json();
  expect(saved.task.current_analysis).toBeNull();
  expect(saved.directions.at(-1)?.analysis_ref).toBeNull();
  expect(saved.directions.at(-1)?.evidence).toEqual([]);
  expect(saved.task.selected_direction).not.toBeNull();
  await page.getByRole('button', { name: 'Production', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Generate production materials', exact: true })).toBeEnabled();
});

test('video processing does not block saving and approving an independent original idea', async ({ page, request }) => {
  let state = await sampleTask(request, 'Concurrent research and ideas');
  const language = await request.post(`/api/tasks/${state.task.task_id}/language`, { data: { expected_version: state.task.version, generation_language: 'English' } });
  expect(language.ok()).toBeTruthy(); state = await language.json();
  await page.addInitScript((id) => localStorage.setItem('video-anatomy-task', id), state.task.task_id);
  let releaseRecognition: () => void = () => {};
  const deferred = new Promise<void>((resolve) => { releaseRecognition = resolve; });
  let held = false;
  let responseReady: () => void = () => {};
  const responsePending = new Promise<void>((resolve) => { responseReady = resolve; });
  await page.route(`**/api/tasks/${state.task.task_id}/operations**`, async (route) => {
    const response = await route.fetch();
    const ticket = await response.json();
    if (ticket.operation === 'recognize' && ticket.status === 'succeeded' && !held) {
      held = true; responseReady(); await deferred;
    }
    await route.fulfill({ response });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Run sample analysis', exact: true }).click();
  await responsePending;
  await expect(page.getByRole('button', { name: /Activity · 1 running/ })).toBeVisible();
  await page.getByRole('button', { name: 'Ideas', exact: true }).click();
  const notebook = page.locator('.idea-notebook');
  await notebook.getByLabel('Idea', { exact: true }).fill('A quieter pause');
  await notebook.getByLabel('Opening', { exact: true }).fill('One cup beside a notebook.');
  await notebook.getByLabel('Story', { exact: true }).fill('A person closes their laptop and takes a short break.');
  await notebook.getByLabel('Call to action', { exact: true }).fill('Make a moment for yourself.');
  await notebook.getByRole('button', { name: 'Use as a direction', exact: true }).click();
  const card = page.getByRole('article', { name: 'Direction A', exact: true });
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: 'Approve this direction', exact: true }).click();
  await expect(card.getByRole('button', { name: 'Approve this direction', exact: true })).toBeDisabled();
  await expect.poll(async () => (await (await request.get(`/api/tasks/${state.task.task_id}`)).json()).task.selected_direction).not.toBeNull();
  const during: TaskState = await (await request.get(`/api/tasks/${state.task.task_id}`)).json();
  expect(during.task.selected_direction).not.toBeNull();
  expect(during.task.current_analysis).not.toBeNull();
  releaseRecognition();
  await expect(page.getByRole('button', { name: /Activity · 1 running/ })).toHaveCount(0);
  expect((await (await request.get(`/api/tasks/${state.task.task_id}`)).json()).task.selected_direction).not.toBeNull();
  await expect(page.getByRole('alert')).toHaveCount(0);
});
