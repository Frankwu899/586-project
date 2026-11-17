// Read-only UI check against a local synthetic project with pending brief changes.
// Uses Chromium's actual Page zoom; no CSS zoom, viewport or pinch emulation.
/* global chrome, requestAnimationFrame, devicePixelRatio, innerWidth, innerHeight,
          outerWidth, outerHeight, visualViewport, document, getComputedStyle */
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { chromium, expect } from '@playwright/test';

const [baseURL, projectId, output] = process.argv.slice(2);
if (!baseURL || !projectId || !output) {
  throw new Error('Usage: node frontend/scripts/check-overview-native-zoom.mjs LOCAL_URL PROJECT_ID OUTPUT_DIR');
}
const folder = resolve(output);
mkdirSync(folder, { recursive: true });
const receipts = [];
for (const [width, height] of [[1440, 900], [1280, 800]]) {
  const profile = mkdtempSync(join(tmpdir(), 'overview-native-zoom-'));
  const context = await chromium.launchPersistentContext(profile, {
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? '/usr/bin/chromium',
    headless: true, viewport: null,
    args: ['--no-sandbox', '--disable-gpu', `--window-size=${width},${height}`],
  });
  try {
    const settings = context.pages()[0];
    await settings.goto('chrome://settings/appearance');
    await settings.waitForFunction(() => typeof chrome.settingsPrivate?.setDefaultZoom === 'function');
    const page = await context.newPage();
    await page.goto(`${baseURL}/?project=${encodeURIComponent(projectId)}`);
    await expect(page.getByLabel('Describe your assignment')).toBeVisible();
    const cdp = await context.newCDPSession(page);
    const capture = async name => {
      await page.bringToFront();
      await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))));
      // Playwright's normal screenshot clip assumes an emulated DPR. Capture the
      // physical tab surface directly after changing native browser zoom.
      const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false });
      writeFileSync(join(folder, name), Buffer.from(data, 'base64'));
    };
    for (const factor of [1, 1.25, 1.5, 2]) {
      const observed = await settings.evaluate(factor => new Promise(resolve => {
        chrome.settingsPrivate.setDefaultZoom(factor, () => chrome.settingsPrivate.getDefaultZoom(resolve));
      }), factor);
      await page.waitForFunction(factor => Math.abs(devicePixelRatio - factor) < .001, factor);
      const dimensions = await page.evaluate(() => ({
        innerWidth, innerHeight, outerWidth, outerHeight, devicePixelRatio,
        visualViewportScale: visualViewport.scale,
        cssZoom: getComputedStyle(document.documentElement).zoom,
        scrollWidth: document.documentElement.scrollWidth,
      }));
      assert(Math.abs(observed - factor) < .001);
      assert.equal(dimensions.outerWidth, width);
      assert.equal(dimensions.outerHeight, height);
      assert.equal(dimensions.visualViewportScale, 1);
      assert.equal(dimensions.cssZoom, '1');
      assert(dimensions.scrollWidth <= dimensions.innerWidth + 1);
      const send = page.getByRole('button', { name: 'Send message', exact: true });
      await send.scrollIntoViewIfNeeded();
      const bounds = await send.boundingBox();
      assert(bounds.x >= 0 && bounds.x + bounds.width <= dimensions.innerWidth + 1);
      assert(bounds.y >= 0 && bounds.y + bounds.height <= dimensions.innerHeight + 1);
      assert(await send.evaluate(button => {
        const box = button.getBoundingClientRect();
        return button.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));
      }));
      const lastMessage = page.locator('.va-message').last();
      await expect(lastMessage).toBeVisible();
      await lastMessage.scrollIntoViewIfNeeded();
      const message = await lastMessage.boundingBox();
      const composer = await page.locator('.va-composer').boundingBox();
      assert(message.y + message.height <= composer.y + 1);
      const view = page.getByRole('button', { name: 'View brief' });
      const narrow = await view.isVisible();
      if (narrow) await view.click();
      const reviewTrigger = page.getByRole('button', { name: /^Review changes \(\d+\)$/ });
      await reviewTrigger.click();
      const dialog = page.getByRole('dialog', { name: 'Review brief changes', exact: true });
      await expect(dialog).toBeVisible();
      await expect(dialog.locator('.va-review-values').first()).toBeVisible();
      for (let i = 0; i < 10; i++) {
        await page.keyboard.press('Tab');
        // Native Chromium may visit browser chrome between Tab cycles. It must
        // never focus an inert background DOM control while the page has focus.
        assert(await dialog.evaluate(node => !document.hasFocus() || node.contains(document.activeElement)));
      }
      await send.evaluate(button => button.focus());
      assert(await dialog.evaluate(node => !document.hasFocus() || node.contains(document.activeElement)));
      if (width === 1440 && factor === 1) await capture('brief-review-desktop.png');
      await page.keyboard.press('Escape');
      await expect(dialog).not.toBeVisible();
      await expect(narrow ? view : reviewTrigger).toBeFocused();
      await page.getByLabel('Describe your assignment').scrollIntoViewIfNeeded();
      const screenshot = `overview-native-${width}x${height}-${factor * 100}.png`;
      await capture(screenshot);
      const metrics = await cdp.send('Page.getLayoutMetrics');
      assert(Math.abs(metrics.visualViewport.zoom - factor) < .001);
      const receipt = { requestedZoom: factor, settingsGetDefaultZoom: observed,
        windowRequested: [width, height], browserVersion: context.browser().version(),
        narrowBrief: narrow, ...dimensions, screenshot,
        checks: ['no document horizontal overflow', 'Send reachable and unobscured',
          'composer does not cover last message', 'Brief review readable',
          'modal background inert', 'Escape restores focus'] };
      receipts.push(receipt);
      console.log(JSON.stringify(receipt));
    }
  } finally {
    await context.close();
    rmSync(profile, { recursive: true, force: true });
  }
}
writeFileSync(join(folder, 'native-zoom-receipts.json'), JSON.stringify(receipts, null, 2) + '\n');
