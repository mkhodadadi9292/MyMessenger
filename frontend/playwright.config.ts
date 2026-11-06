import { defineConfig } from '@playwright/test'

import {
  E2E_POSTGRES_CONTAINER,
  E2E_POSTGRES_PASSWORD,
  E2E_POSTGRES_PORT,
} from './e2e/containers'

const BACKEND_URL = 'http://127.0.0.1:8000'
const POSTGRES_URL = (database: string) =>
  `postgresql+asyncpg://postgres:${E2E_POSTGRES_PASSWORD}@127.0.0.1:${E2E_POSTGRES_PORT}/${database}`

const startPostgres = [
  `docker rm -f ${E2E_POSTGRES_CONTAINER} >/dev/null 2>&1 || true`,
  `docker run -d --rm --name ${E2E_POSTGRES_CONTAINER} -e POSTGRES_PASSWORD=${E2E_POSTGRES_PASSWORD} -e POSTGRES_DB=messenger -p 127.0.0.1:${E2E_POSTGRES_PORT}:5432 --tmpfs /var/lib/postgresql/data -v "$PWD/e2e/postgres-init.sql:/docker-entrypoint-initdb.d/init.sql:ro" postgres:17-alpine >/dev/null`,
].join(' && ')

const migrateWhenReady = (alembic: string) =>
  `attempt=0; until ${alembic} upgrade head; do attempt=$((attempt + 1)); [ $attempt -ge 60 ] && exit 1; sleep 1; done`

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
  globalTeardown: './e2e/global-teardown.ts',
  webServer: [
    {
      command: `${startPostgres} && cd .. && ${migrateWhenReady('.venv/bin/alembic')} && .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000`,
      url: `${BACKEND_URL}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        DATABASE_URL: POSTGRES_URL('messenger'),
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
