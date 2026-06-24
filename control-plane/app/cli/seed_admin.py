"""Seed (or promote) a platform admin user.

Usage:
    python -m app.cli.seed_admin --email admin@example.com --password '<pw>'

Reads ``FORGE_SEED_ADMIN_EMAIL`` / ``FORGE_SEED_ADMIN_PASSWORD`` if flags are
omitted. Idempotent: an existing user is promoted to platform admin.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from app.core.security import PasswordHasher
from app.db.models.enums import OrgPlan, Role
from app.db.models.membership import Membership
from app.db.models.organization import Organization
from app.db.models.user import User
from app.db.repositories.membership_repository import MembershipRepository
from app.db.repositories.organization_repository import OrganizationRepository
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.wallet_repository import WalletRepository
from app.db.session import dispose_engine, get_sessionmaker


async def seed_admin(email: str, password: str) -> None:
    """Create or promote a platform admin and ensure an org/wallet exist."""
    email = email.lower()
    hasher = PasswordHasher()
    factory = get_sessionmaker()

    async with factory() as session:
        users = UserRepository(session)
        existing = await users.get_by_email(email)

        if existing is not None:
            existing.is_platform_admin = True
            existing.is_active = True
            await session.commit()
            print(f"Promoted existing user to platform admin: {email}")
            return

        user = User(
            email=email,
            full_name="Platform Admin",
            password_hash=hasher.hash(password),
            is_active=True,
            is_platform_admin=True,
        )
        await users.add(user)

        org = Organization(name="Platform", plan=OrgPlan.ENTERPRISE)
        await OrganizationRepository(session).add(org)
        await MembershipRepository(session).add(
            Membership(user_id=user.id, org_id=org.id, role=Role.OWNER)
        )
        await WalletRepository(session).create_with_signup_grant(
            org.id, 0, idempotency_key=f"signup:{org.id}"
        )
        await session.commit()
        print(f"Created platform admin: {email}")


def main() -> None:
    """Parse args and run the seeding coroutine."""
    parser = argparse.ArgumentParser(description="Seed a platform admin user.")
    parser.add_argument("--email", default=os.getenv("FORGE_SEED_ADMIN_EMAIL"))
    parser.add_argument("--password", default=os.getenv("FORGE_SEED_ADMIN_PASSWORD"))
    args = parser.parse_args()

    if not args.email or not args.password:
        parser.error("email and password are required (flags or FORGE_SEED_ADMIN_* env)")
    if len(args.password) < 8:
        parser.error("password must be at least 8 characters")

    async def _run() -> None:
        try:
            await seed_admin(args.email, args.password)
        finally:
            await dispose_engine()

    asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
