import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

const API = process.env.VISION_STUDIO_TEST_API ?? 'http://127.0.0.1:8765';

test('lists locally opened USB camera indexes and can rescan them', async ({ page }) => {
  let scans = 0;
  await page.route('**/cameras/usb', async route => {
    scans += 1;
    await route.fulfill({ json: { cameras: [{ id: 'usb-2', index: 2, name: 'Camera 2', source_type: 'usb' }], scanned: 4 } });
  });
  await page.goto('/#Cameras');
  await expect(page.getByRole('heading', { name: 'USB cameras', exact: true })).toBeVisible();
  await expect(page.getByText('Camera 2', { exact: true })).toBeVisible();
  await expect(page.getByText('Camera index 2', { exact: true })).toBeVisible();
  const scansBefore = scans;
  await page.getByRole('button', { name: 'Scan USB cameras' }).click();
  await expect.poll(() => scans).toBe(scansBefore + 1);
});

test('shows a binary JPEG preview with filtered live detection overlays and stops its session', async ({ page, request }) => {
  const project = await (await request.post(`${API}/projects`, { data: { name: 'Live inspection' } })).json();
  const session = { id: 'c'.repeat(32), project_id: project.id, camera_index: 2, status: 'running', inference_status: 'ready', active_model_id: 'm'.repeat(32), frame_id: 1, frame_width: 640, frame_height: 320, fps: 10, detections: [], error: null };
  let stops = 0;
  await page.route('**/cameras/usb', route => route.fulfill({ json: { cameras: [{ id: 'usb-2', index: 2, name: 'Camera 2', source_type: 'usb' }], scanned: 4 } }));
  await page.route(`**/projects/${project.id}/cameras/usb/2/sessions`, async route => {
    if (route.request().method() === 'POST') return route.fulfill({ status: 201, json: session });
    return route.fallback();
  });
  await page.route(`**/projects/${project.id}/cameras/usb/sessions/${session.id}`, async route => {
    if (route.request().method() === 'DELETE') { stops += 1; return route.fulfill({ status: 204 }); }
    return route.fallback();
  });
  await page.route(`**/projects/${project.id}/cameras/usb/sessions/${session.id}/frame*`, route => route.fulfill({
    contentType: 'image/jpeg', body: readFileSync('tests/fixtures/images/sample.jpg'),
    headers: { 'X-Vision-Frame-Id': '1', 'X-Vision-Detections': JSON.stringify([{ class_id: 0, class_name: 'Banana', confidence: 0.8, x: 0.1, y: 0.1, width: 0.5, height: 0.5 }]) },
  }));
  try {
    await page.goto('/#Cameras');
    await expect(page.getByRole('button', { name: 'Start preview', exact: true })).toBeEnabled();
    await page.getByRole('button', { name: 'Start preview', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Camera 2 preview', exact: true })).toBeVisible();
    await expect(page.getByText('Banana', { exact: true })).toBeVisible();
    await expect(page.locator('.camera-frame rect')).toHaveCount(1);
    await page.getByLabel('Confidence threshold: 0.50', { exact: true }).fill('0.85');
    await expect(page.getByText('No detections meet the current confidence threshold.', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Stop preview', exact: true }).click();
    await expect.poll(() => stops).toBe(1);
  } finally { await request.delete(`${API}/projects/${project.id}`); }
});
