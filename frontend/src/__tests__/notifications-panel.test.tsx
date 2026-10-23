import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { NotificationsPanel } from '../components/NotificationsPanel'
import type { NotificationOut } from '../types'

const messageNotification: NotificationOut = {
  id: 1,
  type: 'message',
  chat_id: 7,
  chat_title: null,
  sender_id: 2,
  sender_username: 'bob',
  preview: 'hello there',
  message_id: 9,
  invite_id: null,
  is_read: false,
  created_at: '2026-10-23T10:00:00',
}

const inviteNotification: NotificationOut = {
  id: 2,
  type: 'invite',
  chat_id: 8,
  chat_title: 'Team',
  sender_id: 3,
  sender_username: 'alice',
  preview: 'invited you to Team',
  message_id: null,
  invite_id: 4,
  is_read: false,
  created_at: '2026-10-23T11:00:00',
}

function renderPanel(
  props: Partial<{
    notifications: NotificationOut[]
    unreadCount: number
    onOpenChat: (chatId: number) => void
    onOpenInvites: () => void
    onMarkAllRead: () => void
    onMarkChatRead: (chatId: number) => void
  }> = {},
) {
  const defaults = {
    notifications: [],
    unreadCount: 0,
    onOpenChat: vi.fn(),
    onOpenInvites: vi.fn(),
    onMarkAllRead: vi.fn(),
    onMarkChatRead: vi.fn(),
  }
  render(<NotificationsPanel {...defaults} {...props} />)
  return defaults
}

describe('NotificationsPanel', () => {
  it('hides the badge when there are no unread notifications', () => {
    renderPanel({ unreadCount: 0 })
    expect(screen.queryByTestId('notifications-badge')).toBeNull()
  })

  it('shows the unread count in the badge', () => {
    renderPanel({ unreadCount: 3 })
    expect(screen.getByTestId('notifications-badge')).toHaveTextContent('3')
  })

  it('lists notifications with sender and preview when opened', () => {
    renderPanel({ notifications: [messageNotification] })
    fireEvent.click(screen.getByTestId('notifications-button'))
    const panel = screen.getByTestId('notifications-panel')
    expect(panel).toContainElement(screen.getByTestId('notification-1'))
    expect(screen.getByTestId('notification-1')).toHaveTextContent('bob')
    expect(screen.getByTestId('notification-1')).toHaveTextContent('hello there')
  })

  it('shows an empty state when there are no notifications', () => {
    renderPanel({ notifications: [] })
    fireEvent.click(screen.getByTestId('notifications-button'))
    expect(screen.getByTestId('notifications-panel')).toHaveTextContent(
      'No notifications yet',
    )
  })

  it('clicking a message notification marks the chat read and opens it', () => {
    const handlers = renderPanel({ notifications: [messageNotification] })
    fireEvent.click(screen.getByTestId('notifications-button'))
    fireEvent.click(screen.getByTestId('notification-1'))
    expect(handlers.onMarkChatRead).toHaveBeenCalledWith(7)
    expect(handlers.onOpenChat).toHaveBeenCalledWith(7)
  })

  it('clicking an invite notification opens the invites panel', () => {
    const handlers = renderPanel({ notifications: [inviteNotification] })
    fireEvent.click(screen.getByTestId('notifications-button'))
    fireEvent.click(screen.getByTestId('notification-2'))
    expect(handlers.onMarkChatRead).toHaveBeenCalledWith(8)
    expect(handlers.onOpenInvites).toHaveBeenCalled()
  })

  it('mark-all-read button triggers the callback', () => {
    const handlers = renderPanel({ notifications: [messageNotification], unreadCount: 1 })
    fireEvent.click(screen.getByTestId('notifications-button'))
    fireEvent.click(screen.getByTestId('notifications-mark-all'))
    expect(handlers.onMarkAllRead).toHaveBeenCalled()
  })
})
