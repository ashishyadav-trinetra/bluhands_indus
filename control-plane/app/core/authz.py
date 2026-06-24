"""Authorization helpers (RBAC).

Pure, side-effect-free role logic kept separate from FastAPI dependencies so it
can be unit-tested in isolation (Single Responsibility).
"""

from __future__ import annotations

from app.db.models.enums import Role

# Role hierarchy: higher index => more privilege within an organization.
_ORG_ROLE_ORDER: tuple[Role, ...] = (
    Role.VIEWER,
    Role.BILLING,
    Role.EDITOR,
    Role.OWNER,
)


def role_rank(role: Role) -> int:
    """Return a comparable rank for an org role (higher = more privilege)."""
    try:
        return _ORG_ROLE_ORDER.index(role)
    except ValueError:
        return -1


def has_required_role(actual: Role, required: Role) -> bool:
    """True if ``actual`` meets or exceeds ``required`` in the org hierarchy.

    ``PLATFORM_ADMIN`` is not part of the org hierarchy and always satisfies
    org-level checks (platform staff override).
    """
    if actual is Role.PLATFORM_ADMIN:
        return True
    return role_rank(actual) >= role_rank(required)


def is_allowed(actual: Role, allowed: frozenset[Role]) -> bool:
    """True if ``actual`` is explicitly in ``allowed`` (exact-match RBAC)."""
    if actual is Role.PLATFORM_ADMIN:
        return True
    return actual in allowed
