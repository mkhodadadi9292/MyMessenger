import { expect, test } from '@playwright/test'

import { openPrivateChatViaSearch, registerViaUi, uniqueUser } from './helpers'

const PNG_BYTES = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
)

test('image artifact is uploaded and visible to both users', async ({ browser }) => {
  const alice = uniqueUser('alice')
  const bob = uniqueUser('bob')
  const aliceContext = await browser.newContext()
  const bobContext = await browser.newContext()
  const alicePage = await aliceContext.newPage()
  const bobPage = await bobContext.newPage()

  await registerViaUi(alicePage, alice)
  await registerViaUi(bobPage, bob)

  await openPrivateChatViaSearch(alicePage, bob.username)
  await alicePage.getByTestId('attach-input').setInputFiles({
    name: 'pixel.png',
    mimeType: 'image/png',
    buffer: PNG_BYTES,
  })
  await expect(alicePage.getByTestId('messages').locator('img.artifact-img')).toBeVisible()

  await bobPage.getByTestId('chat-list').getByText(alice.username).first().click()
  await expect(bobPage.getByTestId('messages').locator('img.artifact-img')).toBeVisible()

  await aliceContext.close()
  await bobContext.close()
})
