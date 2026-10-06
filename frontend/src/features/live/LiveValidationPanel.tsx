import { AlertTriangle, ArrowUpRight, CheckCircle2, CircleDashed, ShieldCheck, XCircle } from 'lucide-react'
import type { CSSProperties } from 'react'
import { fieldLabel, qualityScoreLabel, reviewRecordId, routeLabel } from './format'
import type { DocumentDetail, ValidationIssue } from './types'

type Props = { document: DocumentDetail; prominent?: boolean; onReviewField: (field: string) => void; onFieldSelect?: (field: string) => void; selectedField?: string | null; showReviewActions?: boolean }

function printable(value: unknown) {
  if (value == null) return 'Not available'
  if (Array.isArray(value)) return value.map(printable).join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function issueTitle(issue: ValidationIssue) {
  return issue.fieldName ? `${fieldLabel(issue.fieldName)} · ${issue.code.replaceAll('_', ' ')}` : issue.code.replaceAll('_', ' ')
}

const layers = [
  { key: 'field', label: 'Field validation', scoreKey: 'fieldScore', weightKey: 'fieldWeight', contributionKey: 'fieldContribution' },
  { key: 'record', label: 'Record validation', scoreKey: 'recordScore', weightKey: 'recordWeight', contributionKey: 'recordContribution' },
  { key: 'cross_system', label: 'Local reference check', scoreKey: 'crossSystemScore', weightKey: 'crossSystemWeight', contributionKey: 'crossSystemContribution' },
] as const

export function LiveValidationPanel({ document, prominent = false, onReviewField, onFieldSelect, selectedField, showReviewActions = true }: Props) {
  const validation = document.validation
  const score = document.scoreBreakdown
  const conflicts = validation?.issues.filter((issue) => issue.level === 'cross_system' && issue.code !== 'reference_unavailable' && issue.code !== 'reference_not_found') ?? []
  const attention = validation?.issues.filter((issue) => !conflicts.includes(issue)) ?? []
  const route = validation?.routing ?? score?.routing ?? null
  const reviewId = reviewRecordId(document)
  const errors = validation?.issues.filter((issue) => issue.severity === 'error').length ?? 0
  const warnings = validation?.issues.filter((issue) => issue.severity === 'warning').length ?? 0
  const selectIssue = onFieldSelect ?? onReviewField
  return (
    <section className={`ldw-validation-card ${prominent ? 'ldw-validation-card--prominent' : ''}`} aria-labelledby="ldw-validation-title">
      <div className="ldw-card-heading"><div><span className="ldw-eyebrow">Backend validation</span><h2 id="ldw-validation-title">Validation findings & quality</h2></div><span className="ldw-card-aside">{validation ? `Calculated ${new Date(validation.generatedAt).toLocaleDateString()}` : 'Pending processing'}</span></div>
      <div className="ldw-validation-summary" role="status"><span><CheckCircle2 size={14} />{validation ? '3 layers completed' : '0 layers completed'}</span><span><CircleDashed size={14} />{validation ? '0 layers pending' : '3 layers awaiting results'}</span><span><AlertTriangle size={14} />{validation ? `${warnings} warnings · ${conflicts.length} conflicts` : 'Warnings pending'}</span><span><XCircle size={14} />{validation ? `${errors} errors` : 'Errors pending'}</span></div>
      {!validation || !score ? <div className="ldw-panel-empty"><CircleDashed size={28} aria-hidden="true" /><strong>{document.status === 'failed' ? 'Validation interrupted' : document.status === 'completed' ? 'Validation results unavailable' : document.status === 'processing' ? 'Validation is processing' : 'Awaiting processing'}</strong><p>{document.status === 'failed' ? 'Processing failed before all results were saved. Inspect the processing error; an authorized Revenue Officer or Administrator can retry.' : document.status === 'completed' ? 'The backend has not returned a complete validation report. Refresh this document before continuing review.' : 'Field, record, and local reference checks appear after backend processing completes.'}</p></div> : <>
        <div className="ldw-score-hero">
          <div className={`ldw-score-ring ldw-score-ring--${route}`} style={{ '--ldw-score': `${score.qualityScore}%` } as CSSProperties} aria-label={`Quality score ${qualityScoreLabel(score.qualityScore)} out of 100`}><strong>{qualityScoreLabel(score.qualityScore)}</strong><span>/ 100</span></div>
          <div className="ldw-score-summary"><span className="ldw-eyebrow">Quality score</span><h3>{routeLabel(route)}</h3><p>{route === 'approved' ? 'Automated checks met the configured quality threshold. An officer remains responsible for final verification and approval.' : route === 'human_review' ? 'This record needs an officer to compare extracted values and source evidence.' : 'This source did not meet the configured quality threshold. An officer can inspect the findings and decide the next action.'}</p><span className={`ldw-route-tag ldw-route-tag--${route}`}>{routeLabel(route)}</span></div>
        </div>
        <div className="ldw-score-breakdown"><div className="ldw-section-subhead"><h3>Transparent score</h3><span>Weighted field {(score.fieldWeight * 100).toFixed(0)}% · record {(score.recordWeight * 100).toFixed(0)}% · cross-system {(score.crossSystemWeight * 100).toFixed(0)}%</span></div><div className="ldw-score-grid">
          {layers.map((layer) => <div key={layer.key}><span>{layer.label}</span><strong>{validation[layer.scoreKey].toFixed(1)} <small>× {(score[layer.weightKey] * 100).toFixed(0)}%</small></strong><b>= {score[layer.contributionKey].toFixed(1)}</b></div>)}
          <div className="ldw-score-penalty"><span>Warning penalties</span><strong>− {score.warningPenalty.toFixed(1)}</strong></div>
          <div className="ldw-score-final"><span>Final score</span><strong>{score.qualityScore.toFixed(1)} / 100</strong></div>
        </div><p className="ldw-threshold-note">Score bands: below {score.rejectBelow} recommend rejection · {score.rejectBelow}–{score.approveAtOrAbove - 1} require closer review · {score.approveAtOrAbove}+ checks passed. Every record still needs an officer decision.</p></div>
        <p className="ldw-validation-notice">Local reference checks compare available imported data; they do not verify an official government registry.</p>{validation.issues.length === 0 ? <div className="ldw-validation-notice" role="status"><CheckCircle2 size={16} />No validation findings. Compare the extracted values with the source before the final decision.</div> : null}<div className="ldw-validation-layers"><div className="ldw-section-subhead"><h3>Validation layers</h3><span>{validation.issues.length} {validation.issues.length === 1 ? 'finding' : 'findings'}</span></div><div className="ldw-layer-grid">{layers.map((layer) => { const count = validation.issues.filter((issue) => issue.level === layer.key).length; return <div key={layer.key}><span className={count ? 'ldw-layer-warning' : 'ldw-layer-pass'}>{count ? <AlertTriangle size={17} /> : <CheckCircle2 size={17} />}</span><strong>{layer.label}</strong><small>{count ? `${count} ${count === 1 ? 'finding' : 'findings'}` : 'No findings detected'}</small></div> })}</div></div>
        {conflicts.length > 0 ? <div className="ldw-conflict-block"><div className="ldw-section-subhead"><h3><AlertTriangle size={17} aria-hidden="true" /> Potential inconsistencies</h3><span>{conflicts.length} detected</span></div>{conflicts.map((issue) => <article key={`${issue.code}-${issue.fieldName}`} className={`ldw-conflict ${selectedField && selectedField === issue.fieldName ? 'ldw-finding--selected' : ''}`}><strong>{issue.message}</strong><dl><div><dt>Document</dt><dd>{printable(issue.actual)}</dd></div><div><dt>Reference</dt><dd>{printable(issue.expected)}</dd></div></dl>{issue.fieldName && (onFieldSelect || showReviewActions) ? <button type="button" onClick={() => selectIssue(issue.fieldName!)}>View field evidence <ArrowUpRight size={14} /></button> : null}</article>)}</div> : null}
        {attention.length > 0 ? <div className="ldw-issue-block"><div className="ldw-section-subhead"><h3>Validation findings</h3><span>{attention.length} items</span></div><ul>{attention.map((issue, index) => <li key={`${issue.code}-${index}`} className={`${issue.severity === 'error' ? 'ldw-finding--error' : ''} ${selectedField && selectedField === issue.fieldName ? 'ldw-finding--selected' : ''}`}>{issue.severity === 'error' ? <XCircle size={15} aria-hidden="true" /> : <AlertTriangle size={15} aria-hidden="true" />}<span><strong>{issueTitle(issue)}</strong><small>{issue.message}</small></span>{issue.fieldName && (onFieldSelect || showReviewActions) ? <button type="button" onClick={() => selectIssue(issue.fieldName!)}>View field</button> : null}</li>)}</ul></div> : null}
        {showReviewActions && reviewId ? <a className="ldw-review-link" href={`#/review/${encodeURIComponent(reviewId)}`}>Open review workspace <ArrowUpRight size={16} aria-hidden="true" /></a> : null}
        <p className="ldw-validation-notice"><ShieldCheck size={16} aria-hidden="true" /> Source-backed extraction and validation. Human officers remain responsible for final verification and approval.</p>
      </>}
    </section>
  )
}
