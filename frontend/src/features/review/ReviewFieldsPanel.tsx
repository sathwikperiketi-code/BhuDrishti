import { useState } from 'react'
import { Check, CheckCircle2, FilePenLine, FileX2, LocateFixed, Save, ShieldCheck } from 'lucide-react'
import { confidenceLabel, reviewDate, reviewFieldLabel, reviewSourceMethod, reviewSourcePage, reviewValue } from './format'
import { acceptedFieldValue, isClearValidation } from './reviewState'
import type { ReviewAction, ReviewField } from './types'
import { Modal } from '../../components/ui/Overlay'
import { displayRoleName } from '../../lib/roles'

type Props = {
  fields: ReviewField[]
  selectedField: string | null
  canEdit: boolean
  queued: boolean
  decided: boolean
  busy: boolean
  onSelect: (field: string) => void
  onViewSource: (field: string) => void
  onAction: (field: string, action: ReviewAction, reviewedValue?: unknown, reason?: string) => Promise<void>
  onAcceptClear: () => Promise<void>
}

function fieldTone(field: ReviewField) {
  if (field.reviewStatus === 'edit' || field.reviewStatus === 'accept') return 'success'
  if (field.reviewStatus === 'reject') return 'danger'
  if (field.validationStatus && !isClearValidation(field.validationStatus)) return 'warning'
  return 'neutral'
}

function castInput(value: string, original: unknown): unknown {
  if (typeof original === 'number' && value.trim() !== '' && Number.isFinite(Number(value))) return Number(value)
  return value.trim()
}

