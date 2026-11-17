// Offline synthetic full-workspace QA with Chromium's actual Page zoom.
// Usage: node frontend/scripts/check-project-native-zoom.mjs LOCAL_URL PROJECT_ID OUTPUT_DIR
/* global chrome, document, getComputedStyle, innerWidth, innerHeight, outerWidth,
          outerHeight, devicePixelRatio, visualViewport, requestAnimationFrame */
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { chromium, expect } from '@playwright/test';

const [baseURL, projectId, output] = process.argv.slice(2);
if (!baseURL || !projectId || !output) throw new Error('Usage: LOCAL_URL PROJECT_ID OUTPUT_DIR');
const folder = resolve(output);
mkdirSync(folder, { recursive: true });
const receipts = [], failures = [], prohibited = [];
const runId = Date.now();
const windows = process.env.VIDEO_ANATOMY_QA_WINDOWS ? JSON.parse(process.env.VIDEO_ANATOMY_QA_WINDOWS) : [[1440, 900], [1280, 800]];
const factors = process.env.VIDEO_ANATOMY_QA_ZOOMS ? JSON.parse(process.env.VIDEO_ANATOMY_QA_ZOOMS) : [1, 1.25, 1.5, 2];
const button = (page, name) => page.getByRole('button', { name, exact: true });
const projectURL = `${baseURL}/?project=${encodeURIComponent(projectId)}`;
const getProject = async page => {
  const response = await page.request.get(`${baseURL}/api/projects/${projectId}`);
  assert(response.ok()); return response.json();
};
const dimensions = page => page.evaluate(() => ({ innerWidth, innerHeight, outerWidth, outerHeight,
  devicePixelRatio, visualViewportScale: visualViewport.scale, cssZoom: getComputedStyle(document.documentElement).zoom,
  documentScrollWidth: document.documentElement.scrollWidth,
  main: document.querySelector('.va-workspace-main') ? { clientWidth: document.querySelector('.va-workspace-main').clientWidth, scrollWidth: document.querySelector('.va-workspace-main').scrollWidth } : null }));

