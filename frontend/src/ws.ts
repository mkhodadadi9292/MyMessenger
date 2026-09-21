import { getAccessToken } from './api'
import type { MessageOut } from './types'

export type RealtimeEvent =
  | { type: 'message.new'; message: MessageOut }
  | { type: 'chat.list_changed' }
  | { type: 'error'; detail: string }
  | { type: 'pong' }
  | { type: 'message.sent'; message: MessageOut }

type Handler = (event: RealtimeEvent) => void

class RealtimeClient {
  private ws: WebSocket | null = null
  private handlers = new Set<Handler>()
  private subscribed = new Set<number>()
  private _connected = false
  private retryTimer: ReturnType<typeof setTimeout> | null = null

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
    if (this.ws) return
    const token = getAccessToken()
    if (!token) return
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${window.location.host}/ws?token=${encodeURIComponent(token)}`)
    this.ws = ws
    ws.onopen = () => {
      this._connected = true
      for (const chatId of this.subscribed) {
        this.send({ type: 'subscribe', chat_id: chatId })
      }
    }
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data as string) as RealtimeEvent
        this.handlers.forEach((handler) => handler(payload))
      } catch {
        // ignore malformed frames
      }
    }
    ws.onclose = () => {
      this._connected = false
      this.ws = null
      this.retryTimer = setTimeout(() => this.connect(), 2000)
    }
    ws.onerror = () => {
      ws.close()
    }
  }

  disconnect(): void {
    if (this.retryTimer) clearTimeout(this.retryTimer)
    this.retryTimer = null
    this.ws?.close()
    this.ws = null
    this._connected = false
    this.subscribed.clear()
  }

  subscribe(chatId: number): void {
    this.subscribed.add(chatId)
    if (this._connected) this.send({ type: 'subscribe', chat_id: chatId })
  }

  unsubscribe(chatId: number): void {
    this.subscribed.delete(chatId)
    if (this._connected) this.send({ type: 'unsubscribe', chat_id: chatId })
  }

  private send(payload: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload))
    }
  }
}

export const realtime = new RealtimeClient()
