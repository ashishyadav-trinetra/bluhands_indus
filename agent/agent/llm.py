"""LLM construction for the OpenHands agent — OpenRouter or custom models.

The OpenHands SDK and Playwright are imported lazily inside functions so this
module (and the whole service) imports and unit-tests without those heavy deps
installed. They are only needed for a real (non-dry-run) build.
"""

from __future__ import annotations

from agent.config import Settings

# Prefixes for model routing.
_CUSTOM_PREFIX = "custom/"
_OPENROUTER_PREFIX = "openrouter/"


def _is_custom_model(model: str) -> bool:
    """Return ``True`` if the model name uses a custom-model prefix.

    Both ``custom/`` and ``openai/`` prefixes are recognised when
    ``custom_model_enabled`` is set — the ``openai/`` prefix is what the
    OpenHands app-server seed (``_selfhosted_llm_diff``) produces for
    self-hosted models so LiteLLM stays in chat-completion mode.
    """
    return model.startswith(_CUSTOM_PREFIX) or model.startswith("openai/")


def build_llm(settings: Settings, model: str | None = None):
    """Construct an OpenHands ``LLM``.

    ``model`` overrides ``settings.llm_model`` — used for per-role LLM gating, where
    the control-plane sends the model to use (tester/self get fixed models).

    Models with the ``custom/`` prefix are routed to the custom OpenAI-compatible
    endpoint (e.g. ``api.bluehands.ai``). Otherwise routes through OpenRouter.

    Raises:
        RuntimeError: if the OpenHands SDK is not installed or no credentials.
    """
    model = model or settings.llm_model

    if _is_custom_model(model):
        return _build_custom_llm(settings, model)

    # -- OpenRouter path (unchanged) --
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
        model=model,
        api_key=SecretStr(api_key),
        max_output_tokens=settings.llm_max_output_tokens,
    )


def _build_custom_llm(settings: Settings, model: str):
    """Build an ``LLM`` for a ``custom/``-prefixed model.

    The Cloudflare WAF on the bluehands endpoint blocks the OpenAI SDK's default
    ``User-Agent``. We monkey-patch it at the class level so that every OpenAI
    client created within this process uses a safe UA.  This is safe because a
    single agent-replica process only ever serves one LLM provider at a time.
    """
    if not settings.custom_model_enabled:
        raise RuntimeError(
            "Custom model requested but AGENT_CUSTOM_MODEL_ENABLED is not set."
        )

    try:
        from openhands.sdk import LLM  # type: ignore
        from pydantic import SecretStr
    except ImportError as exc:  # pragma: no cover - exercised only with SDK present
        raise RuntimeError(
            "openhands-sdk is not installed; run `pip install openhands-sdk`."
        ) from exc

    # The OpenAI Python SDK's httpx client sends User-Agent: OpenAI/Python …
    # by default from a class-level attribute.  The bluehands Cloudflare WAF
    # blocks this header.  Patching the class attribute once is enough — the
    # OpenRouter path is unaffected (it uses a different base URL and the
    # custom UA is harmless there).
    import openai._base_client as _oai_base  # type: ignore  # noqa: PLC0415

    _oai_base.OpenAI.user_agent = "bluehands-agent/1.0"

    # Strip whichever prefix was used ("custom/foo" -> "foo", "openai/foo" -> "foo")
    for prefix in (_CUSTOM_PREFIX, "openai/"):
        if model.startswith(prefix):
            stripped = model.removeprefix(prefix)
            break
    else:
        stripped = model
    return LLM(
        model=stripped,
        api_key=SecretStr(settings.custom_model_api_key),
        base_url=settings.custom_model_base_url,
        max_output_tokens=settings.llm_max_output_tokens,
    )


def make_completion(settings: Settings):
    """Return a ``(system, user) -> str`` completion fn for one-shot prompts.

    Used by the clarification step (not the agent loop).  Respects the ``custom/``
    model prefix — custom models use a direct OpenAI client (bypassing LiteLLM)
    so we can control the HTTP transport headers.
    Returns ``None`` when no credentials are available, so callers fall back.
    """
    model = settings.llm_model

    if _is_custom_model(model):
        return _make_custom_completion(settings, model)

    # -- OpenRouter path --
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


def _make_custom_completion(settings: Settings, model: str):
    """Build a completion fn backed by the custom OpenAI-compatible endpoint."""
    if not settings.custom_model_enabled:
        return None

    from agent.custom_model import bluehands_client  # type: ignore  # noqa: PLC0415

    client = bluehands_client(
        base_url=settings.custom_model_base_url,
        api_key=settings.custom_model_api_key,
    )
    for prefix in (_CUSTOM_PREFIX, "openai/"):
        if model.startswith(prefix):
            stripped = model.removeprefix(prefix)
            break
    else:
        stripped = model

    def _complete(system: str, user: str) -> str:
        resp = client.chat.completions.create(
            model=stripped,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=2048,
        )
        return resp.choices[0].message.content or ""

    return _complete
