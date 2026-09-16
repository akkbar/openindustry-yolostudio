import { expect, test } from '@playwright/test';

const API = process.env.VISION_STUDIO_TEST_API ?? 'http://127.0.0.1:8765';

test('searches the model library and assigns a built-in preset to a project', async ({ page, request }) => {
  const created = await request.post(`${API}/projects`, {
    data: { name: 'Catalog selection test', description: '' },
  });
  expect(created.ok()).toBeTruthy();
  const project = await created.json() as { id: string; name: string };

  try {
    await page.goto('/#Models');
    const library = page.locator('.model-library');
    await expect(library.getByRole('heading', { name: 'Model Library' })).toBeVisible();
    await expect(library.getByRole('heading', { name: 'General Object Detection' })).toBeVisible();

    await library.getByPlaceholder('Search models...').fill('helmet');
    await expect(library.getByRole('heading', { name: 'Helmet Detection' })).toBeVisible();
    await expect(library.getByRole('heading', { name: 'General Object Detection' })).not.toBeVisible();

    await library.getByPlaceholder('Search models...').fill('bottle');
    const bottleCard = library.locator('.catalog-card', { hasText: 'Bottle Detection' });
    await expect(bottleCard).toBeVisible();
    await library.getByLabel('Project').selectOption(project.id);
    await bottleCard.getByRole('button', { name: 'Use in project' }).click();
    await expect(library.getByRole('status')).toContainText('Bottle Detection is selected for Catalog selection test.');

    const selection = await request.get(`${API}/model-catalog/projects/${project.id}/selection`);
    expect(selection.ok()).toBeTruthy();
    expect((await selection.json()).model.id).toBe('bottle-detection');

    await library.getByRole('button', { name: 'Open cameras' }).click();
    await expect(page).toHaveURL(new RegExp(`#Cameras/${project.id}$`));
  } finally {
    await request.delete(`${API}/projects/${project.id}`);
  }
});
