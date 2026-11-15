import { expect, test, type Locator, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

// Authored persisted fixtures exercise the UI/storage contract, not live AI quality.
// Zoom equivalents preserve available CSS pixels: physical viewport / zoom factor.
const root = resolve(import.meta.dirname, '../..');
const screenshots = process.env.VIDEO_ANATOMY_SCREENSHOT_DIR;
let mediaFolder: string;
let media: string;
type Fixture = { id: string; title: string; resources: { id: string; name: string }[]; contents: { id: string }[]; packs: { id: string; revision: number }[] };
const fixture = (mode = 'seed', id?: string): Fixture => JSON.parse(execFileSync(join(root, '.venv/bin/python'), [join(root, 'frontend/e2e/project-regression-fixtures.py'), process.env.VIDEO_ANATOMY_E2E_DATA_DIR!, mode, id ?? media], { cwd: root, encoding: 'utf8' }));
async function open(page: Page, project: Fixture) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  if (await page.getByRole('button', { name: 'All projects', exact: true }).count()) await page.getByRole('button', { name: 'All projects', exact: true }).click();
  await page.getByRole('button', { name: `Open ${project.title}`, exact: true }).click();
  await page.getByRole('button', { name: 'Analysis', exact: true }).click();
  await page.getByLabel('Analysis scope', { exact: true }).selectOption('');
}
async function reachable(control: Locator) {
  await control.scrollIntoViewIfNeeded();
  await expect(control).toBeInViewport();
  expect(await control.evaluate(element => {
    const bounds = element.getBoundingClientRect();
    return bounds.left >= -1 && bounds.top >= -1 && bounds.right <= innerWidth + 1 && bounds.bottom <= innerHeight + 1;
  })).toBeTruthy();
  await control.click({ trial: true });
}
async function capture(page: Page, name: string) {
  if (screenshots) {
    mkdirSync(screenshots, { recursive: true });
    await page.screenshot({ path: join(screenshots, `${name}.png`), fullPage: false });
  }
}
test.beforeAll(() => {
  mediaFolder = mkdtempSync(join(tmpdir(), 'video-anatomy-181-browser-'));
  media = join(mediaFolder, 'synthetic-blue.mp4');
  execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=24:d=12', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', media]);
});
test.afterAll(() => rmSync(mediaFolder, { recursive: true, force: true }));

