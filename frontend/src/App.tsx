import { useEffect, useRef, useState } from 'react'

import { api, clearTokens, fetchUnreadCount, hasSession, markNotificationsRead } from './api'
import { AuthScreen } from './components/AuthScreen'
import { ChatWindow } from './components/ChatWindow'
import { ContactsPage } from './components/ContactsPage'
import { SettingsPage } from './components/SettingsPage'
import { Sidebar } from './components/Sidebar'
import type { ChatListItem, UserPublic } from './types'
import { notifications } from './sse'
import { realtime } from './ws'

type View = 'main' | 'settings' | 'contacts'

export default function App() {
  const [user, setUser] = useState<UserPublic | null>(null)
  const [loading, setLoading] = useState(hasSession())
  const [chats, setChats] = useState<ChatListItem[]>([])
  const [selectedChatId, setSelectedChatId] = useState<number | null>(null)
  const [unreadCount, setUnreadCount] = useState(0)
  const [view, setView] = useState<View>('main')
  const [isMobile, setIsMobile] = useState(
    () => window.matchMedia('(max-width: 768px)').matches,
  )
  const selectedChatRef = useRef<number | null>(null)
  selectedChatRef.current = selectedChatId

  useEffect(() => {
    const query = window.matchMedia('(max-width: 768px)')
    const onChange = (event: MediaQueryListEvent) => setIsMobile(event.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  // Sidebar order: most recent last-message arrival time first
  const sortedChats = [...chats].sort((a, b) => {
    const ta = a.last_message?.created_at ?? a.created_at
    const tb = b.last_message?.created_at ?? b.created_at
    return Date.parse(tb) - Date.parse(ta)
  })

  useEffect(() => {
    if (!hasSession()) {
      setLoading(false)
      return
    }
    api<UserPublic>('/users/me')
      .then(setUser)
      .catch(() => clearTokens())
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!user) return
    const load = () => {
      api<ChatListItem[]>('/chats')
        .then(setChats)
        .catch(() => {})
    }
    load()
    const offEvent = realtime.onEvent((event) => {
      if (event.type === 'chat.list_changed') load()
      // reading messages in the open chat keeps its badge cleared
      if (
        event.type === 'message.new' &&
        selectedChatRef.current !== null &&
        event.message.chat_id === selectedChatRef.current
      ) {
        markNotificationsRead(selectedChatRef.current)
          .then((result) => setUnreadCount(result.unread_count))
          .catch(() => {})
      }
    })
    realtime.connect()
    // slow polling safety net: heals any missed WS events (e.g. throttled
    // background tabs) while the socket remains the fast path
    const timer = setInterval(load, 5000)
    return () => {
      offEvent()
      clearInterval(timer)
    }
  }, [user])

  useEffect(() => {
    if (!user) return
    fetchUnreadCount()
      .then((result) => setUnreadCount(result.count))
      .catch(() => {})
    const offNotification = notifications.onEvent((event) => {
      if (event.type === 'notification.new') {
        setUnreadCount(event.unread_count)
      }
    })
    notifications.connect()
    return () => {
      offNotification()
      notifications.disconnect()
    }
  }, [user])

  if (loading) return <div className="splash">Loading…</div>

  if (!user) {
    return <AuthScreen onAuthed={setUser} />
  }

  const handleMarkNotificationsRead = (chatId: number | null) => {
    markNotificationsRead(chatId)
      .then((result) => setUnreadCount(result.unread_count))
      .catch(() => {})
  }

  const logout = () => {
    realtime.disconnect()
    notifications.disconnect()
    clearTokens()
    setUser(null)
    setSelectedChatId(null)
    setUnreadCount(0)
    setView('main')
  }

  return (
    <>
      <div className={`layout ${isMobile && selectedChatId !== null ? 'chat-open' : ''}`}>
        <Sidebar
          user={user}
          chats={sortedChats}
          selectedChatId={selectedChatId}
          unreadCount={unreadCount}
          onSelectChat={(id) => {
            setSelectedChatId(id)
            setView('main')
            handleMarkNotificationsRead(id)
          }}
          onMarkNotificationsRead={handleMarkNotificationsRead}
          onOpenSettings={() => setView('settings')}
          onOpenContacts={() => setView('contacts')}
          onLogout={logout}
        />
        <ChatWindow
          key={selectedChatId ?? 'none'}
          user={user}
          chatId={selectedChatId}
          onBack={() => setSelectedChatId(null)}
        />
      </div>

      {view === 'settings' && (
        <SettingsPage
          user={user}
          onClose={() => setView('main')}
          onGroupCreated={(chatId) => {
            setSelectedChatId(chatId)
            setView('main')
          }}
          onLogout={logout}
          onUserUpdated={setUser}
        />
      )}

      {view === 'contacts' && (
        <ContactsPage user={user} onClose={() => setView('main')} />
      )}
    </>
  )
}
