import type { ArtifactOut, MessageOut, UserPublic } from '../types'

interface Props {
  message: MessageOut
  me: UserPublic
  onReply: (message: MessageOut) => void
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

export function MessageBubble({ message, me, onReply }: Props) {
  const mine = message.sender.id === me.id
  return (
    <div className={`message-row ${mine ? 'mine' : 'theirs'}`} data-testid={`message-${message.id}`}>
      <div className="bubble">
        {message.reply_to_id !== null && <div className="reply-chip">↩ reply</div>}
        {message.artifact && <ArtifactView artifact={message.artifact} />}
        {message.deleted_at ? (
          <span className="deleted-text">deleted</span>
        ) : (
          <span className="message-text">{message.text}</span>
        )}
        {message.edited_at && !message.deleted_at && <span className="edited-mark"> (edited)</span>}
      </div>
      <button className="reply-button" data-testid={`reply-${message.id}`} onClick={() => onReply(message)}>
        ↩
      </button>
    </div>
  )
}
