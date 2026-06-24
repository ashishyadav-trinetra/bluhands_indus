# bluhands-agent — PLANNED (T-A01) · scaffold only, not yet implemented

The autonomous coding agent. **Not a fork of OpenHands** — a thin service built
from the OpenHands SDK packages plus our own tools and skills.

Composition (ADR-1 in `../PROJECT-HANDOFF.md`):
- `openhands-sdk` + `openhands-tools` + `openhands-agent-server` (pinned pip deps)
- custom **tools**: `agent/tools/` (Playwright screenshot-and-verify, …)
- custom **skills**: `agent/skills/` (shadcn / frontend-stability microagents)
- `agent/prompts/`: base system prompt (industry skill pack swapped per build)

Runtime: `server.py` launches the OpenHands agent-server (REST/WebSocket). The
control-plane `worker` (`../control-plane/app/tasks/`) calls it; today it talks to
`StubAgentClient` — swap that for this service to go live.

Sandbox: one ephemeral gVisor container per build. Durable state = the generated
app's Git repo + the persisted OpenHands conversation in object storage.

## LLM provider — OpenRouter (via LiteLLM)

The OpenHands SDK uses LiteLLM, which supports OpenRouter natively. Configure:
- `OPENROUTER_API_KEY` = your OpenRouter key
- model string: `openrouter/<vendor>/<model>` (e.g. `openrouter/anthropic/claude-3.5-sonnet`)

In code: `LLM(model="openrouter/anthropic/claude-3.5-sonnet", api_key=SecretStr(OPENROUTER_API_KEY))`.
This mirrors the existing bluhands fork's setup and keeps us model-agnostic (ADR-1).
See `.env.example`.

