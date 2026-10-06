/** A document can enter the sample dataset after OCR recognizes an explicit test notice. */
export async function sampleDocumentAfterOperational404(
  id: string,
  error: unknown,
  readSample: (id: string) => Promise<{ datasetScope?: string | null }>,
): Promise<boolean> {
  if (!error || typeof error !== 'object' || !('status' in error) || error.status !== 404) return false
  try {
    return (await readSample(id)).datasetScope === 'sample'
  } catch {
    return false
  }
}
