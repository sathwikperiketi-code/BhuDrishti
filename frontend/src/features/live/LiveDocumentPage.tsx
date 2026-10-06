import { lazy, Suspense, useState } from 'react'
import { AlertCircle, ArrowRight, ChevronRight, FileCheck2, FileText, RefreshCw, ShieldCheck, Sparkles, Upload } from 'lucide-react'
import { documentWorkflowLabel, formatBytes, formatDate, reviewRecordId } from './format'
import { LiveExtractionPanel } from './LiveExtractionPanel'
import { LiveValidationPanel } from './LiveValidationPanel'
import { ProcessingPanel } from './ProcessingPanel'
import { UploadZone } from './UploadZone'
import { useLiveDocuments } from './useLiveDocuments'
import type { DatasetScope, DocumentSummary, LiveView } from './types'
import './live.css'
import { isQaWorkspace } from '../../lib/workspace'

const LiveDocumentViewer = lazy(async () => ({ default: (await import('./LiveDocumentViewer')).LiveDocumentViewer }))

type Props = { initialView?: LiveView; canUpload?: boolean; token: string; dataset?: DatasetScope }

const views: { view: LiveView; label: string; path: string }[] = [
  { view: 'document', label: 'Document workspace', path: 'documents' },
  { view: 'processing', label: 'Processing', path: 'processing' },
  { view: 'validation', label: 'Validation', path: 'validation' },
]

function statusTone(document: DocumentSummary) {
  if (document.status === 'failed' || document.reviewStatus === 'rejected') return 'danger'
  if (document.reviewStatus === 'queued' || document.reviewStatus === 'in_progress' || document.reviewStatus === 'sent_back') return 'warning'
  return document.status === 'completed' ? 'success' : document.status === 'processing' ? 'info' : 'neutral'
}

function uploadSummary(item: DocumentSummary) {
  return `${item.pageCount} ${item.pageCount === 1 ? 'page' : 'pages'} · ${formatBytes(item.fileSize)}`
}

