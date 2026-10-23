import { useState } from 'react'

import { formatTime } from '../time'
import type { NotificationOut } from '../types'

interface Props {
  notifications: NotificationOut[]
  unreadCount: number
  onOpenChat: (chatId: number) => void
  onOpenInvites: () => void
  onMarkAllRead: () => void
  onMarkChatRead: (chatId: number) => void
}

export function NotificationsPanel({
  notifications,
  unreadCount,
  onOpenChat,
  onOpenInvites,
  onMarkAllRead,
  onMarkChatRead,
}: Props) {
  const [open, setOpen] = useState(false)

  const clickNotification = (notification: NotificationOut) => {
    onMarkChatRead(notification.chat_id)
    setOpen(false)
    if (notification.type === 'invite') {
      onOpenInvites()
    } else {
      onOpenChat(notification.chat_id)
    }
  }

  return (
    <div className="notifications">
      <button
        className="icon-button"
        data-testid="notifications-button"
        title="Notifications"
        onClick={() => setOpen(!open)}
      >
        🔔
        {unreadCount > 0 && (
          <span className="notification-badge" data-testid="notifications-badge">
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="panel notifications-panel" data-testid="notifications-panel">
          <div className="notifications-header">
            <h3>Notifications</h3>
            {unreadCount > 0 && (
              <button
                className="link-button"
                data-testid="notifications-mark-all"
                onClick={() => {
                  onMarkAllRead()
                }}
              >
                Mark all read
              </button>
            )}
          </div>
          {notifications.length === 0 && <p className="muted">No notifications yet</p>}
          {notifications.map((notification) => (
            <button
              key={notification.id}
              data-testid={`notification-${notification.id}`}
              className={`notification-item ${notification.is_read ? '' : 'unread'}`}
              onClick={() => clickNotification(notification)}
            >
              <span className="notification-icon">
                {notification.type === 'invite' ? '💌' : '💬'}
              </span>
              <span className="notification-body">
                <span className="notification-title">
                  {notification.type === 'invite'
                    ? notification.chat_title ?? 'Group invite'
                    : notification.chat_title ?? notification.sender_username ?? 'Chat'}
                </span>
                <span className="notification-preview">{notification.preview}</span>
              </span>
              <span className="notification-time">{formatTime(notification.created_at)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
