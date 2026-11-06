import { execSync } from 'node:child_process'

export const E2E_POSTGRES_CONTAINER = 'mm-e2e-postgres'
export const E2E_POSTGRES_PORT = 55432
export const E2E_POSTGRES_PASSWORD = 'e2e-postgres'
export const E2E_REDIS_CONTAINER = 'mm-e2e-redis'
export const E2E_REDIS_PORT = 56379
export const E2E_CHUNK_SIZE = 256 * 1024

export function removeE2eContainers(): void {
  for (const name of [E2E_POSTGRES_CONTAINER, E2E_REDIS_CONTAINER]) {
    execSync(`docker rm -f ${name} >/dev/null 2>&1 || true`, { stdio: 'ignore' })
  }
}
