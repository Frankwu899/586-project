import { expect, test } from '@playwright/test';
import type { TaskState } from '../src/generated/contracts';

test('application locale covers context, Ideas and Production while retaining authored content and generation language', async ({ page, request }) => {
  const created = await request.post('/api/tasks', { data: { title: 'Original product name 保留' } });
  let state: TaskState = await created.json();
  const selected = await request.post(`/api/tasks/${state.task.task_id}/language`, { data: { expected_version: state.task.version, generation_language: 'English' } });
  state = await selected.json();
  await page.addInitScript((id) => localStorage.setItem('video-anatomy-task', id), state.task.task_id);
  let preference = 'English';
  const writes: unknown[] = [];
  const contentRequests: string[] = [];
  page.on('request', (outgoing) => {
    if (outgoing.method() === 'POST' && /\/(operations|recognize|generate|structure\/analyze)$/.test(new URL(outgoing.url()).pathname)) contentRequests.push(outgoing.url());
  });
  await page.route('**/api/local/preferences', (route) => {
    if (route.request().method() === 'POST') { const body = route.request().postDataJSON(); writes.push(body); preference = body.language; }
    return route.fulfill({ json: { language: preference } });
  });
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await page.getByLabel('Application language', { exact: true }).selectOption('Chinese');
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN');
  expect(writes).toEqual([{ language: 'Chinese' }]);
  await expect(page.getByRole('heading', { name: 'Original product name 保留', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '项目背景', exact: true }).click();
  const context = page.getByRole('dialog', { name: '项目背景', exact: true });
  await expect(context.getByRole('heading', { name: '明确创作方向。', exact: true })).toBeVisible();
  await context.getByRole('button', { name: '编辑品牌与产品', exact: true }).click();
  await context.getByLabel('品牌 / 公司', { exact: true }).fill('Do not translate this brand');
  await context.getByRole('button', { name: '关闭项目背景', exact: true }).click();
  await page.getByRole('button', { name: '创意', exact: true }).click();
  await expect(page.getByLabel('生成语言', { exact: true })).toHaveValue('English');
  await expect(page.getByText('创意笔记', { exact: true })).toBeVisible();
  const notebookSaved = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/editors/idea'));
  await page.getByRole('textbox', { name: '创意', exact: true }).fill('My original idea 创意原文');
  expect((await notebookSaved).ok()).toBe(true);
  await expect(page.getByText('笔记已保存在此项目中', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '制作', exact: true }).click();
  await expect(page.getByRole('heading', { name: '制作', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '生成制作材料', exact: true })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole('heading', { name: '制作', exact: true })).toBeVisible();
  await page.getByLabel('应用语言', { exact: true }).selectOption('English');
  await page.getByRole('button', { name: 'Ideas', exact: true }).click();
  await expect(page.getByLabel('Idea', { exact: true })).toHaveValue('My original idea 创意原文');
  await expect(page.getByLabel('Generation language', { exact: true })).toHaveValue('English');
  const draft = await (await request.get(`/api/tasks/${state.task.task_id}/m2/draft`)).json();
  expect(draft.fields.brand_company).toBe('Do not translate this brand');
  expect(contentRequests).toEqual([]);
});

test('a preferences save failure keeps both visible language and persisted preference unchanged', async ({ page }) => {
  await page.route('**/api/local/preferences', (route) => route.request().method() === 'GET'
    ? route.fulfill({ json: { language: 'English' } })
    : route.fulfill({ status: 409, json: { error: { code: 'settings_busy', message: 'Wait for current work to finish before changing app settings or closing the app.' } } }));
  await page.goto('/');
  await page.getByLabel('Application language', { exact: true }).selectOption('Chinese');
  await expect(page.getByLabel('Application language', { exact: true })).toHaveValue('English');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('alert')).toContainText('Wait for current work to finish');
  expect(await page.evaluate(() => localStorage.getItem('video-anatomy:app-language'))).toBe('English');
});

test('a slow startup preference response cannot overwrite a newer language choice', async ({ page }) => {
  let release = () => {};
  const released = new Promise<void>((resolve) => { release = resolve; });
  await page.route('**/api/local/preferences', async (route) => {
    if (route.request().method() === 'GET') { await released; return route.fulfill({ json: { language: 'English' } }); }
    return route.fulfill({ json: { language: 'Chinese' } });
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByLabel('Application language', { exact: true }).selectOption('Chinese');
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN');
  const startupResponse = page.waitForResponse((response) => new URL(response.url()).pathname === '/api/local/preferences' && response.request().method() === 'GET');
  release();
  await (await startupResponse).finished();
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page.getByLabel('应用语言', { exact: true })).toHaveValue('Chinese');
  expect(await page.evaluate(() => localStorage.getItem('video-anatomy:app-language'))).toBe('Chinese');
});
