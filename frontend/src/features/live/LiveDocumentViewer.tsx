import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Expand, Files, Focus, ImageOff, Minimize2, RotateCw, ZoomIn, ZoomOut } from 'lucide-react'
import { getPageImage } from './api'
import { fieldLabel } from './format'
import { isNormalizedBox } from './evidence'
import type { DatasetScope, DocumentDetail } from './types'

type Props = {
  document: DocumentDetail
  page: number
  selectedField: string | null
  onPageChange: (page: number) => void
  onFieldSelect: (field: string) => void
  dataset?: DatasetScope
}

function clamp(value: number, min: number, max: number) { return Math.min(max, Math.max(min, value)) }

export function LiveDocumentViewer({ document: item, page, selectedField, onPageChange, onFieldSelect, dataset = 'operational' }: Props) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const fullscreenRef = useRef<HTMLElement>(null)
  const focusedBoxRef = useRef<HTMLButtonElement>(null)
  const [viewportSize, setViewportSize] = useState({ width: 680, height: 650 })
  const [fitMode, setFitMode] = useState<'page' | 'width'>('width')
  const [zoom, setZoom] = useState(1)
  const [rotation, setRotation] = useState(0)
  const [showThumbnails, setShowThumbnails] = useState(() => window.innerWidth >= 640)
  const [fullscreen, setFullscreen] = useState(false)
  const [imageRevision, setImageRevision] = useState(0)
  const [imageState, setImageState] = useState<{ src: string; status: 'loaded' | 'error'; width?: number; height?: number } | null>(null)
  const pageCount = Math.max(item.pageCount, item.pages.length)
  const pageData = item.pages.find((entry) => entry.pageNumber === page)
  const neededPagesKey = (showThumbnails ? item.pages.map((entry) => entry.pageNumber) : pageData ? [page] : []).join(',')
  const imageRequestKey = `${dataset}:${item.id}:${neededPagesKey}:${imageRevision}`
  const [pageImages, setPageImages] = useState<{ key: string; urls: Record<number, string>; errors: Record<number, string> }>({ key: '', urls: {}, errors: {} })
  const imageSource = pageImages.key === imageRequestKey ? pageImages.urls[page] : undefined
  const loaded = Boolean(imageSource && imageState?.src === imageSource && imageState?.status === 'loaded')
  const imageError = Boolean(imageSource && imageState?.src === imageSource && imageState?.status === 'error') || (pageImages.key === imageRequestKey && Boolean(pageImages.errors[page]))
  const sourceWidth = pageData?.width || (loaded ? imageState?.width : undefined) || 900
  const sourceHeight = pageData?.height || (loaded ? imageState?.height : undefined) || 1270
  const aspect = sourceWidth / sourceHeight
  const availableWidth = Math.max(220, viewportSize.width - 64)
  const availableHeight = Math.max(260, viewportSize.height - 64)
  const fitWidth = rotation % 180 === 0 ? availableWidth : availableHeight * aspect
  const fitPage = rotation % 180 === 0 ? Math.min(availableWidth, availableHeight * aspect) : Math.min(availableHeight * aspect, availableWidth)
  const imageWidth = Math.round(clamp((fitMode === 'width' ? fitWidth : fitPage) * zoom, 180, 2200))
  const imageHeight = Math.round(imageWidth / aspect)
  const outerWidth = rotation % 180 === 0 ? imageWidth : imageHeight
  const outerHeight = rotation % 180 === 0 ? imageHeight : imageWidth
  const activeField = item.fields.find((field) => field.field === selectedField)
  const isOcrActive = item.status === 'processing' && item.stage === 'ocr'
  const ocrRegions = item.ocrPages.find((entry) => entry.pageNumber === page)?.regions.filter((region) => isNormalizedBox(region.bbox)) ?? []

  useEffect(() => {
    const controller = new AbortController()
    const objectUrls: string[] = []
    for (const pageNumber of neededPagesKey.split(',').filter(Boolean).map(Number)) {
      void getPageImage(item.id, pageNumber, controller.signal, dataset).then((blob) => {
        if (controller.signal.aborted) return
        const url = URL.createObjectURL(blob)
        objectUrls.push(url)
        setPageImages((previous) => ({
          key: imageRequestKey,
          urls: { ...(previous.key === imageRequestKey ? previous.urls : {}), [pageNumber]: url },
          errors: previous.key === imageRequestKey ? previous.errors : {},
        }))
      }).catch((error: unknown) => {
        if (controller.signal.aborted || error instanceof DOMException && error.name === 'AbortError') return
        setPageImages((previous) => ({
          key: imageRequestKey,
          urls: previous.key === imageRequestKey ? previous.urls : {},
          errors: { ...(previous.key === imageRequestKey ? previous.errors : {}), [pageNumber]: error instanceof Error ? error.message : 'The source page could not be loaded.' },
        }))
      })
    }
    return () => { controller.abort(); objectUrls.forEach((url) => URL.revokeObjectURL(url)) }
  }, [item.id, neededPagesKey, imageRequestKey, dataset])

  useEffect(() => {
    const node = viewportRef.current
    if (!node) return
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setViewportSize({ width: entry.contentRect.width, height: entry.contentRect.height })
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === fullscreenRef.current)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  useEffect(() => {
    if (!selectedField || !activeField?.source?.bbox) return
    const frame = window.requestAnimationFrame(() => setZoom((value) => Math.max(value, 1.3)))
    return () => window.cancelAnimationFrame(frame)
  }, [selectedField, activeField?.source?.bbox])

  useEffect(() => {
    if (!activeField?.source?.bbox || activeField.source.page !== page || !loaded || !focusedBoxRef.current || !viewportRef.current) return
    const frame = window.requestAnimationFrame(() => {
      const box = focusedBoxRef.current?.getBoundingClientRect()
      const view = viewportRef.current?.getBoundingClientRect()
      if (!box || !view || !viewportRef.current) return
      viewportRef.current.scrollTo({
        left: viewportRef.current.scrollLeft + box.left + box.width / 2 - view.left - view.width / 2,
        top: viewportRef.current.scrollTop + box.top + box.height / 2 - view.top - view.height / 2,
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
      })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [activeField?.field, activeField?.source?.bbox, activeField?.source?.page, page, loaded, imageWidth, rotation])

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen()
      else await fullscreenRef.current?.requestFullscreen()
    } catch { /* Browser or embedded preview may disallow fullscreen. */ }
  }

  return (
    <section ref={fullscreenRef} className="ldw-viewer-card" aria-labelledby="ldw-viewer-title">
      <header className="ldw-card-heading ldw-viewer-heading"><div><span className="ldw-eyebrow">Original source</span><h2 id="ldw-viewer-title">Document viewer</h2></div><span className="ldw-card-aside">{pageCount} {pageCount === 1 ? 'page' : 'pages'}</span></header>
      <div className="ldw-viewer-toolbar" role="toolbar" aria-label="Document viewer controls">
        <button type="button" aria-label="Toggle page thumbnails" aria-pressed={showThumbnails} onClick={() => setShowThumbnails((value) => !value)}><Files size={16} /></button>
        <span className="ldw-toolbar-divider" />
        <button type="button" aria-label="Previous page" disabled={page <= 1} onClick={() => onPageChange(page - 1)}><ChevronLeft size={16} /></button>
        <span className="ldw-toolbar-value">{pageCount ? `${page} / ${pageCount}` : '0 / 0'}</span>
        <button type="button" aria-label="Next page" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)}><ChevronRight size={16} /></button>
        <span className="ldw-toolbar-divider" />
        <button type="button" aria-label="Zoom out" disabled={zoom <= 0.5} onClick={() => setZoom((value) => clamp(value - 0.2, 0.5, 2.5))}><ZoomOut size={16} /></button>
        <span className="ldw-toolbar-value">{Math.round(zoom * 100)}%</span>
        <button type="button" aria-label="Zoom in" disabled={zoom >= 2.5} onClick={() => setZoom((value) => clamp(value + 0.2, 0.5, 2.5))}><ZoomIn size={16} /></button>
        <button type="button" className="ldw-toolbar-text" aria-pressed={fitMode === 'width'} onClick={() => { setFitMode('width'); setZoom(1) }}>Fit width</button>
        <button type="button" className="ldw-toolbar-text" aria-pressed={fitMode === 'page'} onClick={() => { setFitMode('page'); setZoom(1) }}><Focus size={14} />Fit page</button>
        <span className="ldw-toolbar-divider" />
        <button type="button" aria-label="Rotate clockwise" onClick={() => setRotation((value) => (value + 90) % 360)}><RotateCw size={16} /></button>
        <button type="button" aria-label={fullscreen ? 'Exit fullscreen' : 'Enter fullscreen'} onClick={() => void toggleFullscreen()}>{fullscreen ? <Minimize2 size={16} /> : <Expand size={16} />}</button>
      </div>
      {isOcrActive ? <div className="ldw-ocr-status" role="status"><span className="ldw-current-pulse" aria-hidden="true" /><span>Extracting text from document · page regions appear when returned by the backend</span></div> : null}
      <div className="ldw-viewer-body">
        {showThumbnails && pageCount > 0 ? <div className="ldw-thumbnails" aria-label="Page thumbnails">{Array.from({ length: pageCount }, (_, index) => index + 1).map((number) => {
          const exists = item.pages.some((entry) => entry.pageNumber === number)
          const thumbnailSource = pageImages.key === imageRequestKey ? pageImages.urls[number] : undefined
          return <button key={number} type="button" className={number === page ? 'ldw-thumbnail ldw-thumbnail--active' : 'ldw-thumbnail'} aria-label={`Page ${number}`} aria-current={number === page ? 'page' : undefined} onClick={() => onPageChange(number)}>{exists && thumbnailSource ? <img src={thumbnailSource} alt="" loading="lazy" /> : <span className="ldw-thumbnail-placeholder">{number}</span>}<span>{String(number).padStart(2, '0')}</span></button>
        })}</div> : null}
        <div ref={viewportRef} className="ldw-viewer-viewport">
          {!pageData ? <div className="ldw-viewer-empty"><ImageOff size={28} aria-hidden="true" /><strong>Preview is not available yet</strong><span>{item.status === 'uploaded' ? 'Start processing to prepare the original page images.' : item.status === 'processing' ? 'The backend is preparing the page image.' : 'No page image was returned for this item.'}</span></div> : null}
          {pageData ? <div className="ldw-page-space" style={{ minWidth: outerWidth + 48, minHeight: outerHeight + 48 }}>
            <div className="ldw-page-frame" style={{ width: outerWidth, height: outerHeight }}>
              <div className="ldw-page-layer" style={{ width: imageWidth, height: imageHeight, transform: `translate(-50%, -50%) rotate(${rotation}deg)` }}>
                <img src={imageSource} alt={`Original document page ${page}`} draggable={false} onLoad={(event) => { if (imageSource) setImageState({ src: imageSource, status: 'loaded', width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight }) }} onError={() => { if (imageSource) setImageState({ src: imageSource, status: 'error' }) }} />
                {ocrRegions.map((region, index) => <span key={`${index}-${region.bbox.join(',')}`} className="ldw-ocr-region" aria-hidden="true" style={{ left: `${region.bbox[0] * 100}%`, top: `${region.bbox[1] * 100}%`, width: `${region.bbox[2] * 100}%`, height: `${region.bbox[3] * 100}%` }} />)}
                {item.fields.filter((field) => field.source?.page === page && field.source.bbox).map((field) => {
                  const box = field.source!.bbox!
                  if (!isNormalizedBox(box)) return null
                  const [x, y, width, height] = box
                  const selected = selectedField === field.field
                  return <button key={field.field} ref={selected ? focusedBoxRef : undefined} type="button" className={selected ? 'ldw-evidence-box ldw-evidence-box--selected' : 'ldw-evidence-box'} style={{ left: `${x * 100}%`, top: `${y * 100}%`, width: `${width * 100}%`, height: `${height * 100}%` }} aria-label={`${fieldLabel(field.field)} source evidence, ${field.confidence == null ? 'confidence unmeasured' : `${Math.round(field.confidence * 100)} percent extraction confidence`}`} aria-pressed={selected} title={fieldLabel(field.field)} onClick={() => onFieldSelect(field.field)}>{selected ? <span>{fieldLabel(field.field)}</span> : null}</button>
                })}
                {isOcrActive && loaded ? <div className="ldw-scanline" aria-hidden="true"><span /></div> : null}
              </div>
            </div>
          </div> : null}
          {pageData && !loaded && !imageError ? <div className="ldw-image-state" role="status">Loading source page…</div> : null}
          {imageError ? <div className="ldw-image-state ldw-image-state--error" role="alert"><span>{pageImages.errors[page] || 'The source page image could not be displayed.'}</span><button type="button" className="ldw-button ldw-button--secondary" onClick={() => setImageRevision((value) => value + 1)}>Retry source page</button></div> : null}
        </div>
      </div>
      <footer className="ldw-viewer-footer">{activeField && isNormalizedBox(activeField.source?.bbox) ? `Highlighted: ${fieldLabel(activeField.field)} · page ${activeField.source?.page}` : activeField?.source?.text ? `Text evidence available for ${fieldLabel(activeField.field)} · no source coordinates supplied.` : 'Select an extracted field to locate its source evidence.'}{ocrRegions.length > 0 ? ` ${ocrRegions.length} source text regions returned on this page.` : null}</footer>
    </section>
  )
}
