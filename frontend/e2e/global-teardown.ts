import { removeE2eContainers } from './containers'

export default function globalTeardown() {
  removeE2eContainers()
}
