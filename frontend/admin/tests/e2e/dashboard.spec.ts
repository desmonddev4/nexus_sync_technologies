import { expect, test } from '@playwright/test'

const operator = {
  username: 'e2e-coordinator',
  role: 'emergency_coordinator',
  can_access_operations: true,
}

async function mockApi(page: import('@playwright/test').Page, currentUser: typeof operator | { username: string; role: string; can_access_operations: false }) {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/^.*\/api\/v1\//, '')
    if (path === 'auth/token/') {
      await route.fulfill({ json: { token: 'e2e-session-token' } })
    } else if (path === 'auth/me/') {
      await route.fulfill({ json: currentUser })
    } else if (path === 'incidents/') {
      await route.fulfill({ json: [] })
    } else if (['providers/', 'facilities/', 'vehicles/', 'directory/providers/', 'directory/facilities/', 'directory/vehicles/'].includes(path)) {
      await route.fulfill({ json: [] })
    } else {
      await route.fulfill({ status: 200, json: [] })
    }
  })
}

test('operator can authenticate, view the dashboard and open emergency services', async ({ page }) => {
  await mockApi(page, operator)
  await page.goto('/login')
  await page.getByLabel('Username').fill('e2e-coordinator')
  await page.getByRole('textbox', { name: 'Password' }).fill('e2e-password')
  await page.getByRole('button', { name: 'Sign in' }).click()

  await expect(page.getByRole('heading', { name: 'Operations overview' })).toBeVisible()
  await expect(page.getByText('API session active')).toBeVisible()
  await page.getByRole('link', { name: 'Emergency services' }).click()
  await expect(page.getByRole('heading', { name: 'Emergency services' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Directory administration' })).toBeVisible()
})

test('user without operations permission is not admitted to the dashboard', async ({ page }) => {
  await mockApi(page, { username: 'e2e-patient', role: 'patient', can_access_operations: false })
  await page.goto('/login')
  await page.getByLabel('Username').fill('e2e-patient')
  await page.getByRole('textbox', { name: 'Password' }).fill('e2e-password')
  await page.getByRole('button', { name: 'Sign in' }).click()

  await expect(page.getByRole('heading', { name: 'Sign in to operations' })).toBeVisible()
  await expect(page.getByText('This account is not authorized for the operations dashboard.')).toBeVisible()
  await expect(page.getByText('API session active')).toHaveCount(0)
})
