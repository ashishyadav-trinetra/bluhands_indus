"""Load agent skill files from this directory.

Skills are Markdown reference documents the agent uses for a specific build.
They are industry-aware: ecommerce builds get shadcn + medusa + ecommerce skills;
other industries get a subset. The loader is intentionally simple — the files are
plain Markdown, tested by reading them, and concatenated for injection into the
agent's prompt context.
"""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).parent

# Skills loaded per industry (order matters — most general first).
_INDUSTRY_SKILLS: dict[str, list[str]] = {
    "ecommerce": ["shadcn", "medusa", "ecommerce"],
    "restaurant": ["shadcn", "medusa"],
    "crm": ["shadcn"],
    "erp": ["shadcn"],
    "healthcare": ["shadcn"],
}

_DEFAULT_SKILLS = ["shadcn"]


def load_skills(industry: str | None = None) -> str:
    """Return concatenated skill Markdown for the given industry.

    Falls back to the default skill set when the industry is unknown or None.
    Missing skill files are skipped silently (skills are advisory, not critical).
    """
    names = _INDUSTRY_SKILLS.get(industry or "", _DEFAULT_SKILLS)
    parts: list[str] = []
    for name in names:
        path = _DIR / f"{name}.md"
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n---\n\n".join(parts)
