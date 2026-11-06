import { useEffect, useRef, useState } from 'react'

import { api, removeReaction, setReaction } from '../api'
import type { ReactionCode } from '../reactions'
import type {
  ArtifactKind,
  ChatOut,
  ContactOut,
  MemberOut,
  MessageOut,
  ReactionsChanged,
  UserPublic,
} from '../types'
import { startUpload, UploadCancelledError, type UploadHandle, type UploadProgress } from '../upload'
import { MessageBubble } from './MessageBubble'
import { realtime } from '../ws'

interface Props {
  user: UserPublic
  chatId: number | null
  onBack?: () => void
}

interface ActiveUpload {
  fileName: string
  progress: UploadProgress
}

function mergeMessages(current: MessageOut[], fetched: MessageOut[]): MessageOut[] {
  const byId = new Map(current.map((m) => [m.id, m]))
  for (const message of fetched) byId.set(message.id, message)
  return [...byId.values()].sort((a, b) => b.id - a.id)
}

function artifactKindOf(file: File): ArtifactKind {
  if (file.type.startsWith('image/')) return 'image'
  if (file.type.startsWith('video/')) return 'video'
  return 'audio'
}

function uploadLabel(progress: UploadProgress): string {
  const percent = progress.total ? Math.floor((progress.loaded / progress.total) * 100) : 0
  if (progress.phase === 'hashing') return `Preparing ${percent}%`
  if (progress.phase === 'finishing') return 'Finishing…'
  return `${percent}%`
}

function withReactions(messages: MessageOut[], change: ReactionsChanged): MessageOut[] {
  return messages.map((m) =>
    m.id === change.message_id ? { ...m, reactions: change.reactions } : m,
  )
}

