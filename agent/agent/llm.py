"""LLM construction for the OpenHands agent — OpenRouter via LiteLLM.

The OpenHands SDK and Playwright are imported lazily inside functions so this
module (and the whole service) imports and unit-tests without those heavy deps
installed. They are only needed for a real (non-dry-run) build.
"""

from __future__ import annotations

from agent.config import Settings


def build_llm(settings: Settings, model: str | None = None):
    """Construct an OpenHands ``LLM`` configured for OpenRouter.

    ``model`` overrides ``settings.llm_model`` — used for per-role LLM gating, where
    the control-plane sends the model to use (tester/self get fixed models).

    Raises:
        RuntimeError: if the OpenHands SDK is not installed or no key is set.
    """
    api_key = settings.openrouter_api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set; cannot build a real LLM.")
    try:
        from openhands.sdk import LLM  # type: ignore
        from pydantic import SecretStr
    except ImportError as exc:  # pragma: no cover - exercised only with SDK present
        raise RuntimeError(
            "openhands-sdk is not installed; run `pip install openhands-sdk`."
        ) from exc

    # LiteLLM routes `openrouter/...` models to https://openrouter.ai/api/v1
    # automatically when OPENROUTER_API_KEY is set; passing api_key is explicit.
    return LLM(
        model=model or settings.llm_model,
        api_key=SecretStr(api_key),
        max_output_tokens=settings.llm_max_output_tokens,
    )


def make_completion(settings: Settings):
    """Return a `(system, user) -> str` completion fn for one-shot prompts.

    Used by the clarification step (not the agent loop). Calls LiteLLM directly —
    LiteLLM is a dependency of openhands-sdk and routes `openrouter/...` models.
    Returns ``None`` when no key is set, so callers fall back to offline defaults.
    """
    api_key = settings.openrouter_api_key()
    if not api_key:
        return None

    def _complete(system: str, user: str) -> str:
        import litellm  # type: ignore  # lazy: optional until a real call is made

        resp = litellm.completion(
            model=settings.llm_model,
            api_key=api_key,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""

    return _complete
