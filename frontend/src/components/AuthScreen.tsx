import { useState } from 'react'

import { api, setTokens } from '../api'
import type { AuthTokens, UserPublic } from '../types'

interface VerifyResult {
  registered?: boolean
  registration_token?: string
  access_token?: string
  refresh_token?: string
  user?: UserPublic
}

export function AuthScreen({ onAuthed }: { onAuthed: (user: UserPublic) => void }) {
  const [identifier, setIdentifier] = useState('')
  const [code, setCode] = useState('')
  const [otpSent, setOtpSent] = useState(false)
  const [registrationToken, setRegistrationToken] = useState<string | null>(null)
  const [username, setUsername] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const fail = (err: unknown) =>
    setError(err instanceof Error ? err.message : 'Something went wrong')

  const requestCode = async () => {
    setBusy(true)
    setError(null)
    try {
      await api('/auth/otp/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier }),
      })
      setOtpSent(true)
    } catch (err) {
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  const verifyCode = async () => {
    setBusy(true)
    setError(null)
    try {
      const result = await api<VerifyResult>('/auth/otp/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier, code }),
      })
      if (result.registered === false) {
        setRegistrationToken(result.registration_token ?? null)
      } else {
        setTokens(result as unknown as AuthTokens)
        onAuthed(result.user!)
      }
    } catch (err) {
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  const register = async () => {
    setBusy(true)
    setError(null)
    try {
      const result = await api<AuthTokens>('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          registration_token: registrationToken,
          username,
          first_name: firstName,
          last_name: lastName || null,
        }),
      })
      setTokens(result)
      onAuthed(result.user)
    } catch (err) {
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h1>Messenger</h1>
        {error && <div className="error-banner">{error}</div>}
        {registrationToken === null ? (
          <>
            <label htmlFor="identifier">Email or phone</label>
            <input
              id="identifier"
              data-testid="identifier"
              placeholder="alice@example.com"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
            />
            {!otpSent ? (
              <button data-testid="request-code" disabled={busy || !identifier} onClick={requestCode}>
                Send code
              </button>
            ) : (
              <>
                <label htmlFor="code">Code (printed in server log)</label>
                <input
                  id="code"
                  data-testid="code"
                  placeholder="123456"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
                <button data-testid="verify-code" disabled={busy || !code} onClick={verifyCode}>
                  Verify
                </button>
              </>
            )}
          </>
        ) : (
          <>
            <label htmlFor="username">Username</label>
            <input
              id="username"
              data-testid="username"
              placeholder="alice"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <label htmlFor="first-name">First name</label>
            <input
              id="first-name"
              data-testid="first-name"
              placeholder="Alice"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
            />
            <label htmlFor="last-name">Last name (optional)</label>
            <input
              id="last-name"
              data-testid="last-name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
            />
            <button
              data-testid="register"
              disabled={busy || !username || !firstName}
              onClick={register}
            >
              Register
            </button>
          </>
        )}
      </div>
    </div>
  )
}
