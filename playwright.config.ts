import { mkdirSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { defineConfig } from '@playwright/test';

// A disposable workspace per run, so project tests never touch real developer data.
const qaRoot = process.env.LOCALAPPDATA ? join(process.env.LOCALAPPDATA, 'VisionStudio', 'qa') : tmpdir();
mkdirSync(qaRoot, { recursive: true });
const dataRoot = process.env.VISION_STUDIO_E2E_DIR ??= mkdtempSync(join(qaRoot, 'Browser '));

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:1420', browserName: 'chromium', locale: 'id-ID', viewport: { width: 1280, height: 900 }, screenshot: 'only-on-failure' },
  webServer: [
    { command: 'npm run dev:backend', url: 'http://127.0.0.1:8765/health', reuseExistingServer: false, timeout: 30_000, env: { VISION_STUDIO_DATA_DIR: dataRoot } },
    { command: 'npm run dev:frontend', url: 'http://127.0.0.1:1420', reuseExistingServer: false, timeout: 30_000 },
  ],
});
