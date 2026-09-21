import { useState } from 'react'

import { api } from '../api'
import type { ChatListItem, UserPublic } from '../types'
import { validateUsername } from '../username'

interface Props {
  user: UserPublic
  onClose: () => void
  onGroupCreated: (chatId: number) => void
  onLogout: () => void
  onUserUpdated: (user: UserPublic) => void
}

export function SettingsPage({ user, onClose, onGroupCreated, onLogout, onUserUpdated }: Props) {
  const [username, setUsername] = useState(user.username)
  const [firstName, setFirstName] = useState(user.first_name)
  const [lastName, setLastName] = useState(user.last_name ?? '')
  const [bio, setBio] = useState(user.bio ?? '')
  const [groupTitle, setGroupTitle] = useState('')
  const [groupPublic, setGroupPublic] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const usernameError = username.trim() !== '' ? validateUsername(username) : null
  const profileDirty =
    username !== user.username ||
    firstName !== user.first_name ||
    lastName !== (user.last_name ?? '') ||
    bio !== (user.bio ?? '')

  const saveProfile = async () => {
    setError(null)
    setSaved(false)
    try {
      const updated = await api<UserPublic>('/users/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          first_name: firstName,
          last_name: lastName || null,
          bio: bio || null,
        }),
      })
      onUserUpdated(updated)
      setSaved(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to save profile')
    }
  }

  const uploadAvatar = async (file: File) => {
    setError(null)
    const form = new FormData()
    form.append('file', file)
    try {
      const updated = await api<UserPublic>('/users/me/avatar', { method: 'POST', body: form })
      onUserUpdated(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to upload avatar')
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
      setGroupTitle('')
      onGroupCreated(chat.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to create group')
    }
  }

  return (
    <div className="overlay" data-testid="settings-page">
      <div className="sheet">
        <header className="sheet-header">
          <h2>Settings</h2>
          <button data-testid="settings-close" onClick={onClose}>
            ← Back
          </button>
        </header>

        {error && <div className="error-banner">{error}</div>}
        {saved && <div className="saved-banner">Profile saved</div>}

        <section>
          <h3>Profile</h3>
          <div className="avatar-row">
            {user.avatar_url ? (
              <img className="avatar-img" src={user.avatar_url} alt="avatar" />
            ) : (
              <span className="avatar-circle">{user.username.charAt(0).toUpperCase()}</span>
            )}
            <label className="file-label">
              Upload avatar
              <input
                data-testid="avatar-input"
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) void uploadAvatar(file)
                  e.target.value = ''
                }}
              />
            </label>
          </div>

          <label htmlFor="settings-username">Username</label>
          <input
            id="settings-username"
            data-testid="settings-username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          {usernameError && (
            <div className="field-error" data-testid="settings-username-error">
              {usernameError}
            </div>
          )}

          <label htmlFor="settings-first-name">First name</label>
          <input
            id="settings-first-name"
            data-testid="settings-first-name"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
          />

          <label htmlFor="settings-last-name">Last name</label>
          <input
            id="settings-last-name"
            data-testid="settings-last-name"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
          />

          <label htmlFor="settings-bio">Bio</label>
          <input
            id="settings-bio"
            data-testid="settings-bio"
            value={bio}
            onChange={(e) => setBio(e.target.value)}
          />

          <button
            data-testid="save-profile"
            disabled={!profileDirty || usernameError !== null}
            onClick={() => void saveProfile()}
          >
            Save profile
          </button>
        </section>

        <section>
          <h3>New group</h3>
          <input
            data-testid="settings-group-title"
            placeholder="Group title"
            value={groupTitle}
            onChange={(e) => setGroupTitle(e.target.value)}
          />
          <label className="checkbox-row">
            <input
              type="checkbox"
              data-testid="settings-group-public"
              checked={groupPublic}
              onChange={(e) => setGroupPublic(e.target.checked)}
            />
            Public group
          </label>
          <button
            data-testid="settings-create-group"
            disabled={!groupTitle.trim()}
            onClick={() => void createGroup()}
          >
            Create group
          </button>
        </section>

        <section>
          <h3>Session</h3>
          <button data-testid="settings-logout" onClick={onLogout}>
            Log out
          </button>
        </section>
      </div>
    </div>
  )
}
