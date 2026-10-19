import { expect, type Page } from '@playwright/test';
import type { TaskState } from '../src/generated/contracts';

export async function area(page: Page, name: 'inputs' | 'reference' | 'directions' | 'production') {
  const context = page.getByRole('dialog', { name: 'Project context', exact: true });
  if (name === 'inputs') {
    if (!await context.isVisible()) await page.getByRole('button', { name: /^Project context/ }).click();
    await expect(context).toBeVisible();
    return;
  }
  if (await context.isVisible()) await page.getByRole('button', { name: 'Close context', exact: true }).click();
  if (!await page.locator(`#area-${name}`).isVisible()) await page.locator(`#tab-${name}`).click();
  await expect(page.locator(`#area-${name}`)).toBeVisible();
}

export async function editBrand(page: Page) {
  await area(page, 'inputs');
  if (!await page.getByLabel('Brand/company', { exact: true }).isVisible()) {
    await page.getByRole('button', { name: 'Edit brand & product', exact: true }).click();
  }
}

export async function editTask(page: Page) {
  await area(page, 'inputs');
  if (!await page.getByLabel('Target audience', { exact: true }).isVisible()) {
    await page.getByRole('button', { name: 'Edit task details', exact: true }).click();
  }
}

export async function fillInputs(page: Page, fields: Record<string, string>) {
  await editBrand(page);
  const claims = fields['Selling points']?.split('\n') ?? [];
  for (const [index, claim] of claims.entries()) {
    const control = page.getByLabel(`Selling point ${index + 1}`, { exact: true });
    if (!await control.isVisible()) await page.getByRole('button', { name: 'Add selling point', exact: true }).click();
    await control.fill(claim);
  }
  for (const label of ['Brand/company', 'Product']) {
    if (fields[label] !== undefined) await page.getByLabel(label, { exact: true }).fill(fields[label]);
  }
  await editTask(page);
  for (const label of ['Target audience', 'Publishing platform', 'Communication goal', 'Target duration (seconds)']) {
    if (fields[label] !== undefined) await page.getByLabel(label, { exact: true }).fill(fields[label]);
  }
  if (fields['Approved messages'] !== undefined) {
    if (!await page.getByLabel('Approved messages', { exact: true }).isVisible()) await page.getByText('Production details and restrictions', { exact: true }).click();
    await page.getByLabel('Approved messages', { exact: true }).fill(fields['Approved messages']);
  }
  for (let index = 0; index < claims.length; index += 1) {
    await page.getByRole('checkbox', { name: /^Confirmed for use\s*: selling point/ }).nth(index).check();
  }
}

export async function draftSaved(page: Page) {
  await expect(page.getByTestId('m2-save-status')).toContainText('Draft saved');
}

export async function applyInputs(page: Page, evidencePath?: string): Promise<TaskState> {
  await area(page, 'inputs');
  await page.getByRole('button', { name: /^(Review inputs|Review changes)$/ }).last().click();
  await expect(page.getByRole('heading', { name: 'Review your inputs.', exact: true })).toBeVisible();
  if (evidencePath) await page.getByTestId('m2-editor').screenshot({ path: evidencePath });
  const pending = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/m2/apply'));
  await page.getByRole('button', { name: 'Apply inputs', exact: true }).click();
  const response = await pending;
  expect(response.ok(), await response.text()).toBeTruthy();
  const result: { changed: boolean; task: TaskState } = await response.json();
  await expect(page.getByTestId('m2-editor')).toContainText('Inputs applied');
  return result.task;
}
