"""Rule based extraction from OCR page text and layout regions.

Every extracted value is tied to a labeled line.  Coordinates are reported
only when the OCR provider supplied a region; page-text fallbacks never invent
bounding boxes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Mapping, Sequence
import re

from app.contracts.land_record import (
    AreaUnit,
    BoundingBox,
    ExtractionConfidence,
    FieldProvenance,
    LandClassification,
    LandRecord,
    MutationRecord,
    OwnershipDetails,
    RegistrationInformation,
    SourceDocument,
)

from .models import EvidenceSource, ExtractedField
from .policy import IntelligencePolicy


_ALIASES: dict[str, tuple[str, ...]] = {
    "ownerName": ("owner name", "landholder name", "pattadar name", "owner", "pattadar"),
    "fatherOrGuardianName": (
        "father or guardian name", "father/guardian name", "guardian name",
        "father's name", "father name", "father / guardian", "father/guardian",
        "guardian", "father",
    ),
    "surveyNumber": ("survey number", "survey no.", "survey no", "sy no.", "sy no", "survey / khasra no.", "survey / khasra no"),
    "khasraNumber": ("khasra number", "khasra no.", "khasra no"),
    "khataNumber": ("khata number", "khata no.", "khata no"),
    "recordNumber": ("record number", "record no.", "record no", "patta number", "patta no"),
    "area": ("land area", "area", "extent"),
    "areaUnit": ("area unit", "unit of area"),
    "village": ("village name", "village"),
    "mandalOrTehsil": (
        "mandal or tehsil", "mandal/tehsil", "mandal / taluk", "mandal/taluk",
        "mandal", "tehsil", "taluk",
    ),
    "district": ("district name", "district"),
    "state": ("state name", "state"),
    "landClassification": ("land classification", "classification", "land use", "land type"),
    "ownershipDetails": ("ownership details", "ownership"),
    "mutationRecords": ("mutation records", "mutation record", "mutation no.", "mutation no"),
    "registrationInformation": (
        "registration information", "registration number", "registration no.",
        "registration no",
    ),
}


def _alias_pattern(alias: str) -> str:
    return re.escape(alias).replace(r"\ ", r"\s+")


_LABEL_PATTERNS = tuple(
    (field_name, re.compile(
        rf"^\s*{_alias_pattern(alias)}\s*[:#\-–]\s*(?P<value>\S.*)\s*$",
        re.IGNORECASE,
    ))
    for field_name, alias in sorted(
        ((field_name, alias) for field_name, aliases in _ALIASES.items() for alias in aliases),
        key=lambda item: len(item[1]), reverse=True,
    )
)
_EXACT_LABELS = {
    re.sub(r"\s+", " ", alias.lower().strip(" .:")): field_name
    for field_name, aliases in _ALIASES.items() for alias in aliases
}
_COMBINED_SURVEY_LABELS = frozenset({"survey / khasra no", "survey/khasra no", "survey / khasra number"})

_AREA_PATTERN = re.compile(r"^\s*(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-z ]+)?\s*$")
_UNIT_ALIASES = {
    "acre": AreaUnit.ACRE, "acres": AreaUnit.ACRE, "ac": AreaUnit.ACRE,
    "hectare": AreaUnit.HECTARE, "hectares": AreaUnit.HECTARE, "ha": AreaUnit.HECTARE,
    "square meter": AreaUnit.SQUARE_METER, "square meters": AreaUnit.SQUARE_METER,
    "sq meter": AreaUnit.SQUARE_METER, "sq meters": AreaUnit.SQUARE_METER,
    "sqm": AreaUnit.SQUARE_METER, "m2": AreaUnit.SQUARE_METER,
    "square feet": AreaUnit.SQUARE_FEET, "square foot": AreaUnit.SQUARE_FEET,
    "sq ft": AreaUnit.SQUARE_FEET, "sqft": AreaUnit.SQUARE_FEET,
    "guntha": AreaUnit.GUNTHA, "gunthas": AreaUnit.GUNTHA,
    "cent": AreaUnit.CENT, "cents": AreaUnit.CENT,
}
_CLASSIFICATION_ALIASES = {
    "agricultural": LandClassification.AGRICULTURAL,
    "agriculture": LandClassification.AGRICULTURAL,
    "residential": LandClassification.RESIDENTIAL,
    "commercial": LandClassification.COMMERCIAL,
    "forest": LandClassification.FOREST,
    "water": LandClassification.WATER,
    "government": LandClassification.GOVERNMENT,
}


@dataclass(frozen=True, slots=True)
class OCRLine:
    text: str
    page: int
    width: float
    height: float
    bbox: tuple[float, float, float, float] | None
    confidence: float | None
    from_region: bool
    method: str = "labeled-region-rule"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python", by_alias=True)
    raise TypeError("OCR pages and regions must be mappings or Pydantic models")


def _get(source: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in source:
            return source[name]
    return default


def _confidence(value: Any) -> float | None:
    try:
        return max(0.0, min(1.0, float(value))) if value is not None else None
    except (TypeError, ValueError):
        return None


def _label_fields(text: str) -> tuple[str, ...]:
    label = re.sub(r"\s+", " ", text.lower().strip(" .:#–-"))
    if label in _COMBINED_SURVEY_LABELS:
        return ("surveyNumber", "khasraNumber")
    field = _EXACT_LABELS.get(label)
    return (field,) if field else ()


def _table_rows(regions: list[OCRLine]) -> list[OCRLine]:
    """Pair a table label with the value cell on the same visual row.

    This uses geometry only. A section heading or an unmatched label cannot
    generate a value, and the evidence box points to the value cell.
    """
    paired: list[OCRLine] = []
    for label in regions:
        if not _label_fields(label.text) or label.bbox is None:
            continue
        lx, ly, lw, lh = label.bbox
        label_center = ly + lh / 2
        options: list[tuple[float, float, OCRLine]] = []
        for value in regions:
            if value is label or value.bbox is None or _label_fields(value.text):
                continue
            vx, vy, vw, vh = value.bbox
            vertical_gap = abs(label_center - (vy + vh / 2))
            horizontal_gap = vx - (lx + lw)
            if 0.005 <= horizontal_gap <= 0.45 and vertical_gap <= 0.6 * max(lh, vh):
                options.append((vertical_gap, horizontal_gap, value))
        if not options:
            continue
        _, _, value = min(options, key=lambda item: (item[0], item[1]))
        paired.append(OCRLine(
            text=f"{label.text}: {value.text}", page=label.page,
            width=label.width, height=label.height, bbox=value.bbox,
            confidence=min(label.confidence, value.confidence)
            if label.confidence is not None and value.confidence is not None else None,
            from_region=True, method="aligned-table-cell-rule",
        ))
    return paired


def _bbox(value: Any) -> tuple[float, float, float, float] | None:
    if isinstance(value, Mapping):
        coords = (value.get("x"), value.get("y"), value.get("width"), value.get("height"))
    elif isinstance(value, (tuple, list)) and len(value) == 4:
        coords = value
    else:
        return None
    try:
        x, y, width, height = (float(part) for part in coords)
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0 or min(x, y) < 0:
        return None
    if x + width > 1.000001 or y + height > 1.000001:
        return None
    return (x, y, width, height)


def _ocr_lines(ocr_pages: Sequence[Mapping[str, Any] | Any]) -> list[OCRLine]:
    lines: list[OCRLine] = []
    for index, raw_page in enumerate(ocr_pages, start=1):
        page = _as_mapping(raw_page)
        page_number = int(_get(page, "page_number", "pageNumber", "page", default=index))
        if page_number < 1:
            raise ValueError("OCR page numbers must start at 1")
        width = float(_get(page, "width", default=1) or 1)
        height = float(_get(page, "height", default=1) or 1)
        if width <= 0 or height <= 0:
            raise ValueError("OCR page dimensions must be positive")
        regions = page.get("regions") or []
        region_lines: list[OCRLine] = []
        for raw_region in regions:
            region = _as_mapping(raw_region)
            region_box = _bbox(region.get("bbox"))
            region_confidence = _confidence(region.get("confidence"))
            for text in str(region.get("text") or "").splitlines():
                if text.strip():
                    region_lines.append(OCRLine(
                        text=text.strip(), page=page_number, width=width, height=height,
                        bbox=region_box, confidence=region_confidence, from_region=True,
                    ))
        lines.extend(_table_rows(region_lines))
        lines.extend(region_lines)
        for text in str(page.get("text") or "").splitlines():
            if text.strip():
                lines.append(OCRLine(
                    text=text.strip(), page=page_number, width=width, height=height,
                    bbox=None, confidence=None, from_region=False, method="labeled-page-text-rule",
                ))
    return lines


def _candidate(line: OCRLine) -> tuple[tuple[str, ...], str] | None:
    for field_name, pattern in _LABEL_PATTERNS:
        match = pattern.match(line.text)
        if match:
            label = line.text[:match.start("value")].rstrip(" :#-–")
            return _label_fields(label) or (field_name,), match.group("value").strip()
    return None


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .;\t")


def _unit(value: str) -> AreaUnit:
    key = re.sub(r"\s+", " ", value.lower().strip(" .;"))
    return _UNIT_ALIASES.get(key, AreaUnit.UNKNOWN)


def _normalize(field_name: str, raw_value: str) -> tuple[dict[str, Any], list[str]]:
    value = _clean_text(raw_value)
    warnings: list[str] = []
    if field_name == "area":
        match = _AREA_PATTERN.match(value)
        if not match:
            return {}, ["Area could not be parsed as a number and unit."]
        amount = float(match.group("amount").replace(",", "."))
        result: dict[str, Any] = {"area": amount}
        unit_text = match.group("unit")
        if unit_text:
            result["areaUnit"] = _unit(unit_text)
            if result["areaUnit"] == AreaUnit.UNKNOWN:
                warnings.append(f"Unrecognized area unit: {unit_text.strip()}.")
        return result, warnings
    if field_name == "areaUnit":
        normalized = _unit(value)
        if normalized == AreaUnit.UNKNOWN:
            warnings.append(f"Unrecognized area unit: {value}.")
        return {"areaUnit": normalized}, warnings
    if field_name == "landClassification":
        normalized = _CLASSIFICATION_ALIASES.get(value.lower(), LandClassification.UNKNOWN)
        if normalized == LandClassification.UNKNOWN:
            warnings.append(f"Unrecognized land classification: {value}.")
        return {field_name: normalized}, warnings
    if field_name == "ownershipDetails":
        fraction: Decimal | None = None
        fraction_match = re.search(r"\b(\d+)\s*/\s*(\d+)\s*(?:share)?\b", value)
        if fraction_match and int(fraction_match.group(2)):
            fraction = Decimal(fraction_match.group(1)) / Decimal(fraction_match.group(2))
            if fraction > 1:
                fraction = None
                warnings.append("Ownership share exceeds one and requires review.")
        return {field_name: OwnershipDetails(share_fraction=fraction, notes=value)}, warnings
    if field_name == "mutationRecords":
        mutation_id = re.split(r"[,;\s]", value, maxsplit=1)[0]
        if not mutation_id:
            return {}, ["Mutation identifier is missing."]
        date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", value)
        mutation_date: date | None = None
        if date_match:
            try:
                mutation_date = date.fromisoformat(date_match.group())
            except ValueError:
                warnings.append("Mutation date is malformed.")
        return {field_name: [MutationRecord(mutation_id=mutation_id, mutation_date=mutation_date, details=value)]}, warnings
    if field_name == "registrationInformation":
        registration_number = re.split(r"[,;\s]", value, maxsplit=1)[0]
        date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", value)
        registration_date: date | None = None
        if date_match:
            try:
                registration_date = date.fromisoformat(date_match.group())
            except ValueError:
                warnings.append("Registration date is malformed.")
        return {field_name: RegistrationInformation(
            registration_number=registration_number, registration_date=registration_date,
        )}, warnings
    if field_name in {"surveyNumber", "khasraNumber", "khataNumber", "recordNumber"}:
        value = value.upper()
    return {field_name: value}, warnings


def _evidence(field_name: str, value: Any, line: OCRLine, warnings: list[str]) -> ExtractedField:
    # A searchable PDF supplies exact text coordinates but no measured OCR
    # certainty. Preserve that uncertainty rather than inventing a percentage.
    confidence = round(line.confidence, 3) if line.confidence is not None else None
    return ExtractedField(
        field=field_name,
        value=value,
        confidence=confidence,
        source=EvidenceSource(page=line.page, bbox=line.bbox, text=line.text),
        extraction_method=line.method,
        warnings=warnings,
    )


def extract_document(
    ocr_pages: Sequence[Mapping[str, Any] | Any],
    source_document: SourceDocument | Mapping[str, Any],
    *,
    policy: IntelligencePolicy | None = None,
) -> tuple[LandRecord, list[ExtractedField], list[str]]:
    """Extract canonical fields from OCR output without inventing evidence."""

    del policy  # Extraction currently has no tunable parsing thresholds.
    pages = list(ocr_pages)
    source = SourceDocument.model_validate(source_document)
    if source.page_count is None and pages:
        source = source.model_copy(update={"page_count": len(pages)})
    chosen: dict[str, tuple[ExtractedField, OCRLine]] = {}
    warnings: list[str] = []
    for line in _ocr_lines(pages):
        found = _candidate(line)
        if found is None:
            continue
        field_names, raw_value = found
        for field_name in field_names:
            normalized, field_warnings = _normalize(field_name, raw_value)
            warnings.extend(field_warnings)
            for normalized_name, value in normalized.items():
                field = _evidence(normalized_name, value, line, list(field_warnings))
                existing = chosen.get(normalized_name)
                if existing is None or (
                    (line.from_region and not existing[1].from_region)
                    or (line.from_region == existing[1].from_region
                        and (field.confidence or 0) > (existing[0].confidence or 0))
                ):
                    if existing is not None and existing[0].value != value:
                        field.warnings.append("Conflicting source candidates; stronger labeled evidence selected.")
                        warnings.append(f"Conflicting candidates for {normalized_name}.")
                    chosen[normalized_name] = (field, line)
                elif existing[0].value != value:
                    existing[0].warnings.append("Conflicting source candidates; stronger labeled evidence selected.")
                    warnings.append(f"Conflicting candidates for {normalized_name}.")

    field_values = {name: item[0].value for name, item in chosen.items()}
    if not field_values:
        warnings.append("No labeled land-record fields were detected in OCR output.")
    if "ownerName" in field_values and "ownershipDetails" not in field_values:
        field_values["ownershipDetails"] = OwnershipDetails(owners=[field_values["ownerName"]])
    elif "ownerName" in field_values and "ownershipDetails" in field_values:
        details = field_values["ownershipDetails"]
        field_values["ownershipDetails"] = details.model_copy(update={"owners": [field_values["ownerName"]]})

    provenance: dict[str, FieldProvenance] = {}
    for name, (field, line) in chosen.items():
        box = field.source.bbox
        pixel_box = None
        if box is not None:
            pixel_box = BoundingBox(
                x=box[0] * line.width, y=box[1] * line.height,
                width=box[2] * line.width, height=box[3] * line.height,
            )
        provenance[name] = FieldProvenance(
            source_page=line.page,
            bounding_box=pixel_box,
            extracted_text=field.source.text,
            confidence=field.confidence,
            extraction_method=field.extraction_method,
            validation_results=list(field.warnings),
        )
    per_field = {name: item[0].confidence for name, item in chosen.items() if item[0].confidence is not None}
    overall = round(sum(per_field.values()) / len(per_field), 3) if per_field else None
    record = LandRecord.model_validate({
        **field_values,
        "sourceDocument": source,
        "extractionConfidence": ExtractionConfidence(overall=overall, per_field=per_field),
        "provenance": provenance,
    })
    return record, [item[0] for item in chosen.values()], list(dict.fromkeys(warnings))
