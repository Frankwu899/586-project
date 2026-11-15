import { defineConfig } from '@playwright/test';
import { existsSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const dataDirectory = process.env.VIDEO_ANATOMY_E2E_DATA_DIR ?? mkdtempSync(join(tmpdir(), 'video-anatomy-project-e2e-'));
process.env.VIDEO_ANATOMY_E2E_DATA_DIR = dataDirectory;
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? (existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);

export default defineConfig({
  testDir: './e2e', testMatch: ['**/project-workspace.spec.ts', '**/project-regressions.spec.ts', '**/project-reliability.spec.ts'],
  outputDir: 'test-results/projects', timeout: 90_000,
  expect: { timeout: 15_000 }, fullyParallel: false, workers: 1, reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5176', browserName: 'chromium', headless: true,
    launchOptions: executablePath ? { executablePath } : {},
    screenshot: 'only-on-failure', trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: '.venv/bin/python -m uvicorn backend.app.api:app --host 127.0.0.1 --port 8013',
      cwd: root, url: 'http://127.0.0.1:8013/api/health',
      env: { VIDEO_ANATOMY_DATA_DIR: dataDirectory, OPENAI_API_KEY: '', RUN_LIVE_MODEL_TESTS: '0' },
      timeout: 30_000, reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --port 5176', url: 'http://127.0.0.1:5176',
      env: { API_PROXY_TARGET: 'http://127.0.0.1:8013', VITE_LEGACY_WORKSPACE: '0' },
      timeout: 30_000, reuseExistingServer: false,
    },
  ],
});
