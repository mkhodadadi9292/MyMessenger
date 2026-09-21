import { useEffect, useState } from 'react'

import { api, clearTokens, hasSession } from './api'
import { AuthScreen } from './components/AuthScreen'
import { ChatWindow } from './components/ChatWindow'
import { Sidebar } from './components/Sidebar'
import type { ChatListItem, UserPublic } from './types'

export default function App() {
  const [user, setUser] = useState<UserPublic | null>(null)
  const [loading, setLoading] = useState(hasSession())
  const [chats, setChats] = useState<ChatListItem[]>([])
  const [selectedChatId, setSelectedChatId] = useState<number | null>(null)

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

  return (
    <div className="layout">
      <Sidebar
        user={user}
        chats={chats}
        selectedChatId={selectedChatId}
        onSelectChat={setSelectedChatId}
        onLogout={() => {
          clearTokens()
          setUser(null)
          setSelectedChatId(null)
        }}
      />
      <ChatWindow
        key={selectedChatId ?? 'none'}
        user={user}
        chatId={selectedChatId}
      />
    </div>
  )
}
