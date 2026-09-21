import { expect, test } from '@playwright/test'

import { expectMessageVisible, registerViaUi, sendMessage, uniqueUser } from './helpers'

test('private group: create, invite, accept, message', async ({ browser }) => {
  const alice = uniqueUser('alice')
  const bob = uniqueUser('bob')
  const aliceContext = await browser.newContext()
  const bobContext = await browser.newContext()
  const alicePage = await aliceContext.newPage()
  const bobPage = await bobContext.newPage()

  await registerViaUi(alicePage, alice)
  await registerViaUi(bobPage, bob)

  // alice creates a private group
  await alicePage.getByTestId('new-group').click()
  await alicePage.getByTestId('group-title').fill('Team')
  await alicePage.getByTestId('create-group').click()
  await expect(alicePage.getByTestId('chat-title')).toHaveText('Team')

  // alice invites bob by username (input clears only after the POST lands)
  await alicePage.getByTestId('invite-username').fill(bob.username)
  await alicePage.getByTestId('invite-submit').click()
  await expect(alicePage.getByTestId('invite-username')).toHaveValue('')

  // bob sees the pending invite and accepts
  await bobPage.getByTestId('invites-button').click()
  await expect(bobPage.getByTestId('invites-panel')).toContainText('Team')
  await bobPage.locator('[data-testid^="accept-invite-"]').click()

  // bob can now open the group from his chat list and read alice's message
  await sendMessage(alicePage, 'welcome to the team')
  await expectMessageVisible(alicePage, 'welcome to the team')

  await bobPage.getByTestId('chat-list').getByText('Team', { exact: true }).click()
  await expect(bobPage.getByTestId('chat-title')).toHaveText('Team')
  await expectMessageVisible(bobPage, 'welcome to the team')

  await aliceContext.close()
  await bobContext.close()
})

test('public group: join by id', async ({ browser }) => {
  const alice = uniqueUser('alice')
  const bob = uniqueUser('bob')
  const aliceContext = await browser.newContext()
  const bobContext = await browser.newContext()
  const alicePage = await aliceContext.newPage()
  const bobPage = await bobContext.newPage()

  await registerViaUi(alicePage, alice)
  await registerViaUi(bobPage, bob)

  await alicePage.getByTestId('new-group').click()
  await alicePage.getByTestId('group-title').fill('Public Room')
  await alicePage.getByTestId('group-public').check()
  await alicePage.getByTestId('create-group').click()
  await expect(alicePage.getByTestId('chat-title')).toHaveText('Public Room')

  const token = await alicePage.evaluate(() => localStorage.getItem('access_token'))
  const groupId = await alicePage.request
    .get('http://127.0.0.1:8000/api/v1/chats', {
      headers: { Authorization: `Bearer ${token}` },
    })
    .then((r) => r.json())
    .then((chats) => chats[0].id as number)

  await bobPage.getByTestId('join-group').click()
  await bobPage.getByTestId('join-value').fill(String(groupId))
  await bobPage.getByTestId('join-submit').click()

  await bobPage.getByTestId('chat-list').getByText('Public Room', { exact: true }).click()
  await expect(bobPage.getByTestId('chat-title')).toHaveText('Public Room')

  await aliceContext.close()
  await bobContext.close()
})
