"""Authentication, session management and MFA."""

from __future__ import annotations


from fastapi import APIRouter, Request, status

from finagent_api.deps import CurrentPrincipal, Db
from finagent_api.schemas import (
    AcceptInviteRequest,
    ChangePasswordRequest,
    LoginRequest,
    MemberResponse,
    Message,
    MfaConfirmRequest,
    MfaDisableRequest,
    MfaEnrolResponse,
    RefreshRequest,
    RegisterRequest,
    SessionResponse,
    TokenResponse,
    UserResponse,
)
from finagent_api.db.models import User
from finagent_api.security.auth_provider import AuthenticatedIdentity, OAuthRegistry
from finagent_api.services import seed_service, workspace_service
from finagent_api.services.auth_service import (
    CredentialAuthProvider,
    RequestMetadata,
    organization_for_user,
)
from finagent_api.settings import get_settings
from finagent_core.errors import ForbiddenError
from finagent_core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_user(principal) -> User:  # noqa: ANN001
    """These endpoints act on a human account; an API key is not an acceptable credential."""
    if principal.user is None:
        raise ForbiddenError("this endpoint requires a user session, not an API key")
    return principal.user


def _metadata(request: Request) -> RequestMetadata:
    return RequestMetadata(
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )


def _provider(db, request: Request) -> CredentialAuthProvider:  # noqa: ANN001
    return CredentialAuthProvider(db, settings=get_settings(), metadata=_metadata(request))


def _token_response(identity: AuthenticatedIdentity, organization_id: str | None) -> TokenResponse:
    settings = get_settings()
    return TokenResponse(
        access_token=identity.access_token,
        refresh_token=identity.refresh_token or "",
        expires_in=settings.access_token_minutes * 60,
        user_id=identity.user_id,
        organization_id=organization_id or identity.detail.get("organization_id"),
        mfa_satisfied=identity.mfa_satisfied,
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account, its organization and an optional demo workspace",
)
def register(payload: RegisterRequest, request: Request, db: Db) -> TokenResponse:
    provider = _provider(db, request)
    user = provider.register(
        email=str(payload.email), password=payload.password, full_name=payload.full_name
    )
    organization = workspace_service.create_organization(
        db,
        name=payload.organization_name or f"{payload.full_name or user.email.split('@')[0]}'s org",
        owner=user,
    )
    if payload.seed_demo_workspace:
        seed_service.seed_demo_workspace(db, organization=organization, user=user)

    identity = provider.authenticate_password(str(payload.email), payload.password)
    return _token_response(identity, organization.id)


@router.post("/login", response_model=TokenResponse, summary="Exchange credentials for tokens")
def login(payload: LoginRequest, request: Request, db: Db) -> TokenResponse:
    provider = _provider(db, request)
    identity = provider.authenticate_password(
        str(payload.email), payload.password, mfa_code=payload.mfa_code
    )
    org = organization_for_user(db, identity.user_id)
    return _token_response(identity, org.id if org else None)


@router.post("/refresh", response_model=TokenResponse, summary="Rotate a refresh token")
def refresh(payload: RefreshRequest, request: Request, db: Db) -> TokenResponse:
    identity = _provider(db, request).refresh(payload.refresh_token)
    org = organization_for_user(db, identity.user_id)
    return _token_response(identity, org.id if org else None)


@router.post("/logout", response_model=Message, summary="Revoke one refresh session")
def logout(payload: RefreshRequest, request: Request, db: Db) -> Message:
    _provider(db, request).revoke(payload.refresh_token)
    return Message(message="Signed out.")


@router.post("/logout-all", response_model=Message, summary="Revoke every session for the user")
def logout_all(request: Request, db: Db, principal: CurrentPrincipal) -> Message:
    if principal.user_id is None:
        return Message(message="Nothing to revoke.")
    count = _provider(db, request).revoke_all_sessions(principal.user_id)
    return Message(message=f"Revoked {count} session(s).", detail={"revoked": count})


@router.get("/me", response_model=UserResponse, summary="The authenticated user")
def me(principal: CurrentPrincipal) -> UserResponse:
    return UserResponse.model_validate(_require_user(principal))


@router.get("/sessions", response_model=list[SessionResponse], summary="Active sessions")
def sessions(request: Request, db: Db, principal: CurrentPrincipal) -> list[SessionResponse]:
    if principal.user_id is None:
        return []
    rows = _provider(db, request).list_sessions(principal.user_id)
    return [SessionResponse.model_validate(row) for row in rows]


@router.delete("/sessions/{session_id}", response_model=Message, summary="Revoke one session")
def revoke_session(
    session_id: str, request: Request, db: Db, principal: CurrentPrincipal
) -> Message:
    if principal.user_id is not None:
        _provider(db, request).revoke_session(session_id, user_id=principal.user_id)
    return Message(message="Session revoked.")


@router.post("/change-password", response_model=Message, summary="Change the account password")
def change_password(
    payload: ChangePasswordRequest, request: Request, db: Db, principal: CurrentPrincipal
) -> Message:
    _provider(db, request).change_password(
        _require_user(principal), payload.current_password, payload.new_password
    )
    return Message(message="Password changed. Other sessions were signed out.")


@router.post("/mfa/enrol", response_model=MfaEnrolResponse, summary="Begin TOTP enrolment")
def begin_mfa(request: Request, db: Db, principal: CurrentPrincipal) -> MfaEnrolResponse:
    enrolment = _provider(db, request).begin_mfa_enrolment(_require_user(principal))
    return MfaEnrolResponse.model_validate(enrolment)


@router.post("/mfa/confirm", response_model=Message, summary="Confirm TOTP enrolment")
def confirm_mfa(
    payload: MfaConfirmRequest, request: Request, db: Db, principal: CurrentPrincipal
) -> Message:
    _provider(db, request).confirm_mfa(_require_user(principal), payload.code)
    return Message(message="Multi-factor authentication is enabled.")


@router.post("/mfa/disable", response_model=Message, summary="Disable TOTP")
def disable_mfa(
    payload: MfaDisableRequest, request: Request, db: Db, principal: CurrentPrincipal
) -> Message:
    _provider(db, request).disable_mfa(_require_user(principal), payload.password)
    return Message(message="Multi-factor authentication is disabled.")


@router.post(
    "/invitations/accept", response_model=MemberResponse, summary="Accept a workspace invitation"
)
def accept_invitation(
    payload: AcceptInviteRequest, db: Db, principal: CurrentPrincipal
) -> MemberResponse:
    user = _require_user(principal)
    member = workspace_service.accept_invitation(db, token=payload.token, user=user)
    return MemberResponse(
        id=member.id,
        user_id=member.user_id,
        email=user.email,
        full_name=user.full_name,
        role=member.role,
        created_at=member.created_at,
    )


@router.get("/providers", summary="Which sign-in methods are configured")
def auth_providers() -> dict[str, object]:
    registry = OAuthRegistry(get_settings())
    return {
        "password": {"key": "password", "configured": True, "status": "available"},
        "oauth": registry.describe(),
        "note": (
            "Providers reporting configured=false have no client credentials in this "
            "deployment and are not offered at sign-in."
        ),
    }
