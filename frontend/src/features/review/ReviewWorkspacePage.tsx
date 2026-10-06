import { lazy, Suspense, useEffect, useState } from 'react'
import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, Clock3, Copy, FileText, LocateFixed, Play, RefreshCw, ShieldCheck, UserRound } from 'lucide-react'
import { getReview, getReviewDocument, startReview, reviewField, resolveReviewIssue, decideReview, acceptClearFields, recommendReview, reprocessReviewDocument, assignReview } from './api'
import { confidenceLabel, priorityLabel, reviewDate, reviewFieldLabel, reviewSourceMethod, reviewSourcePage, reviewSourceText, reviewStatusLabel, reviewValue } from './format'
import { ReviewDecisionPanel } from './ReviewDecisionPanel'
import { ReviewFieldsPanel } from './ReviewFieldsPanel'
import { ReviewValidationPanel } from './ReviewValidationPanel'
import type { ReviewAction, ReviewCaseDetail, ReviewDecision, ReviewDocument, ReviewUser } from './types'
import { qualityScoreLabel } from '../live/format'
import '../live/live.css'
import './review.css'
import { displayRoleName } from '../../lib/roles'

type Props = { token: string; user: ReviewUser; recordId?: string }
type WorkspaceTab = 'document' | 'fields' | 'validation' | 'decision'
const LiveDocumentViewer = lazy(() => import('../live/LiveDocumentViewer').then((module) => ({ default: module.LiveDocumentViewer })))

