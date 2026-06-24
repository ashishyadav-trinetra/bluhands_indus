"""Prompt enhancement — the PLAN step (reason → ask → PLAN → build).

After clarification, turn the merchant's one-liner + their answers into a rich,
structured build spec the agent can execute against — not a vague sentence. The
enhancer reasons like a senior engineer: does this use-case need auth (and JWT vs
delegated)? a database? scheduled jobs? a third-party integration (Twilio /
WhatsApp / payments)? what's the API-security posture and the concrete frontend
plan? It distills the engineering constitution (CODING-STANDARDS) so the app the
agent builds is production-shaped from day one.

Pure + offline-safe: with no LLM (dry-run / CI) a deterministic heuristic derives
the spec from keywords, so the step always produces something sane. The LLM path
makes it genuinely smart. The structured spec is rendered into a single
``enhanced_prompt`` that replaces the raw one-liner when the build runs.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from pydantic import BaseModel, Field

from agent.clarify import Answer, apply_answers

LlmComplete = Callable[[str, str], str]


class EnhancedSpec(BaseModel):
    """A production-shaped plan derived from the merchant's request + answers."""

    summary: str = ""
    app_type: str = "web"  # web | mobile | api
    needs_auth: bool = False
    auth_method: str = "none"  # none | supabase | jwt
    needs_database: bool = False
    database: str = "none"  # none | postgres
    integrations: list[str] = Field(default_factory=list)
    scheduled_jobs: bool = False
    api_security: list[str] = Field(default_factory=list)
    frontend_plan: list[str] = Field(default_factory=list)
    tech_notes: list[str] = Field(default_factory=list)
    enhanced_prompt: str = ""


# A distilled slice of the engineering constitution (CODING-STANDARDS) — the lens
# the enhancer reasons through so the result is deployable, async, secure.
_CONSTITUTION = (
    "Engineering rules to honor when planning: async-first APIs; anything an "
    "app stores needs a real database (Postgres) with migrations; any user "
    "accounts mean JWT auth (or delegated IdP) — never roll plaintext sessions; "
    "validate all inputs; rate-limit public endpoints; secrets via env, never in "
    "code; the backend must be a deployable, versioned API; prefer a small, "
    "componentized frontend over a monolith."
)

_SYSTEM = (
    "You are BluHands' senior architect. Given a non-technical user's one-line "
    "app idea plus their answers to clarifying questions, produce a concrete, "
    "production-shaped build plan. Decide what the app actually needs (auth, "
    "database, scheduled jobs, third-party integrations), its API-security "
    "posture, and a short frontend page plan. Be decisive and minimal — only "
    "what the use-case requires. " + _CONSTITUTION + " Output STRICT JSON only."
)

_USER_TEMPLATE = (
    "App idea:\n{prompt}\n\n"
    "Clarifying answers:\n{answers}\n\n"
    "Industry: {industry}\n\n"
    "Return JSON of exactly this shape:\n"
    '{{"summary": "...", "app_type": "web|mobile|api", "needs_auth": true, '
    '"auth_method": "none|supabase|jwt", "needs_database": true, '
    '"database": "none|postgres", "integrations": ["..."], '
    '"scheduled_jobs": true, "api_security": ["..."], '
    '"frontend_plan": ["page or section ..."], "tech_notes": ["..."]}}'
)


# --------------------------------------------------------------------------- #
# Deterministic heuristic (offline / no-LLM path)
# --------------------------------------------------------------------------- #

_SIGNALS = {
    "scheduled_jobs": ("schedule", "remind", "every morning", "every evening",
                       "daily", "cron", "recurring", "at "),
    "messaging": ("whatsapp", "sms", "text message", "send to", "phone", "number"),
    "payments": ("pay", "payment", "checkout", "subscription", "billing"),
    "auth": ("login", "log in", "sign up", "signup", "account", "user", "auth", "profile"),
    "storage": ("save", "store", "track", "list", "dashboard", "history", "records", "tasks"),
    "mobile": ("mobile app", "ios", "android", "react native"),
}


