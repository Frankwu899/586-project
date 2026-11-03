import { test, expect } from '@playwright/test';

test('team uses a persistent project without an API key dialog', async ({ page, browser }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByText('Shared workspace', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /API connection/ })).toHaveCount(0);
  await expect(page.locator('.connection-dialog')).toHaveCount(0);
  await page.getByLabel('New task title').fill('Shared server project');
  await page.getByRole('button', { name: 'Create task', exact: true }).click();
  await expect(page.locator('button.project-open').filter({ hasText: 'Shared server project' })).toBeVisible();
  await page.reload();
  await expect(page.locator('button.project-open').filter({ hasText: 'Shared server project' })).toBeVisible();
  await page.getByLabel('Application language').selectOption('Chinese');
  await expect(page.getByText('团队工作区', { exact: true })).toBeVisible();
  await expect(page.locator('.connection-dialog')).toHaveCount(0);
  expect(errors).toEqual([]);
  // A fresh anonymous browser session cannot read the shared team's projects.
  const anonymous = await browser.newContext();
  expect((await anonymous.request.get('http://127.0.0.1:8018/api/tasks')).status()).toBe(401);
  await anonymous.close();
});
