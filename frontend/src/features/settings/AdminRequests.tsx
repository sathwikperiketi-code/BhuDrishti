import { useEffect, useState } from 'react'
import { Check, CircleAlert, Clock3, ShieldCheck, X } from 'lucide-react'
import { reportUnauthorizedSession, type SessionUser } from '../auth/session'

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')

interface AdminRoleRequest {
  user: SessionUser
  emailVerified: boolean
  createdAt: string
}

async function errorMessage(response: Response): Promise<string> {
  const payload = await response.json().catch(() => ({})) as { detail?: unknown }
  return typeof payload.detail === 'string' ? payload.detail : `Request failed (HTTP ${response.status}).`
}

export function AdminRequests({ token }: { token: string }) {
  const [requests, setRequests] = useState<AdminRoleRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [revision, setRevision] = useState(0)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    void fetch(`${apiBase}/auth/admin-requests`, {
      signal: controller.signal,
      headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
    }).then(async (response) => {
      if (response.status === 401) reportUnauthorizedSession()
      if (!response.ok) throw new Error(await errorMessage(response))
      return await response.json() as AdminRoleRequest[]
    }).then((items) => {
      if (!controller.signal.aborted) { setRequests(items); setError('') }
    }, (caught: unknown) => {
      if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'Requests could not be loaded.')
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [token, revision])

  async function review(request: AdminRoleRequest, decision: 'approve' | 'reject') {
    setBusyId(request.user.id)
    setError('')
    setSuccess('')
    try {
      const response = await fetch(`${apiBase}/auth/admin-requests/${encodeURIComponent(request.user.id)}/${decision}`, {
        method: 'POST',
        headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
      })
      if (response.status === 401) reportUnauthorizedSession()
      if (!response.ok) throw new Error(await errorMessage(response))
      const user = await response.json() as SessionUser
      setRequests((current) => current.map((item) => item.user.id === user.id ? { ...item, user } : item))
      setSuccess(`${user.name}'s administrator request was ${decision === 'approve' ? 'approved' : 'rejected'}.`)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'The request could not be reviewed.') }
    finally { setBusyId(null) }
  }

  const pending = requests.filter((item) => item.user.roleApprovalStatus === 'PENDING')
  const reviewed = requests.filter((item) => item.user.roleApprovalStatus !== 'PENDING')

  return <section className="p5-settings-panel p5-admin-requests" aria-labelledby="p5-admin-requests-title">
    <div className="p5-settings-section-heading"><span className="p5-settings-eyebrow">Administrator</span><h2 id="p5-admin-requests-title">Access requests</h2></div>
    <p className="p5-settings-copy">Review administrator requests from verified accounts. Approval grants the server issued Administrator role.</p>
    {error ? <div className="p5-account-error" role="alert"><CircleAlert size={15} aria-hidden="true" />{error}<button type="button" onClick={() => { setLoading(true); setRevision((value) => value + 1) }}>Retry</button></div> : null}
    {success ? <p className="p5-account-success" role="status">{success}</p> : null}
    {loading ? <p className="p5-admin-requests__empty" role="status">Loading access requests…</p> : pending.length === 0 ? <p className="p5-admin-requests__empty">No pending administrator requests.</p> : <ul className="p5-admin-requests__list">{pending.map((item) => <li key={item.user.id}>
      <div className="p5-admin-requests__identity"><span className="p5-settings-avatar" aria-hidden="true">{item.user.name.split(' ').map((part) => part[0]).join('').slice(0, 2)}</span><div><strong>{item.user.name}</strong><small>{item.user.email}</small><span className="p5-admin-requests__date"><Clock3 size={12} aria-hidden="true" /> Requested {new Date(item.createdAt).toLocaleDateString()}</span></div></div>
      <div className="p5-admin-requests__review"><span className={item.emailVerified ? 'p5-admin-requests__verified' : 'p5-admin-requests__unverified'}>{item.emailVerified ? <ShieldCheck size={13} aria-hidden="true" /> : <Clock3 size={13} aria-hidden="true" />}{item.emailVerified ? 'Email verified' : 'Awaiting email verification'}</span><div><button type="button" className="p5-admin-requests__approve" disabled={!item.emailVerified || busyId !== null} onClick={() => void review(item, 'approve')}><Check size={14} aria-hidden="true" />{busyId === item.user.id ? 'Saving…' : 'Approve'}</button><button type="button" className="p5-admin-requests__reject" disabled={busyId !== null} onClick={() => void review(item, 'reject')}><X size={14} aria-hidden="true" />Reject</button></div></div>
    </li>)}</ul>}
    {reviewed.length > 0 ? <details className="p5-admin-requests__history"><summary>Reviewed requests ({reviewed.length})</summary><ul>{reviewed.map((item) => <li key={item.user.id}><span>{item.user.name} · {item.user.email}</span><strong>{item.user.roleApprovalStatus?.toLowerCase()}</strong></li>)}</ul></details> : null}
  </section>
}
