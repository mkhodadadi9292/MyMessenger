import { expect, test } from '@playwright/test'

import { registerViaUi, uniqueUser } from './helpers'

test('contacts page: add, rename with custom name, remove', async ({ browser }) => {
  const alice = uniqueUser('alice')
  const bob = uniqueUser('bob')
  const aliceContext = await browser.newContext()
  const bobContext = await browser.newContext()
  const alicePage = await aliceContext.newPage()
  const bobPage = await bobContext.newPage()

  await registerViaUi(alicePage, alice)
  await registerViaUi(bobPage, bob)

  // alice opens the contacts page and adds bob by username
  await alicePage.getByTestId('contacts-button').click()
  await expect(alicePage.getByTestId('contacts-page')).toBeVisible()
  await alicePage.getByTestId('contact-identifier').fill(bob.username)
  await alicePage.getByTestId('contact-add').click()
  await expect(alicePage.locator('[data-testid^="contact-label-"]')).toHaveText(bob.username)

  // rename with a custom name
  await alicePage.locator('[data-testid^="contact-edit-"]').click()
  await alicePage.locator('[data-testid^="contact-name-input-"]').fill('Best Buddy')
  await alicePage.locator('[data-testid^="contact-name-save-"]').click()
  await expect(alicePage.locator('[data-testid^="contact-label-"]')).toContainText('Best Buddy')
  await expect(alicePage.locator('[data-testid^="contact-label-"]')).toContainText(
    `@${bob.username}`,
  )

  // back to the app and reopen: the custom name persists
  await alicePage.getByTestId('contacts-close').click()
  await expect(alicePage.getByTestId('contacts-page')).toBeHidden()
  await alicePage.getByTestId('contacts-button').click()
  await expect(alicePage.locator('[data-testid^="contact-label-"]')).toContainText('Best Buddy')

  // remove the contact
  await alicePage.locator('[data-testid^="contact-remove-"]').click()
  await expect(alicePage.getByTestId('contacts-list')).toContainText('No contacts yet')

  await aliceContext.close()
  await bobContext.close()
})

test('settings page: edit profile', async ({ browser }) => {
  const alice = uniqueUser('alice')
  const context = await browser.newContext()
  const page = await context.newPage()

  await registerViaUi(page, alice)

  await page.getByTestId('settings-button').click()
  await expect(page.getByTestId('settings-page')).toBeVisible()

  await page.getByTestId('settings-first-name').fill('Alice Updated')
  await page.getByTestId('settings-bio').fill('hello from settings')
  await page.getByTestId('save-profile').click()
  await expect(page.getByTestId('settings-page')).toContainText('Profile saved')

  await page.getByTestId('settings-close').click()
  await expect(page.getByTestId('settings-page')).toBeHidden()

  await context.close()
})
