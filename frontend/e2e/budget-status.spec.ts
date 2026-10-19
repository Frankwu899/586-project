import { expect, test, type Page } from '@playwright/test';

type Budget = {
  maximum_usd: string; remaining_usd: string; known_estimated_cost_usd: string;
  unresolved_reserved_usd: string; recoverable_rejected_attempts: number; blocked: boolean;
};
async function budgetSettings(page: Page, initial: Budget, reconciled: Budget) {
  const calls: { path: string; method: string; body: unknown }[] = [];
  const connectionWrites: string[] = [];
  let budget = initial;
  await page.route('**/api/local/connection**', (route) => {
    if (route.request().method() !== 'GET') connectionWrites.push(route.request().url());
    return route.fulfill({ json: {
      available: true, configured: true, key_source: 'keychain', can_remember: true,
      remembered: true, last_check: null,
    } });
  });
  await page.route('**/api/local/budget**', (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    calls.push({ path, method: request.method(), body: request.postData() ? request.postDataJSON() : null });
    if (path === '/api/local/budget/reconcile' && request.method() === 'POST') budget = reconciled;
    return route.fulfill({ json: budget });
  });
  await page.goto('/');
  await expect(page.getByRole('dialog', { name: 'API connection', exact: true })).not.toBeVisible();
  await page.locator('.connection-toggle').click();
  const panel = page.getByRole('region', { name: 'Local test budget', exact: true });
  await expect(panel.getByRole('heading', { name: 'Local test budget · $3.00', exact: true })).toBeVisible();
  return { panel, calls, connectionWrites };
}

test('opening budget settings is read-only; explicit release retains the spending limit and unknown reservations', async ({ page }) => {
  const initial: Budget = {
    maximum_usd: '3', remaining_usd: '0.3', known_estimated_cost_usd: '0.2',
    unresolved_reserved_usd: '2.5', recoverable_rejected_attempts: 2, blocked: false,
  };
  const { panel, calls, connectionWrites } = await budgetSettings(page, initial, {
    ...initial, remaining_usd: '1.5', unresolved_reserved_usd: '1.3', recoverable_rejected_attempts: 0,
  });
  await expect(panel.locator('.budget-totals > div').filter({ hasText: 'Remaining' })).toContainText('$0.300');
  await expect(panel.locator('.budget-totals > div').filter({ hasText: 'Estimated usage' })).toContainText('$0.200');
  await expect(panel.locator('.budget-totals > div').filter({ hasText: 'Unresolved reservations' })).toContainText('$2.500');
  expect(calls.length).toBeGreaterThan(0);
  expect(calls.every((call) => call.method === 'GET' && call.path === '/api/local/budget')).toBe(true);
  expect(connectionWrites).toEqual([]);
  await expect(panel.getByText('Only confirmed authentication or permission refusals can be released. Timeouts and unknown charges stay reserved.')).toBeVisible();

  await panel.getByRole('button', { name: 'Release rejected requests (2)', exact: true }).click();
  await expect(panel.getByRole('status')).toHaveText('Budget updated. Completed work and the spending limit are unchanged.');
  expect(calls.filter((call) => call.method === 'POST')).toEqual([{ path: '/api/local/budget/reconcile', method: 'POST', body: {} }]);
  await expect(panel.getByRole('heading', { name: 'Local test budget · $3.00', exact: true })).toBeVisible();
  await expect(panel.locator('.budget-totals > div').filter({ hasText: 'Remaining' })).toContainText('$1.500');
  await expect(panel.locator('.budget-totals > div').filter({ hasText: 'Estimated usage' })).toContainText('$0.200');
  await expect(panel.locator('.budget-totals > div').filter({ hasText: 'Unresolved reservations' })).toContainText('$1.300');
  await expect(panel.getByRole('button', { name: /Release rejected requests/ })).toHaveCount(0);
  await panel.getByRole('button', { name: 'Refresh budget', exact: true }).click();
  await expect.poll(() => calls.at(-1)?.method).toBe('GET');
  expect(calls.filter((call) => call.method === 'POST')).toHaveLength(1);
  expect(connectionWrites).toEqual([]);
});

test('an accounting pause remains explicit despite a positive balance and released rejected requests', async ({ page }) => {
  const initial: Budget = {
    maximum_usd: '3', remaining_usd: '1.75', known_estimated_cost_usd: '0.25',
    unresolved_reserved_usd: '1', recoverable_rejected_attempts: 1, blocked: true,
  };
  const { panel, calls } = await budgetSettings(page, initial, {
    ...initial, remaining_usd: '2.25', unresolved_reserved_usd: '0.5', recoverable_rejected_attempts: 0,
  });
  const message = 'API spending is paused for an accounting check. Releasing rejected requests does not remove this pause.';
  await expect(panel.getByRole('alert')).toHaveText(message);
  await expect(panel.locator('.budget-totals > div').filter({ hasText: 'Remaining' })).toContainText('$1.750');
  expect(calls.every((call) => call.method === 'GET')).toBe(true);
  await panel.getByRole('button', { name: 'Release rejected requests (1)', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('spending limit are unchanged');
  await expect(panel.locator('.budget-totals > div').filter({ hasText: 'Remaining' })).toContainText('$2.250');
  await expect(panel.getByRole('alert')).toHaveText(message);
  expect(calls.filter((call) => call.method === 'POST')).toEqual([{ path: '/api/local/budget/reconcile', method: 'POST', body: {} }]);
});
