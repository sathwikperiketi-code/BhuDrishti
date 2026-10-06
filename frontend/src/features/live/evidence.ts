/** Public workflow boxes are normalized [x, y, width, height], never pixels. */
export function isNormalizedBox(box: readonly number[] | null | undefined): box is [number, number, number, number] {
  if (!box || box.length !== 4 || !box.every(Number.isFinite)) return false
  const [x, y, width, height] = box
  return x >= 0 && y >= 0 && width > 0 && height > 0 && x + width <= 1.000001 && y + height <= 1.000001
}
