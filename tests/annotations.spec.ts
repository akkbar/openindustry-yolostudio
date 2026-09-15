import { readFileSync } from 'node:fs';
import { expect, test, type Page, type APIRequestContext } from '@playwright/test';

const API = process.env.VISION_STUDIO_TEST_API ?? 'http://127.0.0.1:8765';
let project: string;
let classId: string;
let otherClass: string;
let imageId: string;
const route = () => `${API}/projects/${project}/datasets/images/${imageId}/annotations`;
const saved = async (request: APIRequestContext) => (await request.get(route())).json();
async function drag(page: Page, x1: number, y1: number, x2: number, y2: number) {
  const bounds = (await page.locator('.annotation-image-layer').boundingBox())!;
  await page.mouse.move(bounds.x + bounds.width * x1, bounds.y + bounds.height * y1);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width * x2, bounds.y + bounds.height * y2, { steps: 6 });
  await page.mouse.up();
}
async function open(page: Page) {
  await page.getByRole('button', { name: 'Annotate image sample.png', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Annotation editor' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Fit image', exact: true })).toBeEnabled();
}
test.beforeEach(async ({ page, request }) => {
  project = (await (await request.post(`${API}/projects`, { data: { name: `Annotation ${crypto.randomUUID()}` } })).json()).id;
  classId = (await (await request.post(`${API}/projects/${project}/classes`, { data: { name: 'Banana' } })).json()).id;
  otherClass = (await (await request.post(`${API}/projects/${project}/classes`, { data: { name: 'Pallet' } })).json()).id;
  for (const name of ['sample.png', 'sample.webp', 'sample.jpg']) {
    const result = await request.post(`${API}/projects/${project}/datasets/images?filename=${name}`, { data: readFileSync(`tests/fixtures/images/${name}`) });
    if (name === 'sample.png') imageId = (await result.json()).image.id;
  }
  await page.goto(`/#Dataset/${project}`);
  await open(page);
});
test.afterEach(async ({ request }) => { await request.delete(`${API}/projects/${project}`); });

