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
  await expect(alicePage.getByTestId('chat-title')).toHaveText(bob.firstName)

  await sendMessage(alicePage, 'hi bob')
  await expectMessageVisible(alicePage, 'hi bob')

  // bob sees the chat appear in his list (polled) and opens it
  await bobPage.getByTestId('chat-list').getByText(alice.firstName).first().click()
  await expect(bobPage.getByTestId('chat-title')).toHaveText(alice.firstName)
  await expectMessageVisible(bobPage, 'hi bob')

  // bob replies to alice's message
  await bobPage.locator('[data-testid^="reply-"]').first().click()
  await expect(bobPage.getByTestId('reply-preview')).toBeVisible()
  await sendMessage(bobPage, 'hi alice')
  await expectMessageVisible(bobPage, 'hi alice')
  // the reply chip shows the content of the replied message, not just a symbol
  const chip = bobPage.getByTestId('messages').locator('.reply-chip')
  await expect(chip).toBeVisible()
  await expect(chip).toContainText('hi bob')
  await expect(chip).toContainText(alice.username)

  // messages are rendered oldest-first (arrival order, top to bottom)
  const bubbleTexts = bobPage.getByTestId('messages').locator('.message-text')
  await expect(bubbleTexts.nth(0)).toHaveText('hi bob')
  await expect(bubbleTexts.nth(1)).toHaveText('hi alice')

  // alice sees the reply
  await expectMessageVisible(alicePage, 'hi alice')

  await aliceContext.close()
  await bobContext.close()
})
