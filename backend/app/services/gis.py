"""Parcel metadata and officer-sourced WGS84 geometry.

An OCR-derived survey number is not a map coordinate. Operational parcels
have no polygon until an authorized officer supplies source GeoJSON.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import Settings
from app.contracts.auth import AuthenticatedUser
from app.contracts.land_record import LandRecord, ValidationStatus
from app.db.models import DocumentModel, ParcelIndexModel, ReviewCaseModel
from app.services.audit import AuditEventType, append_event
from app.services.documents.storage import document_dir


MAX_GEOMETRY_POSITIONS = 1001  # Includes the repeated closing point.


class GeometryValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value {value} is not allowed.")


def _orientation(a: list[float], b: list[float], c: list[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: list[float], b: list[float], point: list[float]) -> bool:
    epsilon = 1e-12
    return (
        abs(_orientation(a, b, point)) <= epsilon
        and min(a[0], b[0]) - epsilon <= point[0] <= max(a[0], b[0]) + epsilon
        and min(a[1], b[1]) - epsilon <= point[1] <= max(a[1], b[1]) + epsilon
    )


def _segments_intersect(a: list[float], b: list[float], c: list[float], d: list[float]) -> bool:
    epsilon = 1e-12
    ab_c, ab_d = _orientation(a, b, c), _orientation(a, b, d)
    cd_a, cd_b = _orientation(c, d, a), _orientation(c, d, b)
    if ((ab_c > epsilon and ab_d < -epsilon) or (ab_c < -epsilon and ab_d > epsilon)) and (
        (cd_a > epsilon and cd_b < -epsilon) or (cd_a < -epsilon and cd_b > epsilon)
    ):
        return True
    return any((
        abs(ab_c) <= epsilon and _on_segment(a, b, c),
        abs(ab_d) <= epsilon and _on_segment(a, b, d),
        abs(cd_a) <= epsilon and _on_segment(c, d, a),
        abs(cd_b) <= epsilon and _on_segment(c, d, b),
    ))


def validate_geojson_polygon(content: bytes) -> list[list[float]]:
    """Accept one simple closed Polygon exterior ring in GeoJSON lon/lat order."""
    try:
        source = json.loads(content.decode("utf-8-sig"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise GeometryValidationError("invalid_geojson", "The file is not valid UTF-8 GeoJSON.") from exc
    if not isinstance(source, dict):
        raise GeometryValidationError("invalid_geojson", "GeoJSON must be a Polygon or a Feature containing one Polygon.")
    geometry = source.get("geometry") if source.get("type") == "Feature" else source
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        raise GeometryValidationError("unsupported_geometry", "Provide one GeoJSON Polygon or Polygon Feature.")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) != 1:
        raise GeometryValidationError("unsupported_geometry", "Provide exactly one exterior ring without interior holes.")
    raw_ring = coordinates[0]
    if not isinstance(raw_ring, list) or not 4 <= len(raw_ring) <= MAX_GEOMETRY_POSITIONS:
        raise GeometryValidationError("invalid_ring", "The polygon must have 3 to 1000 vertices and a closing point.")
    ring: list[list[float]] = []
    for position in raw_ring:
        if (
            not isinstance(position, list) or len(position) != 2
            or any(isinstance(number, bool) or not isinstance(number, (int, float)) for number in position)
        ):
            raise GeometryValidationError("invalid_coordinate", "Every position must be [longitude, latitude].")
        longitude, latitude = float(position[0]), float(position[1])
        if not isfinite(longitude) or not isfinite(latitude) or not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise GeometryValidationError("invalid_coordinate", "Coordinates must be finite WGS84 longitude and latitude values.")
        ring.append([longitude, latitude])
    if ring[0] != ring[-1]:
        raise GeometryValidationError("open_ring", "The polygon ring must repeat its first position at the end.")
    if len({tuple(point) for point in ring[:-1]}) != len(ring) - 1:
        raise GeometryValidationError("duplicate_coordinate", "A polygon vertex may appear only once before the closing point.")
    twice_area = sum(
        ring[index][0] * ring[index + 1][1] - ring[index + 1][0] * ring[index][1]
        for index in range(len(ring) - 1)
    )
    if abs(twice_area) <= 1e-14:
        raise GeometryValidationError("degenerate_polygon", "The polygon has no measurable area.")
    edge_count = len(ring) - 1
    for first in range(edge_count):
        for second in range(first + 1, edge_count):
            if second == first + 1 or (first == 0 and second == edge_count - 1):
                continue
            if _segments_intersect(ring[first], ring[first + 1], ring[second], ring[second + 1]):
                raise GeometryValidationError("self_intersection", "The polygon boundary intersects itself.")
    return ring


def _fill(parcel: ParcelIndexModel, record: LandRecord, quality_score: float | None) -> None:
    parcel.record_number = record.record_number
    parcel.survey_number = record.survey_number
    parcel.owner_name = record.owner_name
    parcel.area = record.area
    parcel.area_unit = record.area_unit.value if record.area_unit else None
    parcel.state = record.state
    parcel.district = record.district
    parcel.village = record.village
    parcel.validation_status = record.validation_status.value
    parcel.quality_score = quality_score


def upsert_candidate_parcel(
    session: Session,
    *,
    document: DocumentModel,
    record: LandRecord,
    quality_score: float,
    has_conflict: bool,
) -> ParcelIndexModel:
    """Index searchable metadata without inventing a parcel boundary."""
    key = str(record.record_id)
    parcel = session.get(ParcelIndexModel, key)
    if parcel is None:
        parcel = ParcelIndexModel(record_id=key, polygon=None, geometry_source="unavailable", geometry_status="unavailable")
        session.add(parcel)
    parcel.document_id = document.id
    if parcel.status != "verified":
        parcel.status = "conflict" if has_conflict else "review"
    _fill(parcel, record, quality_score)
    return parcel


def index_verified_record(session: Session, review_case: ReviewCaseModel) -> ParcelIndexModel:
    """Promote officer-approved metadata; map indexing still needs geometry."""
    record = LandRecord.model_validate(review_case.reviewed_record)
    record.validation_status = ValidationStatus.APPROVED
    key = review_case.record_id
    parcel = session.get(ParcelIndexModel, key)
    if parcel is None:
        parcel = ParcelIndexModel(record_id=key, polygon=None, geometry_source="unavailable", geometry_status="unavailable")
        session.add(parcel)
    parcel.document_id = review_case.document_id
    parcel.status = "verified"
    _fill(parcel, record, review_case.quality_score)
    return parcel


def persist_geometry_source(settings: Settings, document: DocumentModel, content: bytes) -> tuple[str, Path]:
    """Write original GeoJSON bytes beneath the document's controlled key."""
    directory = document_dir(settings, document.storage_key) / "geometry"
    directory.mkdir(parents=True, exist_ok=True)
    key = str(uuid4())
    final = directory / f"{key}.geojson"
    pending = directory / f".{key}.pending"
    try:
        pending.write_bytes(content)
        os.replace(pending, final)
    finally:
        pending.unlink(missing_ok=True)
    return key, final


