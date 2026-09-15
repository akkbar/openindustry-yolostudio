import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

const API = process.env.VISION_STUDIO_TEST_API ?? 'http://127.0.0.1:8765';
let project: string;
test.beforeEach(async ({ page, request }) => {
  project = (await (await request.post(`${API}/projects`, { data: { name: `Classes ${crypto.randomUUID()}` } })).json()).id;
  await page.goto(`/#Dataset/${project}`);
  await expect(page.getByText('No classes yet. Add your first object class.')).toBeVisible();
});
test.afterEach(async ({ request }) => { await request.delete(`${API}/projects/${project}`); });

test('adds, selects, renames, previews, and deletes without renumbering', async ({ page, request }) => {
  for (const name of ['Banana', 'Pallet']) {
    await page.getByRole('button', { name: 'Add class', exact: true }).click();
    await page.getByLabel('Class name', { exact: true }).fill(name);
    await page.getByRole('dialog').getByRole('button', { name: 'Add class', exact: true }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
  }
  await page.getByRole('button', { name: 'Select class Pallet', exact: true }).click();
  await expect(page.locator('.active-class')).toHaveText('Active class: 1 · Pallet');
  await page.getByRole('button', { name: 'Rename class Pallet', exact: true }).click();
  await page.getByLabel('Class name', { exact: true }).fill('Shipping pallet');
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await page.reload();
  await expect(page.locator('.active-class')).toHaveText('Active class: 1 · Shipping pallet');
  await request.post(`${API}/projects/${project}/datasets/images?filename=sample.png`, { data: readFileSync('tests/fixtures/images/sample.png') });
  await page.getByRole('button', { name: 'Refresh gallery', exact: true }).click();
  await page.getByRole('button', { name: 'Open image sample.png', exact: true }).click();
  await expect(page.locator('.preview-active-class')).toHaveText('Active class: 1 · Shipping pallet');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Delete class Banana', exact: true }).click();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.locator('.class-row')).toHaveCount(2);
  await page.getByRole('button', { name: 'Delete class Banana', exact: true }).click();
  await page.getByRole('button', { name: 'Delete class', exact: true }).click();
  await expect(page.locator('.class-index')).toHaveText(['1']);
  await page.getByRole('button', { name: 'Delete class Shipping pallet', exact: true }).click();
  await page.getByRole('button', { name: 'Delete class', exact: true }).click();
  await expect(page.locator('.active-class')).toHaveText('Active class: No class selected');
  await page.getByRole('button', { name: 'Add class', exact: true }).click();
  await page.getByLabel('Class name', { exact: true }).fill('Crate');
  await page.getByRole('dialog').getByRole('button', { name: 'Add class', exact: true }).click();
  await expect(page.locator('.class-index')).toHaveText(['2']);
});

test('preserves user names, validates duplicates, and fits the minimum width', async ({ page }) => {
  const name = '  Buah 日本 '.padEnd(80, 'x');
  await page.setViewportSize({ width: 900, height: 640 });
  await page.getByRole('button', { name: 'Add class', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Add class', exact: true })).toBeDisabled();
  await page.getByLabel('Class name', { exact: true }).fill(name);
  await page.getByRole('dialog').getByRole('button', { name: 'Add class', exact: true }).click();
  await expect(page.locator('.class-select strong')).toHaveText(name);
  expect(await page.locator('.class-select strong').textContent()).toBe(name);
  await page.getByRole('button', { name: 'Add class', exact: true }).click();
  await page.getByLabel('Class name', { exact: true }).fill(name.trim().toUpperCase());
  await page.getByRole('dialog').getByRole('button', { name: 'Add class', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('A class with this name already exists');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'Add class', exact: true })).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.locator('.class-manager').scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'test-results/class-manager.png' });
});

test('isolates selected classes between projects and persists clear selection', async ({ page, request }) => {
  await request.post(`${API}/projects/${project}/classes`, { data: { name: 'First class' } });
  const other = (await (await request.post(`${API}/projects`, { data: { name: `Other ${crypto.randomUUID()}` } })).json()).id;
  try {
    await request.post(`${API}/projects/${other}/classes`, { data: { name: 'Second class' } });
    await page.reload();
    await expect(page.locator('.active-class')).toContainText('First class');
    await page.getByRole('combobox', { name: 'Project', exact: true }).selectOption(other);
    await expect(page.locator('.active-class')).toContainText('Second class');
    await page.getByRole('button', { name: 'Clear selection', exact: true }).click();
    await expect(page.locator('.active-class')).toHaveText('Active class: No class selected');
    await page.reload();
    await expect(page.locator('.active-class')).toHaveText('Active class: No class selected');
    await page.getByRole('combobox', { name: 'Project', exact: true }).selectOption(project);
    await expect(page.locator('.active-class')).toContainText('First class');
  } finally { await request.delete(`${API}/projects/${other}`); }
});

test('recovers reads without repeating a successful write and retains rejected deletions', async ({ page, request }) => {
  await page.route(`**/projects/${project}/classes`, route => route.request().method() === 'GET' ? route.abort() : route.continue());
  await page.getByRole('button', { name: 'Add class', exact: true }).click();
  await page.getByLabel('Class name', { exact: true }).fill('Saved class');
  await page.getByRole('dialog').getByRole('button', { name: 'Add class', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('.class-manager [role="alert"]')).toBeVisible();
  await page.unroute(`**/projects/${project}/classes`);
  await page.getByRole('button', { name: 'Refresh classes', exact: true }).click();
  await expect(page.locator('.class-row')).toHaveCount(1);
  expect((await (await request.get(`${API}/projects/${project}/classes`)).json()).classes).toHaveLength(1);
  await page.route('**/classes/*', route => route.request().method() === 'DELETE' ? route.fulfill({ status: 409, json: { error: { code: 'class_in_use', message: 'This class is used by annotations. Remove or reassign those annotations before deleting the class.' } } }) : route.continue());
  await page.getByRole('button', { name: 'Delete class Saved class', exact: true }).click();
  await page.getByRole('button', { name: 'Delete class', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('This class is used by annotations.');
  await page.keyboard.press('Escape');
  await expect(page.locator('.class-row')).toHaveCount(1);
});
