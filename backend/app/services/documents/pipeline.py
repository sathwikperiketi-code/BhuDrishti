"""Durable processing stages for uploaded documents.

FastAPI may run this in a background task today. The service takes a document
ID and creates its own database session so it can later run in a job worker.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.contracts.land_record import LandRecord, SourceDocument, ValidationStatus
from app.db.models import DocumentModel, LandRecordModel, ReviewCaseModel
from app.db.session import SessionLocal
from app.services.audit import AuditEventType, append_event
from app.services.gis import upsert_candidate_parcel
from app.services.intelligence import extract_document, validate_document
from app.services.review import create_review_case

from .ocr import OCRProcessingError, OCRUnavailableError, ocr_document
from .preprocess import PreprocessingError, preprocess_pages
from .storage import document_dir


logger = logging.getLogger(__name__)

STAGE_ORDER = (
    "upload", "preprocessing", "ocr", "field_extraction", "normalization",
    "validation", "quality_score", "final_routing",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def initial_stages() -> list[dict]:
    now = utc_now().isoformat()
    return [
        {
            "stage": stage,
            "status": "completed" if stage == "upload" else "pending",
            "started_at": now if stage == "upload" else None,
            "completed_at": now if stage == "upload" else None,
            "message": "Upload stored and pages rendered." if stage == "upload" else None,
        }
        for stage in STAGE_ORDER
    ]


def begin_processing(
    session: Session, document: DocumentModel, *,
    actor_id: str = "system", actor_role: str = "SYSTEM",
) -> None:
    if document.status == "processing":
        raise ValueError("Document processing is already running.")
    if document.status == "completed":
        latest_review = session.scalar(
            select(ReviewCaseModel).where(ReviewCaseModel.document_id == document.id)
            .order_by(ReviewCaseModel.submitted_at.desc(), ReviewCaseModel.id.desc()).limit(1)
        )
        if latest_review and latest_review.status in {"approved", "rejected"}:
            raise ValueError("A finalized officer decision cannot be reprocessed; upload a new source document.")
    document.status = "processing"
    document.stage = "preprocessing"
    document.attempts += 1
    document.provider = None
    document.error = None
    document.processing_metadata = {}
    document.ocr_pages = []
    document.extraction = None
    document.fields = []
    document.validation = None
    document.score_breakdown = None
    document.warnings = []
    document.processed_at = None
    document.pages = [{key: value for key, value in page.items() if key != "ocr_provider"} for page in document.pages]
    document.stages = initial_stages()
    append_event(
        session,
        record_id=str(uuid5(NAMESPACE_URL, f"uploaded-document:{document.id}")),
        document_id=document.id,
        actor_id=actor_id,
        actor_role=actor_role,
        event_type=AuditEventType.PROCESSING_STARTED,
        description="Document processing started.",
        metadata={"attempt": document.attempts},
    )
    _set_stage(session, document, "preprocessing", "running")


def _set_stage(session: Session, document: DocumentModel, stage: str, status: str, message: str | None = None) -> None:
    now = utc_now()
    stages = [dict(item) for item in document.stages]
    for item in stages:
        if item["stage"] == stage:
            item["status"] = status
            if status == "running":
                item["started_at"] = now.isoformat()
                item["completed_at"] = None
            elif status in {"completed", "failed"}:
                item["completed_at"] = now.isoformat()
            item["message"] = message
            break
    document.stages = stages
    document.stage = stage
    document.updated_at = now
    event_type = {
        "preprocessing": AuditEventType.PREPROCESSING_COMPLETED,
        "ocr": AuditEventType.OCR_COMPLETED,
        "field_extraction": AuditEventType.EXTRACTION_COMPLETED,
        "validation": AuditEventType.VALIDATION_COMPLETED,
    }.get(stage) if status == "completed" else AuditEventType.PROCESSING_FAILED if status == "failed" else None
    if event_type is not None:
        details: dict[str, object] = {"stage": stage, "attempt": document.attempts}
        if stage == "ocr" and status == "completed":
            details["provider"] = document.provider or "unknown"
            details["pages"] = document.page_count
        if stage == "field_extraction" and status == "completed":
            details["fieldsDetected"] = len(document.fields)
        if stage == "validation" and status == "completed":
            details["qualityScore"] = (document.score_breakdown or {}).get("qualityScore")
            details["routing"] = (document.validation or {}).get("routing")
        if status == "failed":
            details["errorCode"] = (document.error or {}).get("code")
        append_event(
            session,
            record_id=str(uuid5(NAMESPACE_URL, f"uploaded-document:{document.id}")),
            document_id=document.id,
            actor_id="system",
            actor_role="SYSTEM",
            event_type=event_type,
            description=message or f"{stage.replace('_', ' ').capitalize()} {status}.",
            metadata=details,
        )
    session.commit()


def _advance(session: Session, document: DocumentModel, complete: str, next_stage: str, message: str | None = None) -> None:
    _set_stage(session, document, complete, "completed", message)
    _set_stage(session, document, next_stage, "running")


def _reference_records(session: Session, document_id: str) -> list[LandRecord]:
    """Use only officer-approved local records or explicitly trusted imports.

    An ordinary upload never acquires a synthetic scenario reference. Old
    demo rows remain in the database for audit history but cannot influence
    an operational score or be treated as verified source data.
    """
    documents = {item.id: item for item in session.scalars(select(DocumentModel))}
    latest_review_decision: dict[str, tuple[str, str | None]] = {}
    for record_id, status, decided_by in session.execute(
        select(ReviewCaseModel.record_id, ReviewCaseModel.status, ReviewCaseModel.decided_by)
        .order_by(ReviewCaseModel.submitted_at.desc(), ReviewCaseModel.id.desc())
    ):
        latest_review_decision.setdefault(record_id, (status, decided_by))
    references = []
    rows = session.scalars(select(LandRecordModel).where(
        or_(LandRecordModel.source_document_id.is_(None), LandRecordModel.source_document_id != document_id),
        LandRecordModel.validation_status == "approved",
    ))
    for stored in rows:
        source_id = stored.source_document_id or ""
        source_document = documents.get(source_id)
        payload = stored.payload or {}
        if source_document is not None and (
            source_document.dataset_scope != "operational"
            or source_document.demo_scenario
            or (source_document.processing_metadata or {}).get("syntheticSourceDetected")
            or has_explicit_synthetic_notice(source_document.ocr_pages or [])
        ):
            continue
        latest_decision = latest_review_decision.get(stored.id)
        if source_document is not None and (
            latest_decision is None or latest_decision[0] != "approved" or not latest_decision[1]
        ):
            continue
        if source_document is None and (payload.get("extensions") or {}).get("trustedReference") is not True:
            continue
        if (payload.get("sourceDocument") or {}).get("isSynthetic"):
            continue
        try:
            references.append(LandRecord.model_validate(payload))
        except ValueError:
            logger.warning("Skipping malformed reference record %s", stored.id)
    return references


def _persist_record(session: Session, document: DocumentModel, record: LandRecord, routing: str) -> None:
    key = str(record.record_id)
    stored = session.get(LandRecordModel, key)
    if stored is None:
        stored = LandRecordModel(id=key)
        session.add(stored)
    stored.record_number = record.record_number
    stored.owner_name = record.owner_name
    stored.survey_number = record.survey_number
    stored.area = record.area
    stored.area_unit = record.area_unit.value if record.area_unit else None
    stored.district = record.district
    stored.state = record.state
    stored.validation_status = routing
    stored.source_document_id = document.id
    stored.document_id = document.id
    stored.payload = record.model_dump(mode="json", by_alias=True)
    session.flush()


def has_explicit_synthetic_notice(ocr_pages: list[dict]) -> bool:
    """Recognize source-authored synthetic disclaimers, never filename clues."""
    text = "\n".join(str(page.get("text") or "") for page in ocr_pages).casefold()
    return bool(re.search(r"\bsynthetic\b", text)) or any(notice in text for notice in (
        "fictional data", "demo document", "not an official land record",
        "not a government record", "not for legal or official use",
    ))

def run_document_pipeline(document_id: str, settings: Settings) -> None:
    """Process real uploaded bytes and retain each completed stage in the DB."""
    with SessionLocal() as session:
        document = session.get(DocumentModel, document_id)
        if document is None or document.status != "processing":
            return
        try:
            directory = document_dir(settings, document.storage_key)
            pages, metadata = preprocess_pages(directory, document.page_count, settings)
            document.processing_metadata = metadata
            document.pages = [
                {
                    **raw,
                    "original_width": raw.get("original_width", raw["width"]),
                    "original_height": raw.get("original_height", raw["height"]),
                    "width": processed["width"],
                    "height": processed["height"],
                }
                for raw, processed in zip(document.pages, pages, strict=True)
            ]
            session.commit()
            _advance(session, document, "preprocessing", "ocr", "Pages normalized for text recognition.")

            ocr_pages, provider, page_providers = ocr_document(directory, document.mime_type, pages, settings)
            document.ocr_pages = ocr_pages
            document.provider = provider
            source_has_notice = has_explicit_synthetic_notice(ocr_pages)
            if source_has_notice and document.dataset_scope != "sample":
                document.dataset_scope = "sample"
                document.dataset_reason = "source_notice"
            is_synthetic_source = bool(document.demo_scenario) or source_has_notice
            document.processing_metadata = {
                **document.processing_metadata,
                "syntheticSourceDetected": is_synthetic_source,
            }
            document.pages = [
                {**page, "ocr_provider": page_providers[page["page_number"]]}
                for page in document.pages
            ]
            document.language = next((page["language"] for page in ocr_pages if page.get("language")), None)
            session.commit()
            _advance(session, document, "ocr", "field_extraction", f"Text read with {provider}.")

            source = SourceDocument(
                document_id=document.id,
                file_name=document.file_name,
                mime_type=document.mime_type,
                sha256=document.sha256,
                page_count=document.page_count,
                language=document.language,
                uploaded_at=as_utc(document.uploaded_at),
                is_synthetic=is_synthetic_source,
            )
            record, fields, extraction_warnings = extract_document(ocr_pages, source)
            record = record.model_copy(update={"record_id": uuid5(NAMESPACE_URL, f"uploaded-document:{document.id}")})
            document.extraction = record.model_dump(mode="json", by_alias=True)
            document.fields = [field.model_dump(mode="json", by_alias=True) for field in fields]
            document.warnings = extraction_warnings
            session.commit()
            _advance(session, document, "field_extraction", "normalization", "Labeled OCR regions mapped to canonical fields.")
            _advance(session, document, "normalization", "validation", "Values normalized into the land-record schema.")

            references = _reference_records(session, document.id)
            report, breakdown, validation_warnings = validate_document(
                record, references=references, settings=settings
            )
            document.validation = report.model_dump(mode="json", by_alias=True)
            document.score_breakdown = breakdown.model_dump(mode="json", by_alias=True)
            document.warnings = list(dict.fromkeys([*extraction_warnings, *validation_warnings]))
            session.commit()
            _advance(session, document, "validation", "quality_score", "Field, record, and supplied-reference checks completed.")
            for issue in report.issues:
                if issue.severity == "error" or "mismatch" in issue.code or "conflict" in issue.code:
                    append_event(
                        session,
                        record_id=str(record.record_id), document_id=document.id,
                        actor_id="validation-engine", actor_role="SYSTEM",
                        event_type=AuditEventType.CONFLICT_DETECTED,
                        description=issue.message,
                        metadata={"code": issue.code, "fieldName": issue.field_name,
                                  "severity": issue.severity},
                    )
            session.commit()
            _advance(session, document, "quality_score", "final_routing", "Configured 50/30/20 score calculated.")

            # A quality route is advice for an officer, never a final decision.
            # Even a high score must stay pending until an officer approves it.
            record.validation_status = ValidationStatus.HUMAN_REVIEW
            document.extraction = record.model_dump(mode="json", by_alias=True)
            _persist_record(session, document, record, record.validation_status.value)
            create_review_case(session, document, record, report, breakdown)
            upsert_candidate_parcel(
                session, document=document, record=record,
                quality_score=breakdown.quality_score,
                has_conflict=any(
                    issue.severity == "error" or "mismatch" in issue.code or "conflict" in issue.code
                    for issue in report.issues
                ),
            )
            document.status = "completed"
            document.processed_at = utc_now()
            session.commit()
            recommendation = {
                ValidationStatus.APPROVED: "Automated checks passed",
                ValidationStatus.HUMAN_REVIEW: "Closer officer review recommended",
                ValidationStatus.REJECTED: "Rejection recommended",
            }[report.routing]
            _set_stage(session, document, "final_routing", "completed", f"{recommendation}. Officer decision required.")
        except Exception as exc:
            logger.exception("Document processing failed for %s", document_id)
            session.rollback()
            document = session.get(DocumentModel, document_id)
            if document is None:
                return
            if isinstance(exc, OCRUnavailableError):
                code, message = "ocr_unavailable", str(exc)
            elif isinstance(exc, OCRProcessingError):
                code, message = "ocr_failed", str(exc)
            elif isinstance(exc, PreprocessingError):
                code, message = "preprocessing_failed", str(exc)
            else:
                code, message = "processing_failed", "Document processing failed. Please retry or choose a clearer file."
            document.status = "failed"
            document.error = {"code": code, "message": message}
            _set_stage(session, document, document.stage, "failed", message)