def source_parcel_geometry(
    session: Session,
    *,
    parcel: ParcelIndexModel,
    document: DocumentModel,
    review_case: ReviewCaseModel,
    user: AuthenticatedUser,
    settings: Settings,
    ring: list[list[float]],
    content: bytes,
    file_name: str,
    source_reference: str,
) -> ParcelIndexModel:
    """Store original evidence and append geometry/index events transactionally."""
    digest = sha256(content).hexdigest()
    previous = {
        "geometrySha256": parcel.geometry_sha256,
        "geometryReference": parcel.geometry_reference,
        "geometryFileName": parcel.geometry_file_name,
        "geometryStorageKey": parcel.geometry_storage_key,
    } if parcel.geometry_status == "sourced" else None
    key, path = persist_geometry_source(settings, document, content)
    try:
        recorded_at = datetime.now(timezone.utc)
        parcel.polygon = ring
        parcel.geometry_source = "officer_geojson"
        parcel.geometry_status = "sourced"
        parcel.geometry_reference = source_reference
        parcel.geometry_file_name = file_name
        parcel.geometry_sha256 = digest
        parcel.geometry_recorded_at = recorded_at
        parcel.geometry_recorded_by = user.id
        parcel.geometry_storage_key = key
        parcel.indexed_at = recorded_at
        append_event(
            session, record_id=parcel.record_id, document_id=document.id,
            actor_id=user.id, actor_role=user.role.value,
            event_type=AuditEventType.GEOMETRY_REPLACED if previous else AuditEventType.GEOMETRY_IMPORTED,
            description=f"{user.name} {'replaced' if previous else 'imported'} officer-sourced parcel geometry.",
            metadata={
                "reviewCaseId": review_case.id, "sourceReference": source_reference,
                "fileName": file_name, "sha256": digest, "geometryStorageKey": key,
                "vertexCount": len(ring) - 1,
                "geometrySource": parcel.geometry_source, "previous": previous,
            },
        )
        if previous is None:
            append_event(
                session, record_id=parcel.record_id, document_id=document.id,
                actor_id=user.id, actor_role=user.role.value,
                event_type=AuditEventType.GIS_INDEXED,
                description="Officer-approved record indexed with sourced WGS84 parcel geometry.",
                metadata={
                    "reviewCaseId": review_case.id, "geometrySha256": digest,
                    "geometrySource": parcel.geometry_source,
                },
            )
        session.commit()
        session.refresh(parcel)
    except Exception:
        session.rollback()
        path.unlink(missing_ok=True)
        raise
    return parcel


def set_parcel_review_status(session: Session, record_id: str, status: str) -> None:
    if status not in {"review", "conflict", "rejected", "sent_back"}:
        raise ValueError("Unsupported parcel review state.")
    parcel = session.get(ParcelIndexModel, record_id)
    if parcel is not None and parcel.status != "verified":
        parcel.status = status
