import { defineConfig } from '@playwright/test';
import { existsSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';

const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? (existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);

export default defineConfig({
  testDir: './shared-e2e',
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8018',
    httpCredentials: { username: 'team', password: 'test-only-team-password-with-32-characters' },
    launchOptions: executablePath ? { executablePath } : {},
    trace: 'retain-on-failure',
  },
  webServer: {
    command: '.venv/bin/python -m scripts.shared_server',
    cwd: resolve(import.meta.dirname, '..'),
    url: 'http://127.0.0.1:8018/healthz',
    env: {
      VIDEO_ANATOMY_DATA_DIR: mkdtempSync(join(tmpdir(), 'video-anatomy-shared-')),
      VIDEO_PUBLIC_ORIGIN: 'http://127.0.0.1:8018',
      VIDEO_TEAM_USERNAME: 'team',
      VIDEO_TEAM_PASSWORD: 'test-only-team-password-with-32-characters',
      OPENAI_API_KEY: 'sk-fake-shared-browser-test',
      PORT: '8018',
    },
    reuseExistingServer: false,
  },
});
