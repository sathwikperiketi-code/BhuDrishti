import { useState } from 'react'
import { ArrowRight, Check, CheckCircle2, ClipboardCheck, CornerUpLeft, LockKeyhole, ShieldCheck, X } from 'lucide-react'
import type { ReviewCaseDetail, ReviewDecision } from './types'
import { reviewDate, reviewStatusLabel } from './format'
import { Modal } from '../../components/ui/Overlay'
import { displayRoleName } from '../../lib/roles'

type Props = {
  item: ReviewCaseDetail
  canDecide: boolean
  canRecommend: boolean
  queued: boolean
  busy: boolean
  canViewAudit: boolean
  onDecision: (decision: ReviewDecision, reason?: string) => Promise<void>
  onRecommendation: (recommendation: ReviewDecision, reason: string) => Promise<void>
}

const REJECT_REASONS = ['Invalid source', 'Unresolvable conflict', 'Insufficient information', 'Unreadable document', 'Duplicate record']

export function ReviewDecisionPanel({ item, canDecide, canRecommend, queued, busy, canViewAudit, onDecision, onRecommendation }: Props) {
  const [choice, setChoice] = useState<ReviewDecision | null>(null)
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [recommendChoice, setRecommendChoice] = useState<ReviewDecision>('approve')
  const [recommendReason, setRecommendReason] = useState('')
  const [recommendError, setRecommendError] = useState('')
  const decided = ['approved', 'rejected', 'sent_back'].includes(item.status)

  async function confirm() {
    if (!choice || busy) return
    if (choice !== 'approve' && !reason.trim()) { setError('A reason is required for rejection or send back.'); return }
    setError('')
    try { await onDecision(choice, reason.trim() || undefined); setChoice(null); setReason('') }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'The decision could not be recorded.') }
  }

  async function submitRecommendation() {
    if (recommendReason.trim().length < 4) { setRecommendError('Enter a recommendation reason of at least four characters.'); return }
    setRecommendError('')
    try { await onRecommendation(recommendChoice, recommendReason.trim()); setRecommendReason('') }
    catch (caught) { setRecommendError(caught instanceof Error ? caught.message : 'The recommendation could not be recorded.') }
  }

  return <section className="rv-panel rv-decision-panel" aria-labelledby="rv-decision-title" aria-busy={busy}>
    <div className="rv-panel-heading"><div><span className="rv-eyebrow">Authorized officer disposition</span><h2 id="rv-decision-title">Final decision</h2></div><ClipboardCheck size={19} className="rv-panel-heading__icon" /></div>
    {decided ? <div className={`rv-final-state rv-final-state--${item.status}`} role="status"><span><CheckCircle2 size={19} /></span><div><strong>Final decision · {reviewStatusLabel(item.status)}</strong><p>{item.decisionReason || (item.status === 'approved' ? 'Reviewed values saved to the approved record. No optional note was recorded.' : 'Decision recorded in the audit trail.')}</p><small>{item.decidedBy?.name || 'Authorized officer'}{item.decidedBy?.role ? ` · ${displayRoleName(item.decidedBy.role)}` : ''} · {reviewDate(item.decidedAt)}</small></div></div> : null}
    <div className="rv-summary-grid"><div><span>Fields reviewed</span><strong>{item.summary.fieldsReviewed} <small>/ {item.summary.fieldsTotal}</small></strong></div><div><span>Findings resolved</span><strong>{item.summary.warningsResolved} <small>/ {item.summary.warningsTotal}</small></strong></div><div><span>Critical conflicts</span><strong>{item.summary.criticalConflicts}</strong></div></div>
    {!decided && (item.summary.blockingReasons?.length ? <div className="rv-blockers"><strong><LockKeyhole size={14} />Approval needs attention</strong><ul>{item.summary.blockingReasons.map((reason, index) => <li key={`${reason}-${index}`}>{reason}</li>)}</ul></div> : <div className="rv-ready"><ShieldCheck size={16} /><span>All required review checks are complete. An officer can make the final decision.</span></div>)}
    {item.recommendation ? <div className="rv-recommendation-record"><strong>{item.recommendation.reviewerRole === 'VERIFIER' ? 'Verifier recommendation' : 'Recommendation'} · advisory</strong><p>{item.recommendation.value === 'approve' ? 'Approve' : item.recommendation.value === 'reject' ? 'Reject' : item.recommendation.value === 'send_back' ? 'Send back' : 'Recorded'}</p><p><span>Reason: </span>{String(item.recommendation.reason ?? 'No reason available')}</p><small>{displayRoleName(String(item.recommendation.reviewerRole ?? 'Reviewer'))}{item.recommendation.reviewerId ? ` · ID ${String(item.recommendation.reviewerId).slice(0, 8)}` : ''}{item.recommendation.at ? ` · ${reviewDate(String(item.recommendation.at))}` : ''}</small><p>A recommendation does not make the final decision.</p></div> : <div className="rv-recommendation-record rv-recommendation-record--empty"><strong>No recommendation recorded</strong><p>A Verifier may save an evidence-based recommendation. An authorized Revenue Officer or Administrator makes the final decision.</p></div>}
    {!decided && canDecide ? <><div className="rv-decision-actions"><button type="button" className="rv-button rv-button--primary" disabled={busy || !item.summary.canApprove} onClick={() => { setChoice('approve'); setError('') }}><Check size={15} />Approve record</button><button type="button" className="rv-button rv-button--danger-outline" disabled={busy} onClick={() => { setChoice('reject'); setError('') }}><X size={15} />Reject</button><button type="button" className="rv-button rv-button--quiet" disabled={busy} onClick={() => { setChoice('send_back'); setError('') }}><CornerUpLeft size={15} />Send back</button></div>
      <Modal open={choice !== null} onClose={() => { if (!busy) setChoice(null) }} title={choice === 'approve' ? 'Approve · confirm final decision' : choice === 'reject' ? 'Reject · confirm final decision' : 'Send back · confirm final decision'} description={`Record ${item.recordNumber || item.recordId}`} size="sm" className="rv-confirm-modal">
        <div className="rv-decision-confirm" aria-busy={busy}>
          <p>{choice === 'approve' ? 'Your approval publishes the human-reviewed values to this record. This review attempt will close; the original extraction and corrections remain in the audit trail.' : choice === 'reject' ? 'This closes the review attempt as rejected. The source and history remain available. Reprocessing a finalized rejection requires a new source upload.' : 'This closes the current attempt as sent back. A Revenue Officer or Administrator can reprocess the stored source for another review attempt.'}</p>
          {choice !== 'approve' ? <><div className="rv-reason-chips">{choice === 'reject' ? REJECT_REASONS.map((entry) => <button type="button" key={entry} disabled={busy} onClick={() => setReason(entry)}>{entry}</button>) : null}</div><label>Decision reason · required<textarea disabled={busy} rows={3} maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain the final decision for the audit trail" /></label></> : <label>Decision note <span>Optional</span><textarea disabled={busy} rows={2} maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Add evidence supporting this approval" /></label>}
          {error ? <p className="rv-form-error" role="alert">{error}</p> : null}
          <div className="rv-decision-confirm__actions"><button type="button" className="rv-button rv-button--quiet" disabled={busy} onClick={() => setChoice(null)}>Cancel</button><button type="button" className={choice === 'reject' ? 'rv-button rv-button--danger' : 'rv-button rv-button--primary'} disabled={busy || (choice !== 'approve' && !reason.trim())} onClick={() => void confirm()}>{busy ? 'Recording final decision…' : `Confirm ${choice === 'send_back' ? 'send back' : choice}`}</button></div>
        </div>
      </Modal>
    </> : !decided && canRecommend ? <div className="rv-recommend-form"><strong>Verifier recommendation</strong><p>Record an advisory recommendation for the Revenue Officer. The final decision remains pending.</p><label>Recommendation<select disabled={busy} value={recommendChoice} onChange={(event) => setRecommendChoice(event.target.value as ReviewDecision)}><option value="approve">Approve · recommendation</option><option value="reject">Reject · recommendation</option><option value="send_back">Send back · recommendation</option></select></label><label>Reason<textarea disabled={busy} rows={3} maxLength={1000} value={recommendReason} onChange={(event) => setRecommendReason(event.target.value)} placeholder="Describe your evidence and reasoning" /></label>{recommendError ? <p className="rv-form-error" role="alert">{recommendError}</p> : null}<button type="button" className="rv-button rv-button--primary" disabled={busy || recommendReason.trim().length < 4} onClick={() => void submitRecommendation()}>{busy ? 'Recording recommendation…' : 'Record recommendation'}</button></div> : !decided ? <p className="rv-read-only">{queued ? 'An authorized reviewer must start this case before field review. The Revenue Officer or Administrator makes the final decision.' : 'Final decisions are available to the Revenue Officer or Administrator. Your current view preserves the source, findings, and review history.'}</p> : null}
    {item.status === 'approved' ? <div className="rv-verified-flow" aria-label="Persisted verification state"><span className="rv-verified-flow__active">Review complete <Check size={12} /></span><span className="rv-verified-flow__active">Final decision recorded <Check size={12} /></span><span className={item.gisIndexed ? 'rv-verified-flow__active' : ''}>{item.gisIndexed ? 'Stored parcel geometry available' : 'Geometry unavailable'} <ArrowRight size={12} /></span></div> : null}
    {decided ? <div className="rv-post-links"><a href={`#/records/${encodeURIComponent(item.recordId)}`}>Open record <ArrowRight size={13} /></a>{canViewAudit ? <a href={`#/audit/${encodeURIComponent(item.recordId)}`}>View audit trail <ArrowRight size={13} /></a> : null}</div> : null}
  </section>
}
