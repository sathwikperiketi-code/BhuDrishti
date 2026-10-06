import { displayRoleName } from '../../lib/roles'
import { useEffect, useState, type FormEvent } from 'react'
import { CircleAlert, UserPlus } from 'lucide-react'
import { reportUnauthorizedSession, type SessionRole, type SessionUser } from '../auth/session'

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')
const roles: { value: SessionRole; label: string }[] = [
  { value: 'REVENUE_OFFICER', label: 'Revenue Officer' },
  { value: 'VERIFIER', label: 'Verifier' },
  { value: 'AUDITOR', label: 'Auditor' },
  { value: 'ADMIN', label: 'Administrator' },
]

async function responseError(response: Response, fallback: string): Promise<string> {
  const data = await response.json().catch(() => ({})) as { detail?: unknown }
  return typeof data.detail === 'string' ? data.detail : fallback
}

export function AccountProvisioning({ token }: { token: string }) {
  const [accounts, setAccounts] = useState<SessionUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [saving, setSaving] = useState(false)
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<SessionRole>('REVENUE_OFFICER')

  useEffect(() => {
    const controller = new AbortController()
    void fetch(`${apiBase}/auth/users`, { signal: controller.signal, headers: { Accept: 'application/json', Authorization: `Bearer ${token}` } }).then(async (response) => {
      if (response.status === 401) reportUnauthorizedSession()
      if (!response.ok) throw new Error(await responseError(response, `Accounts could not be loaded (HTTP ${response.status}).`))
      return await response.json() as SessionUser[]
    }).then((items) => { if (!controller.signal.aborted) setAccounts(items) }, (caught: unknown) => {
      if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'Accounts could not be loaded.')
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [token])

  async function createAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const response = await fetch(`${apiBase}/auth/users`, {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ email: email.trim(), name: name.trim(), password, role }),
      })
      if (response.status === 401) reportUnauthorizedSession()
      if (!response.ok) throw new Error(await responseError(response, `Account creation failed (HTTP ${response.status}).`))
      const created = await response.json() as SessionUser
      setAccounts((current) => [...current, created].sort((a, b) => a.name.localeCompare(b.name)))
      setSuccess(`${created.name} can now sign in with the credentials you assigned.`)
      setEmail('')
      setName('')
      setPassword('')
      setRole('REVENUE_OFFICER')
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Account creation failed.') }
    finally { setSaving(false) }
  }

  return <section className="p5-settings-panel p5-account-admin" aria-labelledby="p5-account-admin-title">
    <div className="p5-settings-section-heading"><span className="p5-settings-eyebrow">Administrator</span><h2 id="p5-account-admin-title">User accounts</h2></div>
    <p className="p5-settings-copy">Create named accounts with server-enforced roles. Share each password with its owner through a trusted channel.</p>
    <form className="p5-account-form" onSubmit={(event) => void createAccount(event)}>
      <label>Full name<input type="text" autoComplete="name" minLength={2} maxLength={160} required value={name} onChange={(event) => setName(event.target.value)} /></label>
      <label>Email address<input type="email" autoComplete="off" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      <label>Role<select value={role} onChange={(event) => setRole(event.target.value as SessionRole)}>{roles.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
      <label>Initial password<input type="password" autoComplete="new-password" minLength={12} maxLength={256} required value={password} onChange={(event) => setPassword(event.target.value)} /><small>At least 12 characters.</small></label>
      {error ? <p className="p5-account-error" role="alert"><CircleAlert size={14} aria-hidden="true" />{error}</p> : null}
      {success ? <p className="p5-account-success" role="status">{success}</p> : null}
      <button type="submit" disabled={saving}><UserPlus size={15} aria-hidden="true" />{saving ? 'Creating account…' : 'Create account'}</button>
    </form>
    <div className="p5-account-list"><h3>Provisioned accounts</h3>{loading ? <p role="status">Loading accounts…</p> : accounts.length === 0 ? <p>No accounts found.</p> : <ul>{accounts.map((account) => <li key={account.id}><span className="p5-settings-avatar" aria-hidden="true">{account.name.split(' ').map((part) => part[0]).join('').slice(0, 2)}</span><div><strong>{account.name}</strong><small>{account.email}</small></div><span>{displayRoleName(account.role)}</span></li>)}</ul>}</div>
  </section>
}
