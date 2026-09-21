import { expect, test } from '@playwright/test'

import {
  expectMessageVisible,
  registerViaUi,
  sendMessage,
  uniqueUser,
} from './helpers'

test('private chat journey with reply', async ({ browser }) => {
  const alice = uniqueUser('alice')
  const bob = uniqueUser('bob')
  const aliceContext = await browser.newContext()
  const bobContext = await browser.newContext()
  const alicePage = await aliceContext.newPage()
  const bobPage = await bobContext.newPage()

  await registerViaUi(alicePage, alice)
  await registerViaUi(bobPage, bob)

  // alice searches bob, adds him as contact and opens a private chat
  await alicePage.getByTestId('search-input').fill(bob.username)
  await alicePage.getByTestId('search-button').click()
  await alicePage.getByTestId(`add-contact-${bob.username}`).click()
  await alicePage.getByTestId(`message-${bob.username}`).click()
  await expect(alicePage.getByTestId('chat-title')).toHaveText(bob.username)

  await sendMessage(alicePage, 'hi bob')
  await expectMessageVisible(alicePage, 'hi bob')

  // bob sees the chat appear in his list (polled) and opens it
  await bobPage.getByTestId('chat-list').getByText(alice.username).first().click()
  await expect(bobPage.getByTestId('chat-title')).toHaveText(alice.username)
  await expectMessageVisible(bobPage, 'hi bob')

  // bob replies to alice's message
  await bobPage.locator('[data-testid^="reply-"]').first().click()
  await expect(bobPage.getByTestId('reply-preview')).toBeVisible()
  await sendMessage(bobPage, 'hi alice')
  await expectMessageVisible(bobPage, 'hi alice')
  await expect(bobPage.getByTestId('messages').locator('.reply-chip')).toBeVisible()

  // alice sees the reply
  await expectMessageVisible(alicePage, 'hi alice')

  await aliceContext.close()
  await bobContext.close()
})
