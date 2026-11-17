import { expect, test } from '@playwright/test';

test('project dialogs keep focus, recent openings sort first, and Trash restores', async ({ page, request }) => {
  const older = await (await request.post('/api/projects', { data: { title: `Older synthetic project ${Date.now()}` } })).json();
  await request.post('/api/projects', { data: { title: `Newer synthetic project ${Date.now()}` } });
  await page.goto('/');
  const create = page.getByRole('button', { name: 'New project', exact: true });
  await create.click();
  const dialog = page.getByRole('dialog', { name: 'Create a project', exact: true });
  await expect(dialog.getByLabel('Project name')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(create).toBeFocused();
  await page.getByRole('button', { name: `Open ${older.title}`, exact: true }).click();
  await page.getByRole('button', { name: 'All projects', exact: true }).click();
  await expect(page.getByLabel('Sort projects')).toHaveValue('recent');
  await expect(page.locator('.va-project-open').first()).toHaveAccessibleName(`Open ${older.title}`);
  await page.getByLabel(`Actions for ${older.title}`).click();
  await page.getByRole('button', { name: 'Move to Trash', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Move to Trash', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await page.getByRole('button', { name: 'Trash', exact: true }).click();
  const card = page.locator('.va-project-card').filter({ hasText: older.title });
  await card.getByRole('button', { name: 'Restore project', exact: true }).click();
  await expect(card).toHaveCount(0);
  await page.getByRole('button', { name: 'Projects', exact: true }).click();
  await expect(page.getByRole('button', { name: `Open ${older.title}`, exact: true })).toBeVisible();
});

test('Discover stays reserved and provides the local import destination', async ({ page, request }) => {
  const project = await (await request.post('/api/projects', { data: { title: `Discover synthetic project ${Date.now()}` } })).json();
  await page.goto(`/?project=${project.id}`);
  await page.getByRole('button', { name: 'Discover', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Discover', exact: true })).toBeVisible();
  await expect(page.getByText('Reserved — awaiting Frank’s specification.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Open Resources', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Resources', exact: true })).toHaveAttribute('aria-current', 'page');
  const saved = await (await request.get(`/api/projects/${project.id}`)).json();
  expect(saved.resources).toEqual([]);
  expect(saved.jobs).toEqual([]);
});
