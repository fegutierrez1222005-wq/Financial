"""Authentication service: signup, login, refresh, logout, MFA enrolment.

Implements :class:`finagent_api.security.auth_provider.AuthProvider` so an external identity
provider can replace it without touching routers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import Organization, OrganizationMember, User
from finagent_api.db.models import Session as SessionRow
from finagent_api.security.auth_provider import AuthenticatedIdentity, BaseAuthProvider
from finagent_api.security.crypto import decrypt_secret, encrypt_secret
from finagent_api.security.mfa import (
    generate_recovery_codes,
    generate_totp_secret,
    provisioning_uri,
    verify_totp,
)
from finagent_api.security.passwords import hash_password, validate_password_strength, verify_password
from finagent_api.security.tokens import (
    AccessTokenClaims,
    create_access_token,
    create_refresh_token,
    hash_token,
    refresh_expiry,
)
from finagent_api.services.audit import AuditAction, record_audit
from finagent_api.settings import Settings, get_settings
from finagent_core.errors import (
    ConflictError,
    ForbiddenError,
    UnauthenticatedError,
    ValidationFailedError,
)
from finagent_core.logging import get_logger

logger = get_logger(__name__)

MAX_FAILED_LOGINS = 8
LOCKOUT_MINUTES = 15


@dataclass
class RequestMetadata:
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None


class CredentialAuthProvider(BaseAuthProvider):
    """Email/password authentication with revocable refresh sessions and TOTP MFA."""

    key = "credentials"

    def __init__(
        self,
        db: DbSession,
        *,
        settings: Settings | None = None,
        metadata: RequestMetadata | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.metadata = metadata or RequestMetadata()

    # ------------------------------------------------------------------- signup

    def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None = None,
        is_platform_admin: bool = False,
    ) -> User:
        normalised = (email or "").strip().lower()
        if not normalised or "@" not in normalised:
            raise ValidationFailedError("a valid email address is required")
        if self.db.scalar(select(User).where(User.email == normalised)) is not None:
            raise ConflictError("an account with this email already exists")
        validate_password_strength(password, min_length=self.settings.password_min_length)

        user = User(
            email=normalised,
            full_name=(full_name or "").strip() or None,
            password_hash=hash_password(password, rounds=self.settings.bcrypt_rounds),
            is_platform_admin=is_platform_admin,
            onboarding_state={"created_via": "password", "steps_completed": []},
        )
        self.db.add(user)
        self.db.flush()
        logger.info("user_registered", extra={"user_id": user.id})
        return user

    # -------------------------------------------------------------------- login

    def authenticate_password(
        self, email: str, password: str, *, mfa_code: str | None = None
    ) -> AuthenticatedIdentity:
        normalised = (email or "").strip().lower()
        user = self.db.scalar(select(User).where(User.email == normalised))
        now = datetime.now(UTC)

        if user and user.locked_until and user.locked_until > now:
            raise ForbiddenError(
                "account temporarily locked after repeated failed sign-in attempts",
                details={"locked_until": user.locked_until.isoformat()},
            )

        if user is None or not verify_password(password, user.password_hash):
            if user is not None:
                user.failed_login_count += 1
                if user.failed_login_count >= MAX_FAILED_LOGINS:
                    user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                    user.failed_login_count = 0
                self.db.flush()
                self._audit_login_failure(user)
            logger.info("login_failed", extra={"email_hash": hash_token(normalised)[:16]})
            raise UnauthenticatedError("invalid email or password")

        if not user.is_active:
            raise ForbiddenError("this account is disabled")

        if user.mfa_enabled:
            secret = decrypt_secret(user.mfa_secret_encrypted)
            if not secret:
                raise ForbiddenError(
                    "multi-factor authentication is enabled but its secret could not be read; "
                    "contact an administrator to re-enrol"
                )
            if not mfa_code:
                return AuthenticatedIdentity(
                    user_id=user.id,
                    email=user.email,
                    session_id="",
                    access_token="",
                    mfa_required=True,
                    detail={"reason": "mfa_code_required"},
                )
            if not verify_totp(secret, mfa_code):
                raise UnauthenticatedError("invalid multi-factor code")

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        identity = self._issue_session(user, mfa_satisfied=True)
        record_audit(
            self.db,
            action=AuditAction.LOGIN,
            organization_id=self._primary_organization_id(user) or "",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            ip_address=self.metadata.ip_address,
            user_agent=self.metadata.user_agent,
            request_id=self.metadata.request_id,
            metadata={"mfa_used": user.mfa_enabled},
        )
        return identity

    def _audit_login_failure(self, user: User) -> None:
        organization_id = self._primary_organization_id(user)
        if not organization_id:
            return
        record_audit(
            self.db,
            action=AuditAction.LOGIN_FAILED,
            organization_id=organization_id,
            user_id=user.id,
            outcome="FAILURE",
            resource_type="user",
            resource_id=user.id,
            ip_address=self.metadata.ip_address,
            user_agent=self.metadata.user_agent,
            request_id=self.metadata.request_id,
        )

    def _primary_organization_id(self, user: User) -> str | None:
        membership = self.db.scalar(
            select(OrganizationMember).where(OrganizationMember.user_id == user.id)
        )
        return membership.organization_id if membership else None

    def _issue_session(self, user: User, *, mfa_satisfied: bool) -> AuthenticatedIdentity:
        refresh_token, refresh_hash = create_refresh_token()
        session_row = SessionRow(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            expires_at=refresh_expiry(self.settings.refresh_token_days),
            ip_address=self.metadata.ip_address,
            user_agent=(self.metadata.user_agent or "")[:400] or None,
            mfa_satisfied=mfa_satisfied,
            last_used_at=datetime.now(UTC),
        )
        self.db.add(session_row)
        self.db.flush()

        return AuthenticatedIdentity(
            user_id=user.id,
            email=user.email,
            session_id=session_row.id,
            access_token=create_access_token(
                AccessTokenClaims(
                    user_id=user.id,
                    session_id=session_row.id,
                    email=user.email,
                    is_platform_admin=user.is_platform_admin,
                    mfa_satisfied=mfa_satisfied,
                ),
                secret=self.settings.secret_key,
                expires_minutes=self.settings.access_token_minutes,
            ),
            refresh_token=refresh_token,
            mfa_satisfied=mfa_satisfied,
        )

    # ------------------------------------------------------------------ refresh

    def refresh(self, refresh_token: str) -> AuthenticatedIdentity:
        session_row = self.db.scalar(
            select(SessionRow).where(SessionRow.refresh_token_hash == hash_token(refresh_token))
        )
        now = datetime.now(UTC)
        if session_row is None or session_row.revoked_at is not None or session_row.expires_at <= now:
            raise UnauthenticatedError("refresh token is not valid")
        user = self.db.get(User, session_row.user_id)
        if user is None or not user.is_active:
            raise UnauthenticatedError("user is inactive")

        # Rotate the refresh token so a stolen token cannot be replayed after use.
        new_token, new_hash = create_refresh_token()
        session_row.refresh_token_hash = new_hash
        session_row.last_used_at = now
        session_row.expires_at = refresh_expiry(self.settings.refresh_token_days)
        self.db.flush()

        return AuthenticatedIdentity(
            user_id=user.id,
            email=user.email,
            session_id=session_row.id,
            access_token=create_access_token(
                AccessTokenClaims(
                    user_id=user.id,
                    session_id=session_row.id,
                    email=user.email,
                    is_platform_admin=user.is_platform_admin,
                    mfa_satisfied=session_row.mfa_satisfied,
                ),
                secret=self.settings.secret_key,
                expires_minutes=self.settings.access_token_minutes,
            ),
            refresh_token=new_token,
            mfa_satisfied=session_row.mfa_satisfied,
        )

    def revoke(self, refresh_token: str) -> None:
        session_row = self.db.scalar(
            select(SessionRow).where(SessionRow.refresh_token_hash == hash_token(refresh_token))
        )
        if session_row is not None and session_row.revoked_at is None:
            session_row.revoked_at = datetime.now(UTC)
            self.db.flush()

    def revoke_session(self, session_id: str, *, user_id: str) -> None:
        session_row = self.db.get(SessionRow, session_id)
        if session_row is not None and session_row.user_id == user_id:
            session_row.revoked_at = datetime.now(UTC)
            self.db.flush()

    def revoke_all_sessions(self, user_id: str) -> int:
        rows = list(
            self.db.scalars(
                select(SessionRow).where(
                    SessionRow.user_id == user_id, SessionRow.revoked_at.is_(None)
                )
            )
        )
        now = datetime.now(UTC)
        for row in rows:
            row.revoked_at = now
        self.db.flush()
        return len(rows)

    # ---------------------------------------------------------------------- MFA

    def begin_mfa_enrolment(self, user: User) -> dict[str, object]:
        secret = generate_totp_secret()
        user.mfa_secret_encrypted = encrypt_secret(secret)
        user.mfa_enabled = False
        user.mfa_confirmed_at = None
        self.db.flush()
        return {
            "secret": secret,
            "provisioning_uri": provisioning_uri(
                secret, account=user.email, issuer=self.settings.product_name
            ),
            "recovery_codes": generate_recovery_codes(),
            "note": (
                "Store the recovery codes now; they are not shown again and are not retrievable "
                "from the server."
            ),
        }

    def confirm_mfa(self, user: User, code: str) -> None:
        secret = decrypt_secret(user.mfa_secret_encrypted)
        if not secret:
            raise ValidationFailedError("start multi-factor enrolment before confirming it")
        if not verify_totp(secret, code):
            raise ValidationFailedError("that code is not valid; check your authenticator clock")
        user.mfa_enabled = True
        user.mfa_confirmed_at = datetime.now(UTC)
        self.db.flush()
        record_audit(
            self.db,
            action=AuditAction.MFA_ENABLED,
            organization_id=self._primary_organization_id(user) or "",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            request_id=self.metadata.request_id,
        )

    def disable_mfa(self, user: User, password: str) -> None:
        if not verify_password(password, user.password_hash):
            raise UnauthenticatedError("password confirmation failed")
        user.mfa_enabled = False
        user.mfa_secret_encrypted = None
        user.mfa_confirmed_at = None
        self.db.flush()
        record_audit(
            self.db,
            action=AuditAction.MFA_DISABLED,
            organization_id=self._primary_organization_id(user) or "",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            request_id=self.metadata.request_id,
        )

    # ----------------------------------------------------------------- password

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise UnauthenticatedError("current password is incorrect")
        validate_password_strength(new_password, min_length=self.settings.password_min_length)
        user.password_hash = hash_password(new_password, rounds=self.settings.bcrypt_rounds)
        self.db.flush()
        self.revoke_all_sessions(user.id)
        record_audit(
            self.db,
            action=AuditAction.PASSWORD_CHANGED,
            organization_id=self._primary_organization_id(user) or "",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            request_id=self.metadata.request_id,
            metadata={"sessions_revoked": True},
        )

    def list_sessions(self, user_id: str) -> list[SessionRow]:
        return list(
            self.db.scalars(
                select(SessionRow)
                .where(SessionRow.user_id == user_id)
                .order_by(SessionRow.created_at.desc())
                .limit(50)
            )
        )


def organization_for_user(db: DbSession, user_id: str) -> Organization | None:
    membership = db.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user_id))
    return db.get(Organization, membership.organization_id) if membership else None