def _hits(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def _heuristic(prompt: str, answers_text: str, industry: str) -> EnhancedSpec:
    text = f"{prompt}\n{answers_text}".lower()
    spec = EnhancedSpec(summary=prompt.strip() or "Build the requested app.")

    spec.app_type = "mobile" if _hits(text, _SIGNALS["mobile"]) else "web"
    spec.scheduled_jobs = _hits(text, _SIGNALS["scheduled_jobs"])

    integrations: list[str] = []
    if _hits(text, _SIGNALS["messaging"]):
        integrations.append("messaging (Twilio / WhatsApp Business API)")
    if _hits(text, _SIGNALS["payments"]):
        integrations.append("payments (Stripe / Razorpay)")
    if spec.scheduled_jobs:
        integrations.append("scheduler (cron / task queue)")
    spec.integrations = integrations

    spec.needs_auth = _hits(text, _SIGNALS["auth"])
    spec.auth_method = "jwt" if spec.needs_auth else "none"

    spec.needs_database = spec.needs_auth or spec.scheduled_jobs or _hits(text, _SIGNALS["storage"])
    spec.database = "postgres" if spec.needs_database else "none"

    spec.api_security = ["input validation (pydantic)", "rate limiting", "secure headers / HTTPS"]
    if spec.needs_auth:
        spec.api_security.insert(0, "JWT auth (RS256) with refresh rotation")

    spec.frontend_plan = _frontend_plan(text, spec)
    spec.tech_notes = ["Expose a deployable, versioned REST API.", _CONSTITUTION]
    spec.enhanced_prompt = render_prompt(spec)
    return spec


def _frontend_plan(text: str, spec: EnhancedSpec) -> list[str]:
    pages: list[str] = []
    if spec.needs_auth:
        pages.append("Auth (login / signup)")
    if spec.scheduled_jobs or "remind" in text or "task" in text:
        pages += ["Create item form (content + recipient + schedule)", "Scheduled items list"]
    pages.append("Dashboard / home")
    pages.append("Settings")
    # De-dupe, keep order.
    seen: set[str] = set()
    return [p for p in pages if not (p in seen or seen.add(p))]


def render_prompt(spec: EnhancedSpec) -> str:
    """Render the structured spec into one instruction block for the agent."""
    lines = [
        "Build this as a production-shaped app (not a toy):",
        f"\n## What\n{spec.summary}",
        f"\n## Type\n{spec.app_type} app",
    ]
    if spec.needs_auth:
        lines.append(f"\n## Auth\nRequired — use {spec.auth_method.upper()}.")
    if spec.needs_database:
        lines.append(f"\n## Data\nPersist with {spec.database} + migrations.")
    if spec.integrations:
        lines.append("\n## Integrations\n" + ", ".join(spec.integrations))
    if spec.scheduled_jobs:
        lines.append("\n## Scheduling\nNeeds reliable scheduled/recurring jobs (queue or cron).")
    if spec.api_security:
        lines.append("\n## API security\n" + ", ".join(spec.api_security))
    if spec.frontend_plan:
        lines.append("\n## Frontend pages\n" + ", ".join(spec.frontend_plan))
    return "\n".join(lines).strip() + "\n"


# --------------------------------------------------------------------------- #
# LLM path
# --------------------------------------------------------------------------- #

def _extract_json(raw: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE | re.MULTILINE)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model response")
    return json.loads(text[start : end + 1])


def enhance(
    *,
    prompt: str = "",
    clarifications: list[Answer] | None = None,
    industry: str = "",
    llm_complete: LlmComplete | None = None,
) -> EnhancedSpec:
    """Produce the enhanced build spec. LLM when available; heuristic otherwise.

    Any LLM/parse failure falls back to the heuristic, so the step never breaks
    the build flow.
    """
    answers_text = apply_answers(clarifications) or "(none)"
    if llm_complete is not None:
        try:
            user = _USER_TEMPLATE.format(
                prompt=prompt.strip() or "(none)",
                answers=answers_text,
                industry=industry or "general",
            )
            data = _extract_json(llm_complete(_SYSTEM, user))
            spec = EnhancedSpec(**data)
            if not spec.summary:
                spec.summary = prompt.strip()
            spec.enhanced_prompt = render_prompt(spec)  # render consistently from fields
            return spec
        except Exception:  # noqa: BLE001 - enhancement must never break the flow
            pass
    return _heuristic(prompt, answers_text, industry)
