import { AlertCircle, ArrowRight, Check, CheckCircle2, Circle, LoaderCircle } from 'lucide-react'
import { PIPELINE_STEPS, STAGE_STATUS_LABELS, completedPipelineCount, durationLabel, pipelineStepStatus, recordedProcessingDuration, recordedStageDuration } from './pipeline'
import { qualityScoreLabel } from './format'
import type { DocumentDetail } from './types'

type Props = { document: DocumentDetail; readOnly?: boolean }

export function ProcessingPanel({ document, readOnly = false }: Props) {
  const complete = completedPipelineCount(document)
  const current = PIPELINE_STEPS.find((stage) => stage.backendStage === document.stage)
  const isProcessing = document.status === 'processing'
  const isCompleted = document.status === 'completed'
  const isFailed = document.status === 'failed'
  const title = isProcessing ? 'Analyzing land record' : isCompleted ? 'Processing completed' : isFailed ? 'Processing failed' : 'Document intelligence pipeline'
  const activeMessage = document.stages.find((entry) => entry.stage === document.stage)?.message
  const percent = Math.round(complete / PIPELINE_STEPS.length * 100)
  const elapsed = recordedProcessingDuration(document)
  return (
    <section className={`ldw-processing-card ldw-processing-card--${document.status}`} aria-labelledby="ldw-processing-title">
      <div className="ldw-processing-hero"><div className="ldw-processing-headline"><span className="ldw-eyebrow">Live from persisted processing state</span><h2 id="ldw-processing-title">{title}</h2><p>{isProcessing ? 'Extracting structured evidence from the uploaded source.' : isCompleted ? 'Evidence extraction and validation completed. An officer should review the result.' : isFailed ? 'The pipeline stopped and the backend saved the error. A Revenue Officer or Administrator can retry processing.' : 'The uploaded source is stored and ready for processing.'}</p></div><div className="ldw-processing-count"><strong>{complete}<span> / {PIPELINE_STEPS.length}</span></strong><small>recorded steps complete</small></div></div>
      <div className="ldw-processing-progress-meta"><strong>{percent}% of pipeline steps recorded complete</strong>{elapsed != null ? <span>{durationLabel(elapsed)} {isProcessing ? 'elapsed at last server update' : 'processing time'}</span> : <span>Timing appears when recorded by the server</span>}</div>
      <div className="ldw-processing-track" role="progressbar" aria-label="Recorded pipeline completion" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}><span style={{ transform: `scaleX(${percent / 100})` }} /></div>
      <div className="ldw-stage-strip" role="list" aria-label="Document processing stages">
        {PIPELINE_STEPS.map((stage, index) => {
          const status = pipelineStepStatus(document, stage)
          const persisted = document.stages.find((entry) => entry.stage === stage.backendStage)
          const duration = recordedStageDuration(persisted)
          return <div role="listitem" key={stage.id} className={`ldw-stage ldw-stage--${status}`} aria-label={`${stage.label}: ${STAGE_STATUS_LABELS[status]}`} title={persisted?.message || (status === 'unavailable' ? 'No persisted stage history is available.' : stage.detail)}>
            <span className="ldw-stage-number">{String(index + 1).padStart(2, '0')}</span><span className="ldw-stage-icon">{status === 'completed' ? <Check size={14} /> : status === 'running' ? <LoaderCircle size={14} className="ldw-stage-spinner" /> : status === 'failed' ? <AlertCircle size={14} /> : <Circle size={10} />}</span>
            <span className="ldw-stage-copy"><strong>{stage.short.toUpperCase()}</strong><small>{STAGE_STATUS_LABELS[status]}</small>{duration != null ? <small>{durationLabel(duration)}</small> : null}</span>
          </div>
        })}
      </div>
      {document.warnings.length > 0 ? <div className="ldw-processing-warning" role="status"><AlertCircle size={16} aria-hidden="true" /><span>{document.warnings.join(' · ')}</span></div> : null}
      <div className={`ldw-processing-current ldw-processing-current--${document.status}`} role="status" aria-live="polite">
        {isProcessing ? <span className="ldw-current-pulse" aria-hidden="true" /> : isCompleted ? <CheckCircle2 size={17} aria-hidden="true" /> : isFailed ? <AlertCircle size={17} aria-hidden="true" /> : <Circle size={15} aria-hidden="true" />}
        <p>{isProcessing ? <><strong>{document.stage === 'validation' ? 'Validation checks' : current?.label ?? 'Processing'} running.</strong> {activeMessage || current?.detail || 'Waiting for the next persisted update.'}</> : isFailed ? <><strong>Processing stopped.</strong> {document.error?.message ?? 'An unknown error occurred.'}</> : isCompleted ? <><strong>Processing finished.</strong> Inspect extracted evidence and validation below.</> : readOnly ? 'This source has not been processed. Your current view is read-only.' : 'Ready to start text extraction and validation.'}</p>
      </div>
      {isCompleted ? <div className="ldw-processing-complete"><div className="ldw-processing-metrics"><div><strong>{document.fields.length}</strong><span>Fields extracted</span></div><div><strong>{document.validation?.issues.length ?? '—'}</strong><span>Validation findings</span></div><div><strong>{document.pageCount}</strong><span>Pages processed</span></div><div><strong>{qualityScoreLabel(document.validation?.qualityScore)}</strong><span>Quality score</span></div></div><div className="ldw-processing-links"><button type="button" onClick={() => window.document.getElementById('ldw-extraction-title')?.scrollIntoView()}>View extracted record <ArrowRight size={14} aria-hidden="true" /></button><button type="button" onClick={() => window.document.getElementById('ldw-validation-title')?.scrollIntoView()}>Review validation <ArrowRight size={14} aria-hidden="true" /></button></div></div> : null}
      <p className="ldw-processing-note">Field, record, and cross-system checks are three views of one backend validation stage. Their results appear together after that stage completes.</p>
    </section>
  )
}
