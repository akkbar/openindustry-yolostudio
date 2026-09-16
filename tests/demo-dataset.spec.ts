import { expect, test } from '@playwright/test';

const API = process.env.VISION_STUDIO_TEST_API ?? 'http://127.0.0.1:8765';

const completeDemo = {
  id: 'apple', name: 'Apple detector demo', source_name: 'AppleBBCH76',
  source_url: 'https://www.kaggle.com/datasets/projectlzp201910094/applebbch76',
  license: 'CC BY 4.0', image_count: 3169, class_name: 'apple', archive_bytes: 243970799,
  status: 'completed', progress: 1, message: 'The Apple detector demo is ready.', project_id: 'missing-demo-project', error: null,
};

test('offers the complete Apple detector demo and shows its completed state', async ({ page, request }) => {
  const projects = await (await request.get(`${API}/projects`)).json();
  await Promise.all(projects.projects.map((project: { id: string }) => request.delete(`${API}/projects/${project.id}`)));
  let started = false;
  await page.route('**/demo-datasets/apple', async route => {
    if (route.request().method() === 'POST') started = true;
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(started ? completeDemo : { ...completeDemo, status: 'not_started', progress: 0, message: 'Download the full AppleBBCH76 source dataset and its YOLO annotations.', project_id: null }) });
  });
  await page.goto('/#Projects');
  await expect(page.getByRole('heading', { name: 'Apple detector demo' })).toBeVisible();
  await expect(page.getByText('3,169 annotated images')).toBeVisible();
  await page.getByRole('button', { name: 'Download Apple detector demo' }).click();
  await expect(page.getByText('Apple detector demo is ready.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Open Apple detector demo' })).toBeVisible();
});
