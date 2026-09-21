import type { ArtifactOut, MessageOut, UserPublic } from '../types'
import { formatTime } from '../time'

interface Props {
  message: MessageOut
  me: UserPublic
  onReply: (message: MessageOut) => void
  showSender?: boolean
}

const SENDER_COLORS = ['#e17076', '#7bc862', '#65aadd', '#ee7aae', '#a695e7', '#6ec9cb', '#faa774']

function senderColor(username: string): string {
  let hash = 0
  for (const char of username) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  return SENDER_COLORS[hash % SENDER_COLORS.length]
}

function ArtifactView({ artifact }: { artifact: ArtifactOut }) {
  if (artifact.kind === 'image') {
    return <img className="artifact-img" src={artifact.url} alt={artifact.file_name} />
  }
  if (artifact.kind === 'video') {
    return <video className="artifact-video" src={artifact.url} controls />
  }
  return <audio className="artifact-audio" src={artifact.url} controls />
}

function replyContent(message: MessageOut): string {
  const reply = message.reply_to
  if (!reply) return 'reply'
  if (reply.deleted) return `${reply.sender_username}: deleted`
  return `${reply.sender_username}: ${reply.text ?? reply.file_name ?? 'message'}`
}

export function MessageBubble({ message, me, onReply, showSender = false }: Props) {
  const mine = message.sender.id === me.id
  return (
    <div className={`message-row ${mine ? 'mine' : 'theirs'}`} data-testid={`message-${message.id}`}>
      <div className="bubble">
        {showSender && !mine && (
          <div
            className="sender-name"
            style={{ color: senderColor(message.sender.username) }}
          >
            {message.sender.first_name || message.sender.username}
          </div>
        )}
        {message.reply_to_id !== null && (
          <div className="reply-chip">↩ {replyContent(message)}</div>
        )}
        {message.artifact && <ArtifactView artifact={message.artifact} />}
        {message.deleted_at ? (
          <span className="deleted-text">deleted</span>
        ) : (
          <span className="message-text">{message.text}</span>
        )}
        {message.edited_at && !message.deleted_at && <span className="edited-mark"> edited</span>}
        <span className="message-time" data-testid={`time-${message.id}`}>
          {formatTime(message.created_at)}
        </span>
      </div>
      <button className="reply-button" data-testid={`reply-${message.id}`} onClick={() => onReply(message)}>
        ↩
      </button>
    </div>
  )
}