for (const [width, height] of [[1440, 900], [1280, 800], [1024, 768], [390, 844]]) {
  for (const zoom of [1, 1.25, 1.5]) {
    test(`expanded resources and bottom actions remain reachable at ${width}x${height} / ${zoom * 100}% CSS equivalent`, async ({ page }) => {
      await page.setViewportSize({ width: Math.floor(width / zoom), height: Math.floor(height / zoom) });
      const project = fixture();
      await open(page, project);
      await page.getByRole('button', { name: 'Resources', exact: true }).click();
      await page.getByRole('button', { name: `Preview ${project.resources[0].name}`, exact: true }).click();
      const previewPlayer = page.locator('.va-resource-inspector video');
      await previewPlayer.scrollIntoViewIfNeeded();
      await previewPlayer.evaluate(async element => {
        const player = element as HTMLVideoElement;
        player.muted = true;
        await player.play();
        player.pause();
      });
      await expect.poll(async () => previewPlayer.evaluate(element => (element as HTMLVideoElement).readyState)).toBeGreaterThanOrEqual(2);
      expect(await page.locator('.va-timecode').first().evaluate(element => {
        const range = document.createRange(); range.selectNodeContents(element);
        return range.getClientRects().length;
      })).toBe(1);
      await capture(page, `player-${width}x${height}-${zoom * 100}`);
      await page.getByText('Coverage and limitations', { exact: true }).click();
      await expect(page.getByText('Speech transcription failed. Retry transcription.', { exact: true }).first()).toBeVisible();
      const relink = page.getByRole('button', { name: 'Relink original', exact: true });
      await page.mouse.move(Math.floor(width / zoom) - 30, Math.floor(height / zoom) - 50);
      for (let attempt = 0; attempt < 8; attempt++) await page.mouse.wheel(0, 1600);
      await reachable(relink);
      await reachable(page.getByRole('button', { name: 'Rebuild media preview', exact: true }));
      await reachable(page.getByRole('button', { name: 'Retry transcription', exact: true }));
      await relink.focus();
      await expect(relink).toBeFocused();
      await expect(relink).toBeInViewport();
      await page.keyboard.press('Shift+Tab');
      await expect(page.locator(':focus')).toBeInViewport();
      expect(await page.locator(':focus').evaluate(element => {
        const bounds = element.getBoundingClientRect();
        return bounds.width >= 24 && bounds.height >= 24 && getComputedStyle(element).clipPath === 'none';
      })).toBeTruthy();
      await capture(page, `resources-${width}x${height}-${zoom * 100}`);
      await reachable(page.getByRole('button', { name: /Analyze selected/ }));
      for (const destination of ['Overview', 'Resources', 'Discover', 'Analysis', 'Content plan', 'Production']) await reachable(page.getByRole('button', { name: destination, exact: true }));
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
      await page.getByRole('button', { name: 'Analysis', exact: true }).click();
      await page.getByLabel('Analysis scope', { exact: true }).selectOption('');
      await expect(page.locator('.va-analysis-report')).toHaveCount(1);
      const graph = page.getByRole('region', { name: /Video logic graph/ });
      await reachable(graph);
      await graph.focus();
      await page.keyboard.press('ArrowRight');
      await page.getByRole('button', { name: /Blue frame held/ }).first().click();
      await expect(page.getByRole('region', { name: 'Selected structure moment' })).toContainText('Observed frame at six seconds.');
      await capture(page, `analysis-${width}x${height}-${zoom * 100}`);
      await page.getByRole('button', { name: 'Production', exact: true }).click();
      for (const document of ['Production brief', 'Script', 'Storyboard', 'Shot list']) await reachable(page.getByRole('tab', { name: document, exact: true }));
      await page.getByRole('tab', { name: 'Storyboard', exact: true }).click();
      await page.getByLabel('Storyboard', { exact: true }).fill('Viewport check: keep the full shot description readable.');
      await page.getByRole('button', { name: 'Save production pack', exact: true }).click();
      await expect(page.getByText('Current · v2', { exact: true })).toBeVisible();
      await page.getByText('Export production pack', { exact: true }).click();
      expect(await page.locator('.va-export-menu > div').evaluate(element => {
        const bounds = element.getBoundingClientRect();
        return bounds.left >= 0 && bounds.right <= innerWidth;
      })).toBeTruthy();
      await reachable(page.getByRole('button', { name: 'Word document (.docx)', exact: true }));
      await capture(page, `production-${width}x${height}-${zoom * 100}`);
    });
  }
}

