import type { GisParcel } from './types'

type ParcelGeometry = Pick<GisParcel, 'geometryStatus' | 'geometrySource' | 'polygon'>

/** Convert a sourced GeoJSON exterior ring to Leaflet's [latitude, longitude] order. */
export function sourcedLeafletRing(parcel: ParcelGeometry): [number, number][] | null {
  if (parcel.geometryStatus !== 'sourced' || parcel.geometrySource !== 'officer_geojson') return null
  const ring = parcel.polygon
  if (!Array.isArray(ring) || ring.length < 4) return null
  const points: [number, number][] = []
  const unique = new Set<string>()
  for (const point of ring) {
    if (!Array.isArray(point) || point.length !== 2) return null
    const [longitude, latitude] = point
    if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180 || !Number.isFinite(latitude) || latitude < -90 || latitude > 90) return null
    points.push([latitude, longitude])
    unique.add(`${longitude}:${latitude}`)
  }
  const first = ring[0]
  const last = ring[ring.length - 1]
  if (first[0] !== last[0] || first[1] !== last[1] || unique.size < 3) return null
  const twiceArea = ring.slice(0, -1).reduce((area, [x, y], index) => {
    const [nextX, nextY] = ring[index + 1]
    return area + x * nextY - nextX * y
  }, 0)
  if (Math.abs(twiceArea) < 1e-12) return null
  return points
}

/** A navigation marker derived from the sourced boundary bounds, not a surveyed point. */
export function sourcedBoundaryCenter(parcel: ParcelGeometry): [number, number] | null {
  const ring = sourcedLeafletRing(parcel)
  if (!ring) return null
  const latitudes = ring.map(([latitude]) => latitude)
  const longitudes = ring.map(([, longitude]) => longitude)
  return [(Math.min(...latitudes) + Math.max(...latitudes)) / 2, (Math.min(...longitudes) + Math.max(...longitudes)) / 2]
}
