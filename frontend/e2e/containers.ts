import { execSync } from 'node:child_process'

export const E2E_POSTGRES_CONTAINER = 'mm-e2e-postgres'
export const E2E_POSTGRES_PORT = 55432
export const E2E_POSTGRES_PASSWORD = 'e2e-postgres'

export function removeE2eContainers(): void {
  execSync(`docker rm -f ${E2E_POSTGRES_CONTAINER} >/dev/null 2>&1 || true`, { stdio: 'ignore' })
}
