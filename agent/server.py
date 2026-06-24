"""Entry point: run the BluHands agent service (uvicorn).

    python server.py            # uses AGENT_* env / .env
    uvicorn agent.app:app       # equivalent

Dry-run by default; set AGENT_DRY_RUN=false + OPENROUTER_API_KEY for real builds.
"""

from __future__ import annotations

from agent.config import get_settings


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run("agent.app:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
