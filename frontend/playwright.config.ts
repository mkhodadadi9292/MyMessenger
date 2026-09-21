import { defineConfig } from '@playwright/test'

const BACKEND_URL = 'http://127.0.0.1:8000'

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  expect: { timeout: 15_000 },
  globalSetup: './e2e/global-setup.ts',
  webServer: [
    {
      command:
        'cd .. && rm -f data/e2e-playwright.db && .venv/bin/alembic upgrade head && .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000',
      url: `${BACKEND_URL}/health`,
      reuseExistingServer: true,
      timeout: 60_000,
      env: {
        DATABASE_URL: 'sqlite+aiosqlite:///./data/e2e-playwright.db',
        MEDIA_ROOT: './data/e2e-media',
        JWT_SECRET: 'e2e-secret-0123456789-0123456789',
        DEBUG: 'true',
      },
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
  projects: [{ name: 'chrome', use: { browserName: 'chromium', channel: 'chrome' } }],
})
