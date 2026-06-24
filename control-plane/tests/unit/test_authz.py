"""Unit tests for RBAC helpers."""

from __future__ import annotations

from app.core.authz import has_required_role, is_allowed, role_rank
from app.db.models.enums import Role


def test_role_hierarchy_ordering() -> None:
    assert role_rank(Role.OWNER) > role_rank(Role.EDITOR)
    assert role_rank(Role.EDITOR) > role_rank(Role.VIEWER)


def test_has_required_role_meets_or_exceeds() -> None:
    assert has_required_role(Role.OWNER, Role.EDITOR) is True
    assert has_required_role(Role.EDITOR, Role.EDITOR) is True
    assert has_required_role(Role.VIEWER, Role.EDITOR) is False


def test_platform_admin_overrides_org_checks() -> None:
    assert has_required_role(Role.PLATFORM_ADMIN, Role.OWNER) is True
    assert is_allowed(Role.PLATFORM_ADMIN, frozenset({Role.OWNER})) is True


def test_is_allowed_exact_match() -> None:
    allowed = frozenset({Role.OWNER, Role.BILLING})
    assert is_allowed(Role.BILLING, allowed) is True
    assert is_allowed(Role.EDITOR, allowed) is False
