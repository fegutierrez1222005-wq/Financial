"""Organizations, workspaces, membership, invitations and API keys."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from finagent_api.db.models import ApiKey, Organization, OrganizationMember, User, Workspace
from finagent_api.deps import CurrentPrincipal, Db, WorkspaceContext, require_permission
from finagent_api.rbac import API_KEY_FORBIDDEN, Permission, describe_role, permissions_for
from finagent_api.schemas import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    DemoSeedResponse,
    InviteRequest,
    InviteResponse,
    MemberResponse,
    Message,
    OrganizationResponse,
    RoleChangeRequest,
    RoleDescription,
    WorkspaceCreateRequest,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)
from finagent_api.security.api_keys import generate_api_key
from finagent_api.services import seed_service, workspace_service
from finagent_api.services.audit import AuditAction, record_audit
from finagent_api.settings import get_settings
from finagent_core.errors import ForbiddenError, NotFoundError
from finagent_core.schemas.enums import WorkspaceRole

router = APIRouter(tags=["workspaces"])


def _require_user(principal):  # noqa: ANN001, ANN201
    if principal.user is None:
        raise ForbiddenError("this endpoint requires a user session, not an API key")
    return principal.user


# ----------------------------------------------------------------- organizations


@router.get("/organizations", response_model=list[OrganizationResponse], summary="My organizations")
def list_organizations(db: Db, principal: CurrentPrincipal) -> list[OrganizationResponse]:
    user = _require_user(principal)
    rows = db.scalars(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
        .order_by(Organization.created_at)
    )
    return [OrganizationResponse.model_validate(row) for row in rows]


@router.patch(
    "/organizations/{organization_id}/data-training",
    response_model=OrganizationResponse,
    summary="Set the model-training opt-in for the organization",
)
def set_data_training(
    organization_id: str, opt_in: bool, db: Db, principal: CurrentPrincipal
) -> OrganizationResponse:
    """Off by default. Customer data is isolated and is not used for model training unless
    explicitly authorized here by an owner."""
    user = _require_user(principal)
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    if membership is None:
        raise NotFoundError("organization not found")
    if membership.role != WorkspaceRole.OWNER.value:
        raise ForbiddenError("only an organization owner may change the data-training setting")

    organization = db.get(Organization, organization_id)
    if organization is None:
        raise NotFoundError("organization not found")
    organization.data_training_opt_in = opt_in
    record_audit(
        db,
        action=AuditAction.ORGANIZATION_UPDATED,
        organization_id=organization.id,
        user_id=user.id,
        resource_type="organization",
        resource_id=organization.id,
        metadata={"data_training_opt_in": opt_in},
    )
    db.flush()
    return OrganizationResponse.model_validate(organization)


# --------------------------------------------------------------------- workspaces


@router.get("/workspaces", response_model=list[WorkspaceResponse], summary="My workspaces")
def list_workspaces(db: Db, principal: CurrentPrincipal) -> list[WorkspaceResponse]:
    user = _require_user(principal)
    return [
        WorkspaceResponse.model_validate(workspace).model_copy(update={"role": role.value})
        for workspace, role in workspace_service.list_workspaces_for_user(db, user.id)
    ]


@router.post(
    "/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace",
)
def create_workspace(
    payload: WorkspaceCreateRequest, db: Db, principal: CurrentPrincipal
) -> WorkspaceResponse:
    user = _require_user(principal)
    organization = db.scalar(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
        .order_by(Organization.created_at)
    )
    if organization is None:
        raise NotFoundError("no organization for this user")

    workspace = workspace_service.create_workspace(
        db,
        organization=organization,
        name=payload.name,
        creator=user,
        description=payload.description,
        use_case=payload.use_case,
    )
    if payload.default_information_cutoff:
        workspace.default_information_cutoff = payload.default_information_cutoff
        db.flush()
    return WorkspaceResponse.model_validate(workspace).model_copy(
        update={"role": WorkspaceRole.OWNER.value}
    )


@router.get("/workspaces/current", response_model=WorkspaceResponse, summary="Active workspace")
def current_workspace(
    context: Annotated[WorkspaceContext, Depends(require_permission(Permission.WORKSPACE_READ))],
) -> WorkspaceResponse:
    return WorkspaceResponse.model_validate(context.workspace).model_copy(
        update={"role": context.role.value}
    )


@router.patch("/workspaces/current", response_model=WorkspaceResponse, summary="Update a workspace")
def update_workspace(
    payload: WorkspaceUpdateRequest,
    db: Db,
    context: Annotated[WorkspaceContext, Depends(require_permission(Permission.WORKSPACE_UPDATE))],
) -> WorkspaceResponse:
    workspace = context.workspace
    for field_name in ("name", "description", "use_case", "default_information_cutoff"):
        value = getattr(payload, field_name)
        if value is not None:
            setattr(workspace, field_name, value)
    record_audit(
        db,
        action=AuditAction.WORKSPACE_UPDATED,
        organization_id=context.organization_id,
        workspace_id=workspace.id,
        user_id=context.user_id,
        resource_type="workspace",
        resource_id=workspace.id,
        metadata=payload.model_dump(exclude_none=True, mode="json"),
    )
    db.flush()
    return WorkspaceResponse.model_validate(workspace).model_copy(update={"role": context.role.value})


@router.delete("/workspaces/current", response_model=Message, summary="Delete a workspace")
def delete_workspace(
    db: Db,
    context: Annotated[WorkspaceContext, Depends(require_permission(Permission.WORKSPACE_DELETE))],
) -> Message:
    workspace: Workspace = context.workspace
    workspace.deleted_at = datetime.now(timezone.utc)
    record_audit(
        db,
        action=AuditAction.WORKSPACE_DELETED,
        organization_id=context.organization_id,
        workspace_id=workspace.id,
        user_id=context.user_id,
        resource_type="workspace",
        resource_id=workspace.id,
    )
    db.flush()
    return Message(
        message="Workspace deleted.",
        detail={"retention": "Content is soft-deleted so audit trails and traces remain intact."},
    )


@router.post(
    "/workspaces/demo",
    response_model=DemoSeedResponse,
    summary="Create or refresh the clearly-labelled ACME Technologies demo workspace",
)
def seed_demo(db: Db, principal: CurrentPrincipal) -> DemoSeedResponse:
    user = _require_user(principal)
    organization = db.scalar(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
        .order_by(Organization.created_at)
    )
    if organization is None:
        raise NotFoundError("no organization for this user")
    result = seed_service.seed_demo_workspace(db, organization=organization, user=user)
    return DemoSeedResponse.model_validate(result)


# ----------------------------------------------------------------------- members


@router.get("/workspaces/current/members", response_model=list[MemberResponse], summary="Members")
def list_members(
    db: Db,
    context: Annotated[WorkspaceContext, Depends(require_permission(Permission.MEMBER_READ))],
) -> list[MemberResponse]:
    return [
        MemberResponse(
            id=member.id,
            user_id=member.user_id,
            email=user.email,
            full_name=user.full_name,
            role=member.role,
            created_at=member.created_at,
        )
        for member, user in workspace_service.list_members(db, context.workspace_id)
    ]


@router.post(
    "/workspaces/current/invitations",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a member",
)
def invite_member(
    payload: InviteRequest,
    db: Db,
    context: Annotated[WorkspaceContext, Depends(require_permission(Permission.MEMBER_INVITE))],
) -> InviteResponse:
    user = _require_user(context.principal)
    if payload.role.rank > context.role.rank:
        raise ForbiddenError("you cannot grant a role above your own")

    invitation, token = workspace_service.invite_member(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        email=str(payload.email),
        role=payload.role,
        invited_by=user,
    )
    return InviteResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        invitation_token=token,
        accept_url=f"{get_settings().web_origin}/invitations/accept?token={token}",
    )


@router.patch(
    "/workspaces/current/members/{member_id}",
    response_model=MemberResponse,
    summary="Change a member's role",
)
def change_role(
    member_id: str,
    payload: RoleChangeRequest,
    db: Db,
    context: Annotated[WorkspaceContext, Depends(require_permission(Permission.MEMBER_UPDATE))],
) -> MemberResponse:
    user = _require_user(context.principal)
    member = workspace_service.change_member_role(
        db,
        workspace_id=context.workspace_id,
        member_id=member_id,
        role=payload.role,
        actor=user,
        actor_role=context.role,
    )
    target = db.get(User, member.user_id)
    return MemberResponse(
        id=member.id,
        user_id=member.user_id,
        email=target.email if target else "",
        full_name=target.full_name if target else None,
        role=member.role,
        created_at=member.created_at,
    )


@router.delete(
    "/workspaces/current/members/{member_id}", response_model=Message, summary="Remove a member"
)
def remove_member(
    member_id: str,
    db: Db,
    context: Annotated[WorkspaceContext, Depends(require_permission(Permission.MEMBER_REMOVE))],
) -> Message:
    workspace_service.remove_member(
        db,
        workspace_id=context.workspace_id,
        member_id=member_id,
        actor=_require_user(context.principal),
    )
    return Message(message="Member removed.")


@router.get("/roles", response_model=list[RoleDescription], summary="The permission matrix")
def roles() -> list[RoleDescription]:
    return [RoleDescription.model_validate(describe_role(role)) for role in WorkspaceRole]


# ---------------------------------------------------------------------- api keys


@router.get("/workspaces/current/api-keys", response_model=list[ApiKeyResponse], summary="API keys")
def list_api_keys(
    db: Db,
    context: Annotated[WorkspaceContext, Depends(require_permission(Permission.API_KEY_READ))],
) -> list[ApiKeyResponse]:
    rows = db.scalars(
        select(ApiKey)
        .where(ApiKey.organization_id == context.organization_id)
        .order_by(ApiKey.created_at.desc())
    )
    return [ApiKeyResponse.model_validate(row) for row in rows]


@router.post(
    "/workspaces/current/api-keys",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an API key (plaintext returned once)",
)
def create_api_key(
    payload: ApiKeyCreateRequest,
    db: Db,
    context: Annotated[WorkspaceContext, Depends(require_permission(Permission.API_KEY_WRITE))],
) -> ApiKeyCreatedResponse:
    settings = get_settings()
    generated = generate_api_key("live" if settings.is_production else "test")
    api_key = ApiKey(
        organization_id=context.organization_id,
        workspace_id=context.workspace_id if payload.scope_to_workspace else None,
        created_by_user_id=context.user_id,
        name=payload.name,
        key_prefix=generated.prefix,
        key_hash=generated.key_hash,
        role=payload.role.value,
        scopes=sorted(
            permission.value
            for permission in permissions_for(payload.role)
            if permission not in API_KEY_FORBIDDEN
        ),
        expires_at=(
            datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)
            if payload.expires_in_days
            else None
        ),
    )
    db.add(api_key)
    db.flush()
    record_audit(
        db,
        action=AuditAction.API_KEY_CREATED,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=context.user_id,
        resource_type="api_key",
        resource_id=api_key.id,
        metadata={"name": payload.name, "role": payload.role.value},
    )
    return ApiKeyCreatedResponse.model_validate(api_key).model_copy(
        update={"plaintext_key": generated.plaintext}
    )


@router.delete(
    "/workspaces/current/api-keys/{api_key_id}", response_model=Message, summary="Revoke an API key"
)
def revoke_api_key(
    api_key_id: str,
    db: Db,
    context: Annotated[WorkspaceContext, Depends(require_permission(Permission.API_KEY_WRITE))],
) -> Message:
    api_key = db.get(ApiKey, api_key_id)
    if api_key is None or api_key.organization_id != context.organization_id:
        raise NotFoundError("api key not found")
    api_key.revoked_at = datetime.now(timezone.utc)
    record_audit(
        db,
        action=AuditAction.API_KEY_REVOKED,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=context.user_id,
        resource_type="api_key",
        resource_id=api_key.id,
    )
    db.flush()
    return Message(message="API key revoked.")
