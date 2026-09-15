import { execFileSync, spawn } from 'node:child_process';
import { once } from 'node:events';
import { cp, mkdir, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, expect } from '@playwright/test';

const root = fileURLToPath(new URL('../', import.meta.url));
const args = process.argv.slice(2);
const installedIndex = args.indexOf('--installed');
const release = args.includes('--release');
const missingBackend = args.includes('--missing-backend');
const crash = args.includes('--crash');
const source = installedIndex >= 0 ? path.resolve(args[installedIndex + 1])
  : path.join(root, 'artifacts', release ? 'desktop' : 'desktop-debug', 'VisionStudio.exe');
if (!existsSync(source)) throw new Error('Build the desktop first with npm run build:desktop or npm run build:installer.');
const testRoot = path.join(process.env.LOCALAPPDATA, 'VisionStudio', 'qa', `Desktop ${crypto.randomUUID()}`);
const relocated = path.join(testRoot, 'Relocated application');
await mkdir(relocated, { recursive: true });
let executable = source;
if (installedIndex < 0) {
  if (missingBackend) await cp(source, path.join(relocated, 'VisionStudio.exe'));
  else await cp(path.dirname(source), relocated, { recursive: true });
  executable = path.join(relocated, 'VisionStudio.exe');
}
const environment = {};
for (const key of ['SystemRoot', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'PROGRAMDATA', 'PROCESSOR_ARCHITECTURE', 'PROCESSOR_IDENTIFIER']) {
  const match = Object.keys(process.env).find(name => name.toLowerCase() === key.toLowerCase());
  if (match) environment[key] = process.env[match];
}
environment.PATH = path.join(environment.SystemRoot, 'System32');
environment.VISION_STUDIO_DATA_DIR = path.join(testRoot, 'Runtime data');
const listener = net.createServer();
listener.listen(0, '127.0.0.1');
await once(listener, 'listening');
const port = listener.address().port;
await new Promise((resolve) => listener.close(resolve));
const child = spawn(executable, [], {
  cwd: testRoot,
  env: { ...environment, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${port}` },
  stdio: 'ignore',
});
const exited = new Promise((resolve, reject) => {
  child.once('exit', (code) => resolve(code));
  child.once('error', reject);
});
let browser;
let page;
let backendUrl;
try {
  await expect.poll(async () => {
    try { return (await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(1000) })).ok; }
    catch { return false; }
  }, { timeout: 35_000 }).toBe(true);
  browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
  await expect.poll(() => browser.contexts()[0].pages().length).toBeGreaterThan(0);
  page = browser.contexts()[0].pages()[0];
  await expect(page.getByRole('status')).toHaveText(missingBackend ? 'Backend Disconnected' : 'Backend Connected', { timeout: 20_000 });
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  const desktop = await page.evaluate(() => window.__TAURI_INTERNALS__.invoke('desktop_info'));
  expect(desktop.mode).toBe('packaged');
  if (missingBackend) {
    await expect(page.getByRole('alert')).toContainText('The bundled backend is missing.');
  } else {
    backendUrl = await page.evaluate(() => window.__TAURI_INTERNALS__.invoke('backend_url'));
    expect(new URL(backendUrl).hostname).toBe('127.0.0.1');
    const processes = JSON.parse(execFileSync('powershell.exe', ['-NoProfile', '-Command',
      `ConvertTo-Json -Compress -InputObject @(Get-CimInstance Win32_Process -Filter 'ParentProcessId = ${child.pid}' | Select-Object Name, ExecutablePath)`,
    ], { encoding: 'utf8', windowsHide: true }));
    const bundledProcess = processes.find(process => process.Name === 'backend.exe');
    expect(bundledProcess?.ExecutablePath.toLowerCase()).toBe(path.join(path.dirname(executable), 'backend/backend.exe').toLowerCase());
  }
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByText('English', { exact: true })).toBeVisible();
  if (!missingBackend) await expect(page.locator('.storage-path:not(.database-path)')).toHaveText(environment.VISION_STUDIO_DATA_DIR);
  await expect(page.getByRole('button', { name: 'Open logs folder' })).toBeVisible();
  if (!missingBackend) {
    await expect(page.locator('.database-path')).toContainText('visionstudio.db');
    await page.getByRole('button', { name: 'Projects', exact: true }).click();
    await page.getByRole('button', { name: 'New project' }).first().click();
    await page.getByLabel('Project name').fill('Desktop QA project');
    await page.getByLabel(/Description/).fill('Bundled project persistence');
    await page.getByRole('button', { name: 'Create project', exact: true }).click();
    await page.getByRole('button', { name: 'Open Desktop QA project', exact: true }).click();
    await expect(page.locator('.project-workspace .project-name')).toHaveText('Desktop QA project');
    const imageFixtures = path.join(root, 'tests/fixtures/images');
    await page.getByLabel('Images to import').setInputFiles(['sample.jpg', 'sample.jpeg', 'sample.png', 'sample.webp'].map(name => path.join(imageFixtures, name)));
    await expect(page.getByText('4 imported · 0 duplicates skipped · 0 failed')).toBeVisible({ timeout: 20_000 });
    await expect.poll(() => page.locator('.import-results img').evaluateAll(images => images.every(image => image.naturalWidth > 0))).toBe(true);
    // CDP delivers file drag events to the actual WebView2 input handler.
    await page.locator('.import-dropzone').scrollIntoViewIfNeeded();
    const dropBounds = await page.locator('.import-dropzone').boundingBox();
    const drag = await page.context().newCDPSession(page);
    const dragData = { items: [], files: [path.join(imageFixtures, 'sample.png')], dragOperationsMask: 1 };
    for (const type of ['dragEnter', 'dragOver', 'drop']) {
      await drag.send('Input.dispatchDragEvent', { type, x: dropBounds.x + dropBounds.width / 2, y: dropBounds.y + dropBounds.height / 2, data: dragData });
    }
    await expect(page.getByText('0 imported · 1 duplicates skipped · 0 failed')).toBeVisible();
    await drag.detach();
    const batchDirectory = path.join(testRoot, 'Image fixtures');
    execFileSync(path.join(root, '.venv/Scripts/python.exe'), [path.join(root, 'scripts/make-image-fixtures.py'), batchDirectory], { windowsHide: true });
    await page.getByLabel('Images to import').setInputFiles(Array.from({ length: 105 }, (_, index) => path.join(batchDirectory, `frame-${String(index).padStart(3, '0')}.png`)));
    await expect(page.getByText('105 imported · 0 duplicates skipped · 0 failed')).toBeVisible({ timeout: 45_000 });
    await expect(page.getByText('109 images in this project')).toBeVisible();
    await page.getByRole('button', { name: 'View dataset gallery', exact: true }).click();
    await expect(page.locator('.gallery-card')).toHaveCount(60);
    await expect(page.getByText('Images 1–60 of 109')).toBeVisible();
    await page.getByRole('button', { name: 'Next page', exact: true }).click();
    await expect(page.locator('.gallery-card')).toHaveCount(49);
    await page.getByRole('button', { name: 'Open image frame-104.png', exact: true }).click();
    await expect.poll(() => page.locator('.gallery-original').evaluate(image => image.naturalWidth)).toBe(64);
    await page.getByRole('button', { name: 'Close preview', exact: true }).click();
    await page.getByRole('button', { name: 'Delete image frame-104.png', exact: true }).click();
    await page.getByRole('button', { name: 'Delete image', exact: true }).click();
    await expect(page.locator('.gallery-card')).toHaveCount(48);
    await expect(page.getByText('108 images in this project')).toBeVisible();
    await page.reload();
    await expect(page.getByText('Images 1–60 of 108')).toBeVisible();
    await page.locator('.gallery-grid').scrollIntoViewIfNeeded();
    await expect.poll(() => page.locator('.gallery-card img').first().evaluate(image => image.naturalWidth)).toBeGreaterThan(0);
    await page.screenshot({ path: path.join(root, 'test-results/desktop-gallery.png') });
    await page.getByRole('button', { name: 'Projects', exact: true }).click();
    await page.getByRole('button', { name: 'Open Desktop QA project', exact: true }).click();
    await page.screenshot({ path: path.join(root, 'test-results/desktop-image-import.png'), fullPage: true });
    await page.reload();
    await expect(page.locator('.project-workspace .project-name')).toHaveText('Desktop QA project');
    await expect(page.getByText('108 images in this project')).toBeVisible();
    await page.getByRole('button', { name: 'Back to projects', exact: true }).click();
    await page.getByRole('button', { name: 'Rename Desktop QA project', exact: true }).click();
    await page.getByLabel('Project name').fill('Desktop QA renamed');
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await expect(page.locator('.project-card h2')).toHaveText('Desktop QA renamed');
    await page.screenshot({ path: path.join(root, 'test-results/desktop-projects.png'), fullPage: true });
    await page.getByRole('button', { name: 'Delete Desktop QA renamed', exact: true }).click();
    await page.getByRole('button', { name: 'Delete project', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Start your first project.' })).toBeVisible();
  }
  await page.getByRole('button', { name: 'Dashboard', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Workspace overview' })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await mkdir(path.join(root, 'test-results'), { recursive: true });
  await page.screenshot({ path: path.join(root, `test-results/desktop${missingBackend ? '-missing-backend' : ''}.png`), fullPage: true });
  // Invoke the public Tauri close command: this exercises the normal window
  // close and RunEvent::Exit path, rather than terminating the process.
  if (crash) child.kill();
  else await page.evaluate(() => { window.__TAURI_INTERNALS__.invoke('plugin:window|close', { label: 'main' }); });
  const exitCode = await Promise.race([
    exited,
    new Promise((_, reject) => {
      const timer = setTimeout(() => reject(new Error('Desktop did not exit after closing its window.')), 10_000);
      timer.unref();
    }),
  ]);
  if (!crash) expect(exitCode).toBe(0);
  if (backendUrl) await expect.poll(async () => {
    try { await fetch(`${backendUrl}/health`, { signal: AbortSignal.timeout(1000) }); return true; }
    catch { return false; }
  }, { timeout: 5000 }).toBe(false);
  await writeFile(path.join(testRoot, 'report.json'), JSON.stringify({
    passed: true, checked_at_utc: new Date().toISOString(), executable,
    missing_backend: missingBackend, parent_crash: crash, project_crud_verified: !missingBackend, image_import_verified: !missingBackend, gallery_verified: !missingBackend,
    clean_machine_verified: false, mode: desktop.mode, backend_url: backendUrl ?? null,
  }, null, 2));
  console.log(`Desktop passed: ${missingBackend ? 'English missing-backend recovery screen' : crash ? 'parent crash and backend cleanup' : 'relocated/installed application, bundled backend, English shell, normal close and cleanup'}.`);
  console.log(`Desktop QA report: ${path.join(testRoot, 'report.json')}`);
} finally {
  if (browser) await browser.close().catch(() => {});
  if (child.exitCode === null) child.kill();
}
