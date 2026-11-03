import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import type { TaskState } from '../src/generated/contracts';

test('an old untranscribed analysis offers speech recovery without claiming transcription is disabled', async ({ page, request }) => {
  const state = await sample(request);
  const previous = structuredClone(state);
  previous.analyses[0].coverage.speech = 'not_analyzed';
  let retried = false;
  await page.route('**/api/tasks', async (route) => {
    const response = await route.fetch(); const saved: TaskState[] = await response.json();
    await route.fulfill({ response, json: saved.map((item) => item.task.task_id === state.task.task_id ? previous : item) });
  });
  await page.route(`**/api/tasks/${state.task.task_id}`, async (route) => route.fulfill({ json: retried ? state : previous }));
  await page.route(`**/api/tasks/${state.task.task_id}/operations`, async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    expect(route.request().postDataJSON().operation).toBe('recognize');
    retried = true;
    await route.fulfill({ json: { operation_id: 'speech-recovery-fixture', status: 'succeeded', error: null, result: state } });
  });
  await open(page, previous);
  await expect(page.locator('.analysis-channel-status')).toContainText('Speech has not been transcribed for this analysis.');
  await expect(page.locator('.analysis-channel-status')).not.toContainText('currently disabled');
  await page.locator('.reference-toolbar').getByRole('button', { name: 'Retry missing analysis', exact: true }).click();
  await expect.poll(() => retried).toBe(true);
});

async function sample(api: APIRequestContext) {
  let state: TaskState = await (await api.post('/api/tasks', { data: { title: 'Research window regression' } })).json();
  for (const path of ['/sample', '/recognize']) {
    const response = await api.post(`/api/tasks/${state.task.task_id}${path}`, { data: { expected_version: state.task.version } });
    expect(response.ok(), await response.text()).toBeTruthy(); state = await response.json();
  }
  return state;
}
async function open(page: Page, state: TaskState) {
  await page.addInitScript((id) => localStorage.setItem('video-anatomy-task', id), state.task.task_id);
  await page.goto('/');
  await expect(page.locator('.m5-timeline')).toBeVisible();
}
async function reachable(page: Page, selector: string) {
  const element = page.locator(selector);
  await element.evaluate(node => node.scrollIntoView({ block: 'center', inline: 'nearest' }));
  const box = await element.boundingBox();
  expect(box).not.toBeNull();
  const viewport = page.viewportSize()!;
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width + 1);
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height + 1);
}

test('research controls remain reachable across desktop, tablet and narrow windows', async ({ page, request }) => {
  const state = await sample(request);
  await open(page, state);
  for (const size of [{ width: 1440, height: 900 }, { width: 1280, height: 720 }, { width: 1024, height: 768 }, { width: 768, height: 1024 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(size);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await reachable(page, '.reference-toolbar');
    await reachable(page, '.frame-controls');
    await reachable(page, '.reference-timeline-slot');
    await reachable(page, '.m5-inspector-heading');
    if (size.width === 1440 || size.width === 390) {
      await page.locator('.reference-toolbar').scrollIntoViewIfNeeded();
      await page.screenshot({ path: test.info().outputPath(`v0.7.3-${size.width === 1440 ? 'desktop' : 'narrow'}.png`) });
    }
    if (size.width < 1051) {
      await expect(page.locator('.task-sidebar')).not.toBeVisible();
      await page.locator('.sidebar-toggle').click();
      await expect(page.locator('.task-sidebar')).toBeVisible();
      await page.locator('.sidebar-toggle').click();
    }
    await page.getByRole('tab', { name: 'Structure', exact: true }).click();
    if (size.width === 1440) {
      await page.getByRole('button', { name: 'Analyze structure', exact: true }).click();
      await expect(page.locator('.logic-node')).toHaveCount(3);
    }
    await reachable(page, '.structure-toolbar');
    await page.getByRole('button', { name: 'Logic map', exact: true }).click();
    await page.locator('.logic-node').first().click();
    await reachable(page, '.structure-inspector .node-feedback button[type=submit]');
    await page.getByRole('button', { name: 'Close details', exact: true }).click();
    await page.getByRole('button', { name: /Transferable methods/ }).click();
    await reachable(page, '.method-choice');
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole('tab', { name: 'Timeline', exact: true }).click();
  }
});

test('speech-only partial analysis names failed channels and allows a missing-channel retry', async ({ page, request }) => {
  const state = await sample(request);
  const partial = structuredClone(state);
  const analysis = partial.analyses[0];
  // The illustrated sample has no spoken audio; this explicit UI fixture supplies one retained utterance.
  analysis.status = 'partial'; analysis.events = [{ ...analysis.events[0], event_id: 'retained-speech-fixture', kind: 'speech', lane: 'audio', text: 'Synthetic retained speech.', description: null, visual_details: null }]; analysis.segments = [];
  analysis.coverage.speech = 'observations';
  analysis.coverage.visual_action = 'failed'; analysis.coverage.on_screen_text = 'failed';
  analysis.extraction_failures = {
    visual_action: { code: 'provider_budget_exhausted', message: 'Visual extraction stopped at the local budget limit.', retryable: true },
    on_screen_text: { code: 'provider_budget_exhausted', message: 'Visible text extraction stopped at the local budget limit.', retryable: true },
  };
  analysis.output_language = 'English';
  let retried = false;
  await page.route('**/api/tasks', async (route) => {
    const response = await route.fetch(); const saved: TaskState[] = await response.json();
    await route.fulfill({ response, json: saved.map((item) => item.task.task_id === state.task.task_id ? partial : item) });
  });
  await page.route(`**/api/tasks/${state.task.task_id}`, async (route) => route.fulfill({ json: retried ? state : partial }));
  await page.route(`**/api/tasks/${state.task.task_id}/editors/analysis`, async (route) => {
    const response = await route.fetch(); const saved = await response.json();
    if (!retried) saved.content = { events: analysis.events, segments: [] };
    await route.fulfill({ response, json: saved });
  });
  await page.route(`**/api/tasks/${state.task.task_id}/operations`, async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    expect(route.request().postDataJSON().operation).toBe('recognize');
    retried = true; await route.fulfill({ json: { operation_id: 'retry-fixture', status: 'succeeded', error: null, result: state } });
  });
  await open(page, partial);
  await expect(page.locator('.timeline-channel-state.failed')).toHaveCount(2);
  await expect(page.locator('.timeline-mark.speech')).not.toHaveCount(0);
  await expect(page.locator('.analysis-channel-status')).toContainText('Visual extraction stopped at the local budget limit.');
  await expect(page.locator('.analysis-channel-status')).toContainText('Visible text extraction stopped at the local budget limit.');
  await expect(page.locator('.analysis-channel-status')).not.toContainText('none found');
  await page.locator('.reference-toolbar').getByRole('button', { name: 'Retry missing analysis', exact: true }).click();
  await expect.poll(() => retried).toBe(true);
});
