"""Organizations, workspaces, membership and invitations."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import (
    Invitation,
    Organization,
    OrganizationMember,
    Subscription,
    User,
    Workspace,
    WorkspaceMember,
)
from finagent_api.security.tokens import create_invitation_token, hash_token
from finagent_api.services.audit import AuditAction, record_audit
from finagent_api.settings import get_settings
from finagent_core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from finagent_core.logging import get_logger
from finagent_core.schemas.enums import WorkspaceRole

logger = get_logger(__name__)

INVITATION_TTL_DAYS = 14
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", (value or "").strip().lower()).strip("-")
    return slug[:60] or "workspace"


def unique_slug(db: DbSession, base: str, *, organization_id: str | None = None) -> str:
    slug = candidate = slugify(base)
    suffix = 2
    while True:
        exists = (
            db.scalar(select(Organization).where(Organization.slug == candidate))
            if organization_id is None
            else db.scalar(
                select(Workspace).where(
                    Workspace.organization_id == organization_id, Workspace.slug == candidate
                )
            )
        )
        if exists is None:
            return candidate
        candidate = f"{slug}-{suffix}"
        suffix += 1


def create_organization(
    db: DbSession, *, name: str, owner: User, plan: str | None = None
) -> Organization:
    settings = get_settings()
    if not (name or "").strip():
        raise ValidationFailedError("organization name is required")

    organization = Organization(
        name=name.strip(),
        slug=unique_slug(db, name),
        plan=plan or settings.default_plan,
        data_training_opt_in=False,
    )
    db.add(organization)
    db.flush()

    db.add(
        OrganizationMember(
            organization_id=organization.id, user_id=owner.id, role=WorkspaceRole.OWNER.value
        )
    )
    now = datetime.now(UTC)
    db.add(
        Subscription(
            organization_id=organization.id,
            plan=organization.plan,
            status="trialing" if organization.plan == "trial" else "active",
            seats=3,
            research_run_limit=settings.trial_research_run_limit,
            evaluation_limit=settings.trial_evaluation_limit,
            trial_ends_at=now + timedelta(days=14) if organization.plan == "trial" else None,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            features={
                "sso": False,
                "private_deployment": False,
                "custom_evaluation_suites": True,
                "audit_log_export": organization.plan != "trial",
            },
        )
    )
    db.flush()
    record_audit(
        db,
        action=AuditAction.ORGANIZATION_CREATED,
        organization_id=organization.id,
        user_id=owner.id,
        resource_type="organization",
        resource_id=organization.id,
        metadata={"plan": organization.plan},
    )
    return organization


def create_workspace(
    db: DbSession,
    *,
    organization: Organization,
    name: str,
    creator: User,
    description: str | None = None,
    use_case: str | None = None,
    role: WorkspaceRole = WorkspaceRole.OWNER,
    is_demo: bool = False,
) -> Workspace:
    if not (name or "").strip():
        raise ValidationFailedError("workspace name is required")

    workspace = Workspace(
        organization_id=organization.id,
        name=name.strip(),
        slug=unique_slug(db, name, organization_id=organization.id),
        description=(description or "").strip() or None,
        use_case=use_case,
        is_demo=is_demo,
        settings={"created_by": creator.id},
    )
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            organization_id=organization.id,
            user_id=creator.id,
            role=role.value,
        )
    )
    db.flush()
    record_audit(
        db,
        action=AuditAction.WORKSPACE_CREATED,
        organization_id=organization.id,
        workspace_id=workspace.id,
        user_id=creator.id,
        resource_type="workspace",
        resource_id=workspace.id,
        metadata={"use_case": use_case, "is_demo": is_demo},
    )
    return workspace


def list_workspaces_for_user(db: DbSession, user_id: str) -> list[tuple[Workspace, WorkspaceRole]]:
    rows = db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
        .order_by(Workspace.created_at.asc())
    )
    return [(workspace, WorkspaceRole(role)) for workspace, role in rows]


def list_members(db: DbSession, workspace_id: str) -> list[tuple[WorkspaceMember, User]]:
    return list(
        db.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(User.email.asc())
        )
    )


def seat_usage(db: DbSession, organization_id: str) -> tuple[int, int]:
    """Return ``(used_seats, seat_limit)``."""
    used = db.scalar(
        select(func.count(func.distinct(OrganizationMember.user_id))).where(
            OrganizationMember.organization_id == organization_id
        )
    )
    subscription = db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    return int(used or 0), int(subscription.seats if subscription else 0)


def invite_member(
    db: DbSession,
    *,
    organization_id: str,
    workspace_id: str,
    email: str,
    role: WorkspaceRole,
    invited_by: User,
) -> tuple[Invitation, str]:
    normalised = (email or "").strip().lower()
    if "@" not in normalised:
        raise ValidationFailedError("a valid email address is required")

    used, limit = seat_usage(db, organization_id)
    if limit and used >= limit:
        raise ForbiddenError(
            "seat limit reached for this plan", details={"used_seats": used, "seat_limit": limit}
        )

    existing_user = db.scalar(select(User).where(User.email == normalised))
    if existing_user is not None:
        already = db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == existing_user.id,
            )
        )
        if already is not None:
            raise ConflictError("this user is already a member of the workspace")

    token, token_hash = create_invitation_token()
    invitation = Invitation(
        organization_id=organization_id,
        workspace_id=workspace_id,
        email=normalised,
        role=role.value,
        token_hash=token_hash,
        invited_by_user_id=invited_by.id,
        expires_at=datetime.now(UTC) + timedelta(days=INVITATION_TTL_DAYS),
    )
    db.add(invitation)
    db.flush()
    record_audit(
        db,
        action=AuditAction.MEMBER_INVITED,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=invited_by.id,
        resource_type="invitation",
        resource_id=invitation.id,
        metadata={"email": normalised, "role": role.value},
    )
    return invitation, token


def accept_invitation(db: DbSession, *, token: str, user: User) -> WorkspaceMember:
    invitation = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    now = datetime.now(UTC)
    if invitation is None or invitation.revoked_at is not None:
        raise NotFoundError("invitation not found")
    if invitation.accepted_at is not None:
        raise ConflictError("this invitation has already been used")
    if invitation.expires_at <= now:
        raise ValidationFailedError("this invitation has expired")
    if invitation.email.lower() != user.email.lower():
        raise ForbiddenError("this invitation was issued to a different email address")

    if (
        db.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == invitation.organization_id,
                OrganizationMember.user_id == user.id,
            )
        )
        is None
    ):
        db.add(
            OrganizationMember(
                organization_id=invitation.organization_id, user_id=user.id, role=invitation.role
            )
        )

    member = WorkspaceMember(
        workspace_id=invitation.workspace_id,
        organization_id=invitation.organization_id,
        user_id=user.id,
        role=invitation.role,
        invited_by_user_id=invitation.invited_by_user_id,
    )
    db.add(member)
    invitation.accepted_at = now
    db.flush()
    record_audit(
        db,
        action=AuditAction.MEMBER_ADDED,
        organization_id=invitation.organization_id,
        workspace_id=invitation.workspace_id,
        user_id=user.id,
        resource_type="workspace_member",
        resource_id=member.id,
        metadata={"role": invitation.role},
    )
    return member


def change_member_role(
    db: DbSession,
    *,
    workspace_id: str,
    member_id: str,
    role: WorkspaceRole,
    actor: User,
    actor_role: WorkspaceRole,
) -> WorkspaceMember:
    member = db.get(WorkspaceMember, member_id)
    if member is None or member.workspace_id != workspace_id:
        raise NotFoundError("member not found")
    if role.rank > actor_role.rank:
        raise ForbiddenError("you cannot grant a role higher than your own")
    if member.role == WorkspaceRole.OWNER.value and role != WorkspaceRole.OWNER:
        _require_remaining_owner(db, workspace_id=workspace_id, member_id=member.id)

    previous = member.role
    member.role = role.value
    db.flush()
    record_audit(
        db,
        action=AuditAction.MEMBER_ROLE_CHANGED,
        organization_id=member.organization_id,
        workspace_id=workspace_id,
        user_id=actor.id,
        resource_type="workspace_member",
        resource_id=member.id,
        metadata={"from": previous, "to": role.value, "target_user_id": member.user_id},
    )
    return member


def remove_member(db: DbSession, *, workspace_id: str, member_id: str, actor: User) -> None:
    member = db.get(WorkspaceMember, member_id)
    if member is None or member.workspace_id != workspace_id:
        raise NotFoundError("member not found")
    if member.role == WorkspaceRole.OWNER.value:
        _require_remaining_owner(db, workspace_id=workspace_id, member_id=member.id)

    organization_id, user_id = member.organization_id, member.user_id
    db.delete(member)
    db.flush()
    record_audit(
        db,
        action=AuditAction.MEMBER_REMOVED,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=actor.id,
        resource_type="workspace_member",
        resource_id=member_id,
        metadata={"target_user_id": user_id},
    )


def _require_remaining_owner(db: DbSession, *, workspace_id: str, member_id: str) -> None:
    remaining = db.scalar(
        select(func.count(WorkspaceMember.id)).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role == WorkspaceRole.OWNER.value,
            WorkspaceMember.id != member_id,
        )
    )
    if not remaining:
        raise ValidationFailedError("a workspace must retain at least one owner")
