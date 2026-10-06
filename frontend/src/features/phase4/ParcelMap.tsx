import { useReducedMotion } from 'framer-motion'
import L from 'leaflet'
import { useEffect, useRef, useState } from 'react'
import { recordEvidenceHref, recordHref, reviewHref, titleCase } from './format'
import { sourcedBoundaryCenter, sourcedLeafletRing } from './geometry'
import { isQaWorkspace } from '../../lib/workspace'
import type { GisParcel } from './types'
import 'leaflet/dist/leaflet.css'

const tileUrl = import.meta.env.VITE_MAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const tileAttribution = import.meta.env.VITE_MAP_ATTRIBUTION || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

function parcelColor(parcel: GisParcel): string {
  const status = parcel.status.toLowerCase()
  if (status.includes('reject') || status.includes('conflict')) return '#b85a52'
  if (status === 'verified') return '#2f8c65'
  return '#bd914d'
}

function recordPopup(parcel: GisParcel, role: string): HTMLDivElement {
  const popup = document.createElement('div')
  popup.className = 'p4-map-popup'
  const title = document.createElement('strong')
  title.textContent = `Survey ${parcel.surveyNumber || '—'}`
  const owner = document.createElement('span')
  owner.textContent = parcel.ownerName || 'Owner pending'
  const metadata = document.createElement('small')
  metadata.textContent = [parcel.village, titleCase(parcel.status)].filter(Boolean).join(' · ')
  const provenance = document.createElement('small')
  provenance.textContent = 'Marker at sourced boundary bounds center; not a surveyed point.'
  popup.append(title, owner, metadata, provenance)
  if (isQaWorkspace) {
    const notice = document.createElement('strong')
    notice.className = 'p4-map-qa-label'
    notice.textContent = 'Synthetic/test parcel · Not authoritative'
    popup.append(notice)
  }
  const links = document.createElement('div')
  links.className = 'p4-map-popup-links'
  for (const [label, href] of [
    ['View record', recordHref(parcel.recordId)],
    [role === 'AUDITOR' ? 'View review' : 'Review record', reviewHref(parcel.recordId)],
    ['View evidence', recordEvidenceHref(parcel.recordId)],
  ]) {
    const link = document.createElement('a')
    link.href = href
    link.textContent = label
    links.append(link)
  }
  popup.append(links)
  return popup
}

