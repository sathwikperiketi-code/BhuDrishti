import { useState } from 'react'
import { AlertTriangle, CheckCircle2, ChevronRight, CircleHelp, FileWarning, Link2, ShieldCheck } from 'lucide-react'
import { reviewFieldLabel, reviewValue } from './format'
import { qualityScoreLabel } from '../live/format'
import type { ReviewCaseDetail } from './types'
import { isClearValidation, resolutionForIssue } from './reviewState'

type Props = {
  item: ReviewCaseDetail
  canEdit: boolean
  busy: boolean
  selectedField: string | null
  onSelectField: (field: string) => void
  onResolve: (code: string, resolution: 'corrected' | 'confirmed' | 'not_applicable', reason: string, fieldName?: string | null) => Promise<void>
}

export function ReviewValidationPanel({ item, canEdit, busy, selectedField, onSelectField, onResolve }: Props) {
  const issues = item.validation?.issues ?? []
  const [editing, setEditing] = useState<string | null>(null)
  const [resolution, setResolution] = useState<'corrected' | 'confirmed' | 'not_applicable'>('corrected')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')

  async function submit(code: string, fieldName: string | null) {
    if (busy) return
    if (reason.trim().length < 4) { setError('Add at least four characters explaining the finding resolution for the audit trail.'); return }
    setError('')
    try {
      await onResolve(code, resolution, reason.trim(), fieldName)
      setEditing(null)
      setReason('')
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'The validation finding could not be resolved.') }
  }

  return <section className="rv-panel rv-validation-panel" aria-labelledby="rv-validation-title" aria-busy={busy}>
    <div className="rv-panel-heading"><div><span className="rv-eyebrow">Stored checks → reviewer resolution</span><h2 id="rv-validation-title">Validation findings</h2></div><span className="rv-panel-count">{issues.length} {issues.length === 1 ? 'finding' : 'findings'}</span></div>
    <div className="rv-validation-summary"><span className="rv-validation-summary__icon"><ShieldCheck size={19} /></span><div><span>Calculated quality score</span><strong>{qualityScoreLabel(item.qualityScore)} <small>/ 100</small></strong><p>Review preserves the original validation score; officer decisions are recorded separately.</p></div></div>
    <div className="rv-check-counts" aria-label="Backend validation results"><div><strong>{item.fields.filter((field) => isClearValidation(field.validationStatus)).length}</strong><span>Clear fields</span></div><div><strong>{Math.max(0, item.summary.warningsTotal - item.summary.warningsResolved)}</strong><span>Open findings</span></div><div><strong>{item.summary.criticalConflicts}</strong><span>Critical conflicts</span></div></div>
    <div className="rv-check-progress"><div><span>Findings resolved</span><strong>{item.summary.warningsResolved} / {item.summary.warningsTotal}</strong></div><div className="rv-check-progress__bar"><span style={{ width: `${item.summary.warningsTotal ? Math.min(100, item.summary.warningsResolved / item.summary.warningsTotal * 100) : 100}%` }} /></div></div>
    {issues.length === 0 ? <div className="rv-validation-empty">{item.validation ? <CheckCircle2 size={20} /> : <CircleHelp size={20} />}<span>{item.validation ? 'No validation findings. Compare the fields with the original source; an authorized officer must still record the final decision.' : 'Validation results are unavailable. Retry this view or inspect the processing status before making a decision.'}</span></div> : <div className="rv-issues-list">{issues.map((issue, index) => {
      const resolved = resolutionForIssue(item.issueResolutions || [], issue.code, issue.fieldName)
      const key = `${issue.code}:${issue.fieldName || index}`
      const open = editing === key
      const supportedField = issue.fieldName && item.fields.some((field) => field.field === issue.fieldName)
      return <article className={`rv-issue${resolved ? ' rv-issue--resolved' : ''}${issue.fieldName && selectedField === issue.fieldName ? ' rv-issue--selected' : ''}`} key={key}>
        <div className="rv-issue__head"><span className={resolved ? 'rv-issue__icon rv-issue__icon--resolved' : 'rv-issue__icon'}>{resolved ? <CheckCircle2 size={17} /> : issue.severity === 'critical' || issue.severity === 'error' ? <AlertTriangle size={17} /> : <FileWarning size={17} />}</span><div><span className="rv-issue__scope">{issue.level.replace(/_/g, ' ')} · {issue.severity}</span><h3>{issue.message}</h3></div></div>
        {supportedField ? <button type="button" className="rv-issue__field" aria-pressed={selectedField === issue.fieldName} onClick={() => onSelectField(issue.fieldName!)}><Link2 size={13} />{reviewFieldLabel(issue.fieldName!)}<ChevronRight size={13} /></button> : issue.fieldName ? <span className="rv-issue__pending">{reviewFieldLabel(issue.fieldName)} · Field evidence unavailable</span> : null}
        {(issue.actual != null || issue.expected != null) ? <div className="rv-issue__compare"><div><span>Extracted</span><strong>{reviewValue(issue.actual)}</strong></div><div><span>Reference / expected</span><strong>{reviewValue(issue.expected)}</strong></div></div> : null}
        {resolved ? <div className="rv-issue__resolution"><CheckCircle2 size={13} /><div><strong>{resolved.resolution.replace(/_/g, ' ')}</strong><p>{resolved.reason}</p></div></div> : canEdit ? <><button type="button" className="rv-issue__resolve" disabled={busy} onClick={() => { setEditing(open ? null : key); setResolution(item.fields.find((field) => field.field === issue.fieldName)?.reviewStatus === 'edit' ? 'corrected' : 'confirmed'); setError(''); setReason('') }}>{open ? 'Close resolution' : 'Record resolution'} <ChevronRight size={13} /></button>{open ? <div className="rv-issue__form"><label>Resolution<select disabled={busy} value={resolution} onChange={(event) => setResolution(event.target.value as typeof resolution)}><option value="corrected">Corrected after evidence review</option><option value="confirmed">Confirmed with rationale</option><option value="not_applicable">Not applicable</option></select></label><label>Reviewer reason<textarea disabled={busy} rows={3} maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Describe the source or reference used to resolve this finding" /></label>{error ? <p className="rv-form-error" role="alert">{error}</p> : null}<button type="button" className="rv-button rv-button--primary" disabled={busy || reason.trim().length < 4} onClick={() => void submit(issue.code, issue.fieldName)}>{busy ? 'Saving…' : 'Save resolution'}</button></div> : null}</> : <span className="rv-issue__pending"><CircleHelp size={13} />Awaiting reviewer resolution</span>}
      </article>
    })}</div>}
  </section>
}
