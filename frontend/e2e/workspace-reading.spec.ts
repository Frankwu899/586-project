import { expect, test } from '@playwright/test';
import type { TaskState } from '../src/generated/contracts';

test('long evidence follows document scrolling in narrow and short windows', async ({ page, request }) => {
  let state: TaskState = await (await request.post('/api/tasks', { data: { title: 'Long evidence reading' } })).json();
  for (const path of ['/sample', '/recognize']) {
    const response = await request.post(`/api/tasks/${state.task.task_id}${path}`, { data: { expected_version: state.task.version } });
    expect(response.ok(), await response.text()).toBeTruthy();
    state = await response.json();
  }
  const draft = await (await request.get(`/api/tasks/${state.task.task_id}/editors/analysis`)).json();
  draft.content.events[0].description = 'A visible cup sits on a desk beside a notebook. '.repeat(70);
  const saved = await request.post(`/api/tasks/${state.task.task_id}/editors/analysis`, { data: { expected_draft_version: draft.draft_version, base_refs: draft.base_refs, content: draft.content } });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  await page.addInitScript(id => localStorage.setItem('video-anatomy-task', id), state.task.task_id);
  // 720×450 also exercises the effective layout space of a 1440×900 window at 200% zoom.
  for (const viewport of [{ width: 390, height: 844 }, { width: 720, height: 450 }]) {
    await page.setViewportSize(viewport);
    await page.goto('/');
    await page.getByRole('button', { name: 'Research', exact: true }).click();
    const evidence = page.locator('.m5-observation-copy');
    await expect(evidence).toContainText('A visible cup sits');
    const before = await evidence.evaluate(element => {
      element.scrollIntoView({ block: 'start' });
      return window.scrollY;
    });
    await page.mouse.move(viewport.width / 2, viewport.height / 2);
    await page.mouse.wheel(0, 400);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(before);
    expect(await page.locator('.reference-inspector-content').evaluate(element => ({ overflow: getComputedStyle(element).overflowY, top: element.scrollTop }))).toEqual({ overflow: 'visible', top: 0 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const next = page.getByRole('button', { name: 'Next frame', exact: true });
    await next.scrollIntoViewIfNeeded();
    await next.click();
    await expect(page.getByTestId('reference-frame-position')).toContainText('· 1 /');
    await page.getByRole('button', { name: 'Ideas', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Idea', exact: true })).toBeVisible();
  }
});

test('global failures remain visible when the project sidebar is closed', async ({ page }) => {
  await page.route('**/api/local/preferences', route => route.request().method() === 'GET'
    ? route.fulfill({ json: { language: 'English' } })
    : route.fulfill({ status: 503, json: { error: { message: 'Preferences could not be saved.' } } }));
  await page.goto('/');
  const sidebar = page.locator('.sidebar-toggle');
  if (await sidebar.getAttribute('aria-expanded') === 'true') await sidebar.click();
  await expect(page.locator('.task-sidebar')).not.toBeVisible();
  await page.getByLabel('Application language', { exact: true }).selectOption('Chinese');
  await expect(page.locator('.workspace > [role=alert]')).toContainText('Preferences could not be saved.');
  await expect(page.getByLabel('Application language', { exact: true })).toHaveValue('English');
});
