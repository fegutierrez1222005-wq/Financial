"""Role-based access control.

Permissions are declared once here as a matrix, so a reviewer can see the entire
authorisation surface in one place and every router states the permission it needs rather
than re-deriving role logic.
"""

from __future__ import annotations

from enum import StrEnum

from finagent_core.errors import ForbiddenError
from finagent_core.schemas.enums import WorkspaceRole


class Permission(StrEnum):
    # Workspace administration
    WORKSPACE_READ = "workspace:read"
    WORKSPACE_UPDATE = "workspace:update"
    WORKSPACE_DELETE = "workspace:delete"
    MEMBER_READ = "member:read"
    MEMBER_INVITE = "member:invite"
    MEMBER_UPDATE = "member:update"
    MEMBER_REMOVE = "member:remove"

    # Agents and prompts
    AGENT_READ = "agent:read"
    AGENT_CREATE = "agent:create"
    AGENT_UPDATE = "agent:update"
    AGENT_DELETE = "agent:delete"
    AGENT_RUN = "agent:run"

    # Data
    DOCUMENT_READ = "document:read"
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_DELETE = "document:delete"
    DATASET_READ = "dataset:read"
    DATASET_WRITE = "dataset:write"
    DATA_SOURCE_READ = "data_source:read"
    DATA_SOURCE_WRITE = "data_source:write"

    # Research
    RESEARCH_READ = "research:read"
    RESEARCH_CREATE = "research:create"

    # Evaluation
    EVALUATION_READ = "evaluation:read"
    EVALUATION_RUN = "evaluation:run"
    EVALUATION_SUITE_WRITE = "evaluation_suite:write"

    # Backtesting
    BACKTEST_READ = "backtest:read"
    BACKTEST_RUN = "backtest:run"

    # Experiments and benchmarks
    EXPERIMENT_READ = "experiment:read"
    EXPERIMENT_WRITE = "experiment:write"
    BENCHMARK_READ = "benchmark:read"
    BENCHMARK_WRITE = "benchmark:write"

    # Platform
    USAGE_READ = "usage:read"
    AUDIT_READ = "audit:read"
    API_KEY_READ = "api_key:read"
    API_KEY_WRITE = "api_key:write"
    WEBHOOK_READ = "webhook:read"
    WEBHOOK_WRITE = "webhook:write"
    BILLING_READ = "billing:read"
    BILLING_WRITE = "billing:write"
    SECURITY_READ = "security:read"
    SECURITY_WRITE = "security:write"


_VIEWER: frozenset[Permission] = frozenset(
    {
        Permission.WORKSPACE_READ,
        Permission.MEMBER_READ,
        Permission.AGENT_READ,
        Permission.DOCUMENT_READ,
        Permission.DATASET_READ,
        Permission.DATA_SOURCE_READ,
        Permission.RESEARCH_READ,
        Permission.EVALUATION_READ,
        Permission.BACKTEST_READ,
        Permission.EXPERIMENT_READ,
        Permission.BENCHMARK_READ,
        Permission.USAGE_READ,
    }
)

_RESEARCHER: frozenset[Permission] = _VIEWER | frozenset(
    {
        Permission.AGENT_CREATE,
        Permission.AGENT_UPDATE,
        Permission.AGENT_RUN,
        Permission.DOCUMENT_UPLOAD,
        Permission.DATASET_WRITE,
        Permission.RESEARCH_CREATE,
        Permission.EVALUATION_RUN,
        Permission.EVALUATION_SUITE_WRITE,
        Permission.BACKTEST_RUN,
        Permission.EXPERIMENT_WRITE,
        Permission.BENCHMARK_WRITE,
    }
)

_ADMIN: frozenset[Permission] = _RESEARCHER | frozenset(
    {
        Permission.WORKSPACE_UPDATE,
        Permission.MEMBER_INVITE,
        Permission.MEMBER_UPDATE,
        Permission.MEMBER_REMOVE,
        Permission.AGENT_DELETE,
        Permission.DOCUMENT_DELETE,
        Permission.DATA_SOURCE_WRITE,
        Permission.AUDIT_READ,
        Permission.API_KEY_READ,
        Permission.API_KEY_WRITE,
        Permission.WEBHOOK_READ,
        Permission.WEBHOOK_WRITE,
        Permission.BILLING_READ,
        Permission.SECURITY_READ,
        Permission.SECURITY_WRITE,
    }
)

_OWNER: frozenset[Permission] = _ADMIN | frozenset(
    {Permission.WORKSPACE_DELETE, Permission.BILLING_WRITE}
)

ROLE_PERMISSIONS: dict[WorkspaceRole, frozenset[Permission]] = {
    WorkspaceRole.VIEWER: _VIEWER,
    WorkspaceRole.RESEARCHER: _RESEARCHER,
    WorkspaceRole.ADMIN: _ADMIN,
    WorkspaceRole.OWNER: _OWNER,
}

#: Permissions an API key may never exercise. Keys are for automation, not administration.
API_KEY_FORBIDDEN: frozenset[Permission] = frozenset(
    {
        Permission.API_KEY_WRITE,
        Permission.MEMBER_INVITE,
        Permission.MEMBER_UPDATE,
        Permission.MEMBER_REMOVE,
        Permission.WORKSPACE_DELETE,
        Permission.BILLING_WRITE,
        Permission.SECURITY_WRITE,
    }
)


def permissions_for(role: WorkspaceRole | str) -> frozenset[Permission]:
    resolved = WorkspaceRole(role) if isinstance(role, str) else role
    return ROLE_PERMISSIONS.get(resolved, _VIEWER)


def has_permission(
    role: WorkspaceRole | str, permission: Permission, *, via_api_key: bool = False
) -> bool:
    if via_api_key and permission in API_KEY_FORBIDDEN:
        return False
    return permission in permissions_for(role)


def assert_permission(
    role: WorkspaceRole | str, permission: Permission, *, via_api_key: bool = False
) -> None:
    if not has_permission(role, permission, via_api_key=via_api_key):
        raise ForbiddenError(
            f"role {role} lacks {permission.value}",
            details={"required_permission": permission.value, "role": str(role)},
        )


def describe_role(role: WorkspaceRole | str) -> dict[str, object]:
    resolved = WorkspaceRole(role) if isinstance(role, str) else role
    return {
        "role": resolved.value,
        "rank": resolved.rank,
        "permissions": sorted(permission.value for permission in permissions_for(resolved)),
    }