async function runContext(width, height, zooms, narrow = false) {
  const profile = mkdtempSync(join(tmpdir(), 'full-native-zoom-'));
  const context = await chromium.launchPersistentContext(profile, {
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? '/usr/bin/chromium',
    headless: true, viewport: narrow ? { width, height } : null,
    args: ['--no-sandbox', '--disable-gpu', `--window-size=${width},${height}`],
  });
  try {
    const settings = context.pages()[0];
    await settings.goto('chrome://settings/appearance');
    await settings.waitForFunction(() => typeof chrome.settingsPrivate?.setDefaultZoom === 'function');
    const page = await context.newPage();
    page.setDefaultTimeout(12000);
    page.on('request', request => {
      if (request.method() === 'POST' && /\/(generate|analyze|recognize|extract|messages|topics\/suggest)(?:\?|$)/.test(new URL(request.url()).pathname)) prohibited.push(request.url());
    });
    const cdp = await context.newCDPSession(page);
    const capture = async name => {
      await page.bringToFront();
      await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))));
      const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false });
      writeFileSync(join(folder, name), Buffer.from(data, 'base64'));
    };
    const audit = async (locator, label) => {
      await expect(locator).toBeVisible();
      await locator.scrollIntoViewIfNeeded();
      const measured = await locator.evaluate(element => {
        const rect = element.getBoundingClientRect();
        const center = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height,
          viewportWidth: innerWidth, viewportHeight: innerHeight,
          centerUnobscured: Boolean(center && (element === center || element.contains(center))),
          fontSize: getComputedStyle(element).fontSize };
      });
      assert(measured.width > 0 && measured.height > 0, `${label}: empty control`);
      assert(measured.x >= -1 && measured.x + measured.width <= measured.viewportWidth + 1, `${label}: clipped horizontally ${JSON.stringify(measured)}`);
      assert(measured.y >= -1 && measured.y + measured.height <= measured.viewportHeight + 1, `${label}: unreachable vertically ${JSON.stringify(measured)}`);
      assert(measured.centerUnobscured, `${label}: obscured control ${JSON.stringify(measured)}`);
      return { label, ...measured };
    };
    const noPageOverflow = async () => {
      const size = await dimensions(page);
      assert(size.documentScrollWidth <= size.innerWidth + 1, `Document horizontal overflow: ${JSON.stringify(size)}`);
      if (size.main) assert(size.main.scrollWidth <= size.main.clientWidth + 1, `Workspace horizontal overflow: ${JSON.stringify(size.main)}`);
      return size;
    };
    const navigate = async name => {
      const nav = page.getByRole('navigation', { name: 'Project destinations', exact: true });
      if (!(await nav.isVisible())) await page.locator('.va-project-navigation > summary').click();
      await nav.getByRole('button', { name, exact: true }).click();
    };
    const modalAudit = async (dialog, name) => {
      await expect(dialog).toBeVisible();
      const controls = [];
      for (const locator of await dialog.locator('input, select, textarea, button').all()) {
        if (await locator.isVisible()) controls.push(await audit(locator, `${name} ${await locator.getAttribute('type') ?? await locator.evaluate(node => node.tagName)}`));
      }
      for (let i = 0; i < 6; i++) {
        await page.keyboard.press('Tab');
        assert(await dialog.evaluate(node => !document.hasFocus() || node.contains(document.activeElement)), `${name}: focus escaped modal`);
      }
      return controls;
    };
    for (const factor of zooms) {
      const observed = await settings.evaluate(factor => new Promise(resolve => {
        chrome.settingsPrivate.setDefaultZoom(factor, () => chrome.settingsPrivate.getDefaultZoom(resolve));
      }), factor);
      await page.goto(projectURL);
      await expect(page.locator('.va-workspace')).toBeVisible();
      await page.waitForFunction(factor => Math.abs(devicePixelRatio - factor) < .001, factor);
      const before = await getProject(page);
      const prefix = `${narrow ? 'narrow' : 'native'}-${width}x${height}-${factor * 100}`;
      const common = { mode: narrow ? 'narrow CSS viewport at native 100%' : 'native Chromium Page zoom',
        requestedWindow: [width, height], requestedZoom: factor, settingsGetDefaultZoom: observed,
        sourceVersion: (await (await page.request.get(`${baseURL}/api/projects/capabilities`)).json()).version,
        browserVersion: context.browser().version(), ...await dimensions(page) };
      assert.equal(common.visualViewportScale, 1); assert.equal(common.cssZoom, '1');
      if (!narrow) { assert.equal(common.outerWidth, width); assert.equal(common.outerHeight, height); }
      assert(Math.abs(observed - factor) < .001);
      const surface = async (name, work) => {
        const receipt = { ...common, surface: name, status: 'passed' };
        try { Object.assign(receipt, await work()); Object.assign(receipt, await noPageOverflow()); }
        catch (error) { receipt.status = 'failed'; receipt.error = String(error.stack ?? error); failures.push(receipt); }
        receipt.screenshot = `${prefix}-${name}.png`;
        await capture(receipt.screenshot).catch(error => { receipt.captureError = String(error); });
        receipts.push(receipt); console.log(JSON.stringify(receipt));
        writeFileSync(join(folder, 'native-full-receipts.json'), JSON.stringify({ receipts, failures, prohibited }, null, 2) + '\n');
      };
      await surface('media-pool', async () => {
        await navigate('Resources');
        if (await page.locator('.va-back-to-pool').isVisible()) await page.locator('.va-back-to-pool').click();
        const controls = [await audit(button(page, 'Upload files'), 'Upload files'), await audit(button(page, 'New folder'), 'New folder')];
        await button(page, 'New folder').click();
        const dialog = page.getByRole('dialog', { name: 'New folder', exact: true });
        await modalAudit(dialog, 'New folder');
        await page.keyboard.press('Escape'); await expect(dialog).not.toBeVisible();
        await expect(button(page, 'New folder')).toBeFocused();
        await button(page, 'Focus Legacy reference.mp4').click();
        controls.push(await audit(button(page, 'Open in timeline'), 'Open in timeline'));
        const overflow = await page.locator('.va-pool-table-scroll').evaluate(node => ({ clientWidth: node.clientWidth, scrollWidth: node.scrollWidth, overflowX: getComputedStyle(node).overflowX }));
        await button(page, 'Upload files').scrollIntoViewIfNeeded();
        return { controls, localTable: overflow };
      });
      await surface('source-review', async () => {
        await button(page, 'Open in timeline').click();
        const player = page.getByLabel('Reference video player', { exact: true });
        await expect(player).toBeVisible();
        await expect.poll(() => player.evaluate(node => node.readyState)).toBeGreaterThanOrEqual(1);
        const controls = [await audit(page.getByLabel('Evidence revision', { exact: true }), 'Evidence revision'), await audit(button(page, 'Next evidence'), 'Next evidence'), await audit(button(page, 'Fit timeline'), 'Fit timeline')];
        const slider = page.getByRole('slider', { name: 'Source playhead', exact: true });
        await audit(slider, 'Source playhead');
        await slider.focus(); const start = Number(await slider.inputValue()); await page.keyboard.press('ArrowRight');
        assert(Number(await slider.inputValue()) > start || start === 6, 'Native slider keyboard seek failed');
        await button(page, 'Zoom timeline in').click();
        const localTimeline = await page.locator('.va-timeline-scroll').evaluate(node => {
          const before = node.scrollLeft; node.scrollLeft = node.scrollWidth;
          return { clientWidth: node.clientWidth, scrollWidth: node.scrollWidth, scrollLeft: node.scrollLeft, before, overflowX: getComputedStyle(node).overflowX };
        });
        assert(localTimeline.scrollWidth > localTimeline.clientWidth && localTimeline.scrollLeft > 0, 'Timeline zoom lacks local horizontal scroll');
        await audit(player, 'Reference video player');
        const playerGeometry = await player.evaluate(node => ({ rect: node.getBoundingClientRect().toJSON(), maxBlockSize: getComputedStyle(node).maxBlockSize, controls: node.controls, videoWidth: node.videoWidth, videoHeight: node.videoHeight }));
        assert(playerGeometry.controls && playerGeometry.videoWidth === 160);
        await page.locator('.va-timeline-scroll').evaluate(node => { node.scrollLeft = 0; });
        await player.scrollIntoViewIfNeeded();
        return { controls, localTimeline, player: playerGeometry };
      });
      await surface('analysis-graph', async () => {
        await navigate('Analysis');
        await page.getByLabel('Analysis scope', { exact: true }).selectOption('content_browsed_video');
        await expect(page.getByRole('heading', { name: 'Key insights', exact: true })).toBeVisible();
        await expect(page.locator('.va-key-insights .va-insight-copy h3')).toHaveCount(1);
        const sourceButton = page.locator('.va-key-insights .va-sources button').first();
        const controls = [await audit(sourceButton, 'Insight source'), await audit(button(page, 'View as list'), 'View as list')];
        const graph = await page.locator('.logic-viewport').evaluate(node => ({ clientWidth: node.clientWidth, scrollWidth: node.scrollWidth, clientHeight: node.clientHeight, scrollHeight: node.scrollHeight, overflowX: getComputedStyle(node).overflowX }));
        const labels = await page.locator('.logic-node strong').evaluateAll(nodes => nodes.map(node => ({ text: node.textContent, fontSize: getComputedStyle(node).fontSize, scrollHeight: node.scrollHeight, clientHeight: node.clientHeight })));
        assert.equal(labels.length, 3); assert(labels.every(label => label.clientHeight >= label.scrollHeight), 'Graph label text is clipped');
        await page.locator('.logic-viewport').scrollIntoViewIfNeeded();
        assert.equal((await getProject(page)).active_content_id, before.active_content_id, 'Analysis scope changed planned Video');
        return { controls, graph, labels };
      });
      await surface('analysis-list-source', async () => {
        await button(page, 'View as list').click();
        const list = page.getByRole('list', { name: 'Structure as list', exact: true });
        await expect(list.locator('> li')).toHaveCount(3);
        const controls = [await audit(list.locator('.va-structure-list-title').first(), 'First structure label')];
        await page.locator('.va-key-insights .va-sources button').first().click();
        await expect(page.getByLabel('Evidence revision', { exact: true })).toHaveValue('1');
        await expect(page.getByLabel('Reference video player', { exact: true })).toBeVisible();
        controls.push(await audit(page.locator('.va-back-to-pool'), 'Back to Analysis'));
        await page.locator('.va-back-to-pool').click();
        await expect(list).toBeVisible(); await list.scrollIntoViewIfNeeded();
        return { controls, historicalEvidenceRevision: 1, orderedListItems: 3 };
      });
      await surface('content-plan', async () => {
        await navigate('Content plan');
        const controls = [await audit(button(page, 'Plan a video'), 'Plan a video')];
        await button(page, 'Plan a video').click();
        const dialog = page.getByRole('dialog', { name: 'Plan a video', exact: true });
        controls.push(...await modalAudit(dialog, 'Plan a video'));
        await expect(dialog.getByLabel('Series', { exact: true })).toHaveValue('');
        await page.keyboard.press('Escape'); await expect(dialog).not.toBeVisible();
        await expect(button(page, 'Plan a video')).toBeFocused();
        const open = button(page, 'Open Production');
        controls.push(await audit(open, 'Open Production'));
        await open.scrollIntoViewIfNeeded();
        return { controls, standaloneDefault: true };
      });
      await surface('production', async () => {
        await navigate('Production');
        await expect(page.getByRole('heading', { name: 'The planned Video', exact: true })).toBeVisible();
        const save = button(page, 'Save sheet'), exportButton = button(page, 'Export sheet');
        const controls = [await audit(save, 'Save sheet'), await audit(exportButton, 'Export sheet')];
        const localSheet = await page.locator('.va-sheet-scroll').evaluate(node => {
          node.scrollLeft = node.scrollWidth;
          return { clientWidth: node.clientWidth, scrollWidth: node.scrollWidth, scrollLeft: node.scrollLeft, overflowX: getComputedStyle(node).overflowX };
        });
        assert(localSheet.scrollWidth <= localSheet.clientWidth || localSheet.scrollLeft > 0, 'Overflowing storyboard table must scroll locally');
        const notes = page.getByLabel('Shot 01 Production Notes', { exact: true });
        const text = `Native browser zoom QA ${prefix} run ${runId}; human-authored saved row.`;
        await notes.fill(text); await capture(`${prefix}-production-table.png`); await save.click(); await expect(save).toBeDisabled();
        const downloadPromise = page.waitForEvent('download'); await exportButton.click(); const download = await downloadPromise;
        const downloadPath = join(folder, `${prefix}-sheet.csv`); await download.saveAs(downloadPath);
        assert(readFileSync(downloadPath, 'utf8').includes(text), 'Export did not use the saved human edit');
        const sheet = (await getProject(page)).packs.at(-1);
        assert.equal(sheet.shots[0].notes, text);
        await page.locator('.va-sheet-scroll').evaluate(node => { node.scrollLeft = 0; });
        await save.scrollIntoViewIfNeeded();
        return { controls, localSheet, savedRevision: sheet.revision, export: `${prefix}-sheet.csv` };
      });
      await surface('dashboard-dialog', async () => {
        await button(page, 'All projects').click();
        const trigger = button(page, 'New project');
        const controls = [await audit(trigger, 'New project')]; await trigger.click();
        const dialog = page.getByRole('dialog', { name: 'Create a project', exact: true });
        controls.push(...await modalAudit(dialog, 'Create project'));
        await dialog.getByLabel('Project name', { exact: true }).fill('Synthetic name only; not created');
        controls.push(await audit(dialog.getByRole('button', { name: 'Create project', exact: true }), 'Create project'));
        await capture(`${prefix}-dashboard-dialog-open.png`);
        await page.keyboard.press('Escape'); await expect(dialog).not.toBeVisible(); await expect(trigger).toBeFocused();
        return { controls, nativeModalFocus: 'passed' };
      });
      assert.deepEqual((await getProject(page)).jobs, [], 'An offline UI probe unexpectedly submitted processing');
    }
  } finally { await context.close(); rmSync(profile, { recursive: true, force: true }); }
}
for (const [width, height] of windows) await runContext(width, height, factors);
if (!process.env.VIDEO_ANATOMY_QA_SKIP_NARROW) await runContext(390, 844, [1], true);
writeFileSync(join(folder, 'native-full-receipts.json'), JSON.stringify({ receipts, failures, prohibited }, null, 2) + '\n');
assert.equal(prohibited.length, 0, 'A probe attempted a processing request');
console.log(`Workspace zoom checks: ${receipts.length - failures.length}/${receipts.length} passed; failures=${failures.length}`);
if (failures.length) process.exitCode = 1;
