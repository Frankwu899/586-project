import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import type { TaskState } from '../src/generated/contracts';

async function createTask(api: APIRequestContext, title: string) {
  const response = await api.post('/api/tasks', { data: { title } });
  expect(response.ok(), await response.text()).toBeTruthy();
  return await response.json() as TaskState;
}

async function commands(page: Page, title: string) {
  await page.getByLabel(`Project actions for ${title}`, { exact: true }).click();
  return page.locator('.project-actions[open]');
}

test('project commands preserve drafts through rename, close, Trash and restore', async ({ page, request }) => {
  await page.goto('/');
  await page.getByLabel('New task title', { exact: true }).fill('Project menu draft recovery');
  await page.getByRole('button', { name: 'Create task', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Project menu draft recovery', exact: true })).toBeVisible();
  const id = await page.evaluate(() => localStorage.getItem('video-anatomy-task'));
  expect(id).toBeTruthy();
  await page.getByRole('button', { name: 'Project context', exact: true }).click();
  const context = page.getByRole('dialog', { name: 'Project context', exact: true });
  await context.getByRole('button', { name: 'Edit brand & product', exact: true }).click();
  await context.getByLabel('Brand/company', { exact: true }).fill('Retained unsent brand');
  await context.getByRole('button', { name: 'Close context', exact: true }).click();

  await (await commands(page, 'Project menu draft recovery')).getByRole('button', { name: 'Rename project', exact: true }).click();
  const rename = page.getByRole('dialog', { name: 'Rename project', exact: true });
  await rename.getByLabel('Project name', { exact: true }).fill('Renamed classroom project');
  await rename.getByRole('button', { name: 'Rename', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Renamed classroom project', exact: true })).toBeVisible();
  const before = await (await request.get(`/api/tasks/${id}/m2/draft`)).json();
  expect(before.fields.brand_company).toBe('Retained unsent brand');

  await page.getByRole('button', { name: 'Close project', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Start with a video. Or an idea.', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Start with a video. Or an idea.', exact: true })).toBeVisible();
  await page.locator('.project-open').filter({ hasText: 'Renamed classroom project' }).click();
  await expect(page.getByRole('heading', { name: 'Renamed classroom project', exact: true })).toBeVisible();

  await (await commands(page, 'Renamed classroom project')).getByRole('button', { name: 'Move to Trash', exact: true }).click();
  let confirm = page.getByRole('dialog', { name: 'Move “Renamed classroom project” to Trash?', exact: true });
  await confirm.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Renamed classroom project', exact: true })).toBeVisible();
  await (await commands(page, 'Renamed classroom project')).getByRole('button', { name: 'Move to Trash', exact: true }).click();
  confirm = page.getByRole('dialog', { name: 'Move “Renamed classroom project” to Trash?', exact: true });
  await confirm.getByRole('button', { name: 'Move to Trash', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Start with a video. Or an idea.', exact: true })).toBeVisible();
  await expect(page.locator('.task-list .project-open').filter({ hasText: 'Renamed classroom project' })).toHaveCount(0);
  await page.reload();
  await page.getByRole('button', { name: 'Trash', exact: true }).click();
  const trashed = page.locator('.project-row').filter({ hasText: 'Renamed classroom project' });
  await expect(trashed).toBeVisible();
  await trashed.getByRole('button', { name: 'Restore project', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Renamed classroom project', exact: true })).toBeVisible();
  const after = await (await request.get(`/api/tasks/${id}/m2/draft`)).json();
  expect(after).toEqual(before);
  await page.getByRole('button', { name: /^Project context/ }).click();
  await context.getByRole('button', { name: 'Edit brand & product', exact: true }).click();
  await expect(context.getByLabel('Brand/company', { exact: true })).toHaveValue('Retained unsent brand');
});

test('active provider work blocks destructive project commands while another project stays openable', async ({ page, request }) => {
  const active = await createTask(request, 'Project with running analysis');
  const other = await createTask(request, 'Other project remains available');
  await page.addInitScript((id) => localStorage.setItem('video-anatomy-task', id), active.task.task_id);
  const ticket = { operation_id: 'operation-project-menu-test', task_id: active.task.task_id, operation: 'recognize', status: 'running', result: null, error: null, created_at: new Date().toISOString() };
  await page.route(`**/api/tasks/${active.task.task_id}/operations`, (route) => route.fulfill({ json: { operations: [ticket] } }));
  await page.route(`**/api/tasks/${active.task.task_id}/operations/${ticket.operation_id}`, (route) => route.fulfill({ json: ticket }));
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Close project', exact: true })).toBeDisabled();
  const menu = await commands(page, active.task.title);
  await expect(menu.getByRole('button', { name: 'Rename project', exact: true })).toBeDisabled();
  await expect(menu.getByRole('button', { name: 'Move to Trash', exact: true })).toBeDisabled();
  await page.locator('.project-open').filter({ hasText: other.task.title }).click();
  await expect(page.getByRole('heading', { name: other.task.title, exact: true })).toBeVisible();
});

test('application language changes the shell without rewriting project titles or Ideas language', async ({ page, request }) => {
  let state = await createTask(request, 'Keep this user title in English');
  const languageResponse = await request.post(`/api/tasks/${state.task.task_id}/language`, { data: { expected_version: state.task.version, generation_language: 'English' } });
  expect(languageResponse.ok(), await languageResponse.text()).toBeTruthy();
  state = await languageResponse.json();
  await page.addInitScript((id) => localStorage.setItem('video-anatomy-task', id), state.task.task_id);
  await page.goto('/');
  await page.getByLabel('Application language', { exact: true }).selectOption('Chinese');
  await expect(page.getByRole('heading', { name: '项目', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '研究', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: state.task.title, exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: '项目', exact: true })).toBeVisible();
  const saved: TaskState = await (await request.get(`/api/tasks/${state.task.task_id}`)).json();
  expect(saved.task.generation_language).toBe('English');
  await page.getByLabel('应用语言', { exact: true }).selectOption('English');
  await expect(page.getByRole('button', { name: 'Research', exact: true })).toBeVisible();
});
