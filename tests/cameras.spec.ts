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
  await expect(page.getByText('USB camera', { exact: true })).toBeVisible();
  const scansBefore = scans;
  await page.getByRole('button', { name: 'Scan USB cameras' }).click();
  await expect.poll(() => scans).toBe(scansBefore + 1);
});

test('shows a binary JPEG preview with filtered live detection overlays and stops its session', async ({ page, request }) => {
  const project = await (await request.post(`${API}/projects`, { data: { name: 'Live inspection' } })).json();
  const session = { id: 'c'.repeat(32), project_id: project.id, camera_index: 2, status: 'running', inference_status: 'ready', active_model_id: 'm'.repeat(32), frame_id: 1, frame_width: 640, frame_height: 320, fps: 10, detections: [], error: null };
  let stops = 0;
  await page.route('**/cameras/usb', route => route.fulfill({ json: { cameras: [{ id: 'usb-2', index: 2, name: 'Camera 2', source_type: 'usb' }], scanned: 4 } }));
  await page.route(`**/projects/${project.id}/cameras/usb/usb-2/sessions`, async route => {
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

test('draws a normalized counting line and ROI on a live camera preview', async ({ page, request }) => {
  const project = await (await request.post(`${API}/projects`, { data: { name: 'Counting preview' } })).json();
  const session = { id: 'd'.repeat(32), project_id: project.id, camera_index: 2, status: 'running', inference_status: 'ready', active_model_id: 'm'.repeat(32), active_model_source: 'custom', active_catalog_model_id: null, recommended_confidence: 0.5, roi_active: false, counters: [], frame_id: 1, frame_width: 640, frame_height: 320, fps: 10, detections: [], error: null };
  const configuration: { lines: { id: string; name: string; start: { x: number; y: number }; end: { x: number; y: number }; direction: string; enabled: boolean; created_at: string; updated_at: string }[]; roi: { points: { x: number; y: number }[]; enabled: boolean; updated_at: string } | null } = { lines: [], roi: null };
  await page.route('**/cameras/usb', route => route.fulfill({ json: { cameras: [{ id: 'usb-2', index: 2, name: 'Camera 2', source_type: 'usb' }], scanned: 4 } }));
  await page.route(`**/projects/${project.id}/cameras/usb/usb-2/sessions`, async route => {
    if (route.request().method() === 'POST') return route.fulfill({ status: 201, json: session });
    return route.fallback();
  });
  await page.route(`**/projects/${project.id}/counting**`, async route => {
    const body = route.request().postDataJSON() as { name?: string; start?: { x: number; y: number }; end?: { x: number; y: number }; direction?: string; points?: { x: number; y: number }[] } | null;
    if (route.request().method() === 'GET') return route.fulfill({ json: configuration });
    if (route.request().method() === 'POST') {
      const line = { id: 'line-1', name: body?.name ?? 'Counting line 1', start: body?.start!, end: body?.end!, direction: body?.direction ?? 'both', enabled: true, created_at: '', updated_at: '' };
      configuration.lines.push(line);
      return route.fulfill({ status: 201, json: line });
    }
    if (route.request().method() === 'PUT') { configuration.roi = { points: body?.points ?? [], enabled: true, updated_at: '' }; return route.fulfill({ json: configuration.roi }); }
    return route.fallback();
  });
  await page.route(`**/projects/${project.id}/cameras/usb/sessions/${session.id}/counting/reload`, route => route.fulfill({ json: { ...session, roi_active: configuration.roi !== null } }));
  await page.route(`**/projects/${project.id}/cameras/usb/sessions/${session.id}`, route => route.request().method() === 'DELETE' ? route.fulfill({ status: 204 }) : route.fallback());
  await page.route(`**/projects/${project.id}/cameras/usb/sessions/${session.id}/frame*`, route => route.fulfill({ contentType: 'image/jpeg', body: readFileSync('tests/fixtures/images/sample.jpg'), headers: { 'X-Vision-Frame-Id': '1', 'X-Vision-Detections': '[]', 'X-Vision-Counters': '[]', 'X-Vision-ROI-Active': String(configuration.roi !== null) } }));
  try {
    await page.goto('/#Cameras');
    await page.getByRole('button', { name: 'Start preview', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Draw line' })).toBeEnabled();
    await page.getByRole('button', { name: 'Draw line' }).click();
    const frame = page.locator('.camera-frame svg');
    await frame.click({ position: { x: 100, y: 120 } });
    await frame.click({ position: { x: 500, y: 120 } });
    await expect(page.getByText('Counting line 1', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'Draw ROI' }).click();
    await frame.click({ position: { x: 80, y: 80 } });
    await frame.click({ position: { x: 500, y: 80 } });
    await frame.click({ position: { x: 300, y: 240 } });
    await page.getByRole('button', { name: 'Save ROI' }).click();
    await expect(page.getByText('ROI active', { exact: true })).toBeVisible();
    expect(configuration.lines).toHaveLength(1);
    expect(configuration.roi?.points).toHaveLength(3);
  } finally { await request.delete(`${API}/projects/${project.id}`); }
});

test('saves an RTSP camera and starts its reconnect-capable preview', async ({ page, request }) => {
  const project = await (await request.post(`${API}/projects`, { data: { name: 'Network inspection' } })).json();
  const camera = { id: 'r'.repeat(32), project_id: project.id, name: 'Receiving dock', source_type: 'rtsp', url: 'rtsp://camera.local/live', username: 'operator', has_password: true, created_at: '', updated_at: '' };
  const session = { id: 's'.repeat(32), project_id: project.id, camera_index: null, camera_id: camera.id, camera_name: camera.name, source_type: 'rtsp', reconnect_count: 1, status: 'running', inference_status: 'no_active_model', active_model_id: null, active_model_source: 'none', active_catalog_model_id: null, recommended_confidence: 0.5, roi_active: false, counters: [], frame_id: 1, frame_width: 640, frame_height: 320, fps: 10, detections: [], error: null };
  let saved: typeof camera[] = [];
  await page.route('**/cameras/usb', route => route.fulfill({ json: { cameras: [], scanned: 4 } }));
  await page.route(`**/projects/${project.id}/cameras/rtsp`, async route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: { cameras: saved } });
    if (route.request().method() === 'POST') { saved = [camera]; return route.fulfill({ status: 201, json: camera }); }
    return route.fallback();
  });
  await page.route(`**/projects/${project.id}/cameras/rtsp/${camera.id}/sessions`, route => route.fulfill({ status: 201, json: session }));
  await page.route(`**/projects/${project.id}/cameras/rtsp/sessions/${session.id}/frame*`, route => route.fulfill({ contentType: 'image/jpeg', body: readFileSync('tests/fixtures/images/sample.jpg'), headers: { 'X-Vision-Frame-Id': '1', 'X-Vision-Detections': '[]', 'X-Vision-Counters': '[]', 'X-Vision-ROI-Active': 'false' } }));
  await page.route(`**/projects/${project.id}/cameras/rtsp/sessions/${session.id}`, route => route.request().method() === 'DELETE' ? route.fulfill({ status: 204 }) : route.fallback());
  await page.route(`**/projects/${project.id}/events?limit=20`, route => route.fulfill({ json: { events: [], total: 0 } }));
  try {
    await page.goto('/#Cameras');
    await page.getByLabel('Camera name').fill(camera.name);
    await page.getByLabel('RTSP URL').fill(camera.url);
    await page.getByLabel('Username').fill('operator');
    await page.getByLabel('Password').fill('not-returned');
    await page.getByRole('button', { name: 'Add RTSP camera' }).click();
    await expect(page.getByText(camera.name, { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Start preview', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Receiving dock preview', exact: true })).toBeVisible();
    await expect(page.getByText('Reconnects: 1.')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Recent events', exact: true })).toBeVisible();
  } finally { await request.delete(`${API}/projects/${project.id}`); }
});
