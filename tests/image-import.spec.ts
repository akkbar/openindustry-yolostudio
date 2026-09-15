import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, test } from '@playwright/test';

const API = process.env.VISION_STUDIO_TEST_API ?? 'http://127.0.0.1:8765';
const fixtures = path.resolve('tests/fixtures/images');
let projectId: string;
test.beforeEach(async ({ request, page }) => {
  const response = await request.post(`${API}/projects`, { data: { name: `Image QA ${crypto.randomUUID()}` } });
  projectId = (await response.json()).id;
  await page.goto(`/#Dataset/${projectId}`);
  await expect(page.getByText('0 images in this project')).toBeVisible();
});
test.afterEach(async ({ request }) => {
  await request.delete(`${API}/projects/${projectId}`);
});

test('selects supported files, renders generated thumbnails, and persists the count', async ({ page }) => {
  await page.getByLabel('Images to import').setInputFiles(['sample.jpg', 'sample.jpeg', 'sample.png', 'sample.webp'].map(file => path.join(fixtures, file)));
  await expect(page.getByText('4 imported · 0 duplicates skipped · 0 failed')).toBeVisible();
  await expect(page.getByText('4 images in this project')).toBeVisible();
  await expect(page.locator('.import-results img')).toHaveCount(4);
  await expect.poll(() => page.locator('.import-results img').evaluateAll(images => images.every(image => (image as HTMLImageElement).naturalWidth > 0))).toBe(true);
  await page.screenshot({ path: 'test-results/image-import.png', fullPage: true });
  await page.reload();
  await expect(page.getByText('4 images in this project')).toBeVisible();
});

test('accepts dropped files and skips duplicates', async ({ page }) => {
  const bytes = Array.from(readFileSync(path.join(fixtures, 'sample.png')));
  const transfer = await page.evaluateHandle(data => {
    const transfer = new DataTransfer();
    transfer.items.add(new File([new Uint8Array(data)], 'Dropped image.png', { type: 'image/png' }));
    return transfer;
  }, bytes);
  await page.locator('.import-dropzone').dispatchEvent('drop', { dataTransfer: transfer });
  await expect(page.getByText('1 imported · 0 duplicates skipped · 0 failed')).toBeVisible();
  await page.getByLabel('Images to import').setInputFiles(path.join(fixtures, 'sample.png'));
  await expect(page.getByText('0 imported · 1 duplicates skipped · 0 failed')).toBeVisible();
  await expect(page.getByText('1 image in this project')).toBeVisible();
  await transfer.dispose();
});

test('imports 105 files with progress and keeps the result display bounded', async ({ page }) => {
  test.setTimeout(60_000);
  const directory = path.resolve('test-results/image-batch');
  execFileSync(path.resolve('.venv/Scripts/python.exe'), ['scripts/make-image-fixtures.py', directory]);
  await page.getByLabel('Images to import').setInputFiles(Array.from({ length: 105 }, (_, index) => path.join(directory, `frame-${String(index).padStart(3, '0')}.png`)));
  await expect(page.getByText('105 imported · 0 duplicates skipped · 0 failed')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText('105 images in this project')).toBeVisible();
  await expect(page.getByRole('progressbar')).toHaveAttribute('value', '105');
  await expect(page.locator('.import-results img')).toHaveCount(20);
  await page.reload();
  await expect(page.getByText('105 images in this project')).toBeVisible();
});

test('isolates invalid files and retries a temporary failure without duplicating successful files', async ({ page }) => {
  await page.route('**/datasets/images?*', route => route.abort());
  await page.getByLabel('Images to import').setInputFiles(path.join(fixtures, 'sample.png'));
  await expect(page.getByText('0 imported · 0 duplicates skipped · 1 failed')).toBeVisible();
  await page.unroute('**/datasets/images?*');
  await page.getByRole('button', { name: 'Retry failed files' }).click();
  await expect(page.getByText('1 imported · 0 duplicates skipped · 0 failed')).toBeVisible();
  await page.getByLabel('Images to import').setInputFiles([
    { name: 'broken.png', mimeType: 'image/png', buffer: Buffer.from('not an image') },
    { name: 'readme.txt', mimeType: 'text/plain', buffer: Buffer.from('not supported') },
    { name: 'Valid.webp', mimeType: 'image/webp', buffer: readFileSync(path.join(fixtures, 'sample.webp')) },
  ]);
  await expect(page.getByText('1 imported · 0 duplicates skipped · 2 failed')).toBeVisible();
  await expect(page.getByText('This image is damaged or cannot be decoded. Choose another file.')).toBeVisible();
  await expect(page.getByText('Choose a JPG, JPEG, PNG, or WEBP image.')).toBeVisible();
  await expect(page.getByText('2 images in this project')).toBeVisible();
});

test('imports from the project overview at the minimum desktop width', async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 640 });
  await page.goto(`/#Projects/${projectId}`);
  await page.getByLabel('Images to import').setInputFiles(path.join(fixtures, 'sample.jpg'));
  await expect(page.getByText('1 imported · 0 duplicates skipped · 0 failed')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
