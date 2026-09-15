import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

const API = process.env.VISION_STUDIO_TEST_API ?? 'http://127.0.0.1:8765';
let project: string;
let definition: string;
let images: string[];
test.beforeEach(async ({ request, page }) => {
  project = (await (await request.post(`${API}/projects`, { data: { name: `Export ${crypto.randomUUID()}` } })).json()).id;
  definition = (await (await request.post(`${API}/projects/${project}/classes`, { data: { name: 'Pallet' } })).json()).id;
  images = [];
  for (const file of ['sample.png', 'sample.jpg']) {
    images.push((await (await request.post(`${API}/projects/${project}/datasets/images?filename=${file}`, { data: readFileSync(`tests/fixtures/images/${file}`) })).json()).image.id);
  }
  await page.goto(`/#Dataset/${project}`);
});
test.afterEach(async ({ request }) => { await request.delete(`${API}/projects/${project}`); });

test('validates, blocks unannotated images, exports a complete snapshot and revalidates edits', async ({ page, request }) => {
  const panel = page.getByRole('region', { name: 'Dataset validation and export' });
  await panel.getByRole('button', { name: 'Export YOLO dataset', exact: true }).click();
  await expect(panel.getByRole('status')).toHaveText('Dataset needs attention');
  await expect(panel.getByRole('heading', { name: '2 validation issues' })).toBeVisible();
  for (const image of images) {
    const response = await request.post(`${API}/projects/${project}/datasets/images/${image}/annotations`, { data: { id: crypto.randomUUID().replaceAll('-', ''), class_id: definition, center_x: .5, center_y: .5, width: .4, height: .3, expected_revision: 0 } });
    expect(response.status()).toBe(201);
  }
  await panel.getByRole('button', { name: 'Validate dataset', exact: true }).click();
  await expect(panel.getByRole('status')).toHaveText('Dataset valid');
  await panel.getByRole('button', { name: 'Export YOLO dataset', exact: true }).click();
  await expect(panel.getByRole('heading', { name: 'Dataset exported', exact: true })).toBeVisible();
  await expect(panel.getByText('1 training images / 1 validation images', { exact: true })).toBeVisible();
  const path = await panel.getByLabel('Export folder', { exact: true }).inputValue();
  expect(existsSync(join(path, 'data.yaml'))).toBe(true);
  const manifest = JSON.parse(readFileSync(join(path, 'manifest.json'), 'utf8'));
  expect(manifest.images).toHaveLength(2);
  for (const row of manifest.images) expect(existsSync(join(path, 'labels', row.split, `${row.image_id}.txt`))).toBe(true);
  await page.setViewportSize({ width: 900, height: 640 });
  await panel.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await panel.screenshot({ path: 'test-results/dataset-export.png' });
  const url = `${API}/projects/${project}/datasets/images/${images[0]}/annotations`;
  const state = await (await request.get(url)).json();
  await request.delete(`${url}/${state.annotations[0].id}?expected_revision=1`);
  await panel.getByRole('button', { name: 'Export YOLO dataset', exact: true }).click();
  await expect(panel.getByRole('status')).toHaveText('Dataset needs attention');
  await expect(panel.getByLabel('Export folder', { exact: true })).toHaveCount(0);
  expect(existsSync(join(path, 'data.yaml'))).toBe(true);
});

test('shows request failures and prevents duplicate clicks while checking', async ({ page }) => {
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/datasets/validate', async route => { await pending; await route.abort(); });
  await page.getByRole('button', { name: 'Validate dataset', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Export YOLO dataset', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Validate dataset', exact: true })).toBeDisabled();
  release();
  await expect(page.getByRole('region', { name: 'Dataset validation and export' }).getByRole('alert')).toBeVisible();
  await page.unroute('**/datasets/validate');
  await page.getByRole('button', { name: 'Validate dataset', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Dataset validation and export' }).getByRole('status')).toHaveText('Dataset needs attention');
});
