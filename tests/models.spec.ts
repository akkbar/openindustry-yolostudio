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
    if (route.request().method() !== 'POST') return route.fallback();
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
  await page.route(new RegExp(`/projects/${project.id}/training-jobs/${queued.id}$`), async route => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(job(project.id, 'running', queued.id)) });
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

test('polls epoch metrics and presents a completed model for production selection', async ({ page, request }) => {
  const project = await createProject(request, 'Progress inspection');
  const running = { ...job(project.id, 'running', 'c'.repeat(32)), progress: 0.5, metrics: { 'train/box_loss': 0.25, 'metrics/precision(B)': 0.8, 'metrics/recall(B)': 0.7, 'metrics/mAP50(B)': 0.75 } };
  const completed = { ...running, status: 'completed', progress: 1, finished_at: '2026-09-16T00:00:12.000000Z' };
  const registered = { id: 'd'.repeat(32), project_id: project.id, training_job_id: running.id, name: 'Progress inspection v1', version: 1, status: 'development', path: 'C:/models/model.pt', dataset_export_id: 'snapshot-1', settings: { model: 'yolo11n', epochs: 12, imgsz: 320, device: 'auto' }, metrics: completed.metrics, created_at: '2026-09-16T00:00:12.000000Z', active: false };
  let pollCount = 0;
  let production = false;
  await page.route(new RegExp(`/projects/${project.id}/training-jobs$`), async route => {
    if (route.request().method() !== 'POST') return route.fallback();
    await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(running) });
  });
  await page.route(new RegExp(`/projects/${project.id}/training-jobs/${running.id}/start$`), async route => {
    await route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify(running) });
  });
  await page.route(new RegExp(`/projects/${project.id}/training-jobs/${running.id}$`), async route => {
    pollCount += 1;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(pollCount === 1 ? running : completed) });
  });
  await page.route(new RegExp(`/projects/${project.id}/models$`), async route => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ models: [{ ...registered, status: production ? 'production' : 'development', active: production }], active_model_id: production ? registered.id : null }) });
  });
  await page.route(new RegExp(`/projects/${project.id}/models/${registered.id}/activate$`), async route => {
    production = true;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...registered, status: 'production', active: true }) });
  });

  const training = await openTraining(page);
  await training.getByLabel('Project').selectOption(project.id);
  await training.getByRole('button', { name: 'Start training' }).click();
  const progress = page.locator('.training-progress');
  await expect(progress.getByText('Epoch 6 / 12')).toBeVisible();
  await expect(progress.getByText('0.25', { exact: true })).toBeVisible();
  await expect(progress.getByText('0.75', { exact: true })).toBeVisible();
  await expect(progress.getByText('Training completed')).toBeVisible();
  const registry = page.locator('.model-registry');
  await expect(registry.getByText('Progress inspection v1')).toBeVisible();
  await registry.getByRole('button', { name: 'Use in production' }).click();
  await expect(registry.getByText('Active model')).toBeVisible();
});

test('validates numeric settings before it creates a training job', async ({ page, request }) => {
  const project = await createProject(request, 'Label inspection');
  let createCalls = 0;
  await page.route(new RegExp(`/projects/${project.id}/training-jobs$`), async route => {
    if (route.request().method() !== 'POST') return route.fallback();
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
