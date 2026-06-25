"""Unit tests for the pre-build clarification step (pure, offline)."""

from __future__ import annotations

import json

from agent.clarify import (
    MAX_QUESTIONS,
    Answer,
    Question,
    apply_answers,
    generate_questions,
)


def test_detailed_prompt_asks_no_questions() -> None:
    # A fully-specified technical prompt should get ZERO clarifying questions.
    detailed = (
        "Create a modern landing page with a hero section, features grid, "
        "testimonials, and a CTA. Use React with Tailwind CSS. Make it responsive. "
        "Use port 8011 and bind to 0.0.0.0."
    )
    assert generate_questions(prompt=detailed).questions == []


def test_vague_prompt_still_asks() -> None:
    result = generate_questions(prompt="build me a todo app")
    assert len(result.questions) >= 1


def test_default_questions_offline_are_valid_and_capped() -> None:
    result = generate_questions(industry="ecommerce")
    assert 1 <= len(result.questions) <= MAX_QUESTIONS
    ids = [q.id for q in result.questions]
    assert len(ids) == len(set(ids))  # unique
    # No business name known -> asks for the store name as free text.
    name_q = next(q for q in result.questions if q.id == "store_name")
    assert name_q.kind == "text" and name_q.options == []


def test_known_context_suppresses_redundant_questions() -> None:
    result = generate_questions(
        industry="ecommerce",
        business={"name": "Trinetra Threads", "tone": "premium"},
        brand={"primary": "#1a1a1a"},
    )
    ids = {q.id for q in result.questions}
    assert "store_name" not in ids  # name known
    assert "palette" not in ids  # color known
    assert "vibe" not in ids  # tone known


def test_catalog_drives_featured_products_question() -> None:
    result = generate_questions(
        industry="ecommerce",
        products=[{"name": "Classic Tee"}, {"name": "Hoodie"}, {"name": ""}],
    )
    featured = next(q for q in result.questions if q.id == "featured")
    assert featured.kind == "multi"
    assert "Classic Tee" in featured.options and "Hoodie" in featured.options
    assert "" not in featured.options


def test_llm_path_is_used_and_clamped() -> None:
    payload = {
        "reasoning": "need brand + audience",
        "questions": [
            {"id": "Brand Name!", "text": "Name?", "kind": "text", "options": []},
            {"id": "aud", "text": "Audience?", "kind": "single", "options": ["A", "B"]},
            {"id": "x3", "text": "q3", "kind": "single", "options": ["1", "2"]},
            {"id": "x4", "text": "q4", "kind": "single", "options": ["1", "2"]},
            {"id": "x5", "text": "q5", "kind": "single", "options": ["1", "2"]},
            {"id": "x6", "text": "too many", "kind": "single", "options": ["1", "2"]},
        ],
    }

    def fake_llm(system: str, user: str) -> str:
        return "```json\n" + json.dumps(payload) + "\n```"

    result = generate_questions(prompt="build me a shop", llm_complete=fake_llm, max_questions=5)
    assert len(result.questions) == 5  # clamped
    assert result.questions[0].id == "brand_name"  # slugified


def test_llm_failure_falls_back_to_defaults() -> None:
    def broken_llm(system: str, user: str) -> str:
        return "not json at all"

    result = generate_questions(industry="ecommerce", llm_complete=broken_llm)
    assert result.questions  # fell back, not empty


def test_apply_answers_renders_block_and_handles_empty() -> None:
    qs = [Question(id="store_name", text="Store name?", kind="text")]
    answers = [
        Answer(question_id="store_name", text="Trinetra Threads"),
        Answer(question_id="palette", selected=["Bold & vibrant"]),
        Answer(question_id="blank"),  # empty -> skipped
    ]
    block = apply_answers(answers, qs)
    assert "Store name?: Trinetra Threads" in block
    assert "Bold & vibrant" in block
    assert "blank" not in block
    assert apply_answers([]) == ""
    assert apply_answers(None) == ""
