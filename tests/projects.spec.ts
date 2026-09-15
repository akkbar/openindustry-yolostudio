import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const API = 'http://127.0.0.1:8765';

async function clearProjects(request: APIRequestContext) {
  const listing = await (await request.get(`${API}/projects`)).json();
  for (const project of listing.projects) {
    await request.delete(`${API}/projects/${project.id}`);
  }
}

test.beforeEach(async ({ request, page }) => {
  await clearProjects(request);
  await page.goto('/#Projects');
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();
});

test.afterEach(async ({ request }) => {
  await clearProjects(request);
});

async function createProject(page: Page, name: string, description?: string) {
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(name);
  if (description) await page.getByLabel(/Description/).fill(description);
  await page.getByRole('button', { name: 'Create project' }).click();
}

test('creates a project from the interface and stores it on disk', async ({ page, request }) => {
  await expect(page.getByRole('heading', { name: 'Start your first project.' })).toBeVisible();
  await createProject(page, 'Banana Counter', 'Packing line 3');

  await expect(page.getByRole('heading', { name: 'Banana Counter' })).toBeVisible();
  await expect(page.getByText('Packing line 3')).toBeVisible();
  await expect(page.getByText('1 project')).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(0);

  const listing = await (await request.get(`${API}/projects`)).json();
  expect(listing.total).toBe(1);
  expect(listing.projects[0].name).toBe('Banana Counter');
  expect(listing.projects[0].task_type).toBe('object_detection');
  expect(listing.projects[0].storage_path).toContain(listing.projects[0].id);
});

test('keeps projects after a reload', async ({ page }) => {
  await createProject(page, 'Carton Counter');
  await expect(page.getByRole('heading', { name: 'Carton Counter' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Carton Counter' })).toBeVisible();
});

test('opens a project workspace and restores it after reload', async ({ page }) => {
  await createProject(page, 'Banana Counter', 'Packing line 3');
  await page.getByRole('button', { name: 'Open Banana Counter' }).click();
  await expect(page).toHaveURL(/#Projects\/[0-9a-f]{32}$/);
  await expect(page.getByText('Project overview', { exact: true })).toBeVisible();
  await expect(page.locator('.project-workspace .project-name')).toHaveText('Banana Counter');
  await page.reload();
  await expect(page.locator('.project-workspace .project-name')).toHaveText('Banana Counter');
  await expect(page.locator('.project-workspace .project-path')).toContainText('projects');
  await page.screenshot({ path: 'test-results/project-workspace.png', fullPage: true });
  await page.getByRole('button', { name: 'Back to projects' }).click();
  await expect(page.getByRole('button', { name: 'Open Banana Counter' })).toBeVisible();
  await page.goBack();
  await expect(page.locator('.project-workspace .project-name')).toHaveText('Banana Counter');
});

test('keeps keyboard focus inside the project dialog and restores it', async ({ page }) => {
  const opener = page.getByRole('button', { name: 'New project' }).first();
  await opener.click();
  const name = page.getByLabel('Project name');
  await expect(name).toBeFocused();
  await name.fill('Keyboard test');
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('button', { name: 'Create project' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(name).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(opener).toBeFocused();
});

test('preserves user text and handles long names at minimum desktop size', async ({ page, request }) => {
  await page.setViewportSize({ width: 900, height: 640 });
  const name = '  Jalur   produksi ' + 'x'.repeat(55);
  const description = '  Catatan pengguna\nBaris kedua  ';
  await createProject(page, name, description);
  await expect(page.locator('.project-card')).toHaveCount(1);
  const listing = await (await request.get(`${API}/projects`)).json();
  expect(listing.projects[0].name).toBe(name);
  expect(listing.projects[0].description).toBe(description);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/projects-small.png', fullPage: true });
});

test('rejects a duplicate name with an English message and keeps the dialog open', async ({ page }) => {
  await createProject(page, 'Banana Counter');
  await expect(page.getByRole('heading', { name: 'Banana Counter' })).toBeVisible();

  await createProject(page, 'banana counter');
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('alert')).toHaveText('A project with this name already exists. Choose a different name.');

  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByText('1 project')).toBeVisible();
});

test('requires a name before a project can be created', async ({ page }) => {
  await page.getByRole('button', { name: 'New project' }).first().click();
  const create = page.getByRole('button', { name: 'Create project' });
  await expect(create).toBeDisabled();
  await page.getByLabel('Project name').fill('   ');
  await expect(create).toBeDisabled();
  await page.getByLabel('Project name').fill('Valid name');
  await expect(create).toBeEnabled();
});

test('renames a project and preserves its description', async ({ page }) => {
  await createProject(page, 'Banana Counter', 'Packing line 3');
  await page.getByRole('button', { name: 'Rename Banana Counter' }).click();
  await page.getByLabel('Project name').fill('Banana Counter v2');
  await page.getByRole('button', { name: 'Save changes' }).click();

  await expect(page.getByRole('heading', { name: 'Banana Counter v2' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Banana Counter', exact: true })).toHaveCount(0);
  await expect(page.getByText('Packing line 3')).toBeVisible();
});

test('deletes a project only after confirmation', async ({ page, request }) => {
  await createProject(page, 'Banana Counter');
  await page.getByRole('button', { name: 'Delete Banana Counter' }).click();

  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('Deleting Banana Counter permanently removes');
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('heading', { name: 'Banana Counter' })).toBeVisible();

  await page.getByRole('button', { name: 'Delete Banana Counter' }).click();
  await page.getByRole('button', { name: 'Delete project' }).click();

  await expect(page.getByRole('heading', { name: 'Start your first project.' })).toBeVisible();
  expect((await (await request.get(`${API}/projects`)).json()).total).toBe(0);
});

test('closes the dialog with Escape without creating a project', async ({ page }) => {
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill('Discarded');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Start your first project.' })).toBeVisible();
});

test('reports an English error when the backend is unavailable, then recovers', async ({ page }) => {
  await page.route('**/projects', (route) => route.abort());
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('The local backend is unavailable.');
  await page.unroute('**/projects');
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('heading', { name: 'Start your first project.' })).toBeVisible();
});

test('sorts projects alphabetically and stays English under an Indonesian locale', async ({ page }) => {
  for (const name of ['zebra line', 'Apple line', 'mango line']) await createProject(page, name);
  await expect(page.locator('.project-card h2')).toHaveText(['Apple line', 'mango line', 'zebra line']);
  await expect(page.getByText('3 projects')).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('button', { name: 'New project' }).first()).toBeVisible();
});
