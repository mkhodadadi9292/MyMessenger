import { useEffect, useState } from 'react'

import { api, clearTokens, hasSession } from './api'
import { AuthScreen } from './components/AuthScreen'
import { ChatWindow } from './components/ChatWindow'
import { ContactsPage } from './components/ContactsPage'
import { SettingsPage } from './components/SettingsPage'
import { Sidebar } from './components/Sidebar'
import type { ChatListItem, UserPublic } from './types'

type View = 'main' | 'settings' | 'contacts'

export default function App() {
  const [user, setUser] = useState<UserPublic | null>(null)
  const [loading, setLoading] = useState(hasSession())
  const [chats, setChats] = useState<ChatListItem[]>([])
  const [selectedChatId, setSelectedChatId] = useState<number | null>(null)
  const [view, setView] = useState<View>('main')
  const [isMobile, setIsMobile] = useState(
    () => window.matchMedia('(max-width: 768px)').matches,
  )

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
    const timer = setInterval(load, 3000)
    return () => clearInterval(timer)
  }, [user])

  if (loading) return <div className="splash">Loading…</div>

  if (!user) {
    return <AuthScreen onAuthed={setUser} />
  }

  const logout = () => {
    clearTokens()
    setUser(null)
    setSelectedChatId(null)
    setView('main')
  }

  return (
    <>
      <div className={`layout ${isMobile && selectedChatId !== null ? 'chat-open' : ''}`}>
        <Sidebar
          user={user}
          chats={sortedChats}
          selectedChatId={selectedChatId}
          onSelectChat={(id) => {
            setSelectedChatId(id)
            setView('main')
          }}
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
