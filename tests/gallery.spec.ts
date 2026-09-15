import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, test } from '@playwright/test';

const API = 'http://127.0.0.1:8765';
let project: string;
test.beforeEach(async ({ request }) => {
  project = (await (await request.post(`${API}/projects`, { data: { name: `Gallery ${crypto.randomUUID()}` } })).json()).id;
});
test.afterEach(async ({ request }) => { await request.delete(`${API}/projects/${project}`); });

test('opens the original, preserves user names, and confirms deletion', async ({ page, request }) => {
  const name = 'Gambar 日本.png';
  const uploaded = await request.post(`${API}/projects/${project}/datasets/images?filename=${encodeURIComponent(name)}`, { data: readFileSync('tests/fixtures/images/sample.png') });
  const image = (await uploaded.json()).image;
  await page.goto(`/#Dataset/${project}`);
  await expect(page.locator('.gallery-card')).toHaveCount(1);
  await expect(page.locator('.gallery-card')).toContainText('640 × 320 px');
  await expect(page.locator('.gallery-card')).toContainText('Not annotated');
  await page.getByRole('button', { name: `Open image ${name}`, exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Image preview' })).toBeVisible();
  await expect.poll(() => page.locator('.gallery-original').evaluate((image: HTMLImageElement) => image.naturalWidth)).toBe(640);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: `Open image ${name}`, exact: true })).toBeFocused();
  await page.getByRole('button', { name: `Delete image ${name}`, exact: true }).click();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.locator('.gallery-card')).toHaveCount(1);
  await page.getByRole('button', { name: `Delete image ${name}`, exact: true }).click();
  await page.getByRole('button', { name: 'Delete image', exact: true }).click();
  await expect(page.locator('.gallery-card')).toHaveCount(0);
  await expect(page.getByText('0 images in this project')).toBeVisible();
  expect((await request.get(`${API}/projects/${project}/datasets/images/${image.id}/original`)).status()).toBe(404);
  await page.reload();
  await expect(page.getByText('No images yet. Import images below to start your dataset.')).toBeVisible();
});

test('pages through 105 images with bounded cards, scrolling, and an original preview', async ({ page, request }, testInfo) => {
  const folder = testInfo.outputPath('fixtures');
  execFileSync(path.resolve('.venv/Scripts/python.exe'), [path.resolve('scripts/make-image-fixtures.py'), folder], { windowsHide: true });
  for (let i = 0; i < 105; i++) {
    const name = `frame-${String(i).padStart(3, '0')}.png`;
    await request.post(`${API}/projects/${project}/datasets/images?filename=${name}`, { data: readFileSync(path.join(folder, name)) });
  }
  await page.setViewportSize({ width: 900, height: 640 });
  await page.goto(`/#Dataset/${project}`);
  await expect(page.locator('.gallery-card')).toHaveCount(60);
  await expect(page.getByText('Images 1–60 of 105')).toBeVisible();
  await page.locator('.gallery-card').last().scrollIntoViewIfNeeded();
  await expect.poll(() => page.locator('.gallery-card').last().locator('img').evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(page.locator('.gallery-card')).toHaveCount(45);
  await expect(page.getByText('Images 61–105 of 105')).toBeVisible();
  await page.getByRole('button', { name: 'Open image frame-104.png', exact: true }).click();
  await expect.poll(() => page.locator('.gallery-original').evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(64);
  await page.getByRole('button', { name: 'Close preview', exact: true }).click();
  await page.getByRole('button', { name: 'Previous page', exact: true }).click();
  await expect(page.getByText('Images 1–60 of 105')).toBeVisible();
  await page.screenshot({ path: 'test-results/dataset-gallery.png' });
});

test('refreshes after import and recovers gallery, preview, and deletion failures', async ({ page }) => {
  const route = `**/projects/${project}/datasets/images?offset=*`;
  await page.route(route, request => request.abort());
  await page.goto(`/#Dataset/${project}`);
  await expect(page.locator('.dataset-gallery [role="alert"]')).toBeVisible();
  await page.unroute(route);
  await page.locator('.dataset-gallery').getByRole('button', { name: 'Try again', exact: true }).click();
  await page.getByLabel('Images to import').setInputFiles('tests/fixtures/images/sample.png');
  await expect(page.locator('.gallery-card')).toHaveCount(1);
  await page.route('**/original?*', request => request.abort());
  await page.getByRole('button', { name: 'Open image sample.png', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('The image could not be displayed.');
  await page.unroute('**/original?*');
  await page.getByRole('dialog').getByRole('button', { name: 'Try again', exact: true }).click();
  await expect.poll(() => page.locator('.gallery-original').evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(640);
  await page.keyboard.press('Escape');
  await page.route('**/datasets/images/*', route => route.request().method() === 'DELETE' ? route.abort() : route.continue());
  await page.getByRole('button', { name: 'Delete image sample.png', exact: true }).click();
  await page.getByRole('button', { name: 'Delete image', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('alert')).toBeVisible();
  await page.unroute('**/datasets/images/*');
  await page.getByRole('button', { name: 'Delete image', exact: true }).click();
  await expect(page.locator('.gallery-card')).toHaveCount(0);
  await expect(page.locator('.import-results img')).toHaveCount(0);
});
