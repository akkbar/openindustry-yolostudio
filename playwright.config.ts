import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  use: { baseURL: 'http://127.0.0.1:1420', browserName: 'chromium', locale: 'id-ID', viewport: { width: 1280, height: 900 }, screenshot: 'only-on-failure' },
  webServer: [
    { command: 'npm run dev:backend', url: 'http://127.0.0.1:8765/health', reuseExistingServer: false, timeout: 30_000 },
    { command: 'npm run dev:frontend', url: 'http://127.0.0.1:1420', reuseExistingServer: false, timeout: 30_000 },
  ],
});
