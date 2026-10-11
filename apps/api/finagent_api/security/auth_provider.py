"""Authentication provider seam.

The built-in provider handles email/password with revocable refresh sessions and TOTP MFA.
An enterprise deployment can swap in Auth0/Clerk/WorkOS/Okta by implementing
:class:`AuthProvider` — routers depend on this protocol, not on the credential tables.

OAuth/SSO adapters are declared here and report ``configured=False`` without client
credentials, so the login page can honestly show which methods are available.
"""

from __future__ import annotations

import abc
import os
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from finagent_api.settings import Settings


@dataclass
class AuthenticatedIdentity:
    """Provider-agnostic result of a successful authentication."""

    user_id: str
    email: str
    session_id: str
    access_token: str
    refresh_token: str | None = None
    mfa_required: bool = False
    mfa_satisfied: bool = False
    detail: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AuthProvider(Protocol):
    key: str

    def authenticate_password(
        self, email: str, password: str, *, mfa_code: str | None = None
    ) -> AuthenticatedIdentity: ...

    def refresh(self, refresh_token: str) -> AuthenticatedIdentity: ...

    def revoke(self, refresh_token: str) -> None: ...


@dataclass(frozen=True)
class OAuthProviderConfig:
    key: str
    display_name: str
    authorize_url: str
    token_url: str
    scopes: tuple[str, ...]
    client_id: str | None = None
    client_secret: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "configured": self.configured,
            "status": "available" if self.configured else "unavailable",
            "scopes": list(self.scopes),
        }


class OAuthRegistry:
    """Declared OAuth providers and their availability."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._providers = {
            "google": OAuthProviderConfig(
                key="google",
                display_name="Google Workspace",
                authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
                token_url="https://oauth2.googleapis.com/token",
                scopes=("openid", "email", "profile"),
                client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
            ),
            "microsoft": OAuthProviderConfig(
                key="microsoft",
                display_name="Microsoft Entra ID",
                authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
                token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
                scopes=("openid", "email", "profile"),
                client_id=os.getenv("MICROSOFT_OAUTH_CLIENT_ID"),
                client_secret=os.getenv("MICROSOFT_OAUTH_CLIENT_SECRET"),
            ),
            "okta": OAuthProviderConfig(
                key="okta",
                display_name="Okta (SAML/OIDC)",
                authorize_url=os.getenv("OKTA_AUTHORIZE_URL", ""),
                token_url=os.getenv("OKTA_TOKEN_URL", ""),
                scopes=("openid", "email", "profile"),
                client_id=os.getenv("OKTA_CLIENT_ID"),
                client_secret=os.getenv("OKTA_CLIENT_SECRET"),
            ),
        }

    def describe(self) -> list[dict[str, Any]]:
        return [config.describe() for config in self._providers.values()]

    def get(self, key: str) -> OAuthProviderConfig | None:
        return self._providers.get(key)

    def available(self) -> list[str]:
        return [key for key, config in self._providers.items() if config.configured]


class BaseAuthProvider(abc.ABC):
    """Convenience base so implementations only override what they need."""

    key = "abstract"

    @abc.abstractmethod
    def authenticate_password(
        self, email: str, password: str, *, mfa_code: str | None = None
    ) -> AuthenticatedIdentity: ...

    @abc.abstractmethod
    def refresh(self, refresh_token: str) -> AuthenticatedIdentity: ...

    @abc.abstractmethod
    def revoke(self, refresh_token: str) -> None: ...
