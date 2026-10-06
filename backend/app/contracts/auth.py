"""Contracts for persisted user authentication and server-side authorization."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

import re

from pydantic import Field, field_validator, model_validator

from app.contracts.land_record import ContractModel
from app.email_address import normalize_email_address


class Role(StrEnum):
    ADMIN = "ADMIN"
    REVENUE_OFFICER = "REVENUE_OFFICER"
    VERIFIER = "VERIFIER"
    AUDITOR = "AUDITOR"


class RoleApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AuthenticatedUser(ContractModel):
    id: str
    name: str
    username: str
    email: str
    role: Role
    requested_role: Role | None = None
    role_approval_status: RoleApprovalStatus | None = None


class LoginRequest(ContractModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(ContractModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthenticatedUser
    expires_at: datetime


class CreateUserRequest(ContractModel):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=256)
    role: Role

    @field_validator("email")
    @classmethod
    def valid_email(cls, email: str) -> str:
        return normalize_email_address(email)

    @field_validator("name")
    @classmethod
    def valid_name(cls, name: str) -> str:
        normalized = name.strip()
        if len(normalized) < 2:
            raise ValueError("Name must contain at least two characters.")
        return normalized


_USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,32}$", re.ASCII)


def normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not _USERNAME_PATTERN.fullmatch(normalized) or not re.search(r"[a-z0-9]", normalized):
        raise ValueError("Enter a valid username.")
    return normalized


def validate_new_password(password: str) -> str:
    if (
        not 12 <= len(password) <= 256
        or not re.search(r"[a-z]", password)
        or not re.search(r"[A-Z]", password)
        or not re.search(r"[0-9]", password)
        or not re.search(r"[^a-zA-Z0-9]", password)
    ):
        raise ValueError("Password does not meet security requirements.")
    return password


class SignUpRequest(ContractModel):
    full_name: str = Field(min_length=2, max_length=160)
    username: str = Field(min_length=3, max_length=32)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)
    confirm_password: str = Field(min_length=1, max_length=256)
    requested_role: Role

    @field_validator("full_name")
    @classmethod
    def valid_full_name(cls, value: str) -> str:
        normalized = value.strip()
        if not 2 <= len(normalized) <= 160:
            raise ValueError("Enter your full name.")
        return normalized

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        return normalize_username(value)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return normalize_email_address(value)

    @field_validator("password")
    @classmethod
    def valid_password(cls, value: str) -> str:
        return validate_new_password(value)

    @model_validator(mode="after")
    def passwords_match(self) -> "SignUpRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class EmailRequest(ContractModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return SignUpRequest.valid_email(value)


class ActionTokenRequest(ContractModel):
    token: str = Field(min_length=20, max_length=512)


class ResetPasswordRequest(ActionTokenRequest):
    password: str = Field(min_length=12, max_length=256)
    confirm_password: str = Field(min_length=1, max_length=256)

    @field_validator("password")
    @classmethod
    def valid_password(cls, value: str) -> str:
        return validate_new_password(value)

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class AuthMessageResponse(ContractModel):
    message: str


class SignUpResponse(AuthMessageResponse):
    role: Role
    requested_role: Role
    role_approval_status: RoleApprovalStatus | None = None


class AdminRoleRequest(ContractModel):
    user: AuthenticatedUser
    email_verified: bool
    created_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
