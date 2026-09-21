import { expect, test } from '@playwright/test'

import { loginViaUi, registerViaUi, uniqueUser } from './helpers'

test('register, logout and login again', async ({ page }) => {
  const alice = uniqueUser('alice')
  await registerViaUi(page, alice)
  await expect(page.getByTestId('chat-list')).toBeVisible()

  await page.getByTitle('Logout').click()
  await expect(page.getByTestId('identifier')).toBeVisible()

  await loginViaUi(page, alice)
  await expect(page.getByTestId('me-name')).toHaveText(alice.username)
})

test('registration with duplicate username shows conflict', async ({ browser }) => {
  const firstContext = await browser.newContext()
  const secondContext = await browser.newContext()
  const first = await firstContext.newPage()
  const second = await secondContext.newPage()

  const bob = uniqueUser('bob')
  await registerViaUi(first, bob)

  const impostor = uniqueUser('impostor')
  await second.goto('/')
  await second.getByTestId('identifier').fill(impostor.identifier)
  await second.getByTestId('request-code').click()
  await expect(second.getByTestId('code')).toBeVisible()
  const code = await second.request
    .get(
      `http://127.0.0.1:8000/api/v1/auth/otp/dev/latest?identifier=${encodeURIComponent(impostor.identifier)}`,
    )
    .then((r) => r.json())
  await second.getByTestId('code').fill(code.code)
  await second.getByTestId('verify-code').click()
  await second.getByTestId('username').fill(bob.username)
  await second.getByTestId('first-name').fill(impostor.firstName)
  await second.getByTestId('register').click()
  await expect(second.locator('.error-banner')).toContainText('username is already taken')

  await firstContext.close()
  await secondContext.close()
})
