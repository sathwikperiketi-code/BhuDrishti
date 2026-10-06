import { useCallback, useEffect, useRef, useState } from 'react'
import { getDocument, getProcessingStatus, listDocuments, processDocument, uploadDocument } from './api'
import { applyTerminalDocument, readProcessingSnapshot } from './polling'
import { sampleDocumentAfterOperational404 } from './samplePromotion'
import type { DatasetScope, DocumentDetail, DocumentSummary } from './types'

export type UploadQueueState = 'queued' | 'uploading' | 'uploaded' | 'processing' | 'completed' | 'failed' | 'cancelled'
export interface UploadQueueItem {
  id: string
  fileName: string
  fileSize: number
  fileType: string
  file: File | null
  state: UploadQueueState
  progress: number
  documentId: string | null
  datasetScope?: DatasetScope
  error: string | null
}

function errorMessage(error: unknown) { return error instanceof Error ? error.message : 'An unexpected document error occurred.' }

function idFromHash() { return new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('id') }

export function useLiveDocuments(token: string, dataset: DatasetScope = 'operational') {
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [listState, setListState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [listError, setListError] = useState<string | null>(null)
  const [backgroundError, setBackgroundError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(idFromHash)
  const [detailResult, setDetailResult] = useState<{ id: string; data?: DocumentDetail; error?: string } | null>(null)
  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([])
  const [uploadBusy, setUploadBusy] = useState(false)
  const [processError, setProcessError] = useState<string | null>(null)
  const [processingRequest, setProcessingRequest] = useState(false)
  const [pollRevision, setPollRevision] = useState(0)
  const [backgroundRevision, setBackgroundRevision] = useState(0)
  const [pollPaused, setPollPaused] = useState(false)
  const [resultRefreshCount, setResultRefreshCount] = useState(0)
  const [movedToSampleId, setMovedToSampleId] = useState<string | null>(null)
  const xhrRef = useRef<XMLHttpRequest | null>(null)
  const uploadingId = useRef<string | null>(null)
  const cancelledUploads = useRef(new Set<string>())
  const activeUpload = useRef(false)
  const disposed = useRef(false)
  const selectedIdRef = useRef(selectedId)
  const uploadQueueRef = useRef(uploadQueue)

  useEffect(() => { selectedIdRef.current = selectedId }, [selectedId])
  useEffect(() => { uploadQueueRef.current = uploadQueue }, [uploadQueue])

  const updateQueueItem = useCallback((id: string, patch: Partial<UploadQueueItem>) => {
    setUploadQueue((current) => current.map((item) => item.id === id ? { ...item, ...patch } : item))
  }, [])

  const isSamplePromotion = useCallback((id: string, error: unknown) =>
    dataset === 'operational'
      ? sampleDocumentAfterOperational404(id, error, (candidate) => getDocument(candidate, undefined, 'sample'))
      : Promise.resolve(false), [dataset])

  const markMovedToSample = useCallback((id: string) => {
    setMovedToSampleId(id)
    setDocuments((current) => current.filter((item) => item.id !== id))
    setDetailResult({ id })
    setPollPaused(true)
    setProcessError(null)
  }, [])

  const loadList = useCallback(async (signal?: AbortSignal) => {
    try {
      const items = await listDocuments(signal, dataset)
      setDocuments(items)
      setListState('ready')
      setListError(null)
      setBackgroundError(null)
      setSelectedId((current) => current ?? items[0]?.id ?? null)
    } catch (error) {
      if (signal?.aborted) return
      setListState('error')
      setListError(errorMessage(error))
    }
  }, [dataset])

  useEffect(() => {
    const controller = new AbortController()
    void listDocuments(controller.signal, dataset).then(
      (items) => {
        setDocuments(items)
        setListState('ready')
        setListError(null)
        setBackgroundError(null)
        setSelectedId((current) => current ?? items[0]?.id ?? null)
      },
      (error: unknown) => {
        if (controller.signal.aborted) return
        setListState('error')
        setListError(errorMessage(error))
      },
    )
    return () => controller.abort()
  }, [token, dataset])

  useEffect(() => {
    const syncFromHash = () => {
      const id = idFromHash()
      if (!id || id === selectedId) return
      setSelectedId(id)
      setResultRefreshCount(0)
      setPollPaused(false)
      setProcessError(null)
      setMovedToSampleId(null)
    }
    window.addEventListener('hashchange', syncFromHash)
    return () => window.removeEventListener('hashchange', syncFromHash)
  }, [selectedId])

  useEffect(() => {
    if (!selectedId) return
    const controller = new AbortController()
    void getDocument(selectedId, controller.signal, dataset).then(
      (data) => setDetailResult({ id: selectedId, data }),
      (error: unknown) => {
        void isSamplePromotion(selectedId, error).then((moved) => {
          if (controller.signal.aborted) return
          if (moved) markMovedToSample(selectedId)
          else setDetailResult({ id: selectedId, error: errorMessage(error) })
        })
      },
    )
    return () => controller.abort()
  }, [selectedId, token, dataset, isSamplePromotion, markMovedToSample])

  useEffect(() => {
    disposed.current = false
    return () => { disposed.current = true; xhrRef.current?.abort() }
  }, [])

  // The document list is the source of truth for jobs running outside the selected pane.
  // Poll only while a persisted job is active; selection changes never stop another job.
  const backgroundJobs = documents.some((item) => item.status === 'processing') || uploadQueue.some((item) => item.state === 'processing')
  useEffect(() => {
    if (!backgroundJobs) return
    let active = true
    const timer = window.setTimeout(async () => {
      try {
        const items = await listDocuments(undefined, dataset)
        const sampleResults = dataset === 'operational' ? await Promise.all(uploadQueueRef.current
          .filter((entry) => entry.state === 'processing' && entry.documentId && !items.some((item) => item.id === entry.documentId))
          .map(async (entry) => {
            try { return await getDocument(entry.documentId!, undefined, 'sample') }
            catch { return null }
          })) : []
        if (!active) return
        setDocuments(items)
        setBackgroundError(null)
        setUploadQueue((current) => current.map((entry) => {
          if (!entry.documentId) return entry
          const persisted = items.find((item) => item.id === entry.documentId) ?? sampleResults.find((item) => item?.id === entry.documentId)
          if (!persisted) return entry
          const state: UploadQueueState = persisted.status === 'completed' ? 'completed' : persisted.status === 'failed' ? 'failed' : persisted.status === 'processing' ? 'processing' : 'uploaded'
          return entry.state === state && entry.datasetScope === persisted.datasetScope ? entry : { ...entry, state, datasetScope: persisted.datasetScope, error: state === 'failed' ? 'Processing failed. Open this document for details or retry.' : null }
        }))
        const selected = items.find((item) => item.id === selectedIdRef.current)
        if (selected?.status === 'processing') {
          setDetailResult((current) => current?.id === selected.id && current.data && current.data.status === 'uploaded'
            ? { id: selected.id, data: { ...current.data, status: selected.status, stage: selected.stage } }
            : current)
        }
      } catch (error) {
        if (active) setBackgroundError(`Status refresh delayed: ${errorMessage(error)} Retrying automatically.`)
      }
      if (active) setBackgroundRevision((value) => value + 1)
    }, 1800)
    return () => { active = false; window.clearTimeout(timer) }
  }, [backgroundJobs, backgroundRevision, dataset, token])

  const selectedWasMoved = movedToSampleId === selectedId ? movedToSampleId : null
  const document = !selectedWasMoved && detailResult?.id === selectedId ? detailResult.data ?? null : null
  const detailError = !selectedWasMoved && detailResult?.id === selectedId ? detailResult.error ?? null : null
  const detailLoading = Boolean(selectedId && detailResult?.id !== selectedId)

  useEffect(() => {
    if (!selectedId || document?.status !== 'processing' || pollPaused) return
    let active = true
    const timer = window.setTimeout(async () => {
      try {
        const snapshot = await readProcessingSnapshot(selectedId,
          (id) => getProcessingStatus(id, undefined, dataset),
          (id) => getDocument(id, undefined, dataset), document.updatedAt)
        if (!active) return
        if (snapshot.kind === 'terminal') {
          const updated = snapshot.document
          setDetailResult({ id: selectedId, data: updated })
          setDocuments((current) => applyTerminalDocument(current, updated))
        } else {
          const result = snapshot.status
          setDetailResult((current) => current?.id === selectedId && current.data
            ? { id: selectedId, data: snapshot.document ?? { ...current.data, updatedAt: result.updatedAt, status: result.status, stage: result.stage, stages: result.stages, error: result.error } }
            : current)
          setPollRevision((value) => value + 1)
        }
      } catch (error) {
        if (!active) return
        const moved = await isSamplePromotion(selectedId, error)
        if (!active) return
        if (moved) markMovedToSample(selectedId)
        else {
          setProcessError(`Status update failed: ${errorMessage(error)}`)
          setPollPaused(true)
        }
      }
    }, 850)
    return () => { active = false; window.clearTimeout(timer) }
  }, [selectedId, document?.status, document?.updatedAt, pollRevision, pollPaused, token, dataset, isSamplePromotion, markMovedToSample])

  useEffect(() => {
    if (!selectedId || document?.status !== 'completed' || (document.validation && document.fields.length > 0) || resultRefreshCount >= 5) return
    let active = true
    const timer = window.setTimeout(async () => {
      try {
        const updated = await getDocument(selectedId, undefined, dataset)
        if (active) setDetailResult({ id: selectedId, data: updated })
      } catch (error) {
        if (!active) return
        const moved = await isSamplePromotion(selectedId, error)
        if (!active) return
        if (moved) markMovedToSample(selectedId)
        else setProcessError(`Results could not be refreshed: ${errorMessage(error)}`)
      } finally { if (active) setResultRefreshCount((count) => count + 1) }
    }, 900)
    return () => { active = false; window.clearTimeout(timer) }
  }, [selectedId, document?.status, document?.validation, document?.fields.length, resultRefreshCount, token, dataset, isSamplePromotion, markMovedToSample])

  const selectDocument = useCallback((id: string) => {
    selectedIdRef.current = id
    setSelectedId(id)
    setProcessError(null)
    setPollPaused(false)
    setResultRefreshCount(0)
    setMovedToSampleId(null)
    const [route] = window.location.hash.split('?')
    window.history.replaceState(null, '', `${route}?id=${encodeURIComponent(id)}`)
  }, [])

  const refreshSelected = useCallback(async () => {
    if (!selectedId) return
    setResultRefreshCount(0)
    try {
      const updated = await getDocument(selectedId, undefined, dataset)
      setDetailResult({ id: selectedId, data: updated })
      setDocuments((current) => applyTerminalDocument(current, updated))
    }
    catch (error) {
      if (await isSamplePromotion(selectedId, error)) markMovedToSample(selectedId)
      else setDetailResult({ id: selectedId, error: errorMessage(error) })
    }
  }, [selectedId, dataset, isSamplePromotion, markMovedToSample])

  const beginUploadBatch = useCallback(async (files: File[]) => {
    if (dataset === 'sample' || files.length === 0 || activeUpload.current) return false
    activeUpload.current = true
    setUploadBusy(true)
    const entries: UploadQueueItem[] = files.map((file) => ({
      id: crypto.randomUUID(), fileName: file.name, fileSize: file.size,
      fileType: file.name.split('.').pop()?.toUpperCase() || 'Document',
      file, state: 'queued', progress: 0, documentId: null, error: null,
    }))
    setUploadQueue((current) => [...entries, ...current])
    try {
      for (const entry of entries) {
        if (disposed.current) break
        if (cancelledUploads.current.has(entry.id)) continue
        uploadingId.current = entry.id
        updateQueueItem(entry.id, { state: 'uploading' })
        let uploaded: DocumentDetail
        try {
          uploaded = await uploadDocument(entry.file!, (progress) => updateQueueItem(entry.id, { progress }), (xhr) => { xhrRef.current = xhr })
        } catch (error) {
          if (!disposed.current) updateQueueItem(entry.id, error instanceof DOMException && error.name === 'AbortError'
            ? { state: 'cancelled', error: 'Upload cancelled. A file already accepted by the server may remain in Uploaded documents.' }
            : { state: 'failed', error: errorMessage(error) })
          continue
        } finally { xhrRef.current = null; uploadingId.current = null }
        if (disposed.current) break
        updateQueueItem(entry.id, { state: 'uploaded', progress: 100, documentId: uploaded.id, file: null })
        setDocuments((current) => [uploaded, ...current.filter((item) => item.id !== uploaded.id)])
        if (!selectedIdRef.current) {
          setDetailResult({ id: uploaded.id, data: uploaded })
          selectDocument(uploaded.id)
        }
        try {
          const result = await processDocument(uploaded.id)
          updateQueueItem(entry.id, {
            state: result.status === 'failed' ? 'failed' : result.status === 'completed' ? 'completed' : 'processing',
            error: result.error?.message ?? null,
          })
          setDocuments((current) => current.map((item) => item.id === uploaded.id ? { ...item, status: result.status, stage: result.stage } : item))
          setDetailResult((current) => current?.id === uploaded.id && current.data
            ? { id: uploaded.id, data: { ...current.data, status: result.status, stage: result.stage, stages: result.stages, error: result.error } }
            : current)
        } catch (error) {
          updateQueueItem(entry.id, { state: 'failed', error: `Processing could not start: ${errorMessage(error)}` })
        }
      }
      return true
    } finally {
      activeUpload.current = false
      setUploadBusy(false)
    }
  }, [selectDocument, dataset, updateQueueItem])

  const cancelUploadQueueItem = useCallback((id: string) => {
    const entry = uploadQueue.find((item) => item.id === id)
    if (!entry || (entry.state !== 'queued' && entry.state !== 'uploading')) return
    cancelledUploads.current.add(id)
    updateQueueItem(id, { state: 'cancelled', error: null })
    if (uploadingId.current === id) {
      xhrRef.current?.abort()
      // Aborting a transfer cannot retract a source already accepted by the API.
      void loadList()
    }
  }, [uploadQueue, updateQueueItem, loadList])

  const retryUploadQueueItem = useCallback(async (id: string) => {
    const entry = uploadQueue.find((item) => item.id === id)
    if (!entry || (entry.state !== 'failed' && entry.state !== 'cancelled') || activeUpload.current) return
    if (!entry.documentId && entry.file) {
      setUploadQueue((current) => current.filter((item) => item.id !== id))
      await beginUploadBatch([entry.file])
      return
    }
    if (!entry.documentId) return
    updateQueueItem(id, { state: 'uploaded', error: null })
    try {
      const result = await processDocument(entry.documentId)
      updateQueueItem(id, { state: result.status === 'failed' ? 'failed' : result.status === 'completed' ? 'completed' : 'processing', error: result.error?.message ?? null })
      setDocuments((current) => current.map((item) => item.id === entry.documentId ? { ...item, status: result.status, stage: result.stage } : item))
      if (selectedIdRef.current === entry.documentId) {
        const updated = await getDocument(entry.documentId, undefined, dataset)
        setDetailResult({ id: entry.documentId, data: updated })
        setPollPaused(false)
        setPollRevision((value) => value + 1)
      }
    } catch (error) {
      updateQueueItem(id, { state: 'failed', error: errorMessage(error) })
    }
  }, [uploadQueue, beginUploadBatch, updateQueueItem, dataset])

  const beginProcess = useCallback(async () => {
    if (dataset === 'sample' || !selectedId || processingRequest) return
    setProcessingRequest(true)
    setProcessError(null)
    setPollPaused(false)
    setResultRefreshCount(0)
    try {
      const result = await processDocument(selectedId)
      setDetailResult((current) => current?.id === selectedId && current.data
        ? { id: selectedId, data: { ...current.data, status: result.status, stage: result.stage, stages: result.stages, error: result.error } }
        : current)
      setDocuments((current) => current.map((item) => item.id === selectedId ? { ...item, status: result.status, stage: result.stage } : item))
      setPollRevision((value) => value + 1)
      if (result.status === 'completed' || result.status === 'failed') await refreshSelected()
    } catch (error) {
      if (await isSamplePromotion(selectedId, error)) markMovedToSample(selectedId)
      else setProcessError(errorMessage(error))
    }
    finally { setProcessingRequest(false) }
  }, [selectedId, processingRequest, refreshSelected, dataset, isSamplePromotion, markMovedToSample])

  const retryPolling = useCallback(() => {
    setPollPaused(false)
    setProcessError(null)
    setPollRevision((value) => value + 1)
  }, [])

  return {
    documents, listState, listError, backgroundError, loadList, selectedId, selectDocument, document, detailError, detailLoading, movedToSampleId: selectedWasMoved,
    refreshSelected, uploadQueue, uploadBusy, beginUploadBatch, retryUploadQueueItem, cancelUploadQueueItem, beginProcess,
    processError, processingRequest, retryPolling,
    incompleteResult: Boolean(document?.status === 'completed' && (!document.validation || document.fields.length === 0) && resultRefreshCount >= 5),
  }
}
