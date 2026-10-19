import { expect, test, type Page } from '@playwright/test';
import type { TaskState } from '../src/generated/contracts';

const verified = { status: 'verified', code: 'provider_metadata_verified', message: 'Key accepted. Configured models are visible.', missing_models: [], endpoint_permissions_verified: false };
const initial = { available: true, configured: false, key_source: 'none', can_remember: true, remembered: false, last_check: null };
const fakeKey = 'sk-proj-fictional-browser-test-key-never-valid';

async function connectionRoute(page: Page, configured = false) {
  const calls: { path: string; body: Record<string, unknown> }[] = [];
  let status = { ...initial, configured, key_source: configured ? 'keychain' : 'none', remembered: configured };
  await page.route('**/api/local/connection**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === 'GET') return route.fulfill({ json: status });
    const body = route.request().postDataJSON();
    calls.push({ path, body });
    if (path.endsWith('/check')) return route.fulfill({ json: verified });
    if (path.endsWith('/forget')) { status = { ...initial }; return route.fulfill({ json: status }); }
    status = { ...initial, configured: true, key_source: body.remember ? 'keychain' : 'session', remembered: Boolean(body.remember) };
    return route.fulfill({ json: { ...status, last_check: verified } });
  });
  return calls;
}

test('first launch saves a key through the local backend and never browser storage', async ({ page }) => {
  const calls = await connectionRoute(page);
  await page.goto('/');
  const modal = page.getByRole('dialog', { name: 'API connection', exact: true });
  await expect(modal).toBeVisible();
  await expect(modal.getByLabel('Remember on this Mac (Keychain)')).toBeChecked();
  await expect(modal.getByLabel('OpenAI API key', { exact: true })).toHaveAttribute('type', 'password');
  await modal.getByLabel('OpenAI API key', { exact: true }).fill(fakeKey);
  await modal.getByRole('button', { name: 'Check connection', exact: true }).click();
  await expect(modal.getByText(verified.message)).toBeVisible();
  await expect(page.locator('.connection-toggle')).toContainText('Set up');
  await modal.getByRole('button', { name: 'Save key', exact: true }).click();
  await expect(modal.getByText(/Saved in macOS Keychain/)).toBeVisible();
  await expect(modal.getByLabel('Replace API key', { exact: true })).toHaveValue('');
  await expect(page.locator('.connection-toggle')).toContainText('Key added');
  expect(calls).toEqual([{ path: '/api/local/connection/check', body: { api_key: fakeKey } }, { path: '/api/local/connection', body: { api_key: fakeKey, remember: true } }]);
  expect(await page.evaluate(() => `${JSON.stringify(localStorage)}${JSON.stringify(sessionStorage)}`)).not.toContain(fakeKey);
  await modal.getByRole('button', { name: 'Close API connection' }).click();
  await page.reload();
  await expect(page.locator('.connection-toggle')).toContainText('Key added');
  await expect(modal).not.toBeVisible();
});

test('a stored key can be checked without re-entry, removed, and setup dismissed without blocking projects', async ({ page }) => {
  const calls = await connectionRoute(page, true);
  await page.goto('/');
  const modal = page.getByRole('dialog', { name: 'API connection', exact: true });
  await expect(modal).not.toBeVisible();
  await page.locator('.connection-toggle').click();
  await modal.getByRole('button', { name: 'Check connection', exact: true }).click();
  await expect(modal.getByText(verified.message)).toBeVisible();
  expect(calls[0]).toEqual({ path: '/api/local/connection/check', body: {} });
  await modal.getByRole('button', { name: 'Remove API key', exact: true }).click();
  await expect(modal.getByText('Connection cleared. Your projects and videos are unchanged.')).toBeVisible();
  await modal.getByLabel('OpenAI API key', { exact: true }).fill(fakeKey);
  await page.keyboard.press('Escape');
  await expect(modal).not.toBeVisible();
  await page.locator('.connection-toggle').click();
  await expect(modal.getByLabel('OpenAI API key', { exact: true })).toHaveValue('');
  await modal.getByRole('button', { name: 'Close API connection' }).click();
  await page.getByLabel('New task title', { exact: true }).fill('Connection setup can wait');
  await page.getByRole('button', { name: 'Create task', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Connection setup can wait', exact: true })).toBeVisible();
  await expect(modal).not.toBeVisible();
});

test('key rejection stays in the settings dialog and leaves the existing connection intact', async ({ page }) => {
  await connectionRoute(page, true);
  await page.route('**/api/local/connection', async (route) => {
    if (route.request().method() === 'GET') return route.fallback();
    return route.fulfill({ status: 401, json: { error: { code: 'provider_authentication_failed', message: 'OpenAI rejected this key. Check its project and status.' } } });
  });
  await page.goto('/');
  await page.locator('.connection-toggle').click();
  const modal = page.getByRole('dialog', { name: 'API connection', exact: true });
  await modal.getByLabel('Replace API key', { exact: true }).fill(fakeKey);
  await modal.getByRole('button', { name: 'Save key', exact: true }).click();
  await expect(modal.getByRole('alert')).toHaveText('OpenAI rejected this key. Check its project and status.');
  await expect(page.locator('.connection-toggle')).toContainText('Key added');
  await expect(modal.getByRole('alert')).not.toContainText('Reopen');
});

test('analysis authentication failures show the actual reason and an in-place connection action', async ({ page, request }) => {
  await connectionRoute(page, true);
  const created = await request.post('/api/tasks', { data: { title: 'Authentication error recovery' } });
  const initialTask: TaskState = await created.json();
  const sample = await request.post(`/api/tasks/${initialTask.task.task_id}/sample`, { data: { expected_version: initialTask.task.version } });
  const state: TaskState = await sample.json();
  await page.addInitScript((id) => localStorage.setItem('video-anatomy-task', id), state.task.task_id);
  const message = 'OpenAI rejected the API credential (HTTP 401). Replace it in API settings with a complete, active project secret key.';
  await page.route(`**/api/tasks/${state.task.task_id}/operations`, async (route) => {
    if (route.request().method() === 'GET') return route.fallback();
    return route.fulfill({ json: { operation_id: 'operation_auth_failure', status: 'failed', result: null, error: { code: 'provider_authentication_failed', message } } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Run sample analysis', exact: true }).click();
  const feedback = page.locator('.reference-operation-feedback');
  await expect(feedback.getByRole('alert')).toContainText(message);
  await expect(feedback).not.toContainText('Analysis could not complete');
  await expect(page.locator('.workspace-feedback')).not.toContainText('Reopen the saved project');
  await feedback.getByRole('button', { name: 'Check API connection', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'API connection', exact: true })).toBeVisible();
});

test('development servers without local credentials endpoints keep the workspace usable', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Start with a video. Or an idea.', exact: true })).toBeVisible();
  await expect(page.locator('.connection-toggle')).toHaveCount(0);
  await expect(page.getByRole('dialog', { name: 'API connection', exact: true })).not.toBeVisible();
});
