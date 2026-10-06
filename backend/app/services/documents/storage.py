"""Safe upload intake and page-preview persistence.

Only generated UUIDs become directory names. The caller's filename is retained
as sanitized display metadata and is never used to address the filesystem.
"""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
from uuid import uuid4

import pymupdf as fitz
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import Settings


class UploadValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


EXTENSION_TO_MIME = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def safe_display_name(filename: str | None) -> str:
    if not filename or any(char in filename for char in ("/", "\\", "\x00")):
        raise UploadValidationError("unsafe_filename", "The filename contains an unsafe path or is empty.")
    if any(ord(char) < 32 for char in filename):
        raise UploadValidationError("unsafe_filename", "The filename contains control characters.")
    name = re.sub(r"[^\w. ()-]", "_", filename, flags=re.UNICODE).strip(" .")
    if not name or len(name) > 180:
        raise UploadValidationError("unsafe_filename", "The filename is invalid or too long.")
    return name


def detect_mime(filename: str, content: bytes, declared_mime: str | None) -> str:
    extension = Path(filename).suffix.lower()
    expected = EXTENSION_TO_MIME.get(extension)
    if expected is None:
        raise UploadValidationError("unsupported_file", "Supported files are PDF, JPG, PNG, and TIFF.")
    signatures = {
        "application/pdf": content.startswith(b"%PDF-"),
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/tiff": content.startswith((b"II*\x00", b"MM\x00*")),
    }
    if not signatures[expected]:
        raise UploadValidationError("invalid_signature", "The file contents do not match its extension.")
    normalized_declared = (declared_mime or "").lower().split(";", 1)[0].strip()
    if normalized_declared not in ("", "application/octet-stream", expected):
        raise UploadValidationError("mime_mismatch", "The file type supplied by the browser does not match its contents.")
    return expected


def storage_root(settings: Settings) -> Path:
    path = Path(settings.document_storage_dir).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def document_dir(settings: Settings, storage_key: str) -> Path:
    # A UUID, not a user-provided path, is the only accepted storage key.
    from uuid import UUID

    if str(UUID(storage_key)) != storage_key:
        raise ValueError("Invalid document storage key")
    root = storage_root(settings)
    path = (root / storage_key).resolve()
    if path.parent != root:
        raise ValueError("Document storage path escaped configured root")
    return path


def remove_document_dir(settings: Settings, storage_key: str) -> None:
    path = document_dir(settings, storage_key)
    if path.is_dir():
        shutil.rmtree(path)


def persist_upload(
    filename: str | None,
    declared_mime: str | None,
    content: bytes,
    settings: Settings,
) -> dict:
    """Validate, render previews, and atomically move bytes under an opaque key."""

    name = safe_display_name(filename)
    if len(content) == 0:
        raise UploadValidationError("empty_file", "Choose a non-empty document.")
    if len(content) > settings.upload_max_bytes:
        raise UploadValidationError("file_too_large", "The document exceeds the configured upload limit.")
    mime = detect_mime(name, content, declared_mime)
    key = str(uuid4())
    root = storage_root(settings)
    final = document_dir(settings, key)
    with TemporaryDirectory(prefix="bd-upload-", dir=root) as temp_name:
        temp = Path(temp_name)
        (temp / "original.bin").write_bytes(content)
        pages = _render_pages(content, mime, temp, settings)
        temp.rename(final)
    return {
        "storage_key": key,
        "file_name": name,
        "mime_type": mime,
        "file_size": len(content),
        "sha256": sha256(content).hexdigest(),
        "page_count": len(pages),
        "pages": pages,
    }


def _render_pages(content: bytes, mime: str, target: Path, settings: Settings) -> list[dict]:
    if mime == "application/pdf":
        try:
            document = fitz.open(stream=content, filetype="pdf")
            if document.is_encrypted:
                raise UploadValidationError("encrypted_pdf", "Encrypted PDFs are not supported.")
            if not 1 <= document.page_count <= settings.upload_max_pages:
                raise UploadValidationError("page_limit", "The PDF exceeds the configured page limit.")
            pages = []
            total_pixels = 0
            scale = settings.render_dpi / 72
            for index in range(document.page_count):
                page = document.load_page(index)
                estimated_pixels = page.rect.width * page.rect.height * scale * scale
                total_pixels += estimated_pixels
                if estimated_pixels > 40_000_000 or total_pixels > settings.upload_max_total_pixels:
                    raise UploadValidationError("page_too_large", "A page exceeds the safe image size limit.")
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                if pixmap.width * pixmap.height > 40_000_000:
                    raise UploadValidationError("page_too_large", "A page exceeds the safe image size limit.")
                pixmap.save(str(target / f"page-{index + 1}.png"))
                pages.append({"page_number": index + 1, "width": pixmap.width, "height": pixmap.height})
            return pages
        except UploadValidationError:
            raise
        except Exception as exc:
            raise UploadValidationError("invalid_pdf", "The PDF could not be read safely.") from exc

    try:
        Image.MAX_IMAGE_PIXELS = 40_000_000
        image = Image.open(BytesIO(content))
        count = getattr(image, "n_frames", 1)
        if not 1 <= count <= settings.upload_max_pages:
            raise UploadValidationError("page_limit", "The image exceeds the configured page limit.")
        pages = []
        total_pixels = 0
        for index in range(count):
            image.seek(index)
            page_pixels = image.width * image.height
            total_pixels += page_pixels
            if page_pixels > 40_000_000 or total_pixels > settings.upload_max_total_pixels:
                raise UploadValidationError("page_too_large", "A page exceeds the safe image size limit.")
            page = ImageOps.exif_transpose(image.copy()).convert("RGB")
            if page.width * page.height > 40_000_000:
                raise UploadValidationError("page_too_large", "A page exceeds the safe image size limit.")
            page.save(target / f"page-{index + 1}.png", format="PNG", optimize=True)
            pages.append({"page_number": index + 1, "width": page.width, "height": page.height})
        return pages
    except UploadValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise UploadValidationError("invalid_image", "The image could not be read safely.") from exc
