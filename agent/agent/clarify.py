"""Pre-coding clarification — reason → ask → plan, before any code is written.

Right after the merchant submits their request, the agent does NOT start building
blind. It first reasons about what is genuinely ambiguous and asks a SMALL set of
high-value questions (<= 5), surfaced to the UI as a Claude/Lovable-style popup:
multiple-choice with an optional free-text "Something else" escape per question.
The answers are folded into the build prompt so the agent builds the RIGHT thing.

Design rules (ADR-1: this is a tool/skill layer, never a patch to the agent loop):
- **Few questions.** Only ask when the answer materially changes the build. A
  confident agent asks less; that is what makes it look smart. Never ask what is
  already known from the manifest / brand / business / products.
- **Offline-safe + pure.** With no LLM available (dry-run / CI) we derive a sound
  default set deterministically from what is MISSING in the context, so the
  service works with zero network and the popup is always populated.
- **Strict, validated JSON** the frontend can render directly.

The LLM call is injected (`llm_complete`) so this module imports and unit-tests
without any heavy deps or network.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field, field_validator

QuestionKind = Literal["single", "multi", "text"]

# A completion function: (system_prompt, user_prompt) -> raw model text.
LlmComplete = Callable[[str, str], str]

MAX_QUESTIONS = 5


class Question(BaseModel):
    """One clarifying question rendered as a popup card in the UI."""

    id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1)
    kind: QuestionKind = "single"
    # Options for single/multi choice. Empty for free-text questions.
    options: list[str] = Field(default_factory=list)
    # Whether the UI shows a free-text "Something else…" escape hatch.
    allow_other: bool = True
    help: str = ""

    @field_validator("id")
    @classmethod
    def _slug(cls, v: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", v.strip().lower()).strip("_") or "q"

    @field_validator("options")
    @classmethod
    def _trim_options(cls, v: list[str]) -> list[str]:
        # De-dupe, drop blanks, preserve order, cap at 6 so the popup stays small.
        seen: set[str] = set()
        out: list[str] = []
        for opt in v:
            o = (opt or "").strip()
            if o and o.lower() not in seen:
                seen.add(o.lower())
                out.append(o)
        return out[:6]


class ClarificationSet(BaseModel):
    """The (small) set of questions to ask."""

    questions: list[Question] = Field(default_factory=list)


class Answer(BaseModel):
    """A merchant's answer to one question (selected options and/or free text)."""

    question_id: str = Field(min_length=1)
    selected: list[str] = Field(default_factory=list)
    text: str = ""

    def is_empty(self) -> bool:
        return not self.selected and not self.text.strip()


# --------------------------------------------------------------------------- #
# Context summary
# --------------------------------------------------------------------------- #

def _known(business: dict | None, brand: dict | None) -> dict[str, bool]:
    """What do we already know? Used to suppress redundant questions."""
    business = business or {}
    brand = brand or {}
    has_color = any(
        (brand.get(k) or "").strip()
        for k in ("primary", "primaryColor", "accent", "accentColor", "color")
    )
    return {
        "store_name": bool((business.get("name") or business.get("store_name") or "").strip()),
        "tone": bool((business.get("tone") or business.get("vibe") or "").strip()),
        "color": has_color,
    }


# --------------------------------------------------------------------------- #
# Deterministic default questions (offline / no-LLM path)
# --------------------------------------------------------------------------- #

_ECOMMERCE_INDUSTRIES = {"ecommerce", "e-commerce", "restaurant"}


def _default_questions(
    *,
    industry: str,
    business: dict | None,
    brand: dict | None,
    products: list[dict] | None,
    max_questions: int,
) -> ClarificationSet:
    """Derive a sensible question set from what is MISSING — pure & deterministic."""
    if (industry or "").lower() in _ECOMMERCE_INDUSTRIES:
        return _ecommerce_questions(
            business=business, brand=brand, products=products, max_questions=max_questions
        )
    return _general_questions(max_questions=max_questions)


