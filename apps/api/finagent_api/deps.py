"""FastAPI dependencies: authentication, tenancy resolution and authorisation.

Two credential types are supported — a session access token (browser) and an API key
(automation). Both resolve to a :class:`Principal`, and every tenant-scoped route resolves a
:class:`WorkspaceContext` whose role drives the RBAC check. Routes never read the raw
credential.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import ApiKey, Organization, User, Workspace, WorkspaceMember
from finagent_api.db.session import get_db
from finagent_api.middleware import Bucket, get_rate_limiter
from finagent_api.rbac import Permission, assert_permission, permissions_for
from finagent_api.security.api_keys import hash_api_key, looks_like_api_key
from finagent_api.security.tokens import decode_access_token
from finagent_api.settings import Settings, get_settings
from finagent_core.errors import ForbiddenError, NotFoundError, RateLimitedError, UnauthenticatedError
from finagent_core.logging import bind_context, get_logger
from finagent_core.schemas.enums import WorkspaceRole

logger = get_logger(__name__)


@dataclass
class Principal:
    """Authenticated caller: a user session or an API key."""

    user: User | None = None
    api_key: ApiKey | None = None
    session_id: str | None = None
    organization_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    mfa_satisfied: bool = False

    @property
    def via_api_key(self) -> bool:
        return self.api_key is not None

    @property
    def user_id(self) -> str | None:
        return self.user.id if self.user else None

    @property
    def is_platform_admin(self) -> bool:
        return bool(self.user and self.user.is_platform_admin)

    @property
    def label(self) -> str:
        if self.user:
            return self.user.email
        if self.api_key:
            return f"api_key:{self.api_key.key_prefix}"
        return "anonymous"


@dataclass
class WorkspaceContext:
    workspace: Workspace
    role: WorkspaceRole
    principal: Principal
    organization: Organization | None = None
    permissions: frozenset[Permission] = field(default_factory=frozenset)

    @property
    def workspace_id(self) -> str:
        return self.workspace.id

    @property
    def organization_id(self) -> str:
        return self.workspace.organization_id

    @property
    def user_id(self) -> str | None:
        return self.principal.user_id

    def require(self, permission: Permission) -> None:
        assert_permission(self.role, permission, via_api_key=self.principal.via_api_key)

    def can(self, permission: Permission) -> bool:
        from finagent_api.rbac import has_permission

        return has_permission(self.role, permission, via_api_key=self.principal.via_api_key)


def get_current_principal(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> Principal:
    settings = get_settings()
    raw_key = x_api_key or _bearer_api_key(authorization)
    if raw_key:
        principal = _principal_from_api_key(raw_key, db, settings)
    elif authorization and authorization.lower().startswith("bearer "):
        principal = _principal_from_access_token(authorization.split(" ", 1)[1], db, settings)
    else:
        raise UnauthenticatedError("no credentials supplied")

    principal.ip_address = request.client.host if request.client else None
    principal.user_agent = request.headers.get("user-agent")
    principal.request_id = getattr(request.state, "request_id", None)
    bind_context(
        user_id=principal.user_id,
        api_key_id=principal.api_key.id if principal.api_key else None,
        organization_id=principal.organization_id,
    )
    return principal


def _bearer_api_key(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    candidate = parts[1] if len(parts) == 2 else parts[0]
    return candidate if looks_like_api_key(candidate) else None


def _principal_from_access_token(token: str, db: DbSession, settings: Settings) -> Principal:
    from finagent_api.db.models import Session as SessionRow

    claims = decode_access_token(token, secret=settings.secret_key)
    session_row = db.get(SessionRow, claims.session_id)
    if session_row is None or session_row.revoked_at is not None:
        raise UnauthenticatedError("session is no longer valid")
    if session_row.expires_at <= datetime.now(UTC):
        raise UnauthenticatedError("session expired")

    user = db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise UnauthenticatedError("user is inactive")
    if settings.require_mfa_for_admins and user.is_platform_admin and not claims.mfa_satisfied:
        raise ForbiddenError("multi-factor authentication is required for administrators")

    return Principal(user=user, session_id=session_row.id, mfa_satisfied=claims.mfa_satisfied)


def _principal_from_api_key(raw_key: str, db: DbSession, settings: Settings) -> Principal:
    api_key = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw_key)))
    if api_key is None or api_key.revoked_at is not None:
        raise UnauthenticatedError("invalid api key")
    now = datetime.now(UTC)
    if api_key.expires_at and api_key.expires_at <= now:
        raise UnauthenticatedError("api key expired")

    allowed, _ = get_rate_limiter().check(
        f"apikey:{api_key.id}", Bucket(limit=settings.rate_limit_per_api_key_per_minute)
    )
    if not allowed:
        raise RateLimitedError("api key rate limit exceeded")

    api_key.last_used_at = now
    db.flush()
    return Principal(api_key=api_key, organization_id=api_key.organization_id)


def get_workspace_context(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[DbSession, Depends(get_db)],
    workspace_id: Annotated[str | None, Query(description="Target workspace id.")] = None,
    x_workspace_id: Annotated[str | None, Header()] = None,
) -> WorkspaceContext:
    """Resolve the active workspace and the caller's role in it.

    Cross-tenant access is reported as ``404`` rather than ``403`` so an attacker cannot use
    the response to confirm that a workspace exists.
    """
    resolved_id = workspace_id or x_workspace_id
    if not resolved_id and principal.api_key and principal.api_key.workspace_id:
        resolved_id = principal.api_key.workspace_id
    if not resolved_id:
        raise NotFoundError("no workspace specified (pass workspace_id or X-Workspace-Id)")

    workspace = db.get(Workspace, resolved_id)
    if workspace is None or workspace.deleted_at is not None:
        raise NotFoundError("workspace not found")

    if principal.via_api_key:
        assert principal.api_key is not None
        if principal.api_key.organization_id != workspace.organization_id or (
            principal.api_key.workspace_id and principal.api_key.workspace_id != workspace.id
        ):
            logger.warning(
                "cross_tenant_api_key_attempt",
                extra={"workspace_id": resolved_id, "api_key_id": principal.api_key.id},
            )
            raise NotFoundError("workspace not found")
        role = WorkspaceRole(principal.api_key.role)
    else:
        membership = db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.user_id == principal.user_id,
            )
        )
        if membership is None:
            if principal.is_platform_admin:
                # Platform admins may read any workspace; the access is audited.
                role = WorkspaceRole.VIEWER
                logger.info(
                    "platform_admin_workspace_access",
                    extra={"workspace_id": workspace.id, "user_id": principal.user_id},
                )
            else:
                logger.warning(
                    "cross_tenant_access_denied",
                    extra={"workspace_id": resolved_id, "user_id": principal.user_id},
                )
                raise NotFoundError("workspace not found")
        else:
            role = WorkspaceRole(membership.role)

    bind_context(workspace_id=workspace.id, organization_id=workspace.organization_id)
    return WorkspaceContext(
        workspace=workspace,
        role=role,
        principal=principal,
        organization=db.get(Organization, workspace.organization_id),
        permissions=permissions_for(role),
    )


def require_permission(permission: Permission) -> Callable[..., WorkspaceContext]:
    """Dependency factory: resolve the workspace and assert one permission."""

    def dependency(
        context: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    ) -> WorkspaceContext:
        context.require(permission)
        return context

    return dependency


def require_platform_admin(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Principal:
    if not principal.is_platform_admin:
        raise ForbiddenError("platform administrator access required")
    return principal


def expensive_operation_guard(
    context: Annotated[WorkspaceContext, Depends(get_workspace_context)],
) -> WorkspaceContext:
    """Stricter limit for endpoints that spend money (model calls, backtests)."""
    settings = get_settings()
    identity = context.principal.user_id or (
        context.principal.api_key.id if context.principal.api_key else "anonymous"
    )
    allowed, _ = get_rate_limiter().check(
        f"expensive:{identity}", Bucket(limit=settings.rate_limit_expensive_per_minute)
    )
    if not allowed:
        raise RateLimitedError(
            "too many expensive operations",
            details={"limit_per_minute": settings.rate_limit_expensive_per_minute},
        )
    allowed_workspace, _ = get_rate_limiter().check(
        f"workspace:{context.workspace_id}",
        Bucket(limit=settings.rate_limit_per_workspace_per_minute),
    )
    if not allowed_workspace:
        raise RateLimitedError("workspace rate limit exceeded")
    return context


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]
CurrentWorkspace = Annotated[WorkspaceContext, Depends(get_workspace_context)]
Db = Annotated[DbSession, Depends(get_db)]
