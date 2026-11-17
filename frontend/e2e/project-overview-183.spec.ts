import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { Fact, Project } from '../src/project/contracts';

const root = resolve(import.meta.dirname, '../..');
const fact = (id: string, key: string, value: string): Fact => ({ id, key, value, status: 'suggested', origin: 'manual', sources: [], permitted_for_use: false });
const load = async (request: APIRequestContext, id: string): Promise<Project> => (await request.get(`/api/projects/${id}`)).json();
async function create(request: APIRequestContext) { return (await request.post('/api/projects', { data: { title: `Overview 1.8.3 ${Date.now()}` } })).json() as Promise<Project>; }
async function saveFacts(request: APIRequestContext, project: Project, facts: Fact[], apply = false) {
  const response = await request.post(`/api/projects/${project.id}/brief/${apply ? 'apply' : 'draft'}`, { data: { expected_version: project.version, expected_draft_version: project.brief_draft_version, facts } });
  expect(response.ok()).toBeTruthy(); return response.json() as Promise<Project>;
}
async function open(page: Page, project: Project) { await page.goto(`/?project=${project.id}`); await expect(page.getByLabel('Describe your assignment')).toBeVisible(); }
async function capture(page: Page, name: string) {
  const folder = process.env.VIDEO_ANATOMY_SCREENSHOT_DIR;
  if (folder) { mkdirSync(folder, { recursive: true }); await page.screenshot({ path: join(folder, `${name}.png`), fullPage: true }); }
}