export function ParcelMap({ parcels, selectedId, focusId, onSelect, role }: { parcels: GisParcel[]; selectedId: string | null; focusId: string | null; onSelect: (id: string) => void; role: string }) {
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const boundaryGroup = useRef<L.FeatureGroup | null>(null)
  const markerGroup = useRef<L.FeatureGroup | null>(null)
  const tiles = useRef<L.TileLayer | null>(null)
  const polygons = useRef<Map<string, L.Polygon>>(new Map())
  const markers = useRef<Map<string, L.Marker>>(new Map())
  const [basemapState, setBasemapState] = useState<'loading' | 'ready' | 'error' | 'hidden'>('loading')
  const reduceMotion = useReducedMotion()
  const sourcedCount = parcels.filter((parcel) => sourcedLeafletRing(parcel) !== null).length

  useEffect(() => {
    if (!container.current || map.current) return
    const instance = L.map(container.current, {
      attributionControl: true, zoomControl: false, minZoom: 1, maxZoom: 19,
      scrollWheelZoom: false, keyboard: true,
      zoomAnimation: !reduceMotion, fadeAnimation: !reduceMotion,
      markerZoomAnimation: !reduceMotion, inertia: !reduceMotion,
    })
    instance.setView([0, 0], 2)
    L.control.zoom({ position: 'bottomright' }).addTo(instance)
    const basemap = L.tileLayer(tileUrl, { attribution: tileAttribution, maxZoom: 19 })
    basemap.on('loading', () => setBasemapState((previous) => previous === 'error' ? previous : 'loading'))
    basemap.on('load', () => setBasemapState((previous) => previous === 'error' ? previous : 'ready'))
    basemap.on('tileerror', () => setBasemapState('error'))
    basemap.addTo(instance)
    const geometryOnly = L.layerGroup()
    const boundaries = L.featureGroup().addTo(instance)
    const recordMarkers = L.featureGroup().addTo(instance)
    L.control.layers({ Basemap: basemap, 'Geometry only': geometryOnly }, {
      'Sourced boundaries': boundaries, 'Record markers': recordMarkers,
    }, { position: 'topright', collapsed: false }).addTo(instance)
    instance.on('baselayerchange', (event: L.LayersControlEvent) => setBasemapState(event.layer === basemap ? 'ready' : 'hidden'))
    instance.attributionControl.addAttribution('Parcel boundaries: identified officer sources')
    map.current = instance
    boundaryGroup.current = boundaries
    markerGroup.current = recordMarkers
    tiles.current = basemap
    const polygonIndex = polygons.current
    const markerIndex = markers.current
    const observer = new ResizeObserver(() => instance.invalidateSize({ pan: false }))
    observer.observe(container.current)
    return () => {
      observer.disconnect(); basemap.off(); instance.remove()
      map.current = null; boundaryGroup.current = null; markerGroup.current = null; tiles.current = null
      polygonIndex.clear(); markerIndex.clear()
    }
  }, [reduceMotion])

  useEffect(() => {
    const instance = map.current
    const boundaries = boundaryGroup.current
    const recordMarkers = markerGroup.current
    if (!instance || !boundaries || !recordMarkers) return
    boundaries.clearLayers(); recordMarkers.clearLayers(); polygons.current.clear(); markers.current.clear()
    for (const parcel of parcels) {
      const points = sourcedLeafletRing(parcel)
      const center = sourcedBoundaryCenter(parcel)
      if (!points || !center) continue
      const polygon = L.polygon(points, {
        color: parcelColor(parcel), weight: 2, fillColor: parcelColor(parcel), fillOpacity: 0.26,
        className: 'p4-map-polygon',
      })
      const label = document.createElement('span')
      label.textContent = `Survey ${parcel.surveyNumber || '—'}`
      polygon.bindTooltip(label, { sticky: true, direction: 'top' })
      polygon.on('click', () => onSelect(parcel.recordId))
      polygon.addTo(boundaries)
      polygons.current.set(parcel.recordId, polygon)
      const marker = L.marker(center, {
        title: `Survey ${parcel.surveyNumber || '—'} · sourced boundary center`,
        alt: `Select survey ${parcel.surveyNumber || parcel.recordId}`, keyboard: true,
        icon: L.divIcon({ className: 'p4-record-marker', html: '<span></span>', iconSize: [28, 28], iconAnchor: [14, 14] }),
      }).bindPopup(recordPopup(parcel, role), { className: 'p4-record-popup', maxWidth: 270 })
      marker.on('click', () => onSelect(parcel.recordId))
      marker.addTo(recordMarkers)
      markers.current.set(parcel.recordId, marker)
    }
    if (boundaries.getLayers().length) instance.fitBounds(boundaries.getBounds().pad(0.28), { animate: false, maxZoom: 17 })
    else instance.setView([0, 0], 2)
    const frame = requestAnimationFrame(() => instance.invalidateSize({ pan: false }))
    return () => cancelAnimationFrame(frame)
  }, [parcels, onSelect, role, reduceMotion])

  useEffect(() => {
    const instance = map.current
    for (const [id, polygon] of polygons.current) {
      const selected = id === selectedId
      polygon.setStyle({ weight: selected ? 3 : 2, fillOpacity: selected ? 0.43 : 0.26, opacity: selected ? 1 : 0.82 })
      if (selected) polygon.bringToFront()
      const marker = markers.current.get(id)
      marker?.getElement()?.classList.toggle('p4-record-marker--selected', selected)
      marker?.setZIndexOffset(selected ? 500 : 0)
      if (!selected) marker?.closePopup()
    }
    const selectedPolygon = selectedId ? polygons.current.get(selectedId) : null
    if (instance && selectedPolygon && focusId === selectedId) {
      instance.fitBounds(selectedPolygon.getBounds().pad(0.6), { animate: !reduceMotion, duration: 0.3, maxZoom: 17 })
      markers.current.get(selectedId!)?.openPopup()
    }
  }, [selectedId, focusId, parcels, reduceMotion])

  function fitParcels() {
    const bounds = boundaryGroup.current?.getBounds()
    if (bounds?.isValid()) map.current?.fitBounds(bounds.pad(0.28), { animate: !reduceMotion, duration: 0.3, maxZoom: 17 })
  }

  return <div className="p4-map-wrapper">
    <div className="p4-map" ref={container} role="region" aria-label={`Interactive map showing ${sourcedCount} sourced parcel ${sourcedCount === 1 ? 'boundary' : 'boundaries'}. Use arrow keys to pan and plus or minus to zoom.`} />
    <div className="p4-map-tools"><button type="button" onClick={fitParcels} disabled={!sourcedCount}>Fit all parcels</button></div>
    {basemapState === 'loading' ? <span className="p4-map-status" role="status">Loading basemap…</span> : null}
    {basemapState === 'error' ? <div className="p4-map-status p4-map-status--error" role="alert"><span>Basemap unavailable. Sourced geometry remains usable.</span><button type="button" onClick={() => { setBasemapState('loading'); tiles.current?.redraw() }}>Retry basemap</button></div> : null}
    {sourcedCount === 0 ? <div className="p4-map-unavailable" role="status"><strong>Parcel geometry unavailable</strong><span>No sourced boundaries match this view. Select a record to inspect its status or import an identified GeoJSON source after approval.</span></div> : null}
  </div>
}
