import { defineConfig } from '@playwright/test';
import { existsSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const dataDirectory = mkdtempSync(join(tmpdir(), 'video-anatomy-provider-e2e-'));
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? (existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);

// Real application/services with local deterministic provider responses. No paid calls.
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/providers.spec.ts',
  outputDir: 'test-results/providers',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5175', browserName: 'chromium', headless: true,
    launchOptions: executablePath ? { executablePath } : {},
    screenshot: 'only-on-failure', trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: '.venv/bin/python -m uvicorn scripts.mock_provider_server:app --host 127.0.0.1 --port 8012',
      cwd: root, url: 'http://127.0.0.1:8012/api/health',
      env: { VIDEO_ANATOMY_DATA_DIR: dataDirectory, OPENAI_API_KEY: '', RUN_LIVE_MODEL_TESTS: '0' },
      timeout: 30_000, reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --port 5175', url: 'http://127.0.0.1:5175',
      env: { API_PROXY_TARGET: 'http://127.0.0.1:8012', VITE_LEGACY_WORKSPACE: '1' },
      timeout: 30_000, reuseExistingServer: false,
    },
  ],
});
