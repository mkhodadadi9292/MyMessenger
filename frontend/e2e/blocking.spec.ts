import { expect, test } from '@playwright/test'

import {
  expectMessageVisible,
  openPrivateChatViaSearch,
  registerViaUi,
  sendMessage,
  uniqueUser,
} from './helpers'

test('blocking prevents messaging; unblocking restores it', async ({ browser }) => {
  const alice = uniqueUser('alice')
  const bob = uniqueUser('bob')
  const aliceContext = await browser.newContext()
  const bobContext = await browser.newContext()
  const alicePage = await aliceContext.newPage()
  const bobPage = await bobContext.newPage()

  await registerViaUi(alicePage, alice)
  await registerViaUi(bobPage, bob)

  await openPrivateChatViaSearch(alicePage, bob.username)
  await alicePage.getByTestId('block-toggle').click()
  await expect(alicePage.getByTestId('block-toggle')).toHaveText('Unblock')

  // bob opens the chat (no messages yet, so the item title is generic) and tries to send
  await bobPage.getByTestId('chat-list').locator('.chat-item').first().click()
  await sendMessage(bobPage, 'are you there?')
  await expect(bobPage.getByTestId('chat-error')).toContainText('cannot message')

  // alice unblocks; bob can send now
  await alicePage.getByTestId('block-toggle').click()
  await expect(alicePage.getByTestId('block-toggle')).toHaveText('Block')
  await sendMessage(bobPage, 'are you there?')
  await expectMessageVisible(bobPage, 'are you there?')

  await aliceContext.close()
  await bobContext.close()
})
