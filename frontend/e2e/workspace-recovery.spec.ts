import { expect, test, type APIRequestContext } from '@playwright/test';
import { area } from './m2-helpers';
import type { TaskState } from '../src/generated/contracts';

async function readyTask(api: APIRequestContext) {
  const created = await api.post('/api/tasks', { data: { title: 'Recover hidden direction conflict' } });
  expect(created.ok()).toBeTruthy();
  let state: TaskState = await created.json();
  const update = async (path: string, fields: Record<string, unknown> = {}) => {
    const response = await api.post(`/api/tasks/${state.task.task_id}${path}`, { data: { expected_version: state.task.version, ...fields } });
    expect(response.ok(), await response.text()).toBeTruthy();
    state = await response.json();
  };
  await update('/sample');
  await update('/recognize', { video_id: state.task.current_video_id });
  await update('/analysis/confirm', { analysis_ref: state.task.current_analysis });
  await update('/language', { generation_language: 'English' });
  await update('/directions/generate', { brief_ref: state.task.current_brief, analysis_ref: state.task.current_analysis });
  return state;
}

test('a hidden recovered conflict never traps area navigation or discards another tab’s saved draft', async ({ page, request }) => {
  const state = await readyTask(request);
  const otherResponse = await request.post('/api/tasks', { data: { title: 'Another saved workspace' } });
  const other: TaskState = await otherResponse.json();
  const scope = `direction-${state.directions[0].direction_id}`;
  const path = `/api/tasks/${state.task.task_id}/editors/${scope}`;
  const initial = await (await request.get(path)).json();
  const remoteText = 'Newer wording already saved in a second tab.';
  const localText = 'Recovered local wording that must remain available to copy.';
  const remoteSave = await request.post(path, { data: {
    expected_draft_version: initial.draft_version,
    base_refs: initial.base_refs,
    content: { ...initial.content, hook: remoteText },
  } });
  expect(remoteSave.ok(), await remoteSave.text()).toBeTruthy();
  const remote = await remoteSave.json();
  await page.addInitScript(({ taskId, scope, recovery }) => {
    localStorage.setItem('video-anatomy-task', taskId);
    localStorage.setItem(`video-anatomy-area:${taskId}`, 'production');
    localStorage.setItem(`video-anatomy-editor:${taskId}:${scope}`, JSON.stringify(recovery));
  }, { taskId: state.task.task_id, scope, recovery: { draftVersion: initial.draft_version, baseRefs: initial.base_refs, content: { ...initial.content, hook: localText } } });
  await page.goto('/');
  await expect(page.locator('#area-production')).toBeVisible();
  const direction = page.getByRole('article', { name: 'Direction A', exact: true, includeHidden: true });
  await expect(direction.locator('.direction-draft-status')).toContainText('Draft changes retained');

  // Changing task still requires durable saving or explicit conflict resolution.
  await page.getByRole('complementary', { name: 'Saved tasks' }).getByRole('button', { name: new RegExp(other.task.title) }).click();
  await expect(page.getByRole('heading', { name: state.task.title, exact: true })).toBeVisible();
  await expect(page.locator('.workspace > [role=alert]')).toContainText('newer saved draft');

  // Viewing another area is safe: all editors stay mounted with their local text.
  await area(page, 'inputs');
  await expect(page.getByRole('dialog', { name: 'Project context', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Open reference', exact: false }).click();
  await expect(page.locator('#area-reference')).toBeVisible();
  await area(page, 'inputs');
  await page.getByRole('link', { name: 'Continue to directions', exact: true }).click();
  await expect(page.locator('#area-directions')).toBeVisible();
  await direction.getByText('Read full direction and edit', { exact: true }).click();
  await expect(direction.getByLabel('Hook', { exact: true })).toHaveValue(localText);
  await expect(direction.getByLabel('Hook', { exact: true })).toHaveAttribute('readonly', '');
  await expect(direction.getByRole('button', { name: 'Save direction edits', exact: true })).toBeDisabled();
  await direction.getByRole('button', { name: 'Review discard options', exact: true }).click();
  await direction.getByRole('button', { name: 'Discard draft', exact: true }).click();
  await expect(direction.getByLabel('Hook', { exact: true })).toHaveValue(remoteText);
  await expect(direction.getByLabel('Hook', { exact: true })).not.toHaveAttribute('readonly', '');
  const retained = await (await request.get(path)).json();
  expect(retained.draft_version).toBe(remote.draft_version);
  expect(retained.content.hook).toBe(remoteText);
  expect(retained.has_pending_changes).toBe(true);
  expect(await page.evaluate(({ taskId, scope }) => localStorage.getItem(`video-anatomy-editor:${taskId}:${scope}`), { taskId: state.task.task_id, scope })).toBeNull();
  await page.getByRole('complementary', { name: 'Saved tasks' }).getByRole('button', { name: new RegExp(other.task.title) }).click();
  await expect(page.getByRole('heading', { name: other.task.title, exact: true })).toBeVisible();
});