def _ecommerce_questions(
    *,
    business: dict | None,
    brand: dict | None,
    products: list[dict] | None,
    max_questions: int,
) -> ClarificationSet:
    known = _known(business, brand)
    qs: list[Question] = []

    if not known["store_name"]:
        qs.append(
            Question(
                id="store_name",
                text="What should we call your store?",
                kind="text",
                options=[],
                help="Shown in the header, browser tab, and footer.",
            )
        )

    if not known["color"]:
        qs.append(
            Question(
                id="palette",
                text="Which color direction fits your brand best?",
                kind="single",
                options=[
                    "Clean & minimal (black / white / one accent)",
                    "Warm & earthy (terracotta, cream)",
                    "Bold & vibrant (saturated, high-contrast)",
                    "Premium & dark (charcoal, gold accent)",
                ],
                help="We turn this into your design tokens; you can fine-tune later.",
            )
        )

    if not known["tone"]:
        qs.append(
            Question(
                id="vibe",
                text="What overall vibe should the storefront have?",
                kind="single",
                options=["Minimal", "Playful", "Premium / luxury", "Friendly & approachable"],
            )
        )

    named = [str(p.get("name")).strip() for p in (products or []) if (p.get("name") or "").strip()]
    if named:
        qs.append(
            Question(
                id="featured",
                text="Which products should we feature on the homepage?",
                kind="multi",
                options=named[:6],
                help="Pick a few hero items; the rest stay browsable in the catalog.",
            )
        )

    qs.append(
        Question(
            id="priority",
            text="What matters most for launch?",
            kind="single",
            options=[
                "Get selling fast (simple, conversion-focused)",
                "Showcase the brand story (rich visuals)",
                "Wide catalog browsing (filters, categories)",
            ],
        )
    )

    return ClarificationSet(questions=qs[:max_questions])


def _general_questions(*, max_questions: int) -> ClarificationSet:
    """Default questions for non-ecommerce apps."""
    qs = [
        Question(
            id="app_name",
            text="What should we call this app?",
            kind="text",
            options=[],
            help="Used in the title, header, and any branding.",
        ),
        Question(
            id="users",
            text="Who will use this app?",
            kind="single",
            options=[
                "Just me (personal / internal tool)",
                "My team (small group of known users)",
                "Customers / the public (open to anyone)",
            ],
        ),
        Question(
            id="priority",
            text="What matters most for the first version?",
            kind="single",
            options=[
                "Working core features, shipped fast",
                "Clean UI and user experience",
                "Data accuracy and reliability",
                "Easy for non-technical users",
            ],
        ),
        Question(
            id="existing_data",
            text="Does this app need to connect to existing data or systems?",
            kind="single",
            options=["No — start fresh", "Yes — I'll describe in the next field"],
            allow_other=True,
        ),
    ]
    return ClarificationSet(questions=qs[:max_questions])


# --------------------------------------------------------------------------- #
# LLM path
# --------------------------------------------------------------------------- #

_SYSTEM = (
    "You are BluHands, an expert product engineer onboarding a non-technical "
    "user before building their app. Your job is to ask the FEWEST possible "
    "clarifying questions — only those whose answers would genuinely change what "
    "you build. A confident expert asks little. Never ask for information already "
    "provided. Prefer multiple-choice with sensible options so the user can answer "
    "in one tap; allow a free-text escape. Output STRICT JSON only."
)

_USER_TEMPLATE = (
    "Merchant request:\n{prompt}\n\n"
    "Industry: {industry}\n"
    "Known business facts: {business}\n"
    "Known brand: {brand}\n"
    "Catalog (sample names): {products}\n"
    "Backend capability manifest (you build the frontend against this): {manifest}\n\n"
    "Return JSON of this exact shape (ask at most {max_questions} questions; ask "
    "FEWER if the request is already clear):\n"
    '{{"questions": [ '
    '{{"id": "snake_case_id", "text": "...", "kind": "single|multi|text", '
    '"options": ["..."], "allow_other": true, "help": "..."}} ] }}\n'
    "Rules: text questions have empty options; single/multi have 2-5 options; do "
    "not ask anything answerable from the facts above."
)


