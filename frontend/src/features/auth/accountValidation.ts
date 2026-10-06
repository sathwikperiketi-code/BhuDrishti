import type { SignupValues } from './accountApi'

export type SignupErrors = Partial<Record<keyof SignupValues, string>>

export const passwordHint = 'Use 12–256 characters with an uppercase letter, a lowercase letter, a number, and a symbol.'
export const usernameHint = 'Use 3–32 letters, numbers, periods, hyphens, or underscores.'

export function validEmail(email: string) {
  const value = email.trim()
  if (value.length > 254) return false
  const parts = value.split('@')
  if (parts.length !== 2) return false
  const [local, domain] = parts
  if (local.length > 64 || !/^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$/.test(local)) return false
  const labels = domain.split('.')
  return labels.length >= 2 && labels.every((label) =>
    label.length <= 63 && /^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$/.test(label))
}

export function passwordError(password: string): string | undefined {
  return password.length >= 12 && password.length <= 256 && /[A-Z]/.test(password)
    && /[a-z]/.test(password) && /[0-9]/.test(password) && /[^A-Za-z0-9]/.test(password)
    ? undefined : passwordHint
}

export function validateSignup(values: SignupValues): SignupErrors {
  const errors: SignupErrors = {}
  const name = values.fullName.trim()
  if (name.length < 2 || name.length > 160) errors.fullName = 'Enter your full name (2–160 characters).'
  const username = values.username.trim()
  if (!/^[A-Za-z0-9_.-]{3,32}$/.test(username) || !/[A-Za-z0-9]/.test(username)) errors.username = usernameHint
  if (!validEmail(values.email)) errors.email = 'Enter a valid email address.'
  errors.password = passwordError(values.password)
  if (values.confirmPassword !== values.password) errors.confirmPassword = 'Passwords do not match.'
  if (!values.requestedRole) errors.requestedRole = 'Select the role you are requesting.'
  return errors
}

export function validateReset(password: string, confirmPassword: string) {
  return {
    password: passwordError(password),
    confirmPassword: password !== confirmPassword ? 'Passwords do not match.' : undefined,
  }
}
