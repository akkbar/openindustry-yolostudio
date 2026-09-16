import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const API = process.env.VISION_STUDIO_TEST_API ?? 'http://127.0.0.1:8765';

async function clearProjects(request: APIRequestContext) {
  const listing = await (await request.get(`${API}/projects`)).json();
  for (const project of listing.projects) await request.delete(`${API}/projects/${project.id}`);
}

async function createProject(request: APIRequestContext, name: string) {
  const response = await request.post(`${API}/projects`, { data: { name, description: '' } });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<{ id: string; name: string }>;
}

function job(projectId: string, status: 'queued' | 'running', id = 'a'.repeat(32)) {
  return {
    id, project_id: projectId, status, model: 'yolo11n', epochs: 12, imgsz: 320, device: 'auto', progress: 0,
    metrics: null, created_at: '2026-09-16T00:00:00.000000Z', updated_at: '2026-09-16T00:00:00.000000Z',
    started_at: status === 'running' ? '2026-09-16T00:00:01.000000Z' : null, finished_at: null, error: null,
  };
}

async function openTraining(page: Page) {
  await page.goto('/#Models');
  const training = page.locator('.training-panel');
  await expect(training.getByRole('heading', { name: 'Train model', exact: true })).toBeVisible();
  return training;
}

test.beforeEach(async ({ request }) => { await clearProjects(request); });
test.afterEach(async ({ request }) => { await clearProjects(request); });

test('starts a configured training job from the Models page without a CLI', async ({ page, request }) => {
  const project = await createProject(request, 'Pallet inspection');

  const training = await openTraining(page);
  await expect(training.getByLabel('Project')).toHaveValue('');
  await expect(training.getByRole('button', { name: 'Start training' })).toBeDisabled();
  await expect(training.getByLabel('Base model')).toHaveValue('YOLO11 Nano');
  await expect(training.getByLabel('Device')).toHaveValue('Auto');

  await training.getByLabel('Project').selectOption(project.id);
  await expect(page).toHaveURL(new RegExp(`#Models/${project.id}$`));
  await training.getByLabel('Epochs').fill('12');
  await training.getByLabel('Image size').fill('320');
  await training.getByRole('button', { name: 'Start training' }).click();

  await expect(training.getByRole('status')).toContainText('Training started');
  await expect.poll(async () => {
    const response = await request.get(`${API}/projects/${project.id}/training-jobs`);
    const listing = await response.json();
    const created = listing.jobs[0];
    return created && { model: created.model, epochs: created.epochs, imgsz: created.imgsz, status: created.status };
  }, { timeout: 45_000 }).toEqual({ model: 'yolo11n', epochs: 12, imgsz: 320, status: 'failed' });
});

test('retries the same queued job when the worker cannot start immediately', async ({ page, request }) => {
  const project = await createProject(request, 'Carton inspection');
  const queued = job(project.id, 'queued', 'b'.repeat(32));
  let createCalls = 0;
  let startCalls = 0;

  await page.route(new RegExp(`/projects/${project.id}/training-jobs$`), async route => {
    createCalls += 1;
    await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(queued) });
  });
  await page.route(new RegExp(`/projects/${project.id}/training-jobs/${queued.id}/start$`), async route => {
    startCalls += 1;
    if (startCalls === 1) {
      await route.fulfill({
        status: 409, contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'training_worker_busy', message: 'Another training job is already running. Wait for it to finish before starting this job.' } }),
      });
      return;
    }
    await route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify(job(project.id, 'running', queued.id)) });
  });

  const training = await openTraining(page);
  await training.getByLabel('Project').selectOption(project.id);
  await training.getByRole('button', { name: 'Start training' }).click();
  await expect(training.getByRole('alert')).toContainText('Another training job is already running.');
  await expect(training.getByText('The job was created but is still queued. Retry to start this same job.')).toBeVisible();

  await training.getByRole('button', { name: 'Retry starting training' }).click();
  await expect(training.getByRole('status')).toContainText('Training started');
  expect(createCalls).toBe(1);
  expect(startCalls).toBe(2);
});

test('validates numeric settings before it creates a training job', async ({ page, request }) => {
  const project = await createProject(request, 'Label inspection');
  let createCalls = 0;
  await page.route(new RegExp(`/projects/${project.id}/training-jobs$`), async route => {
    createCalls += 1;
    await route.abort();
  });

  const training = await openTraining(page);
  await training.getByLabel('Project').selectOption(project.id);
  await training.getByLabel('Epochs').fill('0');
  await training.getByRole('button', { name: 'Start training' }).click();

  await expect(training.getByRole('alert')).toHaveText('Enter a whole number of epochs from 1 to 10,000.');
  expect(createCalls).toBe(0);
});
