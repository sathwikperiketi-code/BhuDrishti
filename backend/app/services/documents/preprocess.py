"""Configurable image normalization before local OCR.

The enhanced image is retained for the evidence overlay because deskew/crop
change source coordinates. The original rendered preview remains available.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.config import Settings


class PreprocessingError(RuntimeError):
    pass


def preprocess_pages(directory: Path, page_count: int, settings: Settings) -> tuple[list[dict], dict]:
    processed: list[dict] = []
    per_page: list[dict] = []
    for number in range(1, page_count + 1):
        source = directory / f"page-{number}.png"
        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
        if image is None:
            raise PreprocessingError(f"Page {number} could not be decoded for preprocessing.")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if settings.preprocess_denoise:
            gray = cv2.fastNlMeansDenoising(gray, None, h=5, templateWindowSize=7, searchWindowSize=21)
        if settings.preprocess_contrast:
            gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        deskew_angle = 0.0
        if settings.preprocess_deskew:
            gray, deskew_angle = _deskew(gray)
        cropped = False
        if settings.preprocess_crop:
            gray, cropped = _crop_scanner_border(gray)
        output = gray if settings.preprocess_grayscale else cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        destination = directory / f"processed-{number}.png"
        if not cv2.imwrite(str(destination), output):
            raise PreprocessingError(f"Page {number} could not be saved after preprocessing.")
        height, width = output.shape[:2]
        processed.append({"page_number": number, "width": width, "height": height, "path": destination})
        per_page.append({"page": number, "width": width, "height": height, "deskewAngle": round(deskew_angle, 3), "cropped": cropped})
    metadata = {
        "pagesProcessed": len(processed),
        "grayscale": settings.preprocess_grayscale,
        "denoise": settings.preprocess_denoise,
        "contrastEnhanced": settings.preprocess_contrast,
        "deskew": settings.preprocess_deskew,
        "crop": settings.preprocess_crop,
        "perPage": per_page,
    }
    return processed, metadata


def _deskew(image: np.ndarray) -> tuple[np.ndarray, float]:
    # Only small skew is corrected; large rotations are handled by EXIF/PDF
    # orientation during preview rendering to avoid turning sparse pages.
    threshold = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    points = np.column_stack(np.where(threshold > 0))
    if len(points) < 200:
        return image, 0.0
    angle = cv2.minAreaRect(points)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.2 or abs(angle) > 5:
        return image, 0.0
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    rotated = cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    return rotated, float(angle)


def _crop_scanner_border(image: np.ndarray) -> tuple[np.ndarray, bool]:
    threshold = cv2.threshold(image, 230, 255, cv2.THRESH_BINARY_INV)[1]
    points = cv2.findNonZero(threshold)
    if points is None:
        return image, False
    x, y, width, height = cv2.boundingRect(points)
    full_height, full_width = image.shape[:2]
    if width < full_width * 0.5 or height < full_height * 0.5:
        return image, False
    pad = 16
    left, top = max(0, x - pad), max(0, y - pad)
    right, bottom = min(full_width, x + width + pad), min(full_height, y + height + pad)
    cropped = left > 0 or top > 0 or right < full_width or bottom < full_height
    return image[top:bottom, left:right], cropped
