import { mkdirSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { defineConfig } from '@playwright/test';

// A disposable workspace per run, so project tests never touch real developer data.
const qaRoot = process.env.LOCALAPPDATA ? join(process.env.LOCALAPPDATA, 'VisionStudio', 'qa') : tmpdir();
mkdirSync(qaRoot, { recursive: true });
const dataRoot = process.env.VISION_STUDIO_E2E_DIR ??= mkdtempSync(join(qaRoot, 'Browser '));
const backendPort = process.env.VISION_STUDIO_TEST_BACKEND_PORT ?? '18765';
const frontendPort = process.env.VISION_STUDIO_TEST_FRONTEND_PORT ?? '11420';
const backendUrl = process.env.VISION_STUDIO_TEST_API = `http://127.0.0.1:${backendPort}`;
const frontendUrl = `http://127.0.0.1:${frontendPort}`;

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  use: { baseURL: frontendUrl, browserName: 'chromium', locale: 'id-ID', viewport: { width: 1280, height: 900 }, screenshot: 'only-on-failure' },
  webServer: [
    { command: `"${join('.venv', 'Scripts', 'python.exe')}" backend/run_backend.py --port ${backendPort}`, url: `${backendUrl}/health`, reuseExistingServer: false, timeout: 60_000, env: { VISION_STUDIO_DATA_DIR: dataRoot } },
    { command: `node node_modules/vite/bin/vite.js frontend --port ${frontendPort}`, url: frontendUrl, reuseExistingServer: false, timeout: 30_000, env: { VITE_API_BASE_URL: `${frontendUrl}/qa-api`, VISION_STUDIO_TEST_BACKEND_PORT: backendPort } },
  ],
});
