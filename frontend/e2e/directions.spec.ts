import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import type { TaskState } from '../src/generated/contracts';

async function update(api: APIRequestContext, state: TaskState, path: string, body: Record<string, unknown> = {}): Promise<TaskState> {
  const response = await api.post(`/api/tasks/${state.task.task_id}${path}`, { data: { expected_version: state.task.version, ...body } });
  expect(response.ok(), await response.text()).toBeTruthy();
  const saved: TaskState = await response.json();
  expect(saved.jobs.at(-1)?.status).not.toBe('failed');
  return saved;
}

async function readyTask(api: APIRequestContext, title: string, generate = true) {
  const created = await api.post('/api/tasks', { data: { title } });
  expect(created.ok()).toBeTruthy();
  let state: TaskState = await created.json();
  state = await update(api, state, '/sample');
  state = await update(api, state, '/recognize', { video_id: state.task.current_video_id });
  state = await update(api, state, '/analysis/confirm', { analysis_ref: state.task.current_analysis });
  if (generate) {
    state = await update(api, state, '/language', { generation_language: 'English' });
    state = await update(api, state, '/directions/generate', { brief_ref: state.task.current_brief, analysis_ref: state.task.current_analysis });
  }
  return state;
}

async function openDirections(page: Page, state: TaskState) {
  await page.addInitScript((taskId: string) => {
    localStorage.setItem('video-anatomy-task', taskId);
    localStorage.setItem(`video-anatomy-area:${taskId}`, 'directions');
  }, state.task.task_id);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Find the story worth making.' })).toBeVisible();
}

async function clickMutation(page: Page, suffix: string, click: () => Promise<void>): Promise<TaskState> {
  const responsePromise = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith(suffix));
  await click();
  const response = await responsePromise;
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

test('direction language is explicit, summaries are readable, and evidence opens the reference', async ({ page, request }) => {
  const state = await readyTask(request, 'Direction language and evidence', false);
  await openDirections(page, state);
  await expect(page.getByLabel('Generation language', { exact: true })).toHaveValue('');
  await expect(page.getByRole('button', { name: 'Generate two sample directions', exact: true })).toBeDisabled();
  await page.getByLabel('Generation language', { exact: true }).selectOption('English');
  await clickMutation(page, '/language', () => page.getByRole('button', { name: 'Save generation language' }).click());
  await clickMutation(page, '/directions/generate', () => page.getByRole('button', { name: 'Generate two sample directions', exact: true }).click());
  const first = page.getByRole('article', { name: 'Direction A', exact: true });
  await expect(first.getByText('The idea', { exact: true })).toBeVisible();
  await expect(first.getByText('Brand fit', { exact: true })).toBeVisible();
  await expect(first.getByLabel('Core message', { exact: true })).toBeHidden();
  await first.getByText('Read full direction and edit', { exact: true }).click();
  await first.getByText('Evidence, explanation and production notes', { exact: true }).click();
  await expect(first.locator('.direction-evidence blockquote').first()).not.toBeEmpty();
  await first.getByRole('button', { name: /^View reference at / }).first().click();
  await expect(page.locator('#area-reference')).toBeVisible();
  await expect(page.locator('#area-directions')).toBeHidden();
});

test('direction drafts and unsent feedback survive task switching; manual text can be explicitly approved', async ({ page, request }) => {
  const state = await readyTask(request, 'Preserve direction draft');
  const otherResponse = await request.post('/api/tasks', { data: { title: 'Second task for recovery' } });
  const other: TaskState = await otherResponse.json();
  await openDirections(page, state);
  let first = page.getByRole('article', { name: 'Direction A', exact: true });
  await first.getByText('Read full direction and edit', { exact: true }).click();
  await first.getByLabel('Refinement instruction', { exact: true }).fill('Later: explore a quieter opening.');
  await first.getByLabel('Hook', { exact: true }).fill('原创开场：把杯子放入通勤包。');
  await expect(page.getByRole('button', { name: 'Generate two new sample directions', exact: true })).toBeDisabled();
  await page.getByRole('complementary', { name: 'Saved tasks' }).getByRole('button', { name: new RegExp(other.task.title) }).click();
  await expect(page.getByRole('heading', { name: other.task.title, exact: true })).toBeVisible();
  await page.getByRole('complementary', { name: 'Saved tasks' }).getByRole('button', { name: new RegExp(state.task.title) }).click();
  first = page.getByRole('article', { name: 'Direction A', exact: true });
  await expect(page.locator('#area-directions')).toBeVisible();
  await first.getByText('Read full direction and edit', { exact: true }).click();
  await expect(first.getByLabel('Hook', { exact: true })).toHaveValue('原创开场：把杯子放入通勤包。');
  await expect(first.getByLabel('Refinement instruction', { exact: true })).toHaveValue('Later: explore a quieter opening.');
  const edited = await clickMutation(page, '/edit', () => first.getByRole('button', { name: 'Save direction edits' }).click());
  expect(edited.directions.at(-1)?.auxiliary_status).toBe('needs_review');
  first = page.getByRole('article', { name: 'Direction A', exact: true });
  await expect(first.getByText('Brand fit', { exact: true })).toHaveCount(0);
  await expect(first.getByRole('button', { name: 'Approve this direction' })).toBeDisabled();
  await first.getByLabel('I reviewed the edited text', { exact: false }).check();
  const approved = await clickMutation(page, '/approve', () => first.getByRole('button', { name: 'Approve this direction' }).click());
  expect(approved.task.selected_direction?.revision).toBe(2);
  expect(approved.directions.at(-1)?.approval_status).toBe('approved');
  expect(approved.directions.at(-1)?.auxiliary_status).toBe('needs_review');
  expect(approved.feedback).toHaveLength(0);
});

