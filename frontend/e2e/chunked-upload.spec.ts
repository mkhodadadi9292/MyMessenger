import { expect, test } from '@playwright/test'

import { E2E_CHUNK_SIZE } from './containers'
import { openPrivateChatViaSearch, registerViaUi, uniqueUser } from './helpers'

const PIXEL_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
)

function pngLargerThan(chunks: number): Buffer {
  const padding = Buffer.alloc(Math.floor(E2E_CHUNK_SIZE * chunks), 7)
  return Buffer.concat([PIXEL_PNG, padding])
}

test('a multi-chunk image upload shows progress and reaches the other user', async ({
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
  await openPrivateChatViaSearch(alicePage, bob.username)
  await bobPage.getByTestId('chat-list').getByText(alice.firstName).first().click()

  const chunkRequests: string[] = []
  await alicePage.route('**/files/v1/uploads/*/chunks/*', async (route) => {
    chunkRequests.push(route.request().url())
    await new Promise((resolve) => setTimeout(resolve, 400))
    await route.continue()
  })

  const file = pngLargerThan(2.5)
  await alicePage.getByTestId('attach-input').setInputFiles({
    name: 'big-pixel.png',
    mimeType: 'image/png',
    buffer: file,
  })

  await expect(alicePage.getByTestId('upload-progress')).toBeVisible()
  await expect(alicePage.getByTestId('upload-percent')).toHaveText(/\d+%|Finishing/)
  await expect(alicePage.getByTestId('upload-progress')).toBeHidden({ timeout: 30_000 })
  expect(new Set(chunkRequests).size).toBe(Math.ceil(file.length / E2E_CHUNK_SIZE))

  const bobImage = bobPage.getByTestId('messages').locator('img.artifact-img')
  await expect(bobImage).toBeVisible()
  await expect(bobImage).toHaveAttribute('alt', 'big-pixel.png')
  await expect(alicePage.getByTestId('messages').locator('img.artifact-img')).toBeVisible()

  const src = await bobImage.getAttribute('src')
  const media = await bobPage.request.get(src!)
  expect(media.status()).toBe(200)
  expect((await media.body()).length).toBe(file.length)

  await aliceContext.close()
  await bobContext.close()
})

test('cancelling an upload removes the progress bar and sends nothing', async ({ browser }) => {
  const alice = uniqueUser('alice')
  const bob = uniqueUser('bob')
  const context = await browser.newContext()
  const page = await context.newPage()
  await registerViaUi(page, alice)
  const bobContext = await browser.newContext()
  await registerViaUi(await bobContext.newPage(), bob)
  await openPrivateChatViaSearch(page, bob.username)

  await page.route('**/files/v1/uploads/*/chunks/*', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 3000))
    await route.continue().catch(() => undefined)
  })
  const aborted = page.waitForRequest(
    (request) => request.method() === 'DELETE' && request.url().includes('/files/v1/uploads/'),
  )

  await page.getByTestId('attach-input').setInputFiles({
    name: 'cancel-me.png',
    mimeType: 'image/png',
    buffer: pngLargerThan(2),
  })
  await expect(page.getByTestId('upload-progress')).toBeVisible()
  await page.getByTestId('upload-cancel').click()
  await aborted
  await expect(page.getByTestId('upload-progress')).toBeHidden()
  await expect(page.getByTestId('chat-error')).toHaveCount(0)
  await page.waitForTimeout(1500)
  await expect(page.getByTestId('messages').locator('img.artifact-img')).toHaveCount(0)

  await context.close()
  await bobContext.close()
})
