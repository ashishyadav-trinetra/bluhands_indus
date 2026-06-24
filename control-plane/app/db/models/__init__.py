"""ORM models package.

Importing every model here ensures they are registered on ``Base.metadata``
so Alembic autogenerate and ``create_all`` see the full schema.
"""

from app.db.models.api_key import ApiKey
from app.db.models.audit import AuditEvent
from app.db.models.backend import Backend
from app.db.models.build_run import BuildRun
from app.db.models.credit import CreditTransaction, CreditWallet
from app.db.models.membership import Membership
from app.db.models.organization import Organization
from app.db.models.payment import Payment
from app.db.models.tenant import Tenant
from app.db.models.user import User

__all__ = [
    "ApiKey",
    "AuditEvent",
    "Backend",
    "BuildRun",
    "CreditTransaction",
    "CreditWallet",
    "Membership",
    "Organization",
    "Payment",
    "Tenant",
    "User",
]