export function LiveDocumentPage({ initialView = 'document', canUpload = true, token, dataset = 'operational' }: Props) {
  const live = useLiveDocuments(token, dataset)
  const isSample = dataset === 'sample'
  const canAct = canUpload && !isSample
  const [fieldChoices, setFieldChoices] = useState<Record<string, string>>({})
  const [pageChoices, setPageChoices] = useState<Record<string, number>>({})
  const selectedField = live.selectedId ? fieldChoices[live.selectedId] ?? null : null
  const page = live.selectedId ? pageChoices[live.selectedId] ?? 1 : 1
  const item = live.document
  const recordId = item && !isSample ? reviewRecordId(item) : null
  const title = isSample ? 'Sample document dataset' : initialView === 'processing' ? 'Processing workspace' : initialView === 'validation' ? 'Validation center' : 'Document workspace'
  const description = isSample ? 'Inspect clearly separated test documents and their stored evidence in read-only mode.' : !canAct
    ? 'Inspect uploaded source pages, extracted fields, validation, and audit evidence in read-only mode.'
    : initialView === 'processing'
    ? 'Follow the backend pipeline as it prepares, recognizes, and validates your uploaded source.'
    : initialView === 'validation'
      ? 'Inspect actual field, record, and reference checks with a transparent quality score.'
      : 'Upload a land record, inspect its original pages, and trace every extracted field to source evidence.'

  function selectField(field: string) {
    if (!item) return
    setFieldChoices((current) => ({ ...current, [item.id]: field }))
    const sourcePage = item.fields.find((entry) => entry.field === field)?.source?.page
    if (sourcePage) setPageChoices((current) => ({ ...current, [item.id]: sourcePage }))
  }

  function reviewField(field: string) {
    if (isSample) return
    selectField(field)
    if (recordId) window.location.hash = `#/review/${encodeURIComponent(recordId)}?field=${encodeURIComponent(field)}`
  }

  function inspectFinding(field: string) {
    selectField(field)
    document.getElementById('ldw-extraction-title')?.scrollIntoView({ block: 'center', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
  }

  return (
    <section className="ldw-page" aria-label={title}>
      <div className="ldw-breadcrumb"><span>SIH 2026 / SIH26018</span><ChevronRight size={12} aria-hidden="true" /><span>{isSample ? 'Sample/test data' : 'Document intelligence'}</span></div>
      <div className="ldw-page-header"><div><p className="ldw-eyebrow">BhuDrishti AI · document intelligence</p><h1>{title}</h1><p>{description}</p></div><div className="ldw-page-header-actions"><span className="ldw-live-tag"><span />{isSample ? 'Separated test data' : 'Source-backed workflow'}</span>{canAct ? <button type="button" className="ldw-button ldw-button--primary" onClick={() => document.getElementById('ldw-upload-browse')?.click()}><Upload size={15} aria-hidden="true" />Upload document</button> : null}</div></div>
      {!isSample ? <nav className="ldw-tabs" aria-label="Document workspace views">{views.filter(({ view }) => view !== 'processing' || canAct).map(({ view, label, path }) => <a key={view} href={`#/${path}${live.selectedId ? `?id=${encodeURIComponent(live.selectedId)}` : ''}`} className={initialView === view ? 'ldw-tab ldw-tab--active' : 'ldw-tab'} aria-current={initialView === view ? 'page' : undefined}>{label}</a>)}</nav> : null}
      <div className={isSample ? 'ldw-product-note ldw-product-note--sample' : 'ldw-product-note'} role="note"><ShieldCheck size={18} aria-hidden="true" /><p>{isSample ? <><strong>Sample/test dataset · read-only.</strong> These documents and results are separated from operational counts, review decisions, and GIS. <a href="#/documents">Open operational documents</a></> : <><strong>Results come from the uploaded source and persisted backend processing.</strong> Extraction evidence, validation, and quality score support human review.</>}</p></div>
      {live.movedToSampleId ? <div className="ldw-moved-to-sample" role="status"><FileText size={18} aria-hidden="true" /><p><strong>This document is in the sample/test dataset.</strong> Its source text identifies it as sample data, so it was removed from the operational workflow.</p><a href={`#/demo?id=${encodeURIComponent(live.movedToSampleId)}`}>Open sample document <ArrowRight size={14} aria-hidden="true" /></a></div> : null}

      <div className="ldw-intake-grid">
        {canAct ? <UploadZone items={live.uploadQueue} busy={live.uploadBusy} onUpload={(files) => void live.beginUploadBatch(files)} onRetry={(id) => void live.retryUploadQueueItem(id)} onCancel={live.cancelUploadQueueItem} onSelect={live.selectDocument} /> : <section className="ldw-upload-card ldw-read-only-card"><ShieldCheck size={21} /><h2>{isSample ? 'Sample mode is read-only' : 'Read-only document access'}</h2><p>{isSample ? 'Sample files can be inspected here. Upload, processing, and officer decisions belong to the operational workflow.' : 'Your account can inspect source records. Upload and processing require officer access.'}</p></section>}
        <section className="ldw-library-card" aria-labelledby="ldw-library-title"><div className="ldw-card-heading"><div><span className="ldw-eyebrow">{isSample ? 'Separated test data' : 'Persistent intake'}</span><h2 id="ldw-library-title">{isSample ? 'Sample documents' : 'Uploaded documents'}</h2></div><span className="ldw-card-aside">{live.documents.length} files</span></div>
          {live.listState === 'loading' ? <div className="ldw-list-state" role="status">Loading {isSample ? 'sample' : 'operational'} documents…</div> : null}
          {live.listState === 'error' ? <div className="ldw-list-state ldw-list-state--error" role="alert"><AlertCircle size={17} /><span>{live.listError}</span><button type="button" onClick={() => void live.loadList()}><RefreshCw size={14} />Retry</button></div> : null}
          {live.backgroundError ? <div className="ldw-list-state ldw-list-state--error" role="status"><AlertCircle size={17} /><span>{live.backgroundError}</span></div> : null}
          {live.listState === 'ready' && live.documents.length === 0 ? <div className="ldw-list-state"><FileText size={20} aria-hidden="true" /><span>{isSample ? 'No sample documents are available in this dataset.' : canAct ? 'No documents uploaded yet. Choose a PDF or image to store the source and begin processing.' : 'No documents available. A Revenue Officer or Administrator must upload and process a source before you can inspect its evidence.'}</span></div> : null}
          {live.documents.length > 0 ? <div className="ldw-document-list" aria-label={isSample ? 'Sample documents' : 'Uploaded documents'}>{live.documents.map((document) => <button key={document.id} type="button" className={live.selectedId === document.id ? 'ldw-document-item ldw-document-item--active' : 'ldw-document-item'} aria-pressed={live.selectedId === document.id} onClick={() => live.selectDocument(document.id)}><span className="ldw-document-icon"><FileText size={18} aria-hidden="true" /></span><span className="ldw-document-copy"><strong title={document.fileName}>{document.fileName}</strong><small>{isSample ? 'Sample/test data · ' : ''}{uploadSummary(document)}</small></span><span className={`ldw-list-status ldw-list-status--${statusTone(document)}`}><span className={`ldw-status-dot ldw-status-dot--${statusTone(document)}`} />{documentWorkflowLabel(document)}</span></button>)}</div> : null}
        </section>
      </div>

      {!live.selectedId && live.listState === 'ready' ? <div className="ldw-start-state"><div className="ldw-start-illustration"><FileCheck2 size={34} aria-hidden="true" /><Sparkles size={15} aria-hidden="true" /></div><h2>{isSample ? 'No sample selected' : canAct ? 'Start with a source document' : 'Awaiting source documents'}</h2><p>{isSample ? 'Choose a sample file from the test dataset to inspect its stored pages and processing results.' : canAct ? 'Upload a PDF or image to create a persistent record, preview its pages, and run extraction and validation.' : 'Your role can inspect available records. Source intake and processing belong to the Revenue Officer or Administrator.'}</p></div> : null}
      {live.detailLoading ? <div className="ldw-detail-state" role="status"><span className="ldw-loading-dot" />Loading document details…</div> : null}
      {live.detailError ? <div className="ldw-detail-state ldw-detail-state--error" role="alert"><AlertCircle size={22} aria-hidden="true" /><span>{live.detailError}</span><button type="button" className="ldw-button ldw-button--secondary" onClick={() => void live.refreshSelected()}><RefreshCw size={15} />Retry document</button></div> : null}

      {item ? <>
        <section className="ldw-document-header" aria-labelledby="ldw-current-title"><div className="ldw-document-heading"><span className="ldw-section-icon"><FileText size={20} aria-hidden="true" /></span><div><span className="ldw-eyebrow">Current source · {isSample || isQaWorkspace ? 'synthetic/test data' : 'operational upload'}</span><h2 id="ldw-current-title">{item.fileName}</h2><div className="ldw-document-meta"><span>{item.mimeType}</span><span>{formatBytes(item.fileSize)}</span><span>{item.pageCount} {item.pageCount === 1 ? 'page' : 'pages'}</span><span>{item.language || 'Language pending'}</span><span>Uploaded {formatDate(item.uploadedAt)}</span></div></div></div><div className="ldw-document-actions"><span className={`ldw-status-pill ldw-status-pill--${statusTone(item)}`}>{documentWorkflowLabel(item)}</span>{canAct && (item.status === 'uploaded' || item.status === 'failed') ? <button type="button" className="ldw-button ldw-button--primary" disabled={live.processingRequest} onClick={() => void live.beginProcess()}>{live.processingRequest ? 'Starting…' : item.status === 'failed' ? 'Retry processing' : 'Process document'} <ArrowRight size={15} aria-hidden="true" /></button> : null}</div></section>
        {live.processError ? <div className="ldw-process-error" role="alert"><AlertCircle size={17} aria-hidden="true" /><span>{live.processError}</span>{!isSample ? <button type="button" onClick={item.status === 'processing' ? live.retryPolling : item.status === 'completed' ? () => void live.refreshSelected() : () => void live.beginProcess()}><RefreshCw size={14} />Retry</button> : null}</div> : null}
        {live.incompleteResult ? <div className="ldw-process-error" role="alert"><AlertCircle size={17} aria-hidden="true" /><span>Processing finished, but the result details are still unavailable.</span><button type="button" onClick={() => void live.refreshSelected()}><RefreshCw size={14} />Refresh results</button></div> : null}
        {item.error && item.status === 'failed' ? <div className="ldw-process-error" role="alert"><AlertCircle size={17} aria-hidden="true" /><span>{item.error.message}</span></div> : null}
        <ProcessingPanel document={item} readOnly={!canAct} />
        {initialView === 'validation' ? <LiveValidationPanel document={item} prominent onReviewField={reviewField} onFieldSelect={inspectFinding} selectedField={selectedField} showReviewActions={!isSample} /> : null}
        <div className="ldw-workspace-grid"><Suspense fallback={<div className="ldw-viewer-card ldw-detail-state" role="status">Loading source viewer…</div>}><LiveDocumentViewer key={item.id} document={item} page={page} selectedField={selectedField} onPageChange={(next) => setPageChoices((current) => ({ ...current, [item.id]: next }))} onFieldSelect={selectField} dataset={dataset} /></Suspense><LiveExtractionPanel document={item} selectedField={selectedField} onFieldSelect={selectField} showValidationLink={!isSample} /></div>
        {initialView !== 'validation' ? <LiveValidationPanel document={item} onReviewField={reviewField} onFieldSelect={inspectFinding} selectedField={selectedField} showReviewActions={!isSample} /> : null}
        <div className="ldw-final-note"><div><strong>{isSample ? 'Sample evidence only' : 'Officer verification remains essential'}</strong><span>{isSample ? 'This document is in the separated test dataset and cannot enter the operational officer decision workflow.' : 'This workflow prepares evidence and review signals. It does not determine legal ownership.'}</span></div>{recordId ? <a href={`#/review/${encodeURIComponent(recordId)}`}>Open review workspace <ArrowRight size={15} aria-hidden="true" /></a> : null}</div>
      </> : null}
    </section>
  )
}