test('the compact snapshot stays adopted until explicit review and claim permission', async ({ page, request }) => {
  let project = await create(request);
  const objective = { ...fact('fact_goal', 'objective', 'Awareness'), status: 'confirmed' as const };
  project = await saveFacts(request, project, [objective], true);
  project = await saveFacts(request, project, [{ ...objective, value: 'Product clicks', status: 'suggested' }, fact('fact_claim', 'benefit', 'Keeps drinks warm')]);
  await open(page, project);
  const snapshot = page.locator('.va-overview-inspector');
  await expect(snapshot).toContainText('Awareness');
  await expect(snapshot).not.toContainText('Product clicks');
  await expect(snapshot).not.toContainText('Keeps drinks warm');
  await expect(page.getByRole('button', { name: 'Apply updates', exact: true })).toBeHidden();
  await page.getByRole('button', { name: 'Review changes (2)', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Review brief changes' });
  await expect(dialog).toBeVisible();
  await expect(page.getByRole('button', { name: 'Close review', exact: true })).toBeFocused();
  const goal = dialog.getByRole('region', { name: 'Review objective' });
  await expect(goal).toContainText('Awareness'); await expect(goal).toContainText('Product clicks');
  await goal.getByRole('button', { name: 'Keep current', exact: true }).click();
  await expect(goal).toHaveCount(0);
  const claim = dialog.getByRole('region', { name: 'Review benefit' });
  await claim.getByLabel('Use this update').check();
  await expect(dialog.getByRole('button', { name: 'Apply updates', exact: true })).toBeDisabled();
  await claim.getByLabel('Permit this claim’s use. This does not verify its truth.').check();
  await dialog.getByRole('button', { name: 'Apply updates', exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(snapshot).toContainText('In use · v2');
  await expect(snapshot).toContainText('Awareness'); await expect(snapshot).toContainText('Keeps drinks warm');
  const saved = await load(request, project.id);
  expect(saved.briefs.at(-1)?.facts.map(item => item.value)).toEqual(['Awareness', 'Keeps drinks warm']);
  await capture(page, 'overview-183-confirmed-snapshot');
});

for (const status of ['queued', 'running']) test(`Stop targets the ${status} attempt and retry reuses the saved message`, async ({ page, request }) => {
  const project = JSON.parse(execFileSync(join(root, '.venv/bin/python'), [join(root, 'frontend/e2e/project-overview-183-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, status], { cwd: root, encoding: 'utf8' })) as Project;
  await open(page, project);
  await page.getByLabel('Describe your assignment').fill('My next message remains a draft.');
  await expect(page.getByRole('button', { name: 'Send message', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Stop response', exact: true }).click();
  await expect(page.locator('.va-message.assistant p').filter({ hasText: /^Stopped$/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Send message', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Retry assistance', exact: true }).click();
  await expect.poll(async () => (await load(request, project.id)).messages.filter(item => item.role === 'assistant').length).toBe(2);
  const saved = await load(request, project.id);
  expect(saved.messages.filter(item => item.role === 'user')).toHaveLength(1);
  expect(saved.jobs.filter(item => item.kind === 'conversation').map(item => item.attempt_id)[0]).not.toBe(saved.jobs.at(-1)?.attempt_id);
  await expect(page.getByLabel('Describe your assignment')).toHaveValue('My next message remains a draft.');
  await page.reload();
  await expect(page.getByLabel('Describe your assignment')).toHaveValue('My next message remains a draft.');
  expect((await load(request, project.id)).briefs).toEqual([]);
});

test('IME confirmation never sends and a saved attachment survives explicit retry', async ({ page, request }) => {
  const project = await create(request); await open(page, project);
  await page.locator('.va-composer input[type=file]').setInputFiles({ name: 'brief-notes.txt', mimeType: 'text/plain', buffer: Buffer.from('A commuter video task.') });
  await expect(page.getByRole('button', { name: 'Detach brief-notes.txt' })).toBeVisible();
  const input = page.getByLabel('Describe your assignment'); await input.fill('中文创意草稿');
  await input.dispatchEvent('compositionstart');
  await input.dispatchEvent('keydown', { key: 'Enter', ctrlKey: true, isComposing: true, keyCode: 229 });
  await input.dispatchEvent('compositionend');
  await input.dispatchEvent('keydown', { key: 'Enter', ctrlKey: true, isComposing: false, keyCode: 229 });
  expect((await load(request, project.id)).messages).toEqual([]);
  await expect(input).toHaveValue('中文创意草稿');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Retry assistance', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Retry assistance', exact: true }).click();
  await expect.poll(async () => (await load(request, project.id)).messages.filter(item => item.role === 'assistant').length).toBe(2);
  const saved = await load(request, project.id);
  expect(saved.messages.filter(item => item.role === 'user')).toHaveLength(1);
  expect(saved.messages[0].resource_ids).toEqual([saved.resources[0].id]);
  expect(saved.messages[0].text).toBe('中文创意草稿');
});

test('a stale brief edit stays recoverable and never applies over a newer draft', async ({ page, request }) => {
  let project = await create(request); project = await saveFacts(request, project, [fact('fact_audience', 'audience', 'Commuters')]);
  await open(page, project); await page.getByRole('button', { name: 'Review changes (1)', exact: true }).click();
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await page.getByLabel('Correction', { exact: true }).fill('Retained local audience');
  const newer = await saveFacts(request, await load(request, project.id), [fact('fact_audience', 'audience', 'Newer saved audience')]);
  // Observe an actual polling refresh before saving, so a passing assertion
  // verifies the editor did not silently rebase its own draft version.
  await page.waitForResponse(async response => response.request().method() === 'GET' && response.url().endsWith(`/api/projects/${project.id}`) && (await response.json()).brief_draft_version === newer.brief_draft_version);
  await expect(page.getByLabel('Correction', { exact: true })).toHaveValue('Retained local audience');
  await page.getByRole('button', { name: 'Save suggestion', exact: true }).click();
  await expect(page.getByText('Your proposed changes are retained on this computer but are not saved to the project.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Apply updates', exact: true })).toBeDisabled();
  expect((await load(request, project.id)).brief_draft[0].value).toBe(newer.brief_draft[0].value);
  await page.reload(); await page.getByRole('button', { name: 'Review changes (1)', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('Retained local audience');
});

test('Keep current restores adopted claim permission and removal needs explicit confirmation', async ({ page, request }) => {
  let project = await create(request);
  const claim = { ...fact('fact_claim_keep', 'product_claim', 'The supplied product claim.'), status: 'confirmed' as const, permitted_for_use: true };
  project = await saveFacts(request, project, [claim], true);
  project = await saveFacts(request, project, [{ ...claim, value: 'A proposed correction.', status: 'suggested', permitted_for_use: false }]);
  await open(page, project); await page.getByRole('button', { name: 'Review changes (1)', exact: true }).click();
  await page.getByRole('button', { name: 'Keep current', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Review product claim' })).toHaveCount(0);
  await expect.poll(async () => (await load(request, project.id)).brief_draft[0].permitted_for_use).toBe(true);
  expect((await load(request, project.id)).briefs).toHaveLength(1);
  await page.getByText('Edit current information', { exact: true }).click();
  await page.getByRole('button', { name: 'Remove from brief', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Apply updates', exact: true })).toBeDisabled();
  await page.getByLabel('Confirm removing this claim from the brief.').check();
  await page.getByRole('button', { name: 'Apply updates', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Review brief changes' })).toBeHidden();
  expect((await load(request, project.id)).briefs.at(-1)?.facts).toEqual([]);
});

test('editing a migrated adopted fact absent from its draft keeps all adopted identities', async ({ page, request }) => {
  let project = await create(request);
  const adopted = [
    { ...fact('fact_old_objective', 'objective', 'Original objective'), status: 'confirmed' as const },
    { ...fact('fact_old_audience', 'audience', 'Original audience'), status: 'confirmed' as const },
  ];
  project = await saveFacts(request, project, adopted, true);
  project = await saveFacts(request, project, []);
  await open(page, project); await page.getByRole('button', { name: 'Review brief', exact: true }).click();
  await page.getByText('Edit current information', { exact: true }).click();
  await page.getByRole('button', { name: 'Propose a change', exact: true }).first().click();
  await page.getByLabel('Correction', { exact: true }).fill('Changed objective');
  await page.getByRole('button', { name: 'Save suggestion', exact: true }).click();
  await page.getByLabel('Use this update').check();
  await page.getByRole('button', { name: 'Apply updates', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Review brief changes' })).toBeHidden();
  expect((await load(request, project.id)).briefs.at(-1)?.facts.map(item => [item.id, item.value])).toEqual([['fact_old_objective', 'Changed objective'], ['fact_old_audience', 'Original audience']]);
});

test('Stop before composer flush prevents admission and retains the unsent text', async ({ page, request }) => {
  const project = await create(request); await open(page, project);
  let release!: () => void; let reached!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const intercepted = new Promise<void>(resolve => { reached = resolve; });
  await page.route(`**/api/projects/${project.id}`, async route => {
    if (route.request().method() === 'PATCH' && route.request().postDataJSON()?.editor_drafts?.conversation) { reached(); await held; }
    await route.continue();
  });
  await page.getByLabel('Describe your assignment').fill('Keep this unsent draft.');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await intercepted;
  await page.getByRole('button', { name: 'Stop response', exact: true }).click();
  release();
  await expect(page.getByRole('button', { name: 'Send message', exact: true })).toBeVisible();
  await expect(page.getByLabel('Describe your assignment')).toHaveValue('Keep this unsent draft.');
  expect((await load(request, project.id)).messages).toEqual([]);
});

test('narrow layout exposes brief and navigation with native focus return and reachable controls', async ({ page, request }) => {
  const project = await create(request); await open(page, project);
  for (const [width, height] of [[1440, 900], [1280, 800], [720, 450], [390, 844]]) {
    await page.setViewportSize({ width, height });
    if (width <= 900) {
      const navigation = page.getByText('Project navigation', { exact: true });
      await navigation.click(); await expect(page.getByRole('button', { name: 'Overview', exact: true })).toBeHidden();
      await navigation.click(); await expect(page.getByRole('button', { name: 'Overview', exact: true })).toBeVisible();
      const brief = page.getByRole('button', { name: 'View brief', exact: true });
      await brief.click(); await expect(page.getByRole('dialog', { name: 'Current brief' })).toBeVisible();
      await page.keyboard.press('Escape'); await expect(brief).toBeFocused();
    }
    const input = page.getByLabel('Describe your assignment'); await input.fill('A long bilingual title 长标题 '.repeat(8));
    await input.scrollIntoViewIfNeeded(); await expect(input).toBeInViewport();
    await page.getByRole('button', { name: 'Send message', exact: true }).scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await capture(page, `overview-183-${width}x${height}`);
  }
});
