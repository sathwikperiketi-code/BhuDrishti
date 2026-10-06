import { useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, FileUp, RefreshCw, UploadCloud, X } from 'lucide-react'
import { formatBytes } from './format'
import type { UploadQueueItem } from './useLiveDocuments'
import { MAX_UPLOAD_BYTES, validateUploadFile } from './uploadValidation'

type Props = {
  items: UploadQueueItem[]
  busy: boolean
  onUpload: (files: File[]) => void
  onRetry: (id: string) => void
  onCancel: (id: string) => void
  onSelect: (id: string) => void
}

const queueLabels: Record<UploadQueueItem['state'], string> = {
  queued: 'Queued for upload', uploading: 'Uploading', uploaded: 'Upload saved · starting processing',
  processing: 'Processing source', completed: 'Processing completed', failed: 'Failed · retry available',
  cancelled: 'Upload cancelled',
}

export function UploadZone({ items, busy, onUpload, onRetry, onCancel, onSelect }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [staged, setStaged] = useState<File[]>([])
  const [validationErrors, setValidationErrors] = useState<string[]>([])

  function stage(files: FileList | File[] | null) {
    if (!files) return
    const valid: File[] = []
    const errors: string[] = []
    for (const file of Array.from(files)) {
      const problem = validateUploadFile(file)
      if (problem) errors.push(`${file.name}: ${problem}`)
      else valid.push(file)
    }
    setValidationErrors(errors)
    if (valid.length > 0) setStaged((current) => [...current, ...valid])
  }

  function confirm() {
    if (staged.length === 0 || busy) return
    onUpload(staged)
    setStaged([])
    setValidationErrors([])
  }

  return (
    <section className="ldw-upload-card" aria-labelledby="ldw-upload-heading">
      <div className="ldw-upload-title"><div className="ldw-section-icon"><FileUp size={18} aria-hidden="true" /></div><div><span className="ldw-eyebrow">New intake</span><h2 id="ldw-upload-heading">Upload land records</h2></div></div>
      <div
        className={`ldw-dropzone ${dragging ? 'ldw-dropzone--active' : ''}`}
        onDragEnter={(event) => { event.preventDefault(); setDragging(true) }}
        onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
        onDragLeave={(event) => { event.preventDefault(); if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false) }}
        onDrop={(event) => { event.preventDefault(); setDragging(false); stage(event.dataTransfer.files) }}
      >
        <UploadCloud size={25} aria-hidden="true" />
        <div><strong>Drop land records here</strong><span>PDF, PNG, JPG, JPEG or TIFF · up to {formatBytes(MAX_UPLOAD_BYTES)} each</span></div>
        <button id="ldw-upload-browse" type="button" className="ldw-button ldw-button--secondary" onClick={() => inputRef.current?.click()}>Browse files</button>
        <input ref={inputRef} className="ldw-sr-only" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.tif,.tiff,application/pdf,image/jpeg,image/png,image/tiff" aria-label="Choose documents to upload" onChange={(event) => { stage(event.target.files); event.currentTarget.value = '' }} />
      </div>
      {validationErrors.length > 0 ? <div className="ldw-upload-errors" role="alert">{validationErrors.map((error, index) => <p key={`${index}-${error}`}><AlertCircle size={14} aria-hidden="true" />{error}</p>)}</div> : null}
      {staged.length > 0 ? <div className="ldw-staged" aria-label="Selected files awaiting confirmation">
        <div className="ldw-staged-heading"><strong>{staged.length} {staged.length === 1 ? 'document' : 'documents'} selected</strong><span>No file is uploaded until you confirm.</span></div>
        <ul>{staged.map((file, index) => <li key={`${file.name}-${index}`}><FileUp size={15} aria-hidden="true" /><span><strong>{file.name}</strong><small>{formatBytes(file.size)} · {file.name.split('.').pop()?.toUpperCase()}</small></span><button type="button" aria-label={`Remove ${file.name}`} onClick={() => setStaged((current) => current.filter((_, position) => position !== index))}><X size={15} aria-hidden="true" /></button></li>)}</ul>
        <button type="button" className="ldw-button ldw-button--primary" disabled={busy} onClick={confirm}>Upload {staged.length} {staged.length === 1 ? 'document' : 'documents'}</button>
      </div> : null}
      {busy ? <p className="ldw-upload-navigation-note" role="status">You can switch documents or workspace tabs during upload. Leaving this workspace cancels transfers still in progress; stored documents remain available.</p> : null}
      {items.length > 0 ? <div className="ldw-upload-queue" aria-label="Recent uploads"><strong className="ldw-queue-heading">Upload activity</strong><ul>{items.map((item) => <li key={item.id} className={`ldw-queue-item ldw-queue-item--${item.state}`}>
        <span className="ldw-queue-icon">{item.state === 'completed' ? <CheckCircle2 size={16} aria-hidden="true" /> : item.state === 'failed' ? <AlertCircle size={16} aria-hidden="true" /> : <FileUp size={16} aria-hidden="true" />}</span>
        <span className="ldw-queue-copy"><strong title={item.fileName}>{item.fileName}</strong><small role="status">{formatBytes(item.fileSize)} · {item.fileType} · {item.datasetScope === 'sample' ? 'Sample/test data · ' : ''}{queueLabels[item.state]}</small>{item.error ? <small className="ldw-queue-error">{item.error}</small> : null}</span>
        {item.state === 'uploading' ? <span className="ldw-queue-percent">{item.progress}%</span> : null}
        {item.documentId ? <button type="button" className="ldw-queue-action" onClick={() => { if (item.datasetScope === 'sample') window.location.hash = `#/demo?id=${encodeURIComponent(item.documentId!)}`; else onSelect(item.documentId!) }}>View{item.datasetScope === 'sample' ? ' sample' : ''}</button> : null}
        {item.state === 'queued' || item.state === 'uploading' ? <button type="button" className="ldw-queue-action" aria-label={`Cancel upload of ${item.fileName}`} onClick={() => onCancel(item.id)}><X size={13} aria-hidden="true" />Cancel</button> : null}
        {(item.state === 'failed' || item.state === 'cancelled') && item.datasetScope !== 'sample' ? <button type="button" className="ldw-queue-action" disabled={busy} onClick={() => onRetry(item.id)}><RefreshCw size={13} aria-hidden="true" />Retry</button> : null}
        {item.state === 'uploading' ? <div className="ldw-progress-track" role="progressbar" aria-label={`Upload progress for ${item.fileName}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={item.progress}><i style={{ transform: `scaleX(${item.progress / 100})` }} /></div> : null}
      </li>)}</ul></div> : null}
    </section>
  )
}
