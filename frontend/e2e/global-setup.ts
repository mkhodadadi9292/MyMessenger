import { mkdirSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

export default function globalSetup() {
  // NOTE: webServers start BEFORE globalSetup, so the backend's own start
  // command wipes and migrates its database; here we only reset media files.
  const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..')
  for (const directory of ['e2e-media', 'e2e-uploads']) {
    rmSync(join(root, 'data', directory), { recursive: true, force: true })
    mkdirSync(join(root, 'data', directory), { recursive: true })
  }
}
