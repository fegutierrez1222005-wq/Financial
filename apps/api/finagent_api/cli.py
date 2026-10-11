"""Operator CLI.

    python -m finagent_api.cli init-db
    python -m finagent_api.cli create-admin --email ops@example.com
    python -m finagent_api.cli seed-demo --email demo@finagent.local
    python -m finagent_api.cli demo-flow
    python -m finagent_api.cli check-config
    python -m finagent_api.cli routes
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from finagent_api.db.session import create_all, session_scope
from finagent_api.security.passwords import generate_password
from finagent_api.settings import get_settings
from finagent_core.logging import configure_logging, get_logger

logger = get_logger(__name__)


def _json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, default=str))


def init_db(_args: argparse.Namespace) -> int:
    """Create tables directly. Production deployments use Alembic instead."""
    settings = get_settings()
    if settings.is_production:
        print("Refusing to create tables directly in production. Run 'alembic upgrade head'.")
        return 1
    create_all()
    _json({"status": "ok", "database_url": settings.database_url.split("@")[-1]})
    return 0


def create_admin(args: argparse.Namespace) -> int:
    from finagent_api.services import workspace_service
    from finagent_api.services.auth_service import CredentialAuthProvider

    password = args.password or generate_password()
    with session_scope() as db:
        provider = CredentialAuthProvider(db)
        user = provider.register(
            email=args.email,
            password=password,
            full_name=args.name,
            is_platform_admin=True,
        )
        organization = workspace_service.create_organization(
            db, name=args.organization or f"{args.email.split('@')[0]} org", owner=user
        )
        _json(
            {
                "user_id": user.id,
                "email": user.email,
                "organization_id": organization.id,
                "password": None if args.password else password,
                "note": (
                    "Password shown once because it was generated. Store it now."
                    if not args.password
                    else "Password supplied by the operator."
                ),
            }
        )
    return 0


def seed_demo(args: argparse.Namespace) -> int:
    from finagent_api.db.models import Organization, OrganizationMember, User
    from finagent_api.services import seed_service, workspace_service
    from finagent_api.services.auth_service import CredentialAuthProvider

    with session_scope() as db:
        user = db.query(User).filter(User.email == args.email).one_or_none()
        if user is None:
            password = args.password or generate_password()
            user = CredentialAuthProvider(db).register(
                email=args.email, password=password, full_name="Demo Analyst"
            )
            organization = workspace_service.create_organization(
                db, name="Demo Capital Partners", owner=user
            )
            print(f"Created user {args.email} with password: {password}", file=sys.stderr)
        else:
            organization = (
                db.query(Organization)
                .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
                .filter(OrganizationMember.user_id == user.id)
                .first()
            )
        _json(seed_service.seed_demo_workspace(db, organization=organization, user=user))
    return 0


def demo_flow(args: argparse.Namespace) -> int:
    from finagent_api.demo_flow import run_demo_flow

    with session_scope() as db:
        _json(run_demo_flow(db, email=args.email))
    return 0


def check_config(_args: argparse.Namespace) -> int:
    from finagent_api.services.providers import provider_overview

    settings = get_settings()
    problems = settings.insecure_defaults()
    overview = provider_overview()
    _json(
        {
            "environment": settings.environment,
            "job_backend": settings.job_backend,
            "credentials_configured": settings.provider_status_summary(),
            "available_models": [entry["key"] for entry in overview["available_models"]],
            "insecure_defaults": problems,
        }
    )
    return 1 if problems and settings.is_production else 0


def routes(_args: argparse.Namespace) -> int:
    from finagent_api.main import create_app

    app = create_app()
    schema = app.openapi()
    listing = [
        {"path": path, "methods": sorted(operations)}
        for path, operations in sorted(schema["paths"].items())
    ]
    _json({"count": len(listing), "routes": listing})
    return 0


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=False)

    parser = argparse.ArgumentParser(prog="finagent", description="FINAGENT LAB operator CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create database tables (development only).").set_defaults(
        func=init_db
    )

    admin = sub.add_parser("create-admin", help="Create a platform administrator.")
    admin.add_argument("--email", required=True)
    admin.add_argument("--password", default=None, help="Omit to generate one.")
    admin.add_argument("--name", default=None)
    admin.add_argument("--organization", default=None)
    admin.set_defaults(func=create_admin)

    demo = sub.add_parser("seed-demo", help="Seed the ACME Technologies demo workspace.")
    demo.add_argument("--email", default="demo@finagent.local")
    demo.add_argument("--password", default=None)
    demo.set_defaults(func=seed_demo)

    flow = sub.add_parser("demo-flow", help="Run the full seed → run → evaluate → backtest flow.")
    flow.add_argument("--email", default="demo@finagent.local")
    flow.set_defaults(func=demo_flow)

    sub.add_parser("check-config", help="Report configuration problems.").set_defaults(
        func=check_config
    )
    sub.add_parser("routes", help="List every registered route.").set_defaults(func=routes)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
