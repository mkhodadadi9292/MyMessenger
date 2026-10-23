import { expect, test } from '@playwright/test'

import {
  expectMessageVisible,
  openPrivateChatViaSearch,
  registerViaUi,
  sendMessage,
  uniqueUser,
} from './helpers'

test('message notification: badge appears over SSE, panel opens the chat, badge clears', async ({
  browser,
}) => {
  const alice = uniqueUser('alice')
  const bob = uniqueUser('bob')
  const aliceContext = await browser.newContext()
  const bobContext = await browser.newContext()
  const alicePage = await aliceContext.newPage()
  const bobPage = await bobContext.newPage()

  await registerViaUi(alicePage, alice)
  await registerViaUi(bobPage, bob)

  // alice opens a private chat with bob and sends a message
  await openPrivateChatViaSearch(alicePage, bob.username)
  await sendMessage(alicePage, 'hello there')
  await expectMessageVisible(alicePage, 'hello there')

  // bob's bell badge appears without any reload (SSE push)
  await expect(bobPage.getByTestId('notifications-badge')).toHaveText('1')
  // alice gets no self-notification
  await expect(alicePage.getByTestId('notifications-badge')).toHaveCount(0)

  // bob opens the panel and sees the notification
  await bobPage.getByTestId('notifications-button').click()
  const panel = bobPage.getByTestId('notifications-panel')
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('hello there')

  // clicking the notification opens the chat and marks it read
  await panel.locator('[data-testid^="notification-"]').first().click()
  await expect(bobPage.getByTestId('chat-title')).toHaveText(alice.firstName)
  await expectMessageVisible(bobPage, 'hello there')
  await expect(bobPage.getByTestId('notifications-badge')).toHaveCount(0)

  await aliceContext.close()
  await bobContext.close()
})

test('invite notification: badge, panel, and accept through the invites panel', async ({
  browser,
}) => {
  const alice = uniqueUser('alice')
  const bob = uniqueUser('bob')
  const aliceContext = await browser.newContext()
  const bobContext = await browser.newContext()
  const alicePage = await aliceContext.newPage()
  const bobPage = await bobContext.newPage()

  await registerViaUi(alicePage, alice)
  await registerViaUi(bobPage, bob)

  // alice creates a private group and invites bob
  await alicePage.getByTestId('settings-button').click()
  await alicePage.getByTestId('settings-group-title').fill('Notify Team')
  await alicePage.getByTestId('settings-create-group').click()
  await expect(alicePage.getByTestId('chat-title')).toHaveText('Notify Team')
  await alicePage.getByTestId('invite-username').fill(bob.username)
  await alicePage.getByTestId('invite-submit').click()
  await expect(alicePage.getByTestId('invite-username')).toHaveValue('')

  // bob's badge increments over SSE
  await expect(bobPage.getByTestId('notifications-badge')).toHaveText('1')

  // clicking the invite notification opens the invites panel
  await bobPage.getByTestId('notifications-button').click()
  const panel = bobPage.getByTestId('notifications-panel')
  await expect(panel).toContainText('invited you to Notify Team')
  await panel.locator('[data-testid^="notification-"]').first().click()
  await expect(bobPage.getByTestId('invites-panel')).toContainText('Notify Team')
  await expect(bobPage.getByTestId('notifications-badge')).toHaveCount(0)

  // bob accepts and lands in the group (chat appears in his list)
  await bobPage.locator('[data-testid^="accept-invite-"]').click()
  await bobPage.getByTestId('chat-list').getByText('Notify Team', { exact: true }).click()
  await expect(bobPage.getByTestId('chat-title')).toHaveText('Notify Team')

  await aliceContext.close()
  await bobContext.close()
})

test('mark all read clears the badge without opening the chat', async ({ browser }) => {
  const alice = uniqueUser('alice')
  const bob = uniqueUser('bob')
  const aliceContext = await browser.newContext()
  const bobContext = await browser.newContext()
  const alicePage = await aliceContext.newPage()
  const bobPage = await bobContext.newPage()

  await registerViaUi(alicePage, alice)
  await registerViaUi(bobPage, bob)

  await openPrivateChatViaSearch(alicePage, bob.username)
  await sendMessage(alicePage, 'first message')
  await expectMessageVisible(alicePage, 'first message')
  await sendMessage(alicePage, 'second message')
  await expectMessageVisible(alicePage, 'second message')

  await expect(bobPage.getByTestId('notifications-badge')).toHaveText('2')

  await bobPage.getByTestId('notifications-button').click()
  await bobPage.getByTestId('notifications-mark-all').click()
  await expect(bobPage.getByTestId('notifications-badge')).toHaveCount(0)

  await aliceContext.close()
  await bobContext.close()
})
