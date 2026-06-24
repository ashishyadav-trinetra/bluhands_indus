"""Industry seeder registry.

The runner calls ``run_seeder(industry, **kwargs)`` — it never imports a
backend-specific module itself. To add a new industry backend:

  1. Create ``agent/agent/seeders/<name>.py`` with::

       async def seed(*, backend_url, admin_email, admin_password,
                       products, business, **_kwargs) -> None: ...

  2. Register it in ``_SEEDERS`` below.

Industries that need no pre-build data seeding are simply absent from the map.
"""

from __future__ import annotations

import importlib
from typing import Any

# industry string → dotted module path of the seeder
_SEEDERS: dict[str, str] = {
    "ecommerce": "agent.seeders.medusa",
    # "crm":        "agent.seeders.twenty",     # add when Twenty seeder exists
    # "restaurant": "agent.seeders.restaurant",  # add when needed
}


async def run_seeder(industry: str, **kwargs: Any) -> None:
    """Dispatch to the registered seeder for *industry*, or no-op if none."""
    module_path = _SEEDERS.get(industry)
    if not module_path:
        return
    module = importlib.import_module(module_path)
    await module.seed(**kwargs)
