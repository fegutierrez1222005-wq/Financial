"""JWT access tokens and opaque refresh tokens.

Access tokens are stateless and short-lived. Refresh tokens are opaque random strings whose
SHA-256 hash is stored in ``sessions``, so a session can be revoked immediately — which a
stateless refresh token cannot be.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from finagent_core.errors import UnauthenticatedError

ALGORITHM = "HS256"
ISSUER = "finagent-lab"


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: str
    session_id: str
    email: str
    is_platform_admin: bool = False
    mfa_satisfied: bool = False
    expires_at: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "sub": self.user_id,
            "sid": self.session_id,
            "email": self.email,
            "adm": self.is_platform_admin,
            "mfa": self.mfa_satisfied,
        }


def create_access_token(claims: AccessTokenClaims, *, secret: str, expires_minutes: int = 30) -> str:
    now = datetime.now(UTC)
    payload = {
        **claims.as_dict(),
        "iss": ISSUER,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> AccessTokenClaims:
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM], issuer=ISSUER)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthenticatedError("access token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthenticatedError("invalid access token") from exc

    if not payload.get("sub") or not payload.get("sid"):
        raise UnauthenticatedError("access token is missing required claims")
    return AccessTokenClaims(
        user_id=str(payload["sub"]),
        session_id=str(payload["sid"]),
        email=str(payload.get("email", "")),
        is_platform_admin=bool(payload.get("adm", False)),
        mfa_satisfied=bool(payload.get("mfa", False)),
        expires_at=(
            datetime.fromtimestamp(payload["exp"], tz=UTC) if payload.get("exp") else None
        ),
    )


def create_refresh_token() -> tuple[str, str]:
    """Return ``(token, sha256_hash)``. Only the hash is persisted."""
    token = secrets.token_urlsafe(48)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_expiry(days: int) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)


def create_invitation_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)
