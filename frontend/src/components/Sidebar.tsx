import { useEffect, useState } from 'react'

import { api } from '../api'
import { formatTime } from '../time'
import type { ChatListItem, ContactOut, InviteOut, UserPublic } from '../types'

interface SearchResult {
  id: number
  username: string
  first_name: string
}

interface Props {
  user: UserPublic
  chats: ChatListItem[]
  selectedChatId: number | null
  onSelectChat: (id: number) => void
  onLogout: () => void
}

function chatTitle(chat: ChatListItem, me: UserPublic): string {
  if (chat.type === 'group') return chat.title ?? 'Group'
  if (chat.last_message && chat.last_message.sender.id !== me.id) {
    return chat.last_message.sender.username
  }
  return 'Private chat'
}

export function Sidebar({ user, chats, selectedChatId, onSelectChat, onLogout }: Props) {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [contacts, setContacts] = useState<ContactOut[]>([])
  const [invites, setInvites] = useState<InviteOut[]>([])
  const [showInvites, setShowInvites] = useState(false)
  const [showNewGroup, setShowNewGroup] = useState(false)
  const [showJoin, setShowJoin] = useState(false)
  const [groupTitle, setGroupTitle] = useState('')
  const [groupPublic, setGroupPublic] = useState(false)
  const [joinValue, setJoinValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  const refreshInvites = () => {
    api<InviteOut[]>('/me/invites')
      .then(setInvites)
      .catch(() => {})
  }

  useEffect(() => {
    api<ContactOut[]>('/contacts')
      .then(setContacts)
      .catch(() => {})
    refreshInvites()
  }, [])

  const doSearch = async () => {
    setError(null)
    if (!searchQuery.trim()) return
    try {
      const results = await api<SearchResult[]>(
        `/users/search?q=${encodeURIComponent(searchQuery.trim())}`,
      )
      setSearchResults(results)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'search failed')
    }
  }

  const addContact = async (identifier: string) => {
    setError(null)
    try {
      await api('/contacts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier }),
      })
      const updated = await api<ContactOut[]>('/contacts')
      setContacts(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'add failed')
    }
  }

  const openPrivateChat = async (userId: number) => {
    setError(null)
    try {
      const chat = await api<ChatListItem>('/chats/private', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
      })
      onSelectChat(chat.id)
      setSearchQuery('')
      setSearchResults([])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to open chat')
    }
  }

  const createGroup = async () => {
    setError(null)
    try {
      const chat = await api<ChatListItem>('/chats/groups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: groupTitle, is_public: groupPublic }),
      })
      setShowNewGroup(false)
      setGroupTitle('')
      onSelectChat(chat.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to create group')
    }
  }

  const joinGroup = async () => {
    setError(null)
    const value = joinValue.trim()
    try {
      if (/^\d+$/.test(value)) {
        await api(`/chats/${value}/join`, { method: 'POST' })
      } else {
        await api(`/invites/${encodeURIComponent(value)}/accept`, { method: 'POST' })
      }
      setShowJoin(false)
      setJoinValue('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to join')
    }
  }

  const respondInvite = async (inviteId: number, accept: boolean) => {
    try {
      await api(`/me/invites/${inviteId}/${accept ? 'accept' : 'decline'}`, {
        method: 'POST',
      })
      refreshInvites()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed')
    }
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="me-name" data-testid="me-name">
          {user.username}
        </span>
        <button className="icon-button" onClick={onLogout} title="Logout">
          ⏻
        </button>
      </div>

      <div className="sidebar-actions">
        <button data-testid="new-group" onClick={() => setShowNewGroup(true)}>
          New group
        </button>
        <button data-testid="join-group" onClick={() => setShowJoin(true)}>
          Join
        </button>
        <button
          data-testid="invites-button"
          onClick={() => {
            refreshInvites()
            setShowInvites(!showInvites)
          }}
        >
          Invites{invites.length > 0 ? ` (${invites.length})` : ''}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {showInvites && (
        <div className="panel" data-testid="invites-panel">
          <h3>Pending invites</h3>
          {invites.length === 0 && <p className="muted">No pending invites</p>}
          {invites.map((invite) => (
            <div key={invite.invite_id} className="invite-row">
              <span>
                {invite.title} — from {invite.inviter_name}
              </span>
              <div>
                <button
                  data-testid={`accept-invite-${invite.invite_id}`}
                  onClick={() => respondInvite(invite.invite_id, true)}
                >
                  Accept
                </button>
                <button
                  data-testid={`decline-invite-${invite.invite_id}`}
                  onClick={() => respondInvite(invite.invite_id, false)}
                >
                  Decline
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showNewGroup && (
        <div className="panel" data-testid="new-group-panel">
          <h3>New group</h3>
          <input
            data-testid="group-title"
            placeholder="Group title"
            value={groupTitle}
            onChange={(e) => setGroupTitle(e.target.value)}
          />
          <label className="checkbox-row">
            <input
              type="checkbox"
              data-testid="group-public"
              checked={groupPublic}
              onChange={(e) => setGroupPublic(e.target.checked)}
            />
            Public group
          </label>
          <button data-testid="create-group" disabled={!groupTitle} onClick={createGroup}>
            Create
          </button>
        </div>
      )}

      {showJoin && (
        <div className="panel" data-testid="join-panel">
          <h3>Join</h3>
          <input
            data-testid="join-value"
            placeholder="Group id or invite link token"
            value={joinValue}
            onChange={(e) => setJoinValue(e.target.value)}
          />
          <button data-testid="join-submit" disabled={!joinValue.trim()} onClick={joinGroup}>
            Join
          </button>
        </div>
      )}

      <div className="search-box">
        <input
          data-testid="search-input"
          placeholder="Search users (username or phone)"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && doSearch()}
        />
        <button data-testid="search-button" onClick={doSearch}>
          Search
        </button>
      </div>

      {searchResults.length > 0 && (
        <div className="panel" data-testid="search-results">
          {searchResults.map((result) => (
            <div key={result.id} className="invite-row">
              <span>
                {result.username} ({result.first_name})
              </span>
              <div>
                <button
                  data-testid={`add-contact-${result.username}`}
                  onClick={() => addContact(result.username)}
                >
                  Add
                </button>
                <button
                  data-testid={`message-${result.username}`}
                  onClick={() => openPrivateChat(result.id)}
                >
                  Message
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="chat-list" data-testid="chat-list">
        {chats.map((chat) => (
          <button
            key={chat.id}
            data-testid={`chat-item-${chat.id}`}
            className={`chat-item ${chat.id === selectedChatId ? 'selected' : ''}`}
            onClick={() => onSelectChat(chat.id)}
          >
            <span className="avatar-circle">{chatTitle(chat, user).charAt(0).toUpperCase()}</span>
            <span className="chat-item-body">
              <span className="chat-item-title">{chatTitle(chat, user)}</span>
              <span className="chat-item-preview">
                {chat.last_message
                  ? chat.last_message.deleted_at
                    ? 'deleted'
                    : chat.last_message.text ?? chat.last_message.artifact?.file_name
                  : 'no messages yet'}
              </span>
            </span>
            <span className="chat-item-time" data-testid={`chat-time-${chat.id}`}>
              {formatTime(chat.last_message?.created_at ?? chat.created_at)}
            </span>
          </button>
        ))}
        {chats.length === 0 && (
          <p className="muted">No chats yet — search for a user to start messaging.</p>
        )}
      </div>

      <div className="contacts-list">
        <h3>Contacts ({contacts.length})</h3>
        {contacts.map((contact) => (
          <div key={contact.user_id} className="contact-row">
            <span>
              {contact.username} ({contact.first_name})
            </span>
            <button data-testid={`contact-message-${contact.username}`} onClick={() => openPrivateChat(contact.user_id)}>
              Message
            </button>
          </div>
        ))}
      </div>
    </aside>
  )
}