test('current analysis survives tabs, replacement and failure while source graph keeps identity', async ({ page, context }) => {
  const project = fixture();
  await open(page, project);
  await expect(page.getByText('Analysis A saved takeaway.', { exact: true })).toBeVisible();
  await expect(page.locator('.va-analysis-report')).toHaveCount(1);
  await page.reload();
  await page.getByLabel('Analysis scope', { exact: true }).selectOption('');
  await expect(page.getByText('Analysis A saved takeaway.', { exact: true })).toBeVisible();
  const reopened = await context.newPage();
  await page.close();
  await open(reopened, project);
  await expect(reopened.getByText('Analysis A saved takeaway.', { exact: true })).toBeVisible();
  fixture('replace', project.id);
  await reopened.reload();
  await reopened.getByLabel('Analysis scope', { exact: true }).selectOption('');
  await expect(reopened.getByText('Analysis B replacement takeaway.', { exact: true })).toBeVisible();
  await expect(reopened.getByText('Analysis A saved takeaway.', { exact: true })).toHaveCount(0);
  fixture('fail', project.id);
  await reopened.reload();
  await reopened.getByLabel('Analysis scope', { exact: true }).selectOption('');
  await expect(reopened.getByText('Analysis B replacement takeaway.', { exact: true })).toBeVisible();
  await expect(reopened.getByText(/service is temporarily busy|service could not complete/i).first()).toBeVisible();
  await reopened.getByLabel('Analysis scope', { exact: true }).selectOption(project.contents[0].id);
  await expect(reopened.getByText('Independent content result.', { exact: true })).toBeVisible();
  await reopened.getByLabel('Reference structure', { exact: true }).selectOption(project.resources[1].id);
  await reopened.getByRole('button', { name: /Blue frame held/ }).click();
  await reopened.getByRole('button', { name: /Synthetic second reference.mp4.*00:06/ }).click();
  const player = reopened.locator('.va-resource-inspector video');
  await expect(player).toHaveAttribute('src', new RegExp(project.resources[1].id));
  await expect.poll(async () => player.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeGreaterThanOrEqual(5.9);
});

test('storyboard edits reopen and exact saved revision exports consistently', async ({ page, request }) => {
  const project = fixture();
  await open(page, project);
  await page.getByRole('button', { name: 'Production', exact: true }).click();
  await page.getByRole('tab', { name: 'Storyboard', exact: true }).click();
  const revised = '0–6s: Hold blue.\n6–12s: Continue the blue frame. Revision from browser.';
  await page.getByLabel('Storyboard', { exact: true }).fill(revised);
  await page.getByRole('button', { name: 'Save production pack', exact: true }).click();
  await expect(page.getByText('Current · v2', { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole('tab', { name: 'Storyboard', exact: true }).click();
  await expect(page.getByLabel('Storyboard', { exact: true })).toHaveValue(revised);
  await page.getByText('Export production pack', { exact: true }).click();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Markdown (.md)', exact: true }).click();
  const download = await downloadPromise;
  expect(readFileSync((await download.path())!, 'utf8')).toContain(revised);
  for (const format of ['csv', 'html']) {
    const response = await request.get(`/api/projects/${project.id}/packs/${project.packs[0].id}/export?revision=2&format=${format}`);
    expect(response.ok()).toBeTruthy();
    expect(await response.text()).toContain('Revision from browser.');
  }
  const word = await request.get(`/api/projects/${project.id}/packs/${project.packs[0].id}/export?revision=2&format=docx`);
  expect(word.ok()).toBeTruthy();
  const document = execFileSync(join(root, '.venv/bin/python'), ['-c', "import io,sys,zipfile; print(zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())).read('word/document.xml').decode())"], { input: await word.body(), encoding: 'utf8' });
  expect(document).toContain('Revision from browser.');
});

test('no context or references prompts a starting question without creating a job', async ({ page, request }) => {
  const project = await (await request.post('/api/projects', { data: { title: `Empty planning ${Date.now()}` } })).json() as Fixture;
  await open(page, project);
  await page.getByRole('button', { name: 'Content plan', exact: true }).click();
  await page.getByRole('button', { name: 'Suggest series & topics', exact: true }).click();
  await expect(page.getByText(/What would you like to create\?/)).toBeVisible();
  expect((await (await request.get(`/api/projects/${project.id}`)).json()).jobs).toEqual([]);
  await page.getByRole('button', { name: 'Describe the assignment', exact: true }).click();
  await expect(page.getByLabel('Describe your assignment')).toBeVisible();
});

for (const referenceOnly of [false, true]) {
  test(`${referenceOnly ? 'reference-only exploration' : 'confirmed context'} allows empty creative instruction with explicit visual-only consent`, async ({ page }) => {
    const project = fixture();
    if (referenceOnly) fixture('reference_only', project.id);
    await open(page, project);
    await page.getByRole('button', { name: 'Content plan', exact: true }).click();
    await expect(page.getByLabel('Creative instruction (optional)', { exact: true })).toHaveValue('');
    await page.getByLabel('Continue with visual evidence only', { exact: true }).check();
    const responsePromise = page.waitForResponse(response => response.url().endsWith(`/api/projects/${project.id}/concepts/generate`) && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Suggest series & topics', exact: true }).click();
    const response = await responsePromise;
    expect(response.status()).toBe(202);
    expect(response.request().postDataJSON()).toMatchObject({ instruction: '', visual_only: true });
    // No key is configured. Admission is tested; generation quality is not.
  });
}
