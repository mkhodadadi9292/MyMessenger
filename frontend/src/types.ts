export interface UserPublic {
  id: number
  username: string
  first_name: string
  last_name: string | null
  bio: string | null
  avatar_url: string | null
  created_at: string
}

export interface ArtifactOut {
  id: number
  kind: 'image' | 'video' | 'audio'
  file_name: string
  mime_type: string
  size_bytes: number
  url: string
}

export interface ReplyPreview {
  id: number
  sender_username: string
  text: string | null
  file_name: string | null
  deleted: boolean
}

export interface MessageOut {
  id: number
  chat_id: number
  sender: UserPublic
  text: string | null
  reply_to_id: number | null
  reply_to: ReplyPreview | null
  artifact: ArtifactOut | null
  created_at: string
  edited_at: string | null
  deleted_at: string | null
}

export interface ChatOut {
  id: number
  type: 'private' | 'group'
  title: string | null
  description: string | null
  is_public: boolean
  owner_id: number
  created_at: string
}

export interface ChatListItem extends ChatOut {
  last_message: MessageOut | null
}

export interface MemberOut {
  user_id: number
  username: string
  first_name: string
  last_name: string | null
  role: string
  joined_at: string
}

export interface InviteOut {
  invite_id: number
  chat_id: number
  title: string | null
  inviter_name: string | null
  created_at: string
}

export interface ContactOut {
  user_id: number
  username: string
  first_name: string
  last_name: string | null
  avatar_url: string | null
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  user: UserPublic
}
