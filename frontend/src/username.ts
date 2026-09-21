// Username policy — must mirror the backend Username value object
// (app/domain/value_objects.py): 3-32 chars, starts with a lowercase
// letter, only a-z, 0-9 and _ allowed.

const USERNAME_RE = /^[a-z][a-z0-9_]{2,31}$/

export function validateUsername(value: string): string | null {
  const v = value.trim()
  if (v.length < 3 || v.length > 32) {
    return 'Username must be 3-32 characters'
  }
  if (!/^[a-z]/.test(v)) {
    return 'Username must start with a lowercase letter'
  }
  if (!USERNAME_RE.test(v)) {
    return 'Only a-z, 0-9 and _ are allowed'
  }
  return null
}
