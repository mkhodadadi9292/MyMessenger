import { expect, type Page } from '@playwright/test'

export const BACKEND_URL = 'http://127.0.0.1:8000'

const RUN = Date.now().toString(36)
let counter = 0

export interface TestUser {
  username: string
  identifier: string
  firstName: string
}

export function uniqueUser(prefix: string): TestUser {
  const username = `${prefix}${RUN}${counter++}`
  return { username, identifier: `${username}@example.com`, firstName: prefix }
}

export async function getOtpCode(page: Page, identifier: string): Promise<string> {
  const response = await page.request.get(
    `${BACKEND_URL}/api/v1/auth/otp/dev/latest?identifier=${encodeURIComponent(identifier)}`,
  )
  expect(response.ok()).toBeTruthy()
  const body = await response.json()
  return body.code as string
}

export async function registerViaUi(page: Page, user: TestUser): Promise<void> {
  await page.goto('/')
  await page.getByTestId('identifier').fill(user.identifier)
  await page.getByTestId('request-code').click()
  // wait until the OTP request round-trip finished so the dev endpoint has the code
  await expect(page.getByTestId('code')).toBeVisible()
  const code = await getOtpCode(page, user.identifier)
  await page.getByTestId('code').fill(code)
  await page.getByTestId('verify-code').click()
  await page.getByTestId('username').fill(user.username)
  await page.getByTestId('first-name').fill(user.firstName)
  await page.getByTestId('register').click()
  await expect(page.getByTestId('me-name')).toHaveText(user.username)
}

export async function loginViaUi(page: Page, user: TestUser): Promise<void> {
  await page.goto('/')
  await page.getByTestId('identifier').fill(user.identifier)
  await page.getByTestId('request-code').click()
  await expect(page.getByTestId('code')).toBeVisible()
  const code = await getOtpCode(page, user.identifier)
  await page.getByTestId('code').fill(code)
  await page.getByTestId('verify-code').click()
  await expect(page.getByTestId('me-name')).toHaveText(user.username)
}

export async function openPrivateChatViaSearch(
  page: Page,
  otherUsername: string,
): Promise<void> {
  await page.getByTestId('search-input').fill(otherUsername)
  await page.getByTestId('search-button').click()
  await page.getByTestId(`message-${otherUsername}`).click()
}

export async function sendMessage(page: Page, text: string): Promise<void> {
  await page.getByTestId('message-input').fill(text)
  await page.getByTestId('send-button').click()
}

export async function expectMessageVisible(page: Page, text: string): Promise<void> {
  await expect(page.getByTestId('messages').getByText(text, { exact: true })).toBeVisible()
}
