import type { DocumentDetail, DocumentSummary, ProcessingStatusResponse } from './types'

export type ProcessingSnapshot =
  | { kind: 'progress'; status: ProcessingStatusResponse; document?: DocumentDetail }
  | { kind: 'terminal'; document: DocumentDetail }

/** Resolve full persisted details before publishing a terminal processing state. */
export async function readProcessingSnapshot(
  id: string,
  readStatus: (id: string) => Promise<ProcessingStatusResponse>,
  readDocument: (id: string) => Promise<DocumentDetail>,
  knownUpdatedAt?: string,
): Promise<ProcessingSnapshot> {
  const status = await readStatus(id)
  if (status.status === 'completed' || status.status === 'failed') {
    return { kind: 'terminal', document: await readDocument(id) }
  }
  // Pages, OCR regions and fields are persisted between stages. Refresh them
  // when the server advances, so the viewer can show evidence during processing.
  if (status.updatedAt && status.updatedAt !== knownUpdatedAt) {
    const document = await readDocument(id)
    if (document.status === 'completed' || document.status === 'failed') return { kind: 'terminal', document }
    return { kind: 'progress', status, document }
  }
  return { kind: 'progress', status }
}

export function applyTerminalDocument(items: DocumentSummary[], updated: DocumentDetail): DocumentSummary[] {
  return items.map((item) => item.id === updated.id ? updated : item)
}
