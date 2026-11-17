import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

test('a local project keeps conversation drafts, resources, standalone production and reserved Discovery', async ({ page, request }) => {
  const title = `1.8 creative workspace ${Date.now()}`;
  await page.goto('/');
  await page.getByRole('button', { name: 'New project', exact: true }).click();
  await page.getByLabel('Project name', { exact: true }).fill(title);
  await page.getByRole('button', { name: 'Create project', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'What do you want to create today?' })).toBeVisible();
  await page.getByLabel('Describe your assignment').fill('Plan a commuter travel mug video. Keep the assignment draft incomplete.');
  await expect.poll(async () => {
    const projects = await (await request.get('/api/projects')).json();
    return projects.find((item: { title: string }) => item.title === title)?.editor_drafts?.conversation?.text;
  }).toContain('commuter travel mug');
  await page.getByRole('button', { name: 'Discover', exact: true }).click();
  await expect(page.getByText('Reserved — awaiting Frank’s specification.', { exact: true })).toBeVisible();
  await expect(page.getByRole('textbox')).toHaveCount(0);
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await expect(page.getByLabel('Describe your assignment')).toHaveValue(/commuter travel mug/);

  await page.getByRole('button', { name: 'Review brief', exact: true }).click();
  await page.getByRole('button', { name: 'Add information', exact: true }).click();
  await page.getByLabel('Information', { exact: true }).fill('assignment');
  await page.getByLabel('Correction', { exact: true }).fill('Create a 30-second commuter travel mug video.');
  await page.getByRole('button', { name: 'Save suggestion', exact: true }).click();
  await page.getByLabel('Use this update').check();
  await expect(page.getByRole('button', { name: 'Apply updates', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Apply updates', exact: true }).click();
  await expect(page.locator('.va-overview-inspector').getByText('In use · v1', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Resources', exact: true }).click();
  const upload = page.locator('.va-media-pool input[type=file]');
  await upload.setInputFiles({ name: 'campaign-notes.txt', mimeType: 'text/plain', buffer: Buffer.from('Audience: city commuters.\nAvoid unsupported performance claims.') });
  await expect(page.getByRole('button', { name: 'Focus campaign-notes.txt', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Open file', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'campaign-notes.txt' })).toBeVisible();
  await expect(page.locator('.va-document-blocks')).toContainText('city commuters');

  await page.getByRole('button', { name: 'Content plan', exact: true }).click();
  await page.getByRole('button', { name: 'Plan a video', exact: true }).click();
  await page.getByLabel('Title', { exact: true }).fill('The morning commute');
  await page.getByRole('button', { name: 'Create video', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'The morning commute', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Write a direction', exact: true }).click();
  await page.locator('.va-manual-direction').getByLabel('Title', { exact: true }).fill('One routine, three moments');
  await page.locator('.va-manual-direction').getByLabel('Concept', { exact: true }).fill('Follow a commuter preparing their bag, taking the train, and arriving at work.');
  await page.getByRole('button', { name: 'Save direction', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'One routine, three moments' })).toBeVisible();
  await page.getByRole('button', { name: 'Approve direction', exact: true }).click();
  await expect(page.getByText('Approved', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Open Production', exact: true }).click();
  await page.getByRole('button', { name: 'Start a blank sheet', exact: true }).click();
  await page.getByLabel('Production brief', { exact: true }).fill('Audience: commuters. Capture a realistic morning routine.');
  await page.getByRole('button', { name: 'Add shot', exact: true }).click();
  await page.getByLabel('Shot 01 End (seconds)', { exact: true }).fill('10');
  await page.getByLabel('Shot 01 Visual / Action', { exact: true }).fill('Pack the bag.');
  await page.getByLabel('Shot 01 Dialogue / VO', { exact: true }).fill('A morning starts with a plan.');
  await page.getByRole('button', { name: 'Add shot', exact: true }).click();
  await page.getByLabel('Shot 02 End (seconds)', { exact: true }).fill('30');
  await page.getByLabel('Shot 02 Visual / Action', { exact: true }).fill('Travel and arrive.');
  await page.getByRole('button', { name: 'Save sheet', exact: true }).click();
  await expect(page.getByText('Current · v2', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'All projects', exact: true }).click();
  await page.getByRole('button', { name: `Open ${title}`, exact: true }).click();
  await expect(page.getByRole('heading', { name: 'The morning commute', exact: true })).toBeVisible();
  await expect(page.getByLabel('Shot 01 Dialogue / VO', { exact: true })).toHaveValue('A morning starts with a plan.');
  await expect(page.getByLabel('Shot 02 Visual / Action', { exact: true })).toHaveValue('Travel and arrive.');
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await expect(page.getByLabel('Describe your assignment')).toHaveValue(/commuter travel mug/);
});

test('duplicate, rename, Trash and restore preserve independent project content', async ({ page, request }) => {
  const title = `Lifecycle ${Date.now()}`;
  const created = await (await request.post('/api/projects', { data: { title } })).json();
  await page.goto('/');
  await page.getByLabel(`Actions for ${title}`, { exact: true }).click();
  await page.getByRole('button', { name: 'Duplicate', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'What do you want to create today?' })).toBeVisible();
  await page.getByRole('button', { name: 'All projects', exact: true }).click();
  const all = await (await request.get('/api/projects')).json();
  const copy = all.find((item: { duplicated_from: string }) => item.duplicated_from === created.id);
  expect(copy).toBeTruthy();
  await page.getByLabel(`Actions for ${copy.title}`, { exact: true }).click();
  await page.getByRole('button', { name: 'Rename', exact: true }).click();
  await page.getByLabel('Project name', { exact: true }).fill(`${title} independent`);
  await page.getByRole('button', { name: 'Save name', exact: true }).click();
  await expect(page.getByRole('button', { name: `Open ${title}`, exact: true })).toBeVisible();
  await page.getByLabel(`Actions for ${title} independent`, { exact: true }).click();
  await page.getByRole('button', { name: 'Move to Trash', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Move to Trash', exact: true }).click();
  await page.getByRole('button', { name: 'Trash', exact: true }).click();
  await expect(page.getByRole('heading', { name: `${title} independent`, exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Restore project', exact: true }).click();
  await page.getByRole('button', { name: 'Projects', exact: true }).click();
  await expect(page.getByRole('button', { name: `Open ${title} independent`, exact: true })).toBeVisible();
});

test('closing immediately flushes the conversation draft into the project', async ({ page, request }) => {
  const title = `Immediate close ${Date.now()}`;
  const project = await (await request.post('/api/projects', { data: { title } })).json();
  await page.goto('/');
  await page.getByRole('button', { name: `Open ${title}`, exact: true }).click();
  await page.getByLabel('Describe your assignment').fill('This must survive before the debounce expires.');
  await page.getByRole('button', { name: 'All projects', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Your projects', exact: true })).toBeVisible();
  const saved = await (await request.get(`/api/projects/${project.id}`)).json();
  expect(saved.editor_drafts.conversation.text).toBe('This must survive before the debounce expires.');
});

test('a stale second-tab autosave retains local text without overwriting a newer draft', async ({ page, context, request }) => {
  const title = `Concurrent drafts ${Date.now()}`;
  const project = await (await request.post('/api/projects', { data: { title } })).json();
  const other = await context.newPage();
  for (const tab of [page, other]) {
    await tab.goto('/');
    await tab.waitForLoadState('networkidle');
    // 1.8.1 restores the selected project in a new tab. Open from the grid
    // only when there is no remembered project yet.
    if (!await tab.getByRole('button', { name: 'All projects', exact: true }).count()) {
      await tab.getByRole('button', { name: `Open ${title}`, exact: true }).click();
    }
    await expect(tab.getByLabel('Describe your assignment')).toBeVisible();
  }
  let release!: () => void;
  let intercepted!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const reached = new Promise<void>(resolve => { intercepted = resolve; });
  await other.route(`**/api/projects/${project.id}`, async route => {
    const call = route.request();
    if (call.method() === 'PATCH' && call.postDataJSON()?.editor_drafts?.conversation) { intercepted(); await held; }
    await route.continue();
  });
  await other.getByLabel('Describe your assignment').fill('Retained local second-tab edit');
  await reached;
  await page.getByLabel('Describe your assignment').fill('Newer saved first-tab edit');
  await expect.poll(async () => (await (await request.get(`/api/projects/${project.id}`)).json()).editor_drafts?.conversation?.text).toBe('Newer saved first-tab edit');
  release();
  await expect(other.getByText('A newer draft was saved elsewhere. Your local text is retained for comparison.')).toBeVisible();
  await expect(other.getByLabel('Describe your assignment')).toHaveValue('Retained local second-tab edit');
  expect((await (await request.get(`/api/projects/${project.id}`)).json()).editor_drafts.conversation.text).toBe('Newer saved first-tab edit');
  await other.close();
});

test('source citation playback continues while project status polling refreshes', async ({ page, request }) => {
  const folder = mkdtempSync(join(tmpdir(), 'video-anatomy-playback-'));
  try {
    const file = join(folder, 'synthetic-playback.mp4');
    execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=24:d=12', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', file]);
    const title = `Playback polling ${Date.now()}`;
    const project = await (await request.post('/api/projects', { data: { title } })).json();
    const uploaded = await request.post(`/api/projects/${project.id}/resources`, { multipart: { expected_version: String(project.version), role: 'reference', file: { name: 'synthetic-playback.mp4', mimeType: 'video/mp4', buffer: readFileSync(file) } } });
    expect(uploaded.ok()).toBeTruthy();
    await expect.poll(async () => (await (await request.get(`/api/projects/${project.id}`)).json()).resources[0]?.status).toBe('ready');
    // The authored citation is test data. Recognition/provider quality is not
    // exercised; actual local video playback and polling are exercised.
    await page.route(`**/api/projects/${project.id}`, async route => {
      if (route.request().method() !== 'GET') { await route.continue(); return; }
      const response = await route.fetch();
      const state = await response.json();
      const resource = state.resources[0];
      state.analyses = [{ id: 'analysis_test', content_id: null, inputs: { brief_revision: null, selection_revision: 1, resource_ids: [resource.id], evidence_revisions: {}, direction_id: null, direction_revision: null, instruction_version: 'test', model: null }, conclusion: 'Synthetic playback fixture', findings: [], differences: [], opportunities: [], sources: [{ resource_id: resource.id, message_id: null, locator: 'Test source', excerpt: '', url: null, evidence_revision: null, extraction_revision: null, event_id: null, start_seconds: 2, end_seconds: 3 }], limitations: ['Authored test fixture'], created_at: state.created_at, needs_review: false }];
      await route.fulfill({ response, json: state });
    });
    await page.goto('/');
    await page.getByRole('button', { name: `Open ${title}`, exact: true }).click();
    await page.getByRole('button', { name: 'Analysis', exact: true }).click();
    await page.getByText('Evidence and source moments', { exact: true }).click();
    await page.getByRole('button', { name: /synthetic-playback.mp4 · Test source · 00:02/ }).click();
    const video = page.locator('.va-resource-inspector video');
    await expect(video).toBeVisible();
    await expect.poll(async () => video.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeGreaterThanOrEqual(1.9);
    await video.evaluate(async element => { const player = element as HTMLVideoElement; player.muted = true; await player.play(); });
    await expect.poll(async () => video.evaluate(element => (element as HTMLVideoElement).currentTime), { timeout: 10_000 }).toBeGreaterThan(6);
  } finally { rmSync(folder, { recursive: true, force: true }); }
});
