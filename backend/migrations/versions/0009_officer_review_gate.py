"""Require officer disposition for existing processed operational records.

Revision ID: 0009_officer_review
Revises: 0008_accounts

Historical extraction and audit evidence remain intact. Completed uploads
without a review case receive one from their persisted evidence. A quality
score alone cannot leave a local record in the approved state.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "0009_officer_review"
down_revision = "0008_accounts"
branch_labels = None
depends_on = None


def _synthetic_notice(pages: list[dict]) -> bool:
    text = "\n".join(str(page.get("text") or "") for page in pages).casefold()
    return bool(re.search(r"\bsynthetic\b", text)) or any(notice in text for notice in (
        "fictional data", "demo document", "not an official land record",
        "not a government record", "not for legal or official use",
    ))


def _json_dict(value: object, *, name: str, record_id: str) -> dict:
    if not isinstance(value, dict):
        raise RuntimeError(f"Cannot reconcile record {record_id}: {name} is unavailable.")
    return value


def _quality_score(document: dict, record_id: str) -> float:
    breakdown = document.get("score_breakdown") or {}
    validation = document.get("validation") or {}
    value = breakdown.get("qualityScore", validation.get("qualityScore"))
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise RuntimeError(f"Cannot reconcile record {record_id}: quality score is unavailable.")
    return float(value)


def upgrade() -> None:
    connection = op.get_bind()
    metadata = sa.MetaData()
    documents = sa.Table("documents", metadata, autoload_with=connection)
    records = sa.Table("land_records", metadata, autoload_with=connection)
    reviews = sa.Table("review_cases", metadata, autoload_with=connection)
    parcels = sa.Table("parcel_index", metadata, autoload_with=connection)
    audit = sa.Table("audit_events", metadata, autoload_with=connection)
    demo_runs = sa.Table("demo_runs", metadata, autoload_with=connection)

    demo_document_ids = set(connection.scalars(sa.select(demo_runs.c.document_id)))
    latest_reviews: dict[str, dict] = {}
    for case in connection.execute(
        sa.select(reviews.c.id, reviews.c.record_id, reviews.c.status,
                  reviews.c.decided_by, reviews.c.reviewed_record)
        .order_by(reviews.c.submitted_at.desc(), reviews.c.id.desc())
    ).mappings():
        latest_reviews.setdefault(case["record_id"], dict(case))

    rows = connection.execute(
        sa.select(records.c.id.label("record_id"), documents.c.id.label("document_id"))
        .join(documents, records.c.document_id == documents.c.id)
        .where(documents.c.status == "completed")
    ).mappings().all()
    now = datetime.now(timezone.utc)
    for row in rows:
        record = connection.execute(
            sa.select(records).where(records.c.id == row["record_id"])
        ).mappings().one()
        document = connection.execute(
            sa.select(documents).where(documents.c.id == row["document_id"])
        ).mappings().one()
        record_id = record["id"]
        document_id = document["id"]
        source = (record["payload"] or {}).get("sourceDocument") or {}
        if (
            document_id in demo_document_ids
            or document["demo_scenario"]
            or (document["processing_metadata"] or {}).get("syntheticSourceDetected")
            or source.get("isSynthetic")
            or _synthetic_notice(document["ocr_pages"] or [])
        ):
            continue

        latest = latest_reviews.get(record_id)
        if latest and latest["status"] == "approved" and latest["decided_by"]:
            continue

        needs_new_case = latest is None or latest["status"] == "approved"
        if needs_new_case:
            original = deepcopy(_json_dict(
                document["extraction"] or record["payload"], name="extraction", record_id=record_id,
            ))
            reviewed = deepcopy(_json_dict(record["payload"], name="record payload", record_id=record_id))
            reviewed["validationStatus"] = "human_review"
            validation = _json_dict(document["validation"], name="validation", record_id=record_id)
            score = _quality_score(document, record_id)
            issues = validation.get("issues") or []
            critical = next((issue for issue in issues if issue.get("severity") == "error"
                             or "mismatch" in str(issue.get("code", ""))
                             or "conflict" in str(issue.get("code", ""))), None)
            primary = critical or (issues[0] if issues else None)
            review_id = str(uuid4())
            submitted_at = now if latest is not None else (document["processed_at"] or document["uploaded_at"] or now)
            connection.execute(reviews.insert().values(
                id=review_id, record_id=record_id, document_id=document_id,
                status="queued", priority="medium", priority_reasons=[],
                assigned_officer_id=None, original_record=original,
                reviewed_record=reviewed, field_reviews={}, issue_resolutions=[],
                recommendation=None, validation=validation, quality_score=score,
                primary_conflict=str(primary.get("message") or "")[:512] if primary else None,
                submitted_at=submitted_at, updated_at=now, version=1,
            ))
            connection.execute(audit.insert().values(
                id=str(uuid4()), record_id=record_id, document_id=document_id,
                actor_id="system", actor_role="SYSTEM", event_type="REVIEW_CREATED",
                timestamp=now,
                description="Existing processed record placed in officer review during migration.",
                event_metadata={
                    "reviewCaseId": review_id, "qualityScore": score,
                    "sourceRouting": validation.get("routing"),
                    "migration": revision,
                },
            ))

        # The stored quality route is retained as evidence. Only the canonical
        # record state changes; the source extraction snapshot is untouched.
        status = "rejected" if latest and latest["status"] == "rejected" else "human_review"
        if record["validation_status"] != status or (record["payload"] or {}).get("validationStatus") != status:
            payload = deepcopy(_json_dict(record["payload"], name="record payload", record_id=record_id))
            payload["validationStatus"] = status
            connection.execute(records.update().where(records.c.id == record_id).values(
                validation_status=status, payload=payload,
            ))
        if needs_new_case and isinstance(document["extraction"], dict):
            extraction = deepcopy(document["extraction"])
            extraction["validationStatus"] = "human_review"
            connection.execute(documents.update().where(documents.c.id == document_id).values(
                extraction=extraction,
            ))
        if latest is not None and not needs_new_case:
            reviewed = latest["reviewed_record"] or {}
            if isinstance(reviewed, dict) and reviewed.get("validationStatus") != status:
                reviewed = deepcopy(reviewed)
                reviewed["validationStatus"] = status
                connection.execute(reviews.update().where(reviews.c.id == latest["id"]).values(
                    reviewed_record=reviewed,
                ))
        connection.execute(parcels.update().where(parcels.c.record_id == record_id).values(
            validation_status=status,
        ))


def downgrade() -> None:
    # This is an evidence-preserving data reconciliation. Reversing an officer
    # queue entry or restoring an AI-only approval would be unsafe.
    pass