test('language changes preserve reference review and make the prior creative version historical', async ({ page, request }) => {
  let state = await readyTask(request, 'Change creative language');
  const direction = state.directions[0];
  state = await update(request, state, `/directions/${direction.direction_id}/approve`, { direction_revision: direction.revision, brief_ref: state.task.current_brief, analysis_ref: state.task.current_analysis });
  await openDirections(page, state);
  await page.getByLabel('Generation language', { exact: true }).selectOption('Chinese');
  await expect(page.getByText('Saving a different language makes existing directions', { exact: false })).toBeVisible();
  const saved = await clickMutation(page, '/language', () => page.getByRole('button', { name: 'Save generation language' }).click());
  expect(saved.task.selected_direction).toBeNull();
  expect(saved.task.current_analysis).toEqual(state.task.current_analysis);
  expect(saved.analyses.at(-1)?.review.user_confirmed).toBe(true);
  expect(saved.directions.every((item) => item.currentness === 'outdated')).toBe(true);
  await expect(page.getByText('Historical version', { exact: true })).toHaveCount(2);
});

test('a retained direction draft can be copied and discarded after new brand inputs make it historical', async ({ page, request }) => {
  let state = await readyTask(request, 'Recover a historical direction draft');
  const base = `/api/tasks/${state.task.task_id}`;
  const scope = `direction-${state.directions[0].direction_id}`;
  const editor = await (await request.get(`${base}/editors/${scope}`)).json();
  const saveDraft = await request.post(`${base}/editors/${scope}`, { data: {
    expected_draft_version: editor.draft_version, base_refs: editor.base_refs,
    content: { ...editor.content, hook: 'Keep this unsaved creative thought for comparison.' },
  } });
  expect(saveDraft.ok(), await saveDraft.text()).toBeTruthy();
  let m2 = await (await request.get(`${base}/m2/draft`)).json();
  const saveInputs = await request.post(`${base}/m2/draft`, { data: {
    expected_draft_version: m2.draft_version,
    fields: { ...m2.fields, communication_goal: 'Introduce the same product to commuters with a new story.' },
    claims: m2.claims, source_notes: m2.source_notes,
  } });
  expect(saveInputs.ok(), await saveInputs.text()).toBeTruthy();
  m2 = await saveInputs.json();
  const apply = await request.post(`${base}/m2/apply`, { data: { expected_version: state.task.version, expected_draft_version: m2.draft_version, based_on_brief: m2.based_on_brief } });
  expect(apply.ok(), await apply.text()).toBeTruthy();
  state = (await apply.json()).task;
  await openDirections(page, state);
  const first = page.getByRole('article', { name: 'Direction A', exact: true });
  await first.getByText('Read full direction and edit', { exact: true }).click();
  await expect(first.getByLabel('Hook', { exact: true })).toHaveValue('Keep this unsaved creative thought for comparison.');
  await expect(first.getByLabel('Hook', { exact: true })).toBeEnabled();
  await expect(first.getByLabel('Hook', { exact: true })).toHaveAttribute('readonly', '');
  await expect(first.getByRole('button', { name: 'Save direction edits' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Generate two new sample directions', exact: true })).toBeDisabled();
  await first.getByRole('button', { name: 'Discard draft changes', exact: true }).click();
  const response = page.waitForResponse((item) => item.request().method() === 'POST' && new URL(item.url()).pathname.endsWith(`/editors/${scope}/discard`));
  await first.getByRole('button', { name: 'Discard draft', exact: true }).click();
  expect((await response).ok()).toBeTruthy();
  await expect(page.getByRole('button', { name: 'Generate two new sample directions', exact: true })).toBeEnabled();
});
