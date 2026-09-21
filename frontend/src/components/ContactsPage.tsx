import { useEffect, useState } from 'react'

import { api } from '../api'
import type { ContactOut, UserPublic } from '../types'

interface Props {
  user: UserPublic
  onClose: () => void
}

export function ContactsPage({ user, onClose }: Props) {
  const [contacts, setContacts] = useState<ContactOut[]>([])
  const [identifier, setIdentifier] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editingName, setEditingName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    api<ContactOut[]>('/contacts')
      .then(setContacts)
      .catch(() => {})
  }

  useEffect(load, [user.id])

  const add = async () => {
    setError(null)
    try {
      await api('/contacts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: identifier.trim() }),
      })
      setIdentifier('')
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to add contact')
    }
  }

  const remove = async (contactId: number) => {
    setError(null)
    try {
      await api(`/contacts/${contactId}`, { method: 'DELETE' })
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to remove contact')
    }
  }

  const rename = async (contactId: number) => {
    setError(null)
    try {
      await api(`/contacts/${contactId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editingName.trim() || null }),
      })
      setEditingId(null)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to rename contact')
    }
  }

  const displayName = (contact: ContactOut) => contact.name ?? contact.username

  return (
    <div className="overlay" data-testid="contacts-page">
      <div className="sheet">
        <header className="sheet-header">
          <h2>Contacts</h2>
          <button data-testid="contacts-close" onClick={onClose}>
            ← Back
          </button>
        </header>

        {error && <div className="error-banner">{error}</div>}

        <section>
          <h3>Add contact</h3>
          <div className="add-row">
            <input
              data-testid="contact-identifier"
              placeholder="username or phone"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void add()}
            />
            <button data-testid="contact-add" disabled={!identifier.trim()} onClick={() => void add()}>
              Add
            </button>
          </div>
        </section>

        <section data-testid="contacts-list">
          <h3>Your contacts ({contacts.length})</h3>
          {contacts.length === 0 && <p className="muted">No contacts yet</p>}
          {contacts.map((contact) => (
            <div key={contact.user_id} className="contact-row" data-testid={`contact-${contact.user_id}`}>
              {editingId === contact.user_id ? (
                <>
                  <input
                    data-testid={`contact-name-input-${contact.user_id}`}
                    value={editingName}
                    placeholder={contact.username}
                    onChange={(e) => setEditingName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && void rename(contact.user_id)}
                  />
                  <button
                    data-testid={`contact-name-save-${contact.user_id}`}
                    onClick={() => void rename(contact.user_id)}
                  >
                    Save
                  </button>
                </>
              ) : (
                <>
                  <span data-testid={`contact-label-${contact.user_id}`}>
                    {displayName(contact)}
                    {contact.name && (
                      <span className="muted"> @{contact.username}</span>
                    )}
                  </span>
                  <div>
                    <button
                      data-testid={`contact-edit-${contact.user_id}`}
                      onClick={() => {
                        setEditingId(contact.user_id)
                        setEditingName(contact.name ?? '')
                      }}
                    >
                      Rename
                    </button>
                    <button
                      data-testid={`contact-remove-${contact.user_id}`}
                      onClick={() => void remove(contact.user_id)}
                    >
                      Remove
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </section>
      </div>
    </div>
  )
}