function idFromHash() {
  const path = window.location.hash.split('?')[0]
  const id = path.match(/^#\/review\/([^/]+)$/)?.[1]
  try { return id ? decodeURIComponent(id) : '' } catch { return '' }
}
function fieldFromHash() { return new URLSearchParams(window.location.hash.split('?')[1] || '').get('field') }

function canReview(role: string) { return ['ADMIN', 'REVENUE_OFFICER', 'VERIFIER'].includes(role.toUpperCase()) }
function canDecide(role: string) { return ['ADMIN', 'REVENUE_OFFICER'].includes(role.toUpperCase()) }

export function ReviewWorkspacePage({ token, user, recordId: recordIdProp }: Props) {
  const recordId = recordIdProp || idFromHash()
  const requestedField = fieldFromHash()
  const [item, setItem] = useState<ReviewCaseDetail | null>(null)
  const [document, setDocument] = useState<ReviewDocument | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [loadedKey, setLoadedKey] = useState('')
  const [error, setError] = useState('')
  const [documentError, setDocumentError] = useState('')
  const [busy, setBusy] = useState(false)
  const [revision, setRevision] = useState(0)
  const [documentRevision, setDocumentRevision] = useState(0)
  const [feedback, setFeedback] = useState<{ recordId: string; message: string; state: 'loading' | 'success' | 'error' } | null>(null)
  const [selectedField, setSelectedField] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [tab, setTab] = useState<WorkspaceTab>('fields')
  const [copied, setCopied] = useState(false)
  const requestKey = JSON.stringify([token, recordId, requestedField, revision])
  const viewState = !recordId ? 'error' : loadedKey === requestKey ? state : 'loading'
  const viewError = !recordId ? 'No review record was selected.' : error

  useEffect(() => {
    if (!recordId) return
    const controller = new AbortController()
    getReview(token, recordId, controller.signal).then((result) => {
      setItem(result)
      setState('ready')
      setError('')
      setLoadedKey(requestKey)
      const chosen = requestedField && result.fields.some((field) => field.field === requestedField) ? requestedField : result.fields.find((field) => field.validationStatus && field.validationStatus !== 'clear')?.field || result.fields[0]?.field || null
      setSelectedField(chosen)
      setPage(reviewSourcePage(result.fields.find((field) => field.field === chosen)?.source) || 1)
    }).catch((caught: unknown) => {
      if (caught instanceof DOMException && caught.name === 'AbortError') return
      setState('error')
      setError(caught instanceof Error ? caught.message : 'The review case could not be loaded.')
      setLoadedKey(requestKey)
    })
    return () => controller.abort()
  }, [token, recordId, requestedField, revision, requestKey])

  useEffect(() => {
    if (!item?.documentId) return
    const controller = new AbortController()
    getReviewDocument(token, item.documentId, controller.signal).then((result) => { setDocument(result); setDocumentError('') }).catch((caught: unknown) => {
      if (caught instanceof DOMException && caught.name === 'AbortError') return
      setDocument(null)
      setDocumentError(caught instanceof Error ? caught.message : 'The source document could not be loaded.')
    })
    return () => controller.abort()
  }, [token, item?.documentId, documentRevision])

  function selectField(field: string, target: WorkspaceTab = 'fields') {
    setSelectedField(field)
    const sourcePage = document?.fields.find((entry) => entry.field === field)?.source?.page || reviewSourcePage(item?.fields.find((entry) => entry.field === field)?.source)
    if (sourcePage) setPage(sourcePage)
    if (window.innerWidth <= 1150) setTab(target)
  }

  async function saveAction(action: () => Promise<ReviewCaseDetail>, pending: string, saved: string) {
    setBusy(true)
    setError('')
    setFeedback({ recordId, message: pending, state: 'loading' })
    try {
      const result = await action()
      setItem(result)
      setFeedback({ recordId, message: saved, state: 'success' })
    } catch (caught) {
      setFeedback({ recordId, message: caught instanceof Error ? caught.message : 'The review action could not be saved. Retry the action.', state: 'error' })
      throw caught
    }
    finally { setBusy(false) }
  }

  async function handleStart() { try { await saveAction(() => startReview(token, recordId), 'Starting review…', 'Review session started. Your identity and timestamp were recorded.') } catch { /* The action status contains the server error. */ } }
  async function handleAssign() { try { await saveAction(() => assignReview(token, recordId, user.id), 'Saving assignment…', 'Assigned to you. The assignment was recorded in the audit trail.') } catch { /* The action status contains the server error. */ } }
  async function handleField(field: string, action: ReviewAction, reviewedValue?: unknown, reason?: string) { await saveAction(() => reviewField(token, recordId, field, action, reviewedValue, reason), `Saving ${reviewFieldLabel(field)}…`, `${reviewFieldLabel(field)} ${action === 'edit' ? 'correction' : 'decision'} saved. Original extraction and audit history preserved.`) }
  async function handleAcceptClear() { await saveAction(() => acceptClearFields(token, recordId), 'Accepting clear fields…', 'Clear field decisions saved with your authenticated identity.') }
  async function handleResolve(code: string, resolution: 'corrected' | 'confirmed' | 'not_applicable', reason: string, fieldName?: string | null) { await saveAction(() => resolveReviewIssue(token, recordId, code, resolution, reason, fieldName), 'Saving resolution…', 'Validation finding resolution saved with your reason in the audit trail.') }
  async function handleDecision(decision: ReviewDecision, reason?: string) { await saveAction(() => decideReview(token, recordId, decision, reason), 'Recording final decision…', `${decision === 'approve' ? 'Approval' : decision === 'reject' ? 'Rejection' : 'Send back'} saved. The record and audit trail are updated.`) }
  async function handleRecommendation(recommendation: ReviewDecision, reason: string) { await saveAction(() => recommendReview(token, recordId, recommendation, reason), 'Recording recommendation…', 'Verifier recommendation saved. The final decision remains with a Revenue Officer or Administrator.') }
  async function handleReprocess() { if (!item) return; setBusy(true); setError(''); try { await reprocessReviewDocument(token, item.documentId); window.location.hash = `#/processing?id=${encodeURIComponent(item.documentId)}` } catch (caught) { setError(caught instanceof Error ? caught.message : 'The source document could not be reprocessed.') } finally { setBusy(false) } }
  async function copyRecordId() { if (!item) return; try { await navigator.clipboard.writeText(item.recordId); setCopied(true); window.setTimeout(() => setCopied(false), 1800) } catch { setError('The browser could not copy this record ID.') } }

  const activeField = item?.fields.find((field) => field.field === selectedField)
  const editable = Boolean(item && canReview(user.role) && ['queued', 'in_progress'].includes(item.status))
  const started = item?.status === 'in_progress'
  const fieldsEditable = editable && started
  const decisionsEditable = Boolean(item && canDecide(user.role) && started)
  const viewerDocument = document?.id === item?.documentId ? document : null

  return <section className="rv-page rv-workspace-page" aria-label="Review workspace">
    <div className="rv-breadcrumb"><a href="#/review">Review queue</a><span className="rv-breadcrumb__slash">/</span><span>{item?.recordNumber || recordId || 'Record'}</span></div>
    {viewState === 'loading' ? <div className="rv-main-state" role="status"><span className="rv-spinner" /><strong>Opening review workspace…</strong><p>Loading the case, fields, and original source.</p></div> : null}
    {viewState === 'error' ? <div className="rv-main-state rv-main-state--error" role="alert"><AlertCircle size={24} /><strong>Review workspace unavailable</strong><p>{viewError}</p><button type="button" className="rv-button rv-button--primary" onClick={() => setRevision((value) => value + 1)}><RefreshCw size={14} />Retry</button></div> : null}
    {viewState === 'ready' && item ? <>
      <header className="rv-page-header rv-workspace-header"><div><a className="rv-back-link" href="#/review"><ArrowLeft size={14} />Back to queue</a><span className="rv-eyebrow">Review workspace · {item.recordNumber || item.recordId}</span><h1>Review land record</h1><p>Compare extracted and human-reviewed values with the original source. Resolve validation findings, then record a recommendation or authorized final decision.</p></div><div className="rv-workspace-header__actions"><span className={`rv-case-status rv-case-status--${item.status}`}>{reviewStatusLabel(item.status)}</span>{item.status === 'queued' && canReview(user.role) ? <button className="rv-button rv-button--primary" type="button" disabled={busy} onClick={() => void handleStart()}><Play size={14} />{busy ? 'Starting…' : 'Start review'}</button> : null}{item.status === 'sent_back' && canDecide(user.role) ? <button className="rv-button rv-button--primary" type="button" disabled={busy} onClick={() => void handleReprocess()}><RefreshCw size={14} />{busy ? 'Reprocessing…' : 'Reprocess document'}</button> : null}</div></header>
      <div className="rv-auth-note"><ShieldCheck size={17} aria-hidden="true" /><span><strong>Authenticated as {user.name}</strong> ({displayRoleName(user.role)}). Original extracted values remain visible alongside every human correction.</span></div>
      {error ? <div className="rv-inline-error" role="alert"><AlertCircle size={15} />{error}<button type="button" onClick={() => setError('')}>Dismiss</button></div> : null}
      {feedback?.recordId === recordId ? <div className={`rv-action-status rv-action-status--${feedback.state}`} role={feedback.state === 'error' ? 'alert' : 'status'} aria-live="polite">{feedback.state === 'loading' ? <span className="rv-spinner" aria-hidden="true" /> : feedback.state === 'success' ? <CheckCircle2 size={17} aria-hidden="true" /> : <AlertCircle size={17} aria-hidden="true" />}<span>{feedback.message}</span>{feedback.state === 'success' && user.role.toUpperCase() !== 'VERIFIER' ? <a href={`#/audit/${encodeURIComponent(item.recordId)}`}>View audit trail <ArrowRight size={13} /></a> : null}</div> : null}
      <div className="rv-case-strip"><div><span>Record number</span><strong>{item.recordNumber || 'Not detected'}</strong><button type="button" className="rv-copy-id" title={item.recordId} aria-label="Copy technical record ID" onClick={() => void copyRecordId()}><Copy size={11} />{copied ? 'Copied' : `ID ${item.recordId.slice(0, 8)}…`}</button></div><div><span>Document</span><strong title={item.documentName}>{item.documentName}</strong></div><div><span>Owner</span><strong>{item.ownerName || 'Not detected'}</strong></div><div><span>Survey number</span><strong>{reviewValue(item.reviewedRecord.surveyNumber ?? item.surveyNumber)}</strong>{item.reviewedRecord.surveyNumber && item.reviewedRecord.surveyNumber !== item.surveyNumber ? <small>Extracted: {item.surveyNumber}</small> : null}</div><div><span>Quality</span><strong>{qualityScoreLabel(item.qualityScore)} / 100</strong></div><div><span>Priority</span><strong className={`rv-priority-text rv-priority-text--${item.priority.toLowerCase()}`}>{priorityLabel(item.priority)}</strong></div></div>
      <div className="rv-case-context"><div><Clock3 size={14} /><span>Submitted {reviewDate(item.submittedAt)}</span></div><div><UserRound size={14} /><span>{item.assignedOfficer?.name || 'Unassigned officer'}</span></div><div><AlertCircle size={14} /><span>{item.primaryConflict || 'No primary conflict recorded'}</span></div>{item.priorityReasons.length ? <div className="rv-case-context__reasons">{item.priorityReasons.map((reason) => <span key={reason}>{reason}</span>)}</div> : null}</div>
      {canDecide(user.role) && ['queued', 'in_progress'].includes(item.status) && item.assignedOfficer?.id !== user.id ? <div className="rv-assign-row"><span>{item.assignedOfficer ? `Currently assigned to ${item.assignedOfficer.name}.` : 'This case has no assigned officer.'}</span><button type="button" className="rv-button rv-button--quiet" disabled={busy} onClick={() => void handleAssign()}><UserRound size={14} />Assign to me</button></div> : null}
      {item.status === 'queued' ? <div className="rv-start-note"><Play size={16} /><span>{canReview(user.role) ? 'Start this review to record your reviewer session and unlock field decisions.' : 'This case awaits an authorized reviewer.'}</span></div> : null}
      <nav className="rv-mobile-tabs" aria-label="Review workspace panels">{([{ id: 'document', label: 'Source' }, { id: 'fields', label: 'Values' }, { id: 'validation', label: 'Findings' }, { id: 'decision', label: 'Decision' }] as const).map((entry) => <button type="button" key={entry.id} className={tab === entry.id ? 'rv-mobile-tab rv-mobile-tab--active' : 'rv-mobile-tab'} aria-pressed={tab === entry.id} onClick={() => setTab(entry.id)}>{entry.label}</button>)}</nav>
      <div className="rv-review-grid">
        <div className={tab === 'document' ? 'rv-pane rv-pane--document rv-pane--active' : 'rv-pane rv-pane--document'}>{viewerDocument ? <Suspense fallback={<div className="rv-panel rv-panel-empty" role="status">Loading document viewer…</div>}><LiveDocumentViewer document={viewerDocument} page={page} selectedField={selectedField} onPageChange={setPage} onFieldSelect={selectField} /></Suspense> : <section className="rv-panel rv-document-unavailable"><div className="rv-panel-heading"><div><span className="rv-eyebrow">Original source</span><h2>Document viewer</h2></div><FileText size={17} /></div><div className="rv-panel-empty" role={documentError ? 'alert' : 'status'}>{documentError || 'Loading the original document…'}</div>{documentError ? <button type="button" className="rv-button rv-button--quiet" onClick={() => { setDocumentError(''); setDocumentRevision((value) => value + 1) }}><RefreshCw size={14} />Retry document</button> : null}</section>}</div>
        <div className={tab === 'fields' ? 'rv-pane rv-pane--fields rv-pane--active' : 'rv-pane rv-pane--fields'}><ReviewFieldsPanel fields={item.fields} selectedField={selectedField} canEdit={fieldsEditable} queued={item.status === 'queued'} decided={['approved', 'rejected', 'sent_back'].includes(item.status)} busy={busy} onSelect={selectField} onViewSource={(field) => selectField(field, 'document')} onAction={handleField} onAcceptClear={handleAcceptClear} /></div>
        <div className={tab === 'validation' ? 'rv-pane rv-pane--validation rv-pane--active' : 'rv-pane rv-pane--validation'}><section className="rv-source-card" aria-label="Selected field evidence"><div><LocateFixed size={16} /><span className="rv-eyebrow">Source evidence</span></div>{activeField ? <><strong>{reviewFieldLabel(activeField.field)}</strong><p>{reviewSourceText(activeField.source) || 'No source text was returned for this field.'}</p><span>{reviewSourcePage(activeField.source) ? `Page ${reviewSourcePage(activeField.source)}` : 'Source page unavailable'} · Confidence {confidenceLabel(activeField.confidence)}{reviewSourceMethod(activeField.source) ? ` · ${reviewSourceMethod(activeField.source)}` : ''}</span>{reviewSourcePage(activeField.source) ? <button type="button" className="rv-link-button" onClick={() => selectField(activeField.field, 'document')}><LocateFixed size={13} />Open source page</button> : null}</> : <p>Select a field to inspect the evidence returned by extraction.</p>}</section><ReviewValidationPanel item={item} canEdit={fieldsEditable} busy={busy} selectedField={selectedField} onSelectField={selectField} onResolve={handleResolve} /></div>
        <div className={tab === 'decision' ? 'rv-pane rv-pane--decision rv-pane--active' : 'rv-pane rv-pane--decision'}><ReviewDecisionPanel canViewAudit={user.role.toUpperCase() != 'VERIFIER'} item={item} canDecide={decisionsEditable} canRecommend={fieldsEditable && user.role.toUpperCase() === 'VERIFIER'} queued={item.status === 'queued'} busy={busy} onDecision={handleDecision} onRecommendation={handleRecommendation} /></div>
      </div>
      <div className="rv-workspace-footer"><span><CheckCircle2 size={15} />Every field decision and outcome is saved with the authenticated actor and role and timestamp.</span><div>{user.role.toUpperCase() !== 'VERIFIER' ? <a href={`#/audit/${encodeURIComponent(item.recordId)}`}>Audit trail <ArrowRight size={13} /></a> : null}<a href={`#/records/${encodeURIComponent(item.recordId)}`}>Record detail <ArrowRight size={13} /></a></div></div>
    </> : null}
  </section>
}
