import { mkdirSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

export default function globalSetup() {
  // NOTE: webServers start BEFORE globalSetup, so the backend's own start
  // command wipes and migrates its database; here we only reset media files.
  const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..')
  rmSync(join(root, 'data', 'e2e-media'), { recursive: true, force: true })
  mkdirSync(join(root, 'data', 'e2e-media'), { recursive: true })
}
