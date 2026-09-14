import { expect, test } from '@playwright/test';

test('connects to the real backend and stays English with an Indonesian browser locale', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('status')).toHaveText('Backend Connected');
  await expect(page.getByRole('heading', { name: 'Workspace overview' })).toBeVisible();
  await page.getByRole('button', { name: 'View system details' }).click();
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
  await expect(page.getByText('English', { exact: true })).toBeVisible();
  await expect(page.locator('.storage-path')).not.toHaveText('Waiting for backend');
  await page.getByRole('button', { name: 'Projects', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'This workspace is taking shape.' })).toBeVisible();
  await page.getByRole('button', { name: 'Back to dashboard' }).click();
  await expect(page.getByRole('heading', { name: 'Workspace overview' })).toBeVisible();
  await page.screenshot({ path: 'test-results/dashboard.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('shows an English error and recovers when the backend returns', async ({ page }) => {
  await page.route('**/health', (route) => route.abort());
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('Backend Disconnected');
  await expect(page.getByRole('alert')).toContainText('The local backend is unavailable.');
  await page.unroute('**/health');
  await page.getByRole('button', { name: 'Retry connection' }).click();
  await expect(page.getByRole('status')).toHaveText('Backend Connected');
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('does not report an unrelated service as connected', async ({ page }) => {
  await page.route('**/health', (route) => route.fulfill({ json: { status: 'ok', service: 'another-app' } }));
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('Backend Disconnected');
});
