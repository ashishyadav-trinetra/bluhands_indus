from typing import AsyncGenerator

from fastapi import Request
from pydantic import Field

from openhands.app_server.sandbox.preset_sandbox_spec_service import (
    PresetSandboxSpecService,
)
from openhands.app_server.sandbox.sandbox_spec_models import (
    SandboxSpecInfo,
)
from openhands.app_server.sandbox.sandbox_spec_service import (
    SandboxSpecService,
    SandboxSpecServiceInjector,
    get_agent_server_env,
    get_agent_server_image,
)
from openhands.app_server.services.injector import InjectorState


def get_default_sandbox_specs():
    return [
        SandboxSpecInfo(
            id=get_agent_server_image(),
            command=['python', '-m', 'openhands.agent_server'],
            initial_env={
                # agent_server Config reads env as OH_<FIELD_NAME>, so the field
                # `enable_vscode` is OH_ENABLE_VSCODE — the old OH_ENABLE_VS_CODE
                # spelling matched nothing (it only ever worked because the field
                # defaults to True). OH_VSCODE_PORT / OH_VSCODE_BASE_PATH are set
                # per-sandbox in ProcessSandboxService._start_agent_process.
                'OH_ENABLE_VSCODE': 'true',
                # Keep the agent-server's own bookkeeping OUT of workspace/.
                # These default to `workspace/conversations` and
                # `workspace/bash_events`, so the user's project directory was
                # littered with hundreds of event JSON files and screenshots —
                # making it hard to find the code the agent actually wrote, and
                # polluting the VS Code / Changes views. Paths are relative to
                # the agent-server's cwd (the sandbox dir), so `.agent-state/`
                # lands beside workspace/ rather than inside it.
                'OH_CONVERSATIONS_PATH': '.agent-state/conversations',
                'OH_BASH_EVENTS_DIR': '.agent-state/bash_events',
                **get_agent_server_env(),
            },
            working_dir='workspace',
        )
    ]


class ProcessSandboxSpecServiceInjector(SandboxSpecServiceInjector):
    specs: list[SandboxSpecInfo] = Field(
        default_factory=get_default_sandbox_specs,
        description='Preset list of sandbox specs',
    )

    async def inject(
        self, state: InjectorState, request: Request | None = None
    ) -> AsyncGenerator[SandboxSpecService, None]:
        yield PresetSandboxSpecService(specs=self.specs)
