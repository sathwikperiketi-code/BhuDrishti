import type { DatasetScope } from './types'

export function datasetPath(path: string, scope: DatasetScope): string {
  return `${path}${path.includes('?') ? '&' : '?'}dataset=${scope}`
}

export function belongsToDataset(value: { datasetScope?: string | null }, scope: DatasetScope): boolean {
  return value.datasetScope === scope
}