def _build_user_prompt(
    *,
    prompt: str,
    industry: str,
    business: dict | None,
    brand: dict | None,
    products: list[dict] | None,
    manifest: dict | None,
    max_questions: int,
) -> str:
    names = [str(p.get("name")) for p in (products or []) if (p.get("name") or "").strip()][:12]
    return _USER_TEMPLATE.format(
        prompt=(prompt or "(none given)").strip(),
        industry=industry or "ecommerce",
        business=json.dumps(business or {}, ensure_ascii=False),
        brand=json.dumps(brand or {}, ensure_ascii=False),
        products=json.dumps(names, ensure_ascii=False),
        manifest=json.dumps({"backend": (manifest or {}).get("backend", "")}, ensure_ascii=False),
        max_questions=max_questions,
    )


def _extract_json(raw: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model response (handles code fences)."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object in model response")
    return json.loads(text[start : end + 1])


def _parse_llm(raw: str, max_questions: int) -> ClarificationSet:
    data = _extract_json(raw)
    questions = [Question(**q) for q in data.get("questions", []) if isinstance(q, dict)]
    # De-dupe by id, clamp to the cap.
    seen: set[str] = set()
    unique: list[Question] = []
    for q in questions:
        if q.id not in seen:
            seen.add(q.id)
            unique.append(q)
    return ClarificationSet(questions=unique[:max_questions])


def generate_questions(
    *,
    prompt: str = "",
    industry: str = "",
    business: dict | None = None,
    brand: dict | None = None,
    products: list[dict] | None = None,
    manifest: dict | None = None,
    llm_complete: LlmComplete | None = None,
    max_questions: int = MAX_QUESTIONS,
) -> ClarificationSet:
    """Produce the clarification set.

    Uses ``llm_complete`` when provided (real, smart questions); otherwise falls
    back to deterministic defaults. Any LLM/parse failure also falls back, so the
    popup is never empty and the service never hard-fails on clarification.
    """
    max_questions = max(1, min(max_questions, MAX_QUESTIONS))
    if llm_complete is not None:
        try:
            user = _build_user_prompt(
                prompt=prompt,
                industry=industry,
                business=business,
                brand=brand,
                products=products,
                manifest=manifest,
                max_questions=max_questions,
            )
            result = _parse_llm(llm_complete(_SYSTEM, user), max_questions)
            if result.questions:
                return result
        except Exception:  # noqa: BLE001 - clarification must never break the flow
            pass
    return _default_questions(
        industry=industry,
        business=business,
        brand=brand,
        products=products,
        max_questions=max_questions,
    )


# --------------------------------------------------------------------------- #
# Folding answers back into the build prompt
# --------------------------------------------------------------------------- #

def apply_answers(
    answers: list[Answer] | None,
    questions: list[Question] | None = None,
) -> str:
    """Render answers into a concise text block for ``compose_build_prompt``.

    Returns "" when there is nothing to add. When ``questions`` is supplied we
    label each answer with its question text; otherwise we label by id.
    """
    if not answers:
        return ""
    by_id = {q.id: q.text for q in (questions or [])}
    lines: list[str] = []
    for a in answers:
        if a.is_empty():
            continue
        label = by_id.get(a.question_id, a.question_id.replace("_", " "))
        value = ", ".join([*a.selected, *( [a.text.strip()] if a.text.strip() else [] )])
        lines.append(f"- {label}: {value}")
    if not lines:
        return ""
    return "The merchant answered these clarifying questions — honor them:\n" + "\n".join(lines)
