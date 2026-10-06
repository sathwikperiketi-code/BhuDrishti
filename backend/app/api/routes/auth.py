"""Password sign-in, revocable sessions, and administrator user provisioning."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.contracts.auth import (
    ActionTokenRequest, AdminRoleRequest, AuthMessageResponse, AuthenticatedUser, CreateUserRequest,
    EmailRequest, LoginRequest, LoginResponse, ResetPasswordRequest, Role, RoleApprovalStatus,
    SignUpRequest, SignUpResponse,
)
from app.db.models import UserModel
from app.db.session import get_db
from app.services.auth import Permission, require_permission
from app.services.auth.service import (
    as_user, authenticate_token, create_user, get_auth_provider,
    get_current_user, issue_token,
)
from app.services.auth.lifecycle import (
    EMAIL_VERIFICATION, PASSWORD_RESET, InvalidActionToken,
    invalidate_action_token, issue_action_token, recent_token_exists,
    reset_password, verify_email,
)
from app.services.email import (
    EmailConfigurationError, EmailDeliveryError, MailTransport,
    get_mail_transport, send_password_reset_email, send_verification_email,
)


router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)
_logger = logging.getLogger(__name__)
_MAIL_ERROR_MESSAGES = {
    "SMTP_AUTHENTICATION_FAILED": "Email service authentication failed. Please contact the administrator.",
    "SMTP_CONNECTION_FAILED": "The email service is temporarily unreachable. Please try again later.",
    "SMTP_TLS_FAILED": "A secure email connection could not be established. Please contact the administrator.",
    "EMAIL_DELIVERY_FAILED": "Email delivery failed. Please try again later.",
}


def _mail_configuration_unavailable(error: EmailConfigurationError) -> HTTPException:
    _logger.error("Account email configuration failed: setting=%s", error.setting)
    return HTTPException(
        status_code=503, detail="Email delivery is not configured.",
        headers={"X-BhuDrishti-Error-Code": "EMAIL_NOT_CONFIGURED"},
    )


def _mail_transport(settings: Settings = Depends(get_settings)) -> MailTransport:
    try:
        return get_mail_transport(settings)
    except EmailConfigurationError as error:
        raise _mail_configuration_unavailable(error) from None


def _send_or_service_unavailable(sender) -> None:
    try:
        sender()
    except EmailConfigurationError as error:
        raise _mail_configuration_unavailable(error) from None
    except EmailDeliveryError as error:
        _logger.error(
            "Account email delivery failed: code=%s stage=%s error_type=%s smtp_code=%s os_errno=%s winerror=%s",
            error.code, error.stage, error.error_type, error.smtp_code, error.os_errno, error.winerror,
        )
        raise HTTPException(
            status_code=503, detail=_MAIL_ERROR_MESSAGES[error.code],
            headers={"X-BhuDrishti-Error-Code": error.code},
        ) from None


def _send_with_token_cleanup(session: Session, token: str, sender) -> None:
    try:
        _send_or_service_unavailable(sender)
    except HTTPException:
        invalidate_action_token(session, token)
        session.commit()
        raise


@router.post(
    "/signup", response_model=SignUpResponse, status_code=status.HTTP_202_ACCEPTED,
    summary="Register an unverified account and send a verification email",
)
def signup(
    body: SignUpRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    transport: MailTransport = Depends(_mail_transport),
) -> SignUpResponse:
    if session.scalar(select(UserModel.id).where(UserModel.email == body.email)) or session.scalar(
        select(UserModel.id).where(UserModel.username == body.username)
    ):
        raise HTTPException(status_code=409, detail="An account with these details already exists.")
    try:
        assigned_role = Role.AUDITOR if body.requested_role == Role.ADMIN else body.requested_role
        user = create_user(
            session, email=body.email, name=body.full_name, username=body.username,
            password=body.password, role=assigned_role, status="UNVERIFIED",
            requested_role=body.requested_role,
        )
        token = issue_action_token(session, user, EMAIL_VERIFICATION)
        session.commit()
    except (ValueError, IntegrityError) as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="An account with these details already exists.") from error
    link = f"{settings.public_app_url.rstrip('/')}/#/verify-email?token={quote(token, safe='')}"
    _logger.info("Signup verification email requested: recipient=configured")
    _send_with_token_cleanup(session, token, lambda: send_verification_email(
        recipient_email=user.email, verification_url=link,
        settings=settings, transport=transport, expires_minutes=24 * 60,
    ))
    _logger.info("Signup verification email submitted: outcome=transport_accepted")
    return SignUpResponse(
        message="Check your email to verify your BhuDrishti account.",
        role=assigned_role,
        requested_role=body.requested_role,
        role_approval_status=(
            RoleApprovalStatus.PENDING if body.requested_role == Role.ADMIN else None
        ),
    )


@router.post("/verify-email", response_model=AuthMessageResponse, summary="Verify an email with a one-time token")
def verify_email_route(body: ActionTokenRequest, session: Session = Depends(get_db)) -> AuthMessageResponse:
    try:
        verify_email(session, body.token)
        session.commit()
    except InvalidActionToken as error:
        session.rollback()
        raise HTTPException(status_code=400, detail="This verification link is invalid, expired, or already used.") from error
    return AuthMessageResponse(message="Email verified. You can now sign in.")


@router.post(
    "/resend-verification", response_model=AuthMessageResponse,
    status_code=status.HTTP_202_ACCEPTED, summary="Send a replacement verification email when eligible",
)
def resend_verification(
    body: EmailRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    transport: MailTransport = Depends(_mail_transport),
) -> AuthMessageResponse:
    generic = AuthMessageResponse(message="If this account needs verification and email delivery is available, check your email for a new link.")
    user = session.scalar(select(UserModel).where(UserModel.email == body.email))
    if user is None or user.status != "UNVERIFIED":
        _logger.info("Verification email resend skipped: reason=account_not_eligible")
        return generic
    if recent_token_exists(session, user, EMAIL_VERIFICATION):
        _logger.info("Verification email resend skipped: reason=request_cooldown")
        return generic
    token = issue_action_token(session, user, EMAIL_VERIFICATION)
    session.commit()
    link = f"{settings.public_app_url.rstrip('/')}/#/verify-email?token={quote(token, safe='')}"
    _send_with_token_cleanup(session, token, lambda: send_verification_email(
        recipient_email=user.email, verification_url=link,
        settings=settings, transport=transport, expires_minutes=24 * 60,
    ))
    _logger.info("Verification email resend submitted: outcome=transport_accepted")
    return generic


@router.post(
    "/forgot-password", response_model=AuthMessageResponse,
    status_code=status.HTTP_202_ACCEPTED, summary="Send a password reset email when eligible",
)
def forgot_password(
    body: EmailRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    transport: MailTransport = Depends(_mail_transport),
) -> AuthMessageResponse:
    generic = AuthMessageResponse(message="If an eligible account exists and email delivery is available, check your email for a reset link.")
    _logger.info("Password recovery email requested: recipient=configured")
    # Check provider availability independently of account eligibility. A shared
    # SMTP outage must give the same safe service error for known and unknown
    # addresses; the public response never reports account existence.
    _send_or_service_unavailable(transport.verify_connection)
    user = session.scalar(select(UserModel).where(UserModel.email == body.email))
    if (
        user is None or user.status != "ACTIVE" or not user.is_active
        or user.email_verified_at is None
    ):
        _logger.info("Password recovery email skipped: reason=account_not_eligible")
        return generic
    if recent_token_exists(session, user, PASSWORD_RESET):
        _logger.info("Password recovery email skipped: reason=request_cooldown")
        return generic
    token = issue_action_token(session, user, PASSWORD_RESET)
    session.commit()
    link = f"{settings.public_app_url.rstrip('/')}/#/reset-password?token={quote(token, safe='')}"
    _send_with_token_cleanup(session, token, lambda: send_password_reset_email(
        recipient_email=user.email, reset_url=link,
        settings=settings, transport=transport, expires_minutes=30,
    ))
    _logger.info("Password recovery email submitted: outcome=transport_accepted")
    return generic


@router.post("/reset-password", response_model=AuthMessageResponse, summary="Replace a password with a one-time token")
def reset_password_route(
    body: ResetPasswordRequest, session: Session = Depends(get_db),
) -> AuthMessageResponse:
    try:
        reset_password(session, body.token, body.password)
        session.commit()
    except InvalidActionToken as error:
        session.rollback()
        raise HTTPException(status_code=400, detail="This reset link is invalid, expired, or already used.") from error
    return AuthMessageResponse(message="Password updated. Sign in with your new password.")


@router.post("/login", response_model=LoginResponse, summary="Sign in with a persisted account")
def login(
    body: LoginRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    user = get_auth_provider(settings).authenticate(session, body.email, body.password)
    token, expires = issue_token(session, user, settings)
    session.commit()
    return LoginResponse(access_token=token, user=as_user(user), expires_at=expires)


@router.get("/me", response_model=AuthenticatedUser, summary="Read the current authenticated user")
def me(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke the current session")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer session is required.")
    _, stored_session = authenticate_token(credentials.credentials, session, settings)
    from datetime import datetime, timezone
    stored_session.revoked_at = datetime.now(timezone.utc)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users", response_model=list[AuthenticatedUser], summary="List active user accounts")
def list_users(
    session: Session = Depends(get_db),
    _admin: AuthenticatedUser = Depends(require_permission(Permission.USER_MANAGE)),
) -> list[AuthenticatedUser]:
    users = session.scalars(select(UserModel).where(UserModel.is_active.is_(True)).order_by(UserModel.name)).all()
    return [as_user(user) for user in users]


@router.get("/admin-requests", response_model=list[AdminRoleRequest],
            summary="List administrator access requests")
def list_admin_requests(
    session: Session = Depends(get_db),
    _admin: AuthenticatedUser = Depends(require_permission(Permission.USER_MANAGE)),
) -> list[AdminRoleRequest]:
    users = session.scalars(
        select(UserModel)
        .where(UserModel.requested_role == Role.ADMIN.value)
        .order_by(UserModel.created_at.desc(), UserModel.id.desc())
    ).all()
    return [
        AdminRoleRequest(
            user=as_user(user), email_verified=user.email_verified_at is not None,
            created_at=user.created_at, reviewed_by=user.role_reviewed_by,
            reviewed_at=user.role_reviewed_at,
        )
        for user in users
    ]


@router.post("/admin-requests/{user_id}/approve", response_model=AuthenticatedUser,
             summary="Approve verified administrator access")
def approve_admin_request(
    user_id: str,
    session: Session = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_permission(Permission.USER_MANAGE)),
) -> AuthenticatedUser:
    user = session.get(UserModel, user_id)
    if user is None or user.requested_role != Role.ADMIN.value or user.role_approval_status != "PENDING":
        raise HTTPException(status_code=404, detail="Pending administrator request not found.")
    if user.status != "ACTIVE" or not user.is_active or user.email_verified_at is None:
        raise HTTPException(status_code=409, detail="Verify the account email before approval.")
    now = datetime.now(timezone.utc)
    result = session.execute(
        update(UserModel)
        .where(
            UserModel.id == user_id,
            UserModel.requested_role == Role.ADMIN.value,
            UserModel.role_approval_status == RoleApprovalStatus.PENDING.value,
            UserModel.role == Role.AUDITOR.value,
            UserModel.status == "ACTIVE",
            UserModel.is_active.is_(True),
            UserModel.email_verified_at.is_not(None),
        )
        .values(
            role=Role.ADMIN.value,
            role_approval_status=RoleApprovalStatus.APPROVED.value,
            role_reviewed_by=admin.id,
            role_reviewed_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        session.rollback()
        raise HTTPException(status_code=409, detail="Administrator request is no longer pending.")
    session.commit()
    session.refresh(user)
    return as_user(user)


@router.post("/admin-requests/{user_id}/reject", response_model=AuthenticatedUser,
             summary="Reject administrator access while retaining auditor access")
def reject_admin_request(
    user_id: str,
    session: Session = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_permission(Permission.USER_MANAGE)),
) -> AuthenticatedUser:
    user = session.get(UserModel, user_id)
    if user is None or user.requested_role != Role.ADMIN.value or user.role_approval_status != "PENDING":
        raise HTTPException(status_code=404, detail="Pending administrator request not found.")
    result = session.execute(
        update(UserModel)
        .where(
            UserModel.id == user_id,
            UserModel.requested_role == Role.ADMIN.value,
            UserModel.role_approval_status == RoleApprovalStatus.PENDING.value,
            UserModel.role == Role.AUDITOR.value,
        )
        .values(
            role_approval_status=RoleApprovalStatus.REJECTED.value,
            role_reviewed_by=admin.id,
            role_reviewed_at=datetime.now(timezone.utc),
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        session.rollback()
        raise HTTPException(status_code=409, detail="Administrator request is no longer pending.")
    session.commit()
    session.refresh(user)
    return as_user(user)


@router.post("/users", response_model=AuthenticatedUser, status_code=status.HTTP_201_CREATED,
             summary="Create an account and assign its role")
def add_user(
    body: CreateUserRequest,
    session: Session = Depends(get_db),
    _admin: AuthenticatedUser = Depends(require_permission(Permission.USER_MANAGE)),
) -> AuthenticatedUser:
    try:
        user = create_user(session, email=body.email, name=body.name, password=body.password, role=body.role)
        session.commit()
        return as_user(user)
    except (ValueError, IntegrityError) as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from error
