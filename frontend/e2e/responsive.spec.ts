import { expect, test } from '@playwright/test'

import {
  expectMessageVisible,
  openPrivateChatViaSearch,
  registerViaUi,
  sendMessage,
  uniqueUser,
} from './helpers'

const MOBILE = { width: 390, height: 844 }
const DESKTOP = { width: 1280, height: 800 }

test.describe('mobile viewport (390x844)', () => {
  test.use({ viewport: MOBILE })

  test('single-pane navigation with back button', async ({ browser }) => {
    const alice = uniqueUser('alice')
    const bob = uniqueUser('bob')
    const aliceContext = await browser.newContext({ viewport: MOBILE })
    const bobContext = await browser.newContext({ viewport: MOBILE })
    const alicePage = await aliceContext.newPage()
    const bobPage = await bobContext.newPage()

    await registerViaUi(alicePage, alice)
    await registerViaUi(bobPage, bob)

    // chat list fills the screen; no chat window yet
    await expect(alicePage.getByTestId('chat-list')).toBeVisible()
    await expect(alicePage.getByTestId('chat-title')).toBeHidden()

    // opening a chat switches to the chat pane (sidebar hidden)
    await openPrivateChatViaSearch(alicePage, bob.username)
    await expect(alicePage.getByTestId('chat-title')).toHaveText(bob.firstName)
    await expect(alicePage.getByTestId('chat-list')).toBeHidden()

    await sendMessage(alicePage, 'hello from mobile')
    await expectMessageVisible(alicePage, 'hello from mobile')

    // back button returns to the chat list
    await alicePage.getByTestId('back-button').click()
    await expect(alicePage.getByTestId('chat-list')).toBeVisible()
    await expect(alicePage.getByTestId('chat-title')).toBeHidden()

    // the other user still receives the message on mobile
    await bobPage.getByTestId('chat-list').locator('.chat-item').first().click()
    await expect(bobPage.getByTestId('chat-title')).toHaveText(alice.firstName)
    await expectMessageVisible(bobPage, 'hello from mobile')

    await aliceContext.close()
    await bobContext.close()
  })
})

test.describe('desktop viewport (1280x800)', () => {
  test.use({ viewport: DESKTOP })

  test('two panes are visible at the same time', async ({ browser }) => {
    const alice = uniqueUser('alice')
    const bob = uniqueUser('bob')
    const aliceContext = await browser.newContext({ viewport: DESKTOP })
    const bobContext = await browser.newContext({ viewport: DESKTOP })
    const alicePage = await aliceContext.newPage()
    const bobPage = await bobContext.newPage()

    await registerViaUi(alicePage, alice)
    await registerViaUi(bobPage, bob)

    await openPrivateChatViaSearch(alicePage, bob.username)

    // sidebar and chat window are visible simultaneously
    await expect(alicePage.getByTestId('chat-list')).toBeVisible()
    await expect(alicePage.getByTestId('chat-title')).toHaveText(bob.firstName)
    // the back button is a mobile-only element
    await expect(alicePage.getByTestId('back-button')).toBeHidden()

    await aliceContext.close()
    await bobContext.close()
  })
})

test.describe('viewport adaptation', () => {
  test('layout switches when the viewport is resized', async ({ browser }) => {
    const alice = uniqueUser('alice')
    const bob = uniqueUser('bob')
    const aliceContext = await browser.newContext({ viewport: DESKTOP })
    const bobContext = await browser.newContext({ viewport: DESKTOP })
    const alicePage = await aliceContext.newPage()
    const bobPage = await bobContext.newPage()

    await registerViaUi(alicePage, alice)
    await registerViaUi(bobPage, bob)
    await openPrivateChatViaSearch(alicePage, bob.username)

    // desktop: both panes
    await expect(alicePage.getByTestId('chat-list')).toBeVisible()
    await expect(alicePage.getByTestId('chat-title')).toBeVisible()

    // shrink to mobile: sidebar disappears, back button appears
    await alicePage.setViewportSize(MOBILE)
    await expect(alicePage.getByTestId('chat-list')).toBeHidden()
    await expect(alicePage.getByTestId('chat-title')).toBeVisible()
    await expect(alicePage.getByTestId('back-button')).toBeVisible()

    // back to the list on mobile
    await alicePage.getByTestId('back-button').click()
    await expect(alicePage.getByTestId('chat-list')).toBeVisible()
    await expect(alicePage.getByTestId('chat-title')).toBeHidden()

    // grow back to desktop: both panes again (chat list + empty chat pane,
    // since the selection was cleared by the mobile back button)
    await alicePage.setViewportSize(DESKTOP)
    await expect(alicePage.getByTestId('chat-list')).toBeVisible()
    await expect(alicePage.getByText('Select a chat to start messaging')).toBeVisible()
    await expect(alicePage.getByTestId('back-button')).toBeHidden()

    await aliceContext.close()
    await bobContext.close()
  })
})
