import assert from 'node:assert/strict'
import test from 'node:test'
import { sourcedBoundaryCenter, sourcedLeafletRing } from '../src/features/phase4/geometry.ts'
import { gisHref, recordEvidenceHref, recordHref, reviewHref } from '../src/features/phase4/format.ts'

const sourced = {
  geometryStatus: 'sourced',
  geometrySource: 'officer_geojson',
  polygon: [[78.1, 17.2], [78.2, 17.2], [78.2, 17.3], [78.1, 17.2]],
}

test('GIS renders sourced GeoJSON in geographic latitude/longitude order', () => {
  assert.deepEqual(sourcedLeafletRing(sourced), [
    [17.2, 78.1], [17.2, 78.2], [17.3, 78.2], [17.2, 78.1],
  ])
})

test('GIS hides legacy, missing, and malformed geometries', () => {
  assert.equal(sourcedLeafletRing({ ...sourced, geometrySource: 'local_prototype' }), null)
  assert.equal(sourcedLeafletRing({ ...sourced, geometryStatus: 'unavailable' }), null)
  assert.equal(sourcedLeafletRing({ ...sourced, polygon: null }), null)
  assert.equal(sourcedLeafletRing({ ...sourced, polygon: sourced.polygon.slice(0, -1) }), null)
  assert.equal(sourcedLeafletRing({ ...sourced, polygon: [[181, 17.2], ...sourced.polygon.slice(1, -1), [181, 17.2]] }), null)
})

test('navigation markers derive only from validated sourced boundary coordinates', () => {
  const center = sourcedBoundaryCenter(sourced)
  assert.ok(Math.abs(center[0] - 17.25) < 1e-10)
  assert.ok(Math.abs(center[1] - 78.15) < 1e-10)
  assert.equal(sourcedBoundaryCenter({ ...sourced, geometryStatus: 'unavailable' }), null)
  assert.equal(sourcedBoundaryCenter({ ...sourced, polygon: null }), null)
  assert.equal(sourcedBoundaryCenter({ ...sourced, geometrySource: 'local_prototype' }), null)
  assert.equal(sourcedBoundaryCenter({ ...sourced, polygon: [[78, 17], [79, 17], [80, 17], [78, 17]] }), null)
})

test('GIS links preserve the exact record identity and evidence destination', () => {
  const recordId = 'record/with ? query'
  const encoded = encodeURIComponent(recordId)
  assert.equal(recordHref(recordId), `#/records/${encoded}`)
  assert.equal(gisHref(recordId), `#/gis?record=${encoded}`)
  assert.equal(reviewHref(recordId), `#/review/${encoded}`)
  assert.equal(recordEvidenceHref(recordId), `#/records/${encoded}?section=evidence`)
})