test('draws, restores, moves, resizes, reassigns, and deletes a normalized box', async ({ page, request }) => {
  await drag(page, .2, .2, .6, .6);
  await expect.poll(async () => (await saved(request)).revision).toBe(1);
  let box = (await saved(request)).annotations[0];
  expect(box.center_x).toBeCloseTo(.4, 2); expect(box.width).toBeCloseTo(.4, 2); expect(box.class_id).toBe(classId);
  await expect(page.locator('.annotation-progress')).toHaveText('Annotated 1 / 3');
  await page.getByRole('button', { name: 'Close editor', exact: true }).click();
  await page.reload(); await open(page);
  await expect(page.locator('.annotation-rect')).toHaveCount(1);
  await page.getByRole('button', { name: 'Box 1: Banana', exact: true }).click();
  await drag(page, .4, .4, .5, .5);
  await expect.poll(async () => (await saved(request)).revision).toBe(2);
  const handle = (await page.locator('[data-handle="se"]').boundingBox())!;
  const image = (await page.locator('.annotation-image-layer').boundingBox())!;
  await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
  await page.mouse.down(); await page.mouse.move(image.x + image.width * .85, image.y + image.height * .8, { steps: 5 }); await page.mouse.up();
  await expect.poll(async () => (await saved(request)).revision).toBe(3);
  box = (await saved(request)).annotations[0];
  expect(box.width).toBeCloseTo(.55, 2); expect(box.height).toBeCloseTo(.5, 2);
  await page.getByRole('combobox', { name: 'Active class', exact: true }).selectOption(otherClass);
  await page.getByRole('button', { name: 'Assign active class', exact: true }).click();
  await expect.poll(async () => (await saved(request)).annotations[0].class_id).toBe(otherClass);
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  await expect(page.getByText('Zoom 125%', { exact: true })).toBeVisible();
  const zoomed = (await page.locator('.annotation-image-layer').boundingBox())!;
  await page.getByRole('button', { name: 'Pan image', exact: true }).click();
  const viewport = (await page.getByRole('application', { name: 'Annotation canvas' }).boundingBox())!;
  await page.mouse.move(viewport.x + 80, viewport.y + 80); await page.mouse.down(); await page.mouse.move(viewport.x + 100, viewport.y + 100); await page.mouse.up();
  expect((await page.locator('.annotation-image-layer').boundingBox())!.x).toBeCloseTo(zoomed.x + 20, 0);
  await page.getByRole('button', { name: 'Fit image', exact: true }).click();
  await expect(page.getByText('Zoom 100%', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Delete selected box', exact: true }).click();
  await expect.poll(async () => (await saved(request)).annotations.length).toBe(0);
  await expect(page.locator('.annotation-progress')).toHaveText('Annotated 0 / 3');
});

test('retains a failed save for retry and prevents image navigation while unsaved', async ({ page, request }) => {
  await page.route('**/annotations', route => route.request().method() === 'POST' ? route.abort() : route.continue());
  await drag(page, .1, .1, .4, .4);
  await expect(page.getByRole('button', { name: 'Retry save', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Next image', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Close editor', exact: true })).toBeDisabled();
  expect((await saved(request)).annotations).toHaveLength(0);
  await page.unroute('**/annotations');
  await page.getByRole('button', { name: 'Retry save', exact: true }).click();
  await expect.poll(async () => (await saved(request)).annotations.length).toBe(1);
  await expect(page.getByRole('button', { name: 'Close editor', exact: true })).toBeEnabled();
});

test('rejects stale changes and reloads saved annotations only after confirmation', async ({ page, request }) => {
  await request.post(route(), { data: { id: crypto.randomUUID().replaceAll('-', ''), class_id: classId, center_x: .7, center_y: .7, width: .2, height: .2, expected_revision: 0 } });
  await drag(page, .1, .1, .3, .3);
  await expect(page.getByRole('alert')).toContainText('Annotations changed in another window.');
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('button', { name: 'Discard unsaved change and reload', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Close editor', exact: true })).toBeDisabled();
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Discard unsaved change and reload', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Close editor', exact: true })).toBeEnabled();
  await expect(page.locator('.annotation-rect')).toHaveCount(1);
  expect((await saved(request)).annotations[0].center_x).toBe(.7);
});

test('uses annotation shortcuts and counts across image navigation while ignoring form controls', async ({ page, request }) => {
  await page.getByRole('application', { name: 'Annotation canvas' }).focus();
  await page.keyboard.press('2');
  await expect(page.getByRole('combobox', { name: 'Active class', exact: true })).toHaveValue(otherClass);
  await drag(page, .2, .2, .5, .5);
  await expect.poll(async () => (await saved(request)).annotations[0]?.class_id).toBe(otherClass);
  await expect(page.locator('.annotation-save-state')).toHaveText('All changes saved');
  await page.keyboard.press('d');
  await expect(page.getByText('Image 2 of 3', { exact: true })).toBeVisible();
  await expect(page.locator('.annotation-progress')).toHaveText('Annotated 1 / 3');
  await expect(page.getByRole('button', { name: 'Fit image', exact: true })).toBeEnabled();
  await drag(page, .15, .15, .4, .4);
  await expect(page.locator('.annotation-progress')).toHaveText('Annotated 2 / 3');
  await page.keyboard.press('a');
  await expect(page.getByText('Image 1 of 3', { exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: 'Active class', exact: true }).focus();
  await page.keyboard.press('d');
  await expect(page.getByText('Image 1 of 3', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Box 1: Pallet', exact: true }).click();
  await page.keyboard.press('Delete');
  await expect(page.locator('.annotation-progress')).toHaveText('Annotated 1 / 3');
  expect((await saved(request)).annotations).toHaveLength(0);
  await page.getByRole('button', { name: 'Next image', exact: true }).click();
  await expect(page.getByText('Image 2 of 3', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Next image', exact: true }).click();
  await expect(page.getByText('Image 3 of 3', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Next image', exact: true })).toBeDisabled();
  await page.setViewportSize({ width: 900, height: 640 });
  expect(await page.getByRole('dialog').evaluate(dialog => dialog.scrollWidth <= dialog.clientWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/annotation-editor.png' });
});
