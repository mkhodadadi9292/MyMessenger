import { getAccessToken } from './api'
import type { NotificationOut } from './types'

export type NotificationEvent = {
  type: 'notification.new'
  notification: NotificationOut
  unread_count: number
}

type Handler = (event: NotificationEvent) => void

class NotificationClient {
  private source: EventSource | null = null
  private handlers = new Set<Handler>()
  private _connected = false

  get connected(): boolean {
    return this._connected
  }

  onEvent(handler: Handler): () => void {
    this.handlers.add(handler)
    return () => {
      this.handlers.delete(handler)
    }
  }

  connect(): void {
    if (this.source) return
    const token = getAccessToken()
    if (!token) return
    // EventSource cannot send headers → token in the query string (same as /ws)
    const source = new EventSource(
      `/api/v1/notifications/stream?token=${encodeURIComponent(token)}`,
    )
    this.source = source
    source.onopen = () => {
      this._connected = true
    }
    source.addEventListener('notification.new', (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data as string) as NotificationEvent
        this.handlers.forEach((handler) => handler(payload))
      } catch {
        // ignore malformed frames
      }
    })
    // EventSource reconnects natively (server sends retry: 3000); onerror only
    // flips the connected flag.
    source.onerror = () => {
      this._connected = false
    }
  }

  disconnect(): void {
    this.source?.close()
    this.source = null
    this._connected = false
  }
}

export const notifications = new NotificationClient()
