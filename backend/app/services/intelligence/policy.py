"""Configurable deterministic extraction and validation parameters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IntelligencePolicy:
    required_fields: tuple[str, ...] = (
        "ownerName",
        "surveyNumber",
        "area",
        "areaUnit",
        "village",
        "district",
        "state",
    )
    low_confidence_below: float = 0.60
    missing_field_deduction: float = 35.0
    malformed_field_deduction: float = 25.0
    low_confidence_deduction: float = 25.0
    incomplete_record_deduction: float = 10.0
    duplicate_record_deduction: float = 35.0
    cross_conflict_deduction: float = 75.0
    cross_area_deduction: float = 45.0
    no_reference_score: float = 50.0
    warning_penalty: float = 3.0
    no_reference_warning_penalty: float = 7.0
    area_relative_tolerance: float = 0.10
    max_area: float = 1_000_000.0

    def __post_init__(self) -> None:
        if not 0 < self.low_confidence_below < 1:
            raise ValueError("low_confidence_below must be between 0 and 1")
        if not 0 <= self.no_reference_score <= 100:
            raise ValueError("no_reference_score must be between 0 and 100")
        if not 0 <= self.area_relative_tolerance <= 1:
            raise ValueError("area_relative_tolerance must be between 0 and 1")
        if self.max_area <= 0:
            raise ValueError("max_area must be positive")
        deductions = (
            self.missing_field_deduction,
            self.malformed_field_deduction,
            self.low_confidence_deduction,
            self.incomplete_record_deduction,
            self.duplicate_record_deduction,
            self.cross_conflict_deduction,
            self.cross_area_deduction,
            self.warning_penalty,
            self.no_reference_warning_penalty,
        )
        if any(value < 0 for value in deductions):
            raise ValueError("deductions and penalties cannot be negative")
