"""Replaceable providers for embedded PDF text and actual local OCR."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import os
import re
import shutil
from typing import Protocol

import pymupdf as fitz
from PIL import Image
import pytesseract

from app.config import Settings


class OCRUnavailableError(RuntimeError):
    pass


class OCRProcessingError(RuntimeError):
    pass


class OCRProvider(Protocol):
    name: str

    def recognize(self, image_path: Path, page_number: int, *, pdf_page: fitz.Page | None = None) -> dict: ...


def _tesseract_command(settings: Settings) -> str | None:
    command = settings.tesseract_cmd or shutil.which("tesseract")
    if command is None and os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR" / "tesseract.exe"
        if candidate.is_file():
            command = str(candidate)
    return command if command and Path(command).is_file() else None


def local_ocr_capabilities(settings: Settings) -> dict:
    """Report installed models and whether the configured languages can run."""
    requested = [language.strip() for language in settings.ocr_language.split("+") if language.strip()]
    command = _tesseract_command(settings)
    if not command:
        return {
            "available": False, "installed_languages": [],
            "requested_languages": requested, "unsupported_languages": requested,
            "message": "Tesseract is not installed; scanned PDFs and images cannot be recognized locally.",
        }
    pytesseract.pytesseract.tesseract_cmd = command
    try:
        installed = sorted(pytesseract.get_languages(config=""))
    except (pytesseract.TesseractError, pytesseract.TesseractNotFoundError, OSError) as exc:
        return {
            "available": False, "installed_languages": [],
            "requested_languages": requested, "unsupported_languages": requested,
            "message": f"Tesseract language models could not be inspected: {type(exc).__name__}.",
        }
    unsupported = [language for language in requested if language not in installed]
    if not requested:
        message = "No OCR language is configured. Set BHUDRISHTI_OCR_LANGUAGE."
    elif unsupported:
        message = "Requested OCR language models are not installed: " + ", ".join(unsupported) + "."
    else:
        message = "Tesseract is ready for " + ", ".join(requested) + "."
    return {
        "available": bool(requested) and not unsupported,
        "installed_languages": installed,
        "requested_languages": requested,
        "unsupported_languages": unsupported,
        "message": message,
    }


def _normalized_box(x: float, y: float, width: float, height: float, page_width: float, page_height: float) -> list[float]:
    return [
        round(max(0.0, min(1.0, x / page_width)), 5),
        round(max(0.0, min(1.0, y / page_height)), 5),
        round(max(0.0, min(1.0, width / page_width)), 5),
        round(max(0.0, min(1.0, height / page_height)), 5),
    ]


def _usable_embedded_text(page: fitz.Page) -> bool:
    """Ignore a small scanner watermark while preferring substantial text layers."""
    text = page.get_text("text").strip()
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    if len(text) < 20 or len(words) < 4:
        return False
    if len(words) >= 12:
        return True
    return bool(re.search(
        r"\b(owner|survey|khasra|khata|area|village|district|record|mandal|tehsil)\b",
        text, flags=re.IGNORECASE,
    ))


class PDFTextProvider:
    """Read text already embedded in a searchable PDF; no OCR claim is made."""

    name = "pdf-embedded-text"

    def recognize(self, image_path: Path, page_number: int, *, pdf_page: fitz.Page | None = None) -> dict:
        if pdf_page is None:
            raise OCRUnavailableError("Embedded-text extraction requires a PDF page.")
        width, height = pdf_page.rect.width, pdf_page.rect.height
        words = pdf_page.get_text("words")
        grouped: dict[tuple[int, int], list[tuple]] = defaultdict(list)
        for word in words:
            grouped[(int(word[5]), int(word[6]))].append(word)
        regions = []
        for line in grouped.values():
            line.sort(key=lambda item: item[7])
            text = " ".join(str(word[4]) for word in line).strip()
            if not text:
                continue
            x0 = min(word[0] for word in line)
            y0 = min(word[1] for word in line)
            x1 = max(word[2] for word in line)
            y1 = max(word[3] for word in line)
            regions.append({"text": text, "bbox": _normalized_box(x0, y0, x1 - x0, y1 - y0, width, height), "confidence": None})
        with Image.open(image_path) as image:
            image_width, image_height = image.size
        return {
            "page_number": page_number,
            "text": pdf_page.get_text("text").strip(),
            "width": image_width,
            "height": image_height,
            "confidence": None,
            "regions": regions,
            "language": None,
        }


class LocalOCRProvider:
    """Tesseract OCR over the actual uploaded document page."""

    name = "tesseract-local"

    def __init__(self, settings: Settings):
        capabilities = local_ocr_capabilities(settings)
        if not capabilities["available"]:
            raise OCRUnavailableError(capabilities["message"])
        self.language = "+".join(capabilities["requested_languages"])

    def recognize(self, image_path: Path, page_number: int, *, pdf_page: fitz.Page | None = None) -> dict:
        try:
            with Image.open(image_path) as image:
                width, height = image.size
                data = pytesseract.image_to_data(
                    image,
                    lang=self.language,
                    output_type=pytesseract.Output.DICT,
                    config="--psm 6",
                    timeout=90,
                )
        except pytesseract.TesseractNotFoundError as exc:
            raise OCRUnavailableError("Local Tesseract OCR executable was not found.") from exc
        except (pytesseract.TesseractError, RuntimeError) as exc:
            raise OCRProcessingError(f"Local OCR failed on page {page_number}.") from exc

        lines: dict[tuple[int, int, int], list[dict]] = defaultdict(list)
        confidences: list[float] = []
        for index, raw in enumerate(data["text"]):
            token = str(raw).strip()
            if not token:
                continue
            try:
                confidence = max(0.0, min(1.0, float(data["conf"][index]) / 100))
            except (TypeError, ValueError):
                confidence = 0.0
            if confidence > 0:
                confidences.append(confidence)
            key = (int(data["block_num"][index]), int(data["par_num"][index]), int(data["line_num"][index]))
            lines[key].append({
                "text": token,
                "left": int(data["left"][index]),
                "top": int(data["top"][index]),
                "width": int(data["width"][index]),
                "height": int(data["height"][index]),
                "confidence": confidence,
            })
        regions = []
        for words in lines.values():
            left = min(word["left"] for word in words)
            top = min(word["top"] for word in words)
            right = max(word["left"] + word["width"] for word in words)
            bottom = max(word["top"] + word["height"] for word in words)
            regions.append({
                "text": " ".join(word["text"] for word in words),
                "bbox": _normalized_box(left, top, right - left, bottom - top, width, height),
                "confidence": round(sum(word["confidence"] for word in words) / len(words), 4),
            })
        regions.sort(key=lambda region: (region["bbox"][1], region["bbox"][0]))
        return {
            "page_number": page_number,
            "text": "\n".join(region["text"] for region in regions),
            "width": width,
            "height": height,
            "confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
            "regions": regions,
            "language": self.language,
        }


def ocr_document(directory: Path, mime_type: str, pages: list[dict], settings: Settings) -> tuple[list[dict], str, dict[int, str]]:
    """Choose real embedded text or local OCR per page."""

    if settings.ocr_provider not in {"auto", "tesseract", "pdf_text"}:
        raise OCRUnavailableError("Unknown OCR provider. Configure auto, tesseract, or pdf_text.")
    pdf = fitz.open(str(directory / "original.bin"), filetype="pdf") if mime_type == "application/pdf" else None
    results = []
    providers: set[str] = set()
    page_providers: dict[int, str] = {}
    try:
        for page in pages:
            number = page["page_number"]
            pdf_page = pdf.load_page(number - 1) if pdf else None
            path = directory / f"processed-{number}.png"
            use_pdf_text = (
                pdf_page is not None
                and settings.ocr_provider in {"auto", "pdf_text"}
                and _usable_embedded_text(pdf_page)
            )
            if use_pdf_text:
                provider: OCRProvider = PDFTextProvider()
            elif settings.ocr_provider == "pdf_text":
                raise OCRUnavailableError("The PDF has no embedded text. Configure local Tesseract OCR for scanned pages.")
            else:
                provider = LocalOCRProvider(settings)
            result = provider.recognize(path, number, pdf_page=pdf_page)
            results.append(result)
            providers.add(provider.name)
            page_providers[number] = provider.name
    finally:
        if pdf:
            pdf.close()
    if not any(page["text"].strip() for page in results):
        raise OCRProcessingError("No text could be recognized in the uploaded document.")
    return results, "+".join(sorted(providers)), page_providers
