import { useRef, useState } from 'react'

import { REACTION_CODES, REACTION_EMOJI, type ReactionCode } from '../reactions'
import type { ArtifactOut, MessageOut, UserPublic } from '../types'
import { formatTime } from '../time'

interface Props {
  message: MessageOut
  me: UserPublic
  onReply: (message: MessageOut) => void
  onReact: (message: MessageOut, code: ReactionCode) => void
  showSender?: boolean
}

const PICKER_HEIGHT = 48
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

function ReactionChips({
  message,
  me,
  onReact,
}: {
  message: MessageOut
  me: UserPublic
  onReact: Props['onReact']
}) {
  if (message.reactions.length === 0) return null
  return (
    <div className="reactions" data-testid={`reactions-${message.id}`}>
      {message.reactions.map((reaction) => (
        <button
          key={reaction.code}
          className={`reaction-chip ${reaction.user_ids.includes(me.id) ? 'mine' : ''}`}
          data-testid={`reaction-${message.id}-${reaction.code}`}
          onClick={() => onReact(message, reaction.code)}
        >
          {REACTION_EMOJI[reaction.code]} {reaction.count}
        </button>
      ))}
    </div>
  )
}

export function MessageBubble({ message, me, onReply, onReact, showSender = false }: Props) {
  const mine = message.sender.id === me.id
  const [pickerOpen, setPickerOpen] = useState(false)
  const [pickerBelow, setPickerBelow] = useState(false)
  const rowRef = useRef<HTMLDivElement>(null)
  const canReact = !message.deleted_at

  const togglePicker = () => {
    const row = rowRef.current
    const list = row?.closest('.messages')
    if (row && list) {
      const spaceAbove = row.getBoundingClientRect().top - list.getBoundingClientRect().top
      setPickerBelow(spaceAbove < PICKER_HEIGHT)
    }
    setPickerOpen((open) => !open)
  }

  const pick = (code: ReactionCode) => {
    setPickerOpen(false)
    onReact(message, code)
  }

  return (
    <div
      ref={rowRef}
      className={`message-row ${mine ? 'mine' : 'theirs'}`}
      data-testid={`message-${message.id}`}
    >
      <div className="bubble">
        {showSender && !mine && (
          <div className="sender-name" style={{ color: senderColor(message.sender.username) }}>
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
        <ReactionChips message={message} me={me} onReact={onReact} />
      </div>
      <button
        className="reply-button"
        data-testid={`reply-${message.id}`}
        onClick={() => onReply(message)}
      >
        ↩
      </button>
      {canReact && (
        <button className="reply-button" data-testid={`react-${message.id}`} onClick={togglePicker}>
          ☺
        </button>
      )}
      {pickerOpen && (
        <div
          className={`reaction-picker ${pickerBelow ? 'below' : ''}`}
          data-testid={`reaction-picker-${message.id}`}
        >
          {REACTION_CODES.map((code) => (
            <button key={code} onClick={() => pick(code)}>
              {REACTION_EMOJI[code]}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}