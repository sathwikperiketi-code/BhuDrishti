"""Versioned upload and processing API; service modules own all pipeline work."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.contracts.auth import AuthenticatedUser
from app.contracts.document_workflow import DocumentDetail, DocumentList, DocumentSummary, ProcessingStatus
from app.contracts.review import ReviewStatus
from app.db.models import DocumentModel, ReviewCaseModel
from app.db.session import get_db
from app.services.audit import AuditEventType, append_event
from app.services.auth import Permission, require_permission
from app.services.legacy_visibility import Dataset, dataset_document_ids
from app.services.documents.pipeline import begin_processing, has_explicit_synthetic_notice, initial_stages, run_document_pipeline
from app.services.documents.storage import (
    UploadValidationError,
    document_dir,
    persist_upload,
    remove_document_dir,
)


router = APIRouter(prefix="/documents", tags=["documents"])


def _utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _get_document(session: Session, document_id: str, dataset: Dataset = "operational") -> DocumentModel:
    document = session.scalar(select(DocumentModel).where(
        DocumentModel.id == document_id, DocumentModel.id.in_(dataset_document_ids(dataset)),
    ))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


def _review_statuses(session: Session, document_ids: list[str]) -> dict[str, ReviewStatus]:
    """Read the latest persisted officer outcome for each requested document."""
    if not document_ids:
        return {}
    cases = session.execute(
        select(ReviewCaseModel.document_id, ReviewCaseModel.status)
        .where(ReviewCaseModel.document_id.in_(document_ids))
        .order_by(ReviewCaseModel.submitted_at.desc(), ReviewCaseModel.id.desc())
    ).all()
    statuses: dict[str, ReviewStatus] = {}
    for document_id, status in cases:
        if document_id not in statuses:
            try:
                statuses[document_id] = ReviewStatus(status)
            except ValueError:
                # An unknown legacy state must not hide the document itself.
                continue
    return statuses


def _summary(
    document: DocumentModel, dataset: Dataset | None = None,
    review_status: ReviewStatus | None = None,
) -> DocumentSummary:
    return DocumentSummary(
        id=document.id,
        file_name=document.file_name,
        mime_type=document.mime_type,
        file_size=document.file_size,
        page_count=document.page_count,
        language=document.language,
        uploaded_at=_utc(document.uploaded_at),
        status=document.status,
        review_status=review_status,
        stage=document.stage,
        provider=document.provider,
        is_synthetic=bool(
            document.demo_scenario
            or (document.processing_metadata or {}).get("syntheticSourceDetected")
            or has_explicit_synthetic_notice(document.ocr_pages or [])
        ),
        dataset_scope=dataset or ("sample" if document.dataset_scope == "sample" or document.demo_scenario else "operational"),
        dataset_reason=document.dataset_reason,
    )


def _detail(
    document: DocumentModel, settings: Settings, dataset: Dataset | None = None,
    review_status: ReviewStatus | None = None,
) -> DocumentDetail:
    selected_dataset = dataset or ("sample" if document.dataset_scope == "sample" or document.demo_scenario else "operational")
    pages = [
        {
            "page_number": page["page_number"],
            "image_url": f"{settings.api_prefix}/documents/{document.id}/pages/{page['page_number']}/image"
                         + ("?dataset=sample" if selected_dataset == "sample" else ""),
            "width": page.get("original_width", page["width"]) if page.get("ocr_provider") == "pdf-embedded-text" else page["width"],
            "height": page.get("original_height", page["height"]) if page.get("ocr_provider") == "pdf-embedded-text" else page["height"],
        }
        for page in document.pages
    ]
    return DocumentDetail(
        **_summary(document, selected_dataset, review_status).model_dump(),
        updated_at=_utc(document.updated_at),
        processed_at=_utc(document.processed_at),
        attempts=document.attempts,
        pages=pages,
        stages=document.stages,
        processing_metadata=document.processing_metadata,
        ocr_pages=document.ocr_pages,
        extraction=document.extraction,
        fields=document.fields,
        validation=document.validation,
        score_breakdown=document.score_breakdown,
        warnings=document.warnings,
        error=document.error,
    )


def _processing_status(document: DocumentModel) -> ProcessingStatus:
    return ProcessingStatus(
        id=document.id,
        status=document.status,
        stage=document.stage,
        attempts=document.attempts,
        stages=document.stages,
        error=document.error,
        updated_at=_utc(document.updated_at),
    )


@router.post("/upload", status_code=201, response_model=DocumentDetail, summary="Upload a real PDF or image")
def upload_document(
    file: UploadFile = File(...),
    dataset: Literal["operational", "sample"] = Form(default="operational"),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: AuthenticatedUser = Depends(require_permission(Permission.DOCUMENT_UPLOAD)),
) -> DocumentDetail:
    # Bounded incremental read, regardless of the request's Content-Length.
    buffer = BytesIO()
    while chunk := file.file.read(1024 * 1024):
        if buffer.tell() + len(chunk) > settings.upload_max_bytes:
            raise HTTPException(
                status_code=413,
                detail={"code": "file_too_large", "message": "The document exceeds the configured upload limit."},
            )
        buffer.write(chunk)
    try:
        stored = persist_upload(file.filename, file.content_type, buffer.getvalue(), settings)
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=413 if exc.code in {"file_too_large", "page_limit", "page_too_large"} else 400,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    document = DocumentModel(
        id=str(uuid4()),
        file_name=stored["file_name"],
        mime_type=stored["mime_type"],
        file_size=stored["file_size"],
        sha256=stored["sha256"],
        storage_key=stored["storage_key"],
        page_count=stored["page_count"],
        dataset_scope=dataset,
        dataset_reason="declared_sample" if dataset == "sample" else None,
        status="uploaded",
        stage="upload",
        attempts=0,
        pages=stored["pages"],
        stages=initial_stages(),
        processing_metadata={},
        ocr_pages=[],
        fields=[],
        warnings=[],
    )
    try:
        session.add(document)
        append_event(
            session,
            record_id=str(uuid5(NAMESPACE_URL, f"uploaded-document:{document.id}")),
            document_id=document.id,
            actor_id=user.id,
            actor_role=user.role.value,
            event_type=AuditEventType.DOCUMENT_UPLOADED,
            description=f"{user.name} uploaded source document {document.file_name}.",
            metadata={"fileName": document.file_name, "mimeType": document.mime_type,
                      "fileSize": document.file_size, "pageCount": document.page_count},
        )
        session.commit()
        session.refresh(document)
    except Exception:
        session.rollback()
        remove_document_dir(settings, stored["storage_key"])
        raise
    return _detail(document, settings)


@router.get("", response_model=DocumentList, summary="List uploaded documents")
def list_documents(
    dataset: Dataset = Query(default="operational"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.DOCUMENT_READ)),
) -> DocumentList:
    visible = DocumentModel.id.in_(dataset_document_ids(dataset))
    total = session.scalar(select(func.count()).select_from(DocumentModel).where(visible)) or 0
    documents = session.scalars(
        select(DocumentModel).where(visible).order_by(DocumentModel.uploaded_at.desc(), DocumentModel.id.desc()).limit(limit).offset(offset)
    ).all()
    review_statuses = _review_statuses(session, [document.id for document in documents])
    return DocumentList(
        items=[_summary(document, dataset, review_statuses.get(document.id)) for document in documents],
        total=total,
    )


@router.get("/{document_id}", response_model=DocumentDetail, summary="Get uploaded document and evidence")
def get_document(
    document_id: str,
    dataset: Dataset = Query(default="operational"),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _user: AuthenticatedUser = Depends(require_permission(Permission.DOCUMENT_READ)),
) -> DocumentDetail:
    document = _get_document(session, document_id, dataset)
    return _detail(document, settings, dataset, _review_statuses(session, [document.id]).get(document.id))


@router.post("/{document_id}/process", status_code=202, response_model=ProcessingStatus, summary="Start or retry real document processing")
def process_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    dataset: Dataset = Query(default="operational"),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: AuthenticatedUser = Depends(require_permission(Permission.DOCUMENT_PROCESS)),
) -> ProcessingStatus:
    document = _get_document(session, document_id, dataset)
    try:
        begin_processing(session, document, actor_id=user.id, actor_role=user.role.value)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "already_processing", "message": str(exc)}) from exc
    background_tasks.add_task(run_document_pipeline, document.id, settings)
    return _processing_status(document)


@router.get("/{document_id}/processing-status", response_model=ProcessingStatus, summary="Poll actual processing stage")
def processing_status(
    document_id: str,
    dataset: Dataset = Query(default="operational"),
    session: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.DOCUMENT_READ)),
) -> ProcessingStatus:
    return _processing_status(_get_document(session, document_id, dataset))


@router.get("/{document_id}/pages/{page_number}/image", summary="View rendered document page")
def page_image(
    document_id: str,
    page_number: int,
    dataset: Dataset = Query(default="operational"),
    original: bool = False,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _user: AuthenticatedUser = Depends(require_permission(Permission.DOCUMENT_READ)),
) -> FileResponse:
    document = _get_document(session, document_id, dataset)
    if page_number < 1 or page_number > document.page_count:
        raise HTTPException(status_code=404, detail="Page not found.")
    directory = document_dir(settings, document.storage_key)
    enhanced = directory / f"processed-{page_number}.png"
    raw = directory / f"page-{page_number}.png"
    page_metadata = document.pages[page_number - 1]
    uses_embedded_text = page_metadata.get("ocr_provider") == "pdf-embedded-text"
    path: Path = raw if original or uses_embedded_text or not enhanced.is_file() else enhanced
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Page image unavailable.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, no-store"})
