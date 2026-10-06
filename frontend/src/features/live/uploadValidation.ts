export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024

const mimeByExtension: Record<string, string> = {
  pdf: 'application/pdf', jpg: 'image/jpeg', jpeg: 'image/jpeg',
  png: 'image/png', tif: 'image/tiff', tiff: 'image/tiff',
}

export function validateUploadFile(file: Pick<File, 'name' | 'type' | 'size'>): string | null {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
  const expectedMime = mimeByExtension[extension]
  if (!expectedMime || (file.type && file.type !== expectedMime)) return 'Choose a PDF, JPG, JPEG, PNG, or TIFF document.'
  if (file.size === 0) return 'The selected file is empty.'
  if (file.size > MAX_UPLOAD_BYTES) return 'The file exceeds the 20 MB limit.'
  return null
}
