"""Unit tests for the prompt enhancer / PLAN step (pure, offline)."""

from __future__ import annotations

import json

from agent.clarify import Answer
from agent.enhance import enhance


def test_whatsapp_reminder_detects_schedule_messaging_and_db() -> None:
    spec = enhance(
        prompt=(
            "Make a WhatsApp reminder where I put tasks and a number and it goes "
            "to the number on the scheduled time every morning or every evening"
        )
    )
    assert spec.scheduled_jobs is True
    assert any("messaging" in i.lower() for i in spec.integrations)
    assert any("scheduler" in i.lower() for i in spec.integrations)
    assert spec.needs_database is True and spec.database == "postgres"
    assert spec.enhanced_prompt.strip()  # rendered


def test_auth_inferred_from_login_mention() -> None:
    spec = enhance(prompt="A todo app where users log in and save their tasks")
    assert spec.needs_auth is True and spec.auth_method == "jwt"
    assert spec.needs_database is True
    assert any("JWT" in s for s in spec.api_security)


def test_simple_brochure_needs_no_auth_or_db() -> None:
    spec = enhance(prompt="A one-page landing site about my bakery")
    assert spec.needs_auth is False
    assert spec.needs_database is False
    assert spec.enhanced_prompt  # still renders something


def test_clarification_answers_feed_the_plan() -> None:
    answers = [Answer(question_id="channel", selected=["WhatsApp via Twilio"])]
    spec = enhance(prompt="a reminder app", clarifications=answers)
    assert any("messaging" in i.lower() for i in spec.integrations)


def test_llm_path_used_then_rendered_from_fields() -> None:
    payload = {
        "summary": "A scheduling app",
        "app_type": "web",
        "needs_auth": True,
        "auth_method": "jwt",
        "needs_database": True,
        "database": "postgres",
        "integrations": ["messaging"],
        "scheduled_jobs": True,
        "api_security": ["rate limiting"],
        "frontend_plan": ["Home", "Settings"],
        "tech_notes": ["deployable API"],
    }

    def fake_llm(system: str, user: str) -> str:
        return "```json\n" + json.dumps(payload) + "\n```"

    spec = enhance(prompt="thing", llm_complete=fake_llm)
    assert spec.needs_auth and spec.frontend_plan == ["Home", "Settings"]
    assert "Auth" in spec.enhanced_prompt  # rendered from the structured fields


def test_llm_failure_falls_back_to_heuristic() -> None:
    def broken(system: str, user: str) -> str:
        return "not json"

    spec = enhance(prompt="A todo app where users log in", llm_complete=broken)
    assert spec.needs_auth is True  # heuristic kicked in