export function ChatWindow({ user, chatId, onBack }: Props) {
  const [chat, setChat] = useState<ChatOut | null>(null)
  const [members, setMembers] = useState<MemberOut[]>([])
  const [messages, setMessages] = useState<MessageOut[]>([])
  const [draft, setDraft] = useState('')
  const [replyTo, setReplyTo] = useState<MessageOut | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [blocked, setBlocked] = useState<ContactOut[]>([])
  const [inviteUsername, setInviteUsername] = useState('')
  const [upload, setUpload] = useState<ActiveUpload | null>(null)
  const uploadHandle = useRef<UploadHandle | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setChat(null)
    setMembers([])
    setMessages([])
    setReplyTo(null)
    setError(null)
    if (chatId === null) return
    api<ChatOut>(`/chats/${chatId}`).then(setChat).catch(() => {})
    api<MemberOut[]>(`/chats/${chatId}/members`).then(setMembers).catch(() => {})
    api<ContactOut[]>('/blocked').then(setBlocked).catch(() => {})
  }, [chatId])

  useEffect(() => {
    if (chatId === null) return
    const load = () => {
      api<MessageOut[]>(`/chats/${chatId}/messages`)
        .then((fetched) =>
          setMessages((prev) =>
            mergeMessages(
              prev.filter((m) => m.chat_id === chatId),
              fetched,
            ),
          ),
        )
        .catch(() => {})
    }
    load()
    realtime.subscribe(chatId)
    const offEvent = realtime.onEvent((event) => {
      if (event.type === 'message.new' && event.message.chat_id === chatId) {
        setMessages((prev) =>
          prev.some((m) => m.id === event.message.id) ? prev : [event.message, ...prev],
        )
      }
      if (event.type === 'chat.list_changed') load()
      if (event.type === 'message.reactions_changed' && event.chat_id === chatId) {
        setMessages((prev) => withReactions(prev, event))
      }
    })
    // polling is only a fallback while the websocket is down
    const timer = setInterval(() => {
      if (!realtime.connected) load()
    }, 2000)
    return () => {
      offEvent()
      clearInterval(timer)
      realtime.unsubscribe(chatId)
      uploadHandle.current?.cancel()
    }
  }, [chatId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (chatId === null) {
    return (
      <main className="chat-window empty">
        <p>Select a chat to start messaging</p>
      </main>
    )
  }

  const otherMember =
    chat?.type === 'private' ? members.find((m) => m.user_id !== user.id) : null
  const displayName = (member: MemberOut) =>
    [member.first_name, member.last_name].filter(Boolean).join(' ')
  const title =
    chat?.type === 'group'
      ? chat.title
      : otherMember
        ? displayName(otherMember) || otherMember.username
        : 'Private chat'
  const otherBlocked = otherMember
    ? blocked.some((b) => b.user_id === otherMember.user_id)
    : false

  const send = async () => {
    const text = draft.trim()
    if (!text && !replyTo) return
    setError(null)
    try {
      await api(`/chats/${chatId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, reply_to_id: replyTo?.id ?? null }),
      })
      setDraft('')
      setReplyTo(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to send')
    }
  }

  const react = async (message: MessageOut, code: ReactionCode) => {
    setError(null)
    const current = message.reactions.find((r) => r.user_ids.includes(user.id))
    try {
      const change =
        current?.code === code
          ? await removeReaction(message.id)
          : await setReaction(message.id, code)
      setMessages((prev) => withReactions(prev, change))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to react')
    }
  }

  const attach = async (file: File) => {
    if (uploadHandle.current) return
    setError(null)
    const handle = startUpload({
      chatId,
      file,
      kind: artifactKindOf(file),
      replyToId: replyTo?.id ?? null,
      onProgress: (progress) => setUpload({ fileName: file.name, progress }),
    })
    uploadHandle.current = handle
    setUpload({ fileName: file.name, progress: { phase: 'hashing', loaded: 0, total: file.size } })
    try {
      await handle.done
      setReplyTo(null)
    } catch (err) {
      if (!(err instanceof UploadCancelledError)) {
        setError(err instanceof Error ? err.message : 'failed to upload')
      }
    } finally {
      uploadHandle.current = null
      setUpload(null)
    }
  }

  const cancelUpload = () => uploadHandle.current?.cancel()

  const toggleBlock = async () => {
    if (!otherMember) return
    setError(null)
    try {
      if (otherBlocked) {
        await api(`/blocked/${otherMember.user_id}`, { method: 'DELETE' })
      } else {
        await api(`/blocked/${otherMember.user_id}`, { method: 'POST' })
      }
      const updated = await api<ContactOut[]>('/blocked')
      setBlocked(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed')
    }
  }

  const inviteToGroup = async () => {
    setError(null)
    try {
      const results = await api<UserPublic[]>(
        `/users/search?q=${encodeURIComponent(inviteUsername.trim())}`,
      )
      const target = results.find((r) => r.username === inviteUsername.trim())
      if (!target) throw new Error('user not found')
      await api(`/chats/${chatId}/invites`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: target.id }),
      })
      setInviteUsername('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to invite')
    }
  }

  return (
    <main className="chat-window">
      <header className="chat-header">
        {onBack && (
          <button className="back-button" data-testid="back-button" onClick={onBack}>
            ←
          </button>
        )}
        <div>
          <span className="chat-title" data-testid="chat-title">
            {title}
          </span>
          <span className="chat-subtitle">
            {chat?.type === 'group' ? `${members.length} members` : otherMember?.username ?? ''}
          </span>
        </div>
        <div className="chat-actions">
          {chat?.type === 'private' && (
            <button data-testid="block-toggle" onClick={toggleBlock}>
              {otherBlocked ? 'Unblock' : 'Block'}
            </button>
          )}
          {chat?.type === 'group' && (
            <div className="invite-box">
              <input
                data-testid="invite-username"
                placeholder="Invite by username"
                value={inviteUsername}
                onChange={(e) => setInviteUsername(e.target.value)}
              />
              <button data-testid="invite-submit" disabled={!inviteUsername.trim()} onClick={inviteToGroup}>
                Invite
              </button>
            </div>
          )}
        </div>
      </header>

      {error && <div className="error-banner" data-testid="chat-error">{error}</div>}

      <div className="messages" data-testid="messages">
        {/* API returns newest-first; render oldest-first so messages flow
            top-to-bottom by arrival time. */}
        {[...messages].reverse().map((message) => (
          <MessageBubble
             key={message.id}
             message={message}
             me={user}
             onReply={setReplyTo}
             onReact={react}
             showSender={chat?.type === 'group'}
           />
        ))}
        <div ref={bottomRef} />
      </div>

      {replyTo && (
        <div className="reply-preview" data-testid="reply-preview">
          <span>Replying to: {replyTo.text ?? replyTo.artifact?.file_name ?? 'message'}</span>
          <button onClick={() => setReplyTo(null)}>✕</button>
        </div>
      )}

      {upload && (
        <div className="upload-progress" data-testid="upload-progress">
          <span className="upload-name">{upload.fileName}</span>
          <progress
            max={upload.progress.total || 1}
            value={upload.progress.loaded}
            aria-label={`Uploading ${upload.fileName}`}
          />
          <span className="upload-percent" data-testid="upload-percent">
            {uploadLabel(upload.progress)}
          </span>
          <button data-testid="upload-cancel" title="Cancel upload" onClick={cancelUpload}>
            ✕
          </button>
        </div>
      )}

      <footer className="composer">
        <input
          ref={fileInput}
          type="file"
          data-testid="attach-input"
          accept="image/*,video/*,audio/*"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void attach(file)
            e.target.value = ''
          }}
        />
        <button
          className="attach-button"
          data-testid="attach-button"
          title="Attach image / video / audio"
          disabled={upload !== null}
          onClick={() => fileInput.current?.click()}
        >
          📎
        </button>
        <input
          data-testid="message-input"
          placeholder="Message"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void send()
          }}
        />
        <button className="send-button" data-testid="send-button" onClick={() => void send()}>
          ➤
        </button>
      </footer>
    </main>
  )
}
