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

test('a saved library document attaches to Overview without uploading again or replacing the composer', async ({ page, request }) => {
  let project = await (await request.post('/api/projects', { data: { title: `Existing document ${Date.now()}` } })).json();
  const upload = await request.post(`/api/projects/${project.id}/resources`, { multipart: {
    expected_version: String(project.version),
    file: { name: 'existing-brief.txt', mimeType: 'text/plain', buffer: Buffer.from('A 20-second commuter video.') },
  } });
  expect(upload.ok()).toBeTruthy();
  project = await upload.json();
  const resourceId = project.resources[0].id;
  await expect.poll(async () => (await (await request.get(`/api/projects/${project.id}`)).json()).jobs[0].status).toBe('succeeded');
  await page.goto(`/?project=${project.id}`);
  const composer = page.getByLabel('Describe your assignment');
  await composer.fill('Keep my current thought and attach the saved brief.');
  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  await page.getByRole('button', { name: 'Focus existing-brief.txt', exact: true }).click();
  await page.getByRole('button', { name: 'Attach in Overview', exact: true }).click();
  await expect(composer).toHaveValue('Keep my current thought and attach the saved brief.');
  await expect(composer).toBeFocused();
  await expect(page.getByRole('button', { name: 'Detach existing-brief.txt', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.locator('.va-message.user')).toHaveCount(1);
  const saved = await (await request.get(`/api/projects/${project.id}`)).json();
  expect(saved.resources).toHaveLength(1);
  expect(saved.messages[0].resource_ids).toEqual([resourceId]);
  expect(saved.briefs).toEqual([]);
});
