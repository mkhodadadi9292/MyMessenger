import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearTokens, setTokens } from '../api'
import { notifications } from '../sse'
import type { NotificationOut } from '../types'

class MockEventSource {
  static instances: MockEventSource[] = []
  url: string
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  private listeners = new Map<string, Set<(event: MessageEvent) => void>>()

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void): void {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set())
    this.listeners.get(type)!.add(listener)
  }

  removeEventListener(type: string, listener: (event: MessageEvent) => void): void {
    this.listeners.get(type)?.delete(listener)
  }

  close(): void {
    this.closed = true
  }

  emit(type: string, data: unknown): void {
    const event = { data: JSON.stringify(data) } as MessageEvent
    this.listeners.get(type)?.forEach((listener) => listener(event))
  }
}

vi.stubGlobal('EventSource', MockEventSource)

const sampleNotification: NotificationOut = {
  id: 1,
  type: 'message',
  chat_id: 7,
  chat_title: null,
  sender_id: 2,
  sender_username: 'bob',
  preview: 'hello',
  message_id: 9,
  invite_id: null,
  is_read: false,
  created_at: '2026-10-23T10:00:00',
}

describe('NotificationClient', () => {
  beforeEach(() => {
    MockEventSource.instances = []
    notifications.disconnect()
  })

  afterEach(() => {
    notifications.disconnect()
    clearTokens()
  })

  it('builds the stream URL with the access token', () => {
    setTokens({ access_token: 'test-token', refresh_token: 'r', user: {} as never })
    notifications.connect()
    expect(MockEventSource.instances).toHaveLength(1)
    expect(MockEventSource.instances[0].url).toBe(
      '/api/v1/notifications/stream?token=test-token',
    )
  })

  it('does not connect without a token', () => {
    notifications.connect()
    expect(MockEventSource.instances).toHaveLength(0)
    expect(notifications.connected).toBe(false)
  })

  it('marks the client connected on open', () => {
    setTokens({ access_token: 'test-token', refresh_token: 'r', user: {} as never })
    notifications.connect()
    MockEventSource.instances[0].onopen?.()
    expect(notifications.connected).toBe(true)
  })

  it('delivers notification.new events to handlers', () => {
    setTokens({ access_token: 'test-token', refresh_token: 'r', user: {} as never })
    notifications.connect()
    const handler = vi.fn()
    const off = notifications.onEvent(handler)
    MockEventSource.instances[0].emit('notification.new', {
      type: 'notification.new',
      notification: sampleNotification,
      unread_count: 3,
    })
    expect(handler).toHaveBeenCalledTimes(1)
    expect(handler.mock.calls[0][0]).toEqual({
      type: 'notification.new',
      notification: sampleNotification,
      unread_count: 3,
    })
    off()
    MockEventSource.instances[0].emit('notification.new', {
      type: 'notification.new',
      notification: sampleNotification,
      unread_count: 4,
    })
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('disconnects and closes the underlying source', () => {
    setTokens({ access_token: 'test-token', refresh_token: 'r', user: {} as never })
    notifications.connect()
    const source = MockEventSource.instances[0]
    source.onopen?.()
    notifications.disconnect()
    expect(source.closed).toBe(true)
    expect(notifications.connected).toBe(false)
  })
})