export function ReviewFieldsPanel({ fields, selectedField, canEdit, queued, decided, busy, onSelect, onViewSource, onAction, onAcceptClear }: Props) {
  const field = fields.find((entry) => entry.field === selectedField) ?? fields[0]
  const [form, setForm] = useState<{ field: string; mode: 'view' | 'edit' | 'reject'; draft: string; reason: string }>({ field: '', mode: 'view', draft: '', reason: '' })
  const [error, setError] = useState('')
  const mode = form.field === field?.field ? form.mode : 'view'
  const currentValue = field?.reviewedValue ?? field?.originalValue
  const currentDraft = currentValue == null ? '' : reviewValue(currentValue)
  const draft = form.field === field?.field ? form.draft : currentDraft
  const reason = form.field === field?.field ? form.reason : ''

  async function submit(action: ReviewAction) {
    if (!field || busy) return
    if (action === 'edit' && (!draft.trim() || draft.trim() === reviewValue(field.originalValue))) {
      setError('Enter a corrected value that differs from the extracted result.')
      return
    }
    if ((action === 'edit' || action === 'reject') && !reason.trim()) {
      setError('Add a reason so the change is clear in the audit trail.')
      return
    }
    setError('')
    try {
      await onAction(field.field, action, action === 'edit' ? castInput(draft, field.originalValue) : undefined, reason)
      setForm({ field: field.field, mode: 'view', draft: '', reason: '' })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The field decision could not be saved.')
    }
  }

  return <section className="rv-panel rv-fields-panel" aria-labelledby="rv-fields-title" aria-busy={busy}>
    <div className="rv-panel-heading"><div><span className="rv-eyebrow">Extraction → human review</span><h2 id="rv-fields-title">Values & field decisions</h2></div><span className="rv-panel-count">{fields.filter((entry) => entry.reviewStatus !== 'unreviewed').length} / {fields.length} reviewed</span></div>
    {fields.length === 0 ? <div className="rv-panel-empty">No extracted fields are available. Inspect the original source and validation findings; a record cannot be approved while required values are missing.</div> : <>
      {canEdit && fields.some((entry) => entry.reviewStatus === 'unreviewed' && entry.validationStatus === 'clear' && entry.originalValue != null && entry.originalValue !== '') ? <div className="rv-bulk-review"><span>Clear fields still require an explicit reviewer action.</span><button type="button" disabled={busy} onClick={() => { setError(''); void onAcceptClear().catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Clear fields could not be accepted.')) }}><CheckCircle2 size={13} />Accept clear fields</button></div> : null}
      <div className="rv-fields-list" aria-label="Extracted fields">{fields.map((entry) => <button key={entry.field} type="button" className={field?.field === entry.field ? 'rv-field-row rv-field-row--active' : 'rv-field-row'} aria-pressed={field?.field === entry.field} onClick={() => { setError(''); onSelect(entry.field) }}>
        <span className="rv-field-row__body"><span className="rv-field-row__label">{reviewFieldLabel(entry.field)}</span><strong title={reviewValue(entry.originalValue)}>{reviewValue(entry.originalValue)}</strong><small>{reviewSourcePage(entry.source) ? `Page ${reviewSourcePage(entry.source)} source` : 'Source location unavailable'}</small></span>
        <span className="rv-field-row__side"><span className={`rv-field-status rv-field-status--${fieldTone(entry)}`}>{entry.reviewStatus === 'unreviewed' ? 'To review' : entry.reviewStatus === 'accept' ? 'Accepted' : entry.reviewStatus === 'edit' ? 'Edited' : 'Rejected'}</span><span className="rv-field-row__confidence">{confidenceLabel(entry.confidence)}</span></span>
      </button>)}</div>
      {field ? <div className="rv-field-detail" key={field.field}>
        <div className="rv-field-detail__heading"><div><span className="rv-eyebrow">Selected field</span><h3>{reviewFieldLabel(field.field)}</h3></div>{reviewSourcePage(field.source) ? <button type="button" className="rv-link-button" onClick={() => onViewSource(field.field)}><LocateFixed size={14} /> View source</button> : null}</div>
        <div className="rv-value-compare rv-value-compare--three"><div><span>Extracted value</span><strong>{reviewValue(field.originalValue)}</strong><small>Original OCR / text extraction preserved</small></div><div><span>Human-reviewed value</span><strong>{field.reviewStatus === 'edit' ? reviewValue(field.reviewedValue) : field.reviewStatus === 'accept' ? reviewValue(acceptedFieldValue(field)) : field.reviewStatus === 'reject' ? 'Rejected · correction needed' : 'Not reviewed yet'}</strong><small>{field.reviewStatus === 'edit' ? 'Correction saved by a reviewer' : field.reviewStatus === 'accept' ? 'Extracted value accepted by a reviewer' : 'Requires an explicit field decision'}</small></div><div><span>Field decision</span><strong className={field.reviewStatus === 'unreviewed' || field.reviewStatus === 'reject' ? 'rv-value-compare__pending' : ''}>{field.reviewStatus === 'reject' ? 'Reject' : field.reviewStatus === 'unreviewed' ? 'Pending' : field.reviewStatus === 'edit' ? 'Corrected' : 'Accept'}</strong><small>Final record approval is a separate decision</small></div></div>
        <div className="rv-field-facts"><span><ShieldCheck size={13} />Confidence {confidenceLabel(field.confidence)}</span><span>{field.validationStatus || 'Validation state unavailable'}</span>{reviewSourcePage(field.source) ? <span>Page {reviewSourcePage(field.source)} · {reviewSourceMethod(field.source) || 'OCR / text extraction'}</span> : null}</div>
        {field.referenceValue != null ? <div className="rv-reference-value"><span>Reference entry</span><strong>{reviewValue(field.referenceValue)}</strong></div> : null}
        {field.reviewStatus !== 'unreviewed' ? <p className="rv-field-history"><CheckCircle2 size={14} />{field.reviewStatus === 'edit' ? `Changed from “${reviewValue(field.originalValue)}” to “${reviewValue(field.reviewedValue)}”.` : field.reviewStatus === 'accept' ? 'Extracted value explicitly accepted.' : 'Extracted value rejected.'}{field.reviewer ? ` ${field.reviewer.name} · ${displayRoleName(field.reviewer.role)}` : ''}{field.reviewedAt ? ` · ${reviewDate(field.reviewedAt)}` : ''}{field.reason ? ` Reason: ${field.reason}` : ''}</p> : null}
        {canEdit ? <><div className="rv-field-actions"><button type="button" disabled={busy} onClick={() => void submit('accept')} className="rv-action rv-action--accept"><Check size={15} />Accept extracted value</button><button type="button" disabled={busy} onClick={() => { setForm({ field: field.field, mode: 'edit', draft: currentDraft, reason: '' }); setError('') }} className={mode === 'edit' ? 'rv-action rv-action--active' : 'rv-action'}><FilePenLine size={15} />Edit value</button><button type="button" disabled={busy} onClick={() => { setForm({ field: field.field, mode: 'reject', draft: '', reason: '' }); setError('') }} className={mode === 'reject' ? 'rv-action rv-action--reject rv-action--active' : 'rv-action rv-action--reject'}><FileX2 size={15} />Reject value</button></div>
          {mode === 'edit' ? <div className="rv-field-form">
            <label>Human-reviewed value<input disabled={busy} value={draft} maxLength={300} onChange={(event) => setForm((current) => ({ ...current, draft: event.target.value }))} aria-label={`Corrected ${reviewFieldLabel(field.field)}`} /></label>
            <label>Reason <span>Required for the audit trail</span><textarea disabled={busy} value={reason} maxLength={1000} rows={3} onChange={(event) => setForm((current) => ({ ...current, reason: event.target.value }))} placeholder={mode === 'edit' ? 'What source evidence supports this correction?' : 'Why is this value unusable?'} /></label>
            <div className="rv-field-form__actions"><button type="button" className="rv-button rv-button--quiet" disabled={busy} onClick={() => { setForm({ field: field.field, mode: 'view', draft: '', reason: '' }); setError('') }}>Cancel</button><button type="button" className="rv-button rv-button--primary" disabled={busy} onClick={() => void submit(mode === 'edit' ? 'edit' : 'reject')}>{busy ? <span className="rv-spinner" aria-hidden="true" /> : <Save size={14} />}{busy ? 'Saving…' : 'Save field decision'}</button></div>
          </div> : null}
          <Modal open={mode === 'reject'} onClose={() => { if (!busy) { setForm({ field: field.field, mode: 'view', draft: '', reason: '' }); setError('') } }} title="Reject · confirm field decision" description={reviewFieldLabel(field.field)} size="sm" className="rv-confirm-modal">
            <div className="rv-field-form" aria-busy={busy}>
              <p><strong>Extracted value:</strong> {reviewValue(field.originalValue)}</p>
              <p>This rejects the selected field, not the whole record. The original evidence remains visible. Record approval will require resolving this field.</p>
              <label>Reason · required<textarea disabled={busy} rows={3} maxLength={1000} value={reason} onChange={(event) => setForm((current) => ({ ...current, reason: event.target.value }))} placeholder="Explain why this field value is unsuitable" /></label>
              {error ? <p className="rv-form-error" role="alert">{error}</p> : null}
              <div className="rv-field-form__actions"><button type="button" className="rv-button rv-button--quiet" disabled={busy} onClick={() => { setForm({ field: field.field, mode: 'view', draft: '', reason: '' }); setError('') }}>Cancel</button><button type="button" className="rv-button rv-button--danger" disabled={busy || !reason.trim()} onClick={() => void submit('reject')}>{busy ? 'Saving field decision…' : 'Confirm field rejection'}</button></div>
            </div>
          </Modal>
        </> : <p className="rv-read-only">{queued ? 'Start review to record your session and unlock field decisions.' : decided ? 'This review attempt is complete. The original extracted values and human decisions remain preserved.' : 'Your role can inspect this review. Editing and decisions require reviewer access.'}</p>}
        {error && mode !== 'reject' ? <p className="rv-form-error" role="alert">{error}</p> : null}
      </div> : null}
    </>}
  </section>
}
