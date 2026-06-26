"""Process-based sandbox service implementation.

This service creates sandboxes by spawning separate agent server processes,
each running within a dedicated directory.
"""

import asyncio
import json
import logging
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncGenerator

import base62
import httpx
import psutil
from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

from openhands.agent_server.utils import utc_now
from openhands.app_server.errors import SandboxError
from openhands.app_server.sandbox.sandbox_models import (
    AGENT_SERVER,
    ExposedUrl,
    SandboxInfo,
    SandboxPage,
    SandboxStatus,
)
from openhands.app_server.sandbox.sandbox_service import (
    SandboxService,
    SandboxServiceInjector,
)
from openhands.app_server.sandbox.sandbox_spec_models import SandboxSpecInfo
from openhands.app_server.sandbox.sandbox_spec_service import SandboxSpecService
from openhands.app_server.services.injector import InjectorState
from openhands.app_server.utils.docker_utils import (
    replace_localhost_hostname_for_docker,
)

_logger = logging.getLogger(__name__)

# Common dev-server ports the agent might use.
# The App preview panel polls all WORKER_* exposed URLs and lights up whichever
# one responds — so we advertise all of them so any port the agent picks works.
# Port 3000 is intentionally excluded (reserved for the enterprise server itself).
# Common framework-default ports the preview panel detects as a *fallback* when the
# agent doesn't use its dedicated app port (see app_preview_port_for). 8080 is
# intentionally excluded — it commonly hosts other services (e.g. an OpenClaw
# gateway) and would surface the wrong app in the preview.
_APP_PREVIEW_PORTS = [1135, 5173, 5174, 8000, 8011, 8888]

# A sandbox's DEDICATED app-preview port is derived from its (unique) agent-server
# port plus this offset — a unique, stable, high-range port per sandbox that won't
# clash with host services or other sandboxes. The agent is instructed to bind its
# web app here (see live_status_app_conversation_service._build_*).
APP_PREVIEW_PORT_OFFSET = 10000


def app_preview_port_for(agent_server_port: int) -> int:
    """Return the dedicated app-preview port for a sandbox's agent-server port."""
    return agent_server_port + APP_PREVIEW_PORT_OFFSET


class ProcessInfo(BaseModel):
    """Information about a running process."""

    pid: int
    port: int
    user_id: str | None
    working_dir: str
    session_api_key: str
    created_at: datetime
    sandbox_spec_id: str

    model_config = ConfigDict(frozen=True)


# Global store of running sandboxes (restored from disk on startup).
_processes: dict[str, ProcessInfo] = {}

# Lock to prevent the TOCTOU race where concurrent sandbox starts all find the
# same port free before any of them has actually bound it.
_port_allocation_lock: asyncio.Lock = asyncio.Lock()

# --- Restart rate-limiting -----------------------------------------------
# When the home page loads, many conversations are fetched simultaneously and
# each triggers auto-restart for its dead sandbox.  Without a guard, 16+
# Python processes all start at once, starve each other, and all fail the
# health check.  Allow up to 5 concurrent restarts — enough to keep recovery
# fast (10 sandboxes restart in ~2 batches × 30 s = ~60 s) without the
# thundering-herd problem that kills health checks.
_MAX_CONCURRENT_RESTARTS: int = 5
_active_restart_count: int = 0   # how many restarts are in-flight right now
_restarting: set[str] = set()    # sandbox_ids with a restart in progress
# asyncio.Event per sandbox — set when the restart completes (success or fail).
# Secondary requests for the SAME sandbox wait on this event instead of getting
# an immediate MISSING response, so the frontend sees RUNNING and reconnects.
_restart_events: dict[str, asyncio.Event] = {}
# -------------------------------------------------------------------------

_PROCESS_INFO_FILENAME = '.process_info.json'


def _save_process_info(sandbox_id: str, working_dir: str, info: ProcessInfo) -> None:
    """Persist ProcessInfo to disk so session_api_key survives server restarts."""
    try:
        path = os.path.join(working_dir, _PROCESS_INFO_FILENAME)
        data = info.model_dump(mode='json')
        data['sandbox_id'] = sandbox_id
        with open(path, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        _logger.warning(f'Failed to persist process info for {sandbox_id}: {e}')


def _load_process_infos(base_working_dir: str) -> dict[str, ProcessInfo]:
    """Scan sandbox directories and restore ProcessInfo from disk."""
    restored: dict[str, ProcessInfo] = {}
    if not os.path.isdir(base_working_dir):
        return restored
    for entry in os.scandir(base_working_dir):
        if not entry.is_dir():
            continue
        info_path = os.path.join(entry.path, _PROCESS_INFO_FILENAME)
        if not os.path.exists(info_path):
            continue
        try:
            with open(info_path) as f:
                data = json.load(f)
            sandbox_id = data.pop('sandbox_id', entry.name)
            info = ProcessInfo.model_validate(data)
            restored[sandbox_id] = info
        except Exception as e:
            _logger.warning(f'Failed to restore process info from {info_path}: {e}')
    _logger.info(f'Restored {len(restored)} sandbox process infos from disk')
    return restored


@dataclass
class ProcessSandboxService(SandboxService):
    """Sandbox service that spawns separate agent server processes.

    Each sandbox is implemented as a separate Python process running the
    action execution server, with each process:
    - Operating in a dedicated directory
    - Listening on a unique port
    - Having its own session API key
    """

    user_id: str | None
    sandbox_spec_service: SandboxSpecService
    base_working_dir: str
    base_port: int
    python_executable: str
    agent_server_module: str
    health_check_path: str
    httpx_client: httpx.AsyncClient
    # URL pattern for sandbox exposed URLs.
    # Supports {port} placeholder (e.g. "http://192.168.1.26:{port}" or
    # "https://192.168.1.26/runtime/{port}").
    # Defaults to "http://localhost:{port}" when not set.
    container_url_pattern: str = 'http://localhost:{port}'

    # URL of the enterprise server's webhook base (e.g. http://localhost:3000/api/v1/webhooks).
    # When set, each agent subprocess is configured to push events back here so
    # conversation history survives enterprise-server restarts.
    enterprise_webhook_url: str | None = None

    def __post_init__(self):
        """Initialize the service after dataclass creation."""
        global _processes
        os.makedirs(self.base_working_dir, exist_ok=True)
        if not _processes:
            _processes.update(_load_process_infos(self.base_working_dir))

    def _find_unused_port(self) -> int:
        """Find an unused port starting from base_port.

        Must be called while holding _port_allocation_lock to avoid the TOCTOU
        race where two concurrent callers both see the same port as free.
        """
        claimed_ports = {info.port for info in _processes.values()}
        port = self.base_port
        while port < self.base_port + 10000:
            if port not in claimed_ports:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('', port))
                        return port
                except OSError:
                    pass
            port += 1
        raise SandboxError('No available ports found')

    def _create_sandbox_directory(self, sandbox_id: str) -> str:
        """Create a dedicated directory for the sandbox."""
        sandbox_dir = os.path.join(self.base_working_dir, sandbox_id)
        os.makedirs(sandbox_dir, exist_ok=True)
        os.makedirs(os.path.join(sandbox_dir, 'workspace'), exist_ok=True)
        return sandbox_dir

    async def _start_agent_process(
        self,
        sandbox_id: str,
        port: int,
        working_dir: str,
        session_api_key: str,
        sandbox_spec: SandboxSpecInfo,
    ) -> subprocess.Popen:
        """Start the agent server process."""
        env = os.environ.copy()
        env.update(sandbox_spec.initial_env)
        env['SESSION_API_KEY'] = session_api_key
        env['AGENT_SANDBOX_DIR'] = working_dir

        if self.enterprise_webhook_url:
            import json as _json
            env['OH_WEBHOOKS_0_BASE_URL'] = self.enterprise_webhook_url
            env['OH_WEBHOOKS_0_HEADERS'] = _json.dumps(
                {'X-Session-API-Key': session_api_key}
            )
            _logger.info(
                f'Webhook configured for sandbox {sandbox_id}: {self.enterprise_webhook_url}'
            )

        cmd = [
            self.python_executable,
            '-m',
            self.agent_server_module,
            '--port',
            str(port),
        ]

        _logger.info(
            f'Starting agent process for sandbox {sandbox_id}: {" ".join(cmd)}'
        )

        try:
            log_path = os.path.join(working_dir, '.openhands-agent-server.log')
            with open(log_path, 'a', buffering=1) as log_handle:
                process = subprocess.Popen(
                    cmd, env=env, cwd=working_dir, stdout=log_handle, stderr=log_handle
                )

            await asyncio.sleep(1)

            if process.poll() is not None:
                raise SandboxError(
                    f'Agent process failed to start (exit code {process.returncode}). '
                    f'See {log_path} for details.'
                )

            return process

        except Exception as e:
            raise SandboxError(f'Failed to start agent process: {e}')

    async def _wait_for_server_ready(self, port: int, timeout: int = 30) -> bool:
        """Wait for the agent server to be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                url = replace_localhost_hostname_for_docker(
                    f'http://localhost:{port}/alive'
                )
                response = await self.httpx_client.get(url, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'ok':
                        return True
            except Exception:
                pass
            await asyncio.sleep(1)
        return False

    def _get_process_status(self, process_info: ProcessInfo) -> SandboxStatus:
        """Get the status of a process."""
        try:
            process = psutil.Process(process_info.pid)
            if process.is_running():
                status = process.status()
                if status == psutil.STATUS_STOPPED:
                    return SandboxStatus.PAUSED
                elif status in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                    return SandboxStatus.MISSING
                else:
                    # sleeping / waiting / idle are all fine — agent processes
                    # spend most of their time blocked on I/O, not actively
                    # consuming CPU, so STATUS_RUNNING is rare in practice.
                    return SandboxStatus.RUNNING
            else:
                return SandboxStatus.MISSING
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return SandboxStatus.MISSING

    async def _restart_sandbox(
        self, sandbox_id: str, process_info: ProcessInfo
    ) -> ProcessInfo | None:
        """Restart a dead sandbox process, reusing its persisted session_api_key.

        Called automatically when get_sandbox / get_sandbox_by_session_api_key
        detects a MISSING process whose working directory still exists on disk.
        Reusing the same session_api_key means the agent subprocess can still
        authenticate its webhooks without any reconfiguration.

        Rate-limited: at most _MAX_CONCURRENT_RESTARTS in flight at once.
        When the home page loads it fires many parallel requests — without this
        guard all 16+ sandboxes start simultaneously, starve each other, and
        all fail health checks.  Callers that hit the limit get MISSING status
        and are retried on the next UI poll.

        Returns the new ProcessInfo on success, None otherwise.
        """
        global _active_restart_count

        # --- Rate-limiting / deduplication -----------------------------------
        if sandbox_id in _restarting:
            # Another request already triggered a restart for this sandbox.
            # Wait for it to finish rather than returning MISSING immediately —
            # that way the frontend gets RUNNING status and reconnects instead
            # of giving up.
            event = _restart_events.get(sandbox_id)
            if event is not None:
                _logger.debug(
                    'Sandbox %s restart in progress — waiting for completion',
                    sandbox_id,
                )
                try:
                    await asyncio.wait_for(event.wait(), timeout=40)
                except asyncio.TimeoutError:
                    _logger.warning(
                        'Timed out waiting for in-progress restart of sandbox %s',
                        sandbox_id,
                    )
            # After the event fires (or timeout), check whether the restart succeeded.
            current_info = _processes.get(sandbox_id)
            if (
                current_info is not None
                and self._get_process_status(current_info) == SandboxStatus.RUNNING
            ):
                return current_info
            return None

        if _active_restart_count >= _MAX_CONCURRENT_RESTARTS:
            _logger.debug(
                'Too many concurrent restarts (%d/%d), deferring sandbox %s',
                _active_restart_count,
                _MAX_CONCURRENT_RESTARTS,
                sandbox_id,
            )
            return None

        # Claim this slot and create the event that secondary requests will wait on.
        event = asyncio.Event()
        _restart_events[sandbox_id] = event
        _restarting.add(sandbox_id)
        _active_restart_count += 1
        # ---------------------------------------------------------------------

        _logger.info('Auto-restarting dead sandbox %s', sandbox_id)
        new_info: ProcessInfo | None = None
        old_info = _processes.get(sandbox_id)  # saved for rollback on failure
        try:
            sandbox_spec = await self.sandbox_spec_service.get_sandbox_spec(
                process_info.sandbox_spec_id
            )
            if sandbox_spec is None:
                _logger.warning(
                    'Cannot restart sandbox %s: spec %s not found',
                    sandbox_id,
                    process_info.sandbox_spec_id,
                )
                return None

            async with _port_allocation_lock:
                # Prefer the original port so the frontend's saved WebSocket
                # URL stays valid after a restart.  Fall back to a fresh port
                # only if the old one is already in use.
                old_port = process_info.port
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        s.bind(('', old_port))
                    port = old_port
                except OSError:
                    port = self._find_unused_port()
                process = await self._start_agent_process(
                    sandbox_id=sandbox_id,
                    port=port,
                    working_dir=process_info.working_dir,
                    # Reuse the same key — webhook auth continues to work.
                    session_api_key=process_info.session_api_key,
                    sandbox_spec=sandbox_spec,
                )
                new_info = ProcessInfo(
                    pid=process.pid,
                    port=port,
                    user_id=process_info.user_id,
                    working_dir=process_info.working_dir,
                    session_api_key=process_info.session_api_key,
                    created_at=process_info.created_at,
                    sandbox_spec_id=process_info.sandbox_spec_id,
                )
                _processes[sandbox_id] = new_info
                _save_process_info(sandbox_id, process_info.working_dir, new_info)
            # Lock released before the health-check wait.

            if not await self._wait_for_server_ready(port, timeout=30):
                _logger.warning(
                    'Restarted sandbox %s on port %d failed health check — rolling back',
                    sandbox_id,
                    port,
                )
                # Kill the spawned process so it doesn't linger as an orphan.
                try:
                    psutil.Process(new_info.pid).kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                # Restore original entry so the next poll can try again cleanly.
                if old_info is not None:
                    _processes[sandbox_id] = old_info
                    _save_process_info(sandbox_id, old_info.working_dir, old_info)
                elif sandbox_id in _processes:
                    del _processes[sandbox_id]
                return None

            _logger.info(
                'Successfully restarted sandbox %s on port %d', sandbox_id, port
            )
            return new_info
        except Exception:
            _logger.exception('Failed to restart sandbox %s', sandbox_id)
            return None
        finally:
            _active_restart_count -= 1
            _restarting.discard(sandbox_id)
            _restart_events.pop(sandbox_id, None)
            event.set()  # wake up any requests that were waiting for this restart

    @staticmethod
    def _port_is_listening(port: int) -> bool:
        """Cheap check: is something accepting connections on localhost:port?

        On localhost a non-listening port refuses *instantly* (no timeout wait) and
        a listening one connects in ~ms, so this never stalls the event loop the way
        a system-wide psutil.net_connections() scan does. It also detects a dev
        server launched detached/backgrounded (not a child of the agent process),
        which a process-tree scan misses.
        """
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                return True
        except OSError:
            return False

    def _get_listening_preview_ports(self, process_info: ProcessInfo) -> list[int]:
        """Return preview ports this sandbox's app is actually serving on.

        Prefers the sandbox's UNIQUE dedicated port (collision/leak-free); only if
        nothing is there do we fall back to the shared framework-default ports.
        Detection is a cheap localhost connect (see _port_is_listening) — no
        system-wide scan, no event-loop stall, and it finds detached dev servers.
        """
        dedicated = app_preview_port_for(process_info.port)
        if self._port_is_listening(dedicated):
            return [dedicated]
        return [p for p in _APP_PREVIEW_PORTS if self._port_is_listening(p)]

    async def _process_to_sandbox_info(
        self,
        sandbox_id: str,
        process_info: ProcessInfo,
        auto_restart: bool = False,
    ) -> SandboxInfo:
        """Convert process info to sandbox info.

        When auto_restart=True and the process is dead but its working directory
        still exists, attempt to restart the agent subprocess before returning.
        Only pass auto_restart=True from single-sandbox lookups (get_sandbox,
        get_sandbox_by_session_api_key) — not from list/search paths, to avoid
        a thundering-herd restart of every sandbox simultaneously.
        """
        status = self._get_process_status(process_info)

        # Auto-restart dead sandboxes whose workspace directory still exists.
        if (
            auto_restart
            and status == SandboxStatus.MISSING
            and os.path.isdir(process_info.working_dir)
        ):
            restarted = await self._restart_sandbox(sandbox_id, process_info)
            if restarted is not None:
                process_info = restarted
                status = SandboxStatus.RUNNING
            else:
                # Restart was deferred (rate-limit) or failed, but the workspace
                # still exists on disk — this sandbox can recover.  Use STARTING
                # so the router returns HTTP 409 (retryable) instead of HTTP 410
                # (archived/permanent), which would cause the frontend to
                # permanently hide the conversation.
                status = SandboxStatus.STARTING

        exposed_urls = None
        session_api_key = None

        if status == SandboxStatus.RUNNING:
            try:
                url = replace_localhost_hostname_for_docker(
                    f'http://localhost:{process_info.port}{self.health_check_path}'
                )
                response = await self.httpx_client.get(url, timeout=10.0)
                if response.status_code == 200:
                    # Only expose preview ports actually bound by this sandbox's
                    # process tree — prevents cross-conversation port leakage.
                    active_preview_ports = self._get_listening_preview_ports(process_info)
                    worker_urls = [
                        ExposedUrl(
                            name=f'WORKER_{i + 1}',
                            # Ensure trailing slash so nginx proxy_pass receives "/"
                            # and serves index.html rather than looking for a file
                            # named after the port (which would 404).
                            url=self.container_url_pattern.format(port=p).rstrip('/') + '/',
                            port=p,
                        )
                        for i, p in enumerate(active_preview_ports)
                    ]
                    exposed_urls = [
                        ExposedUrl(
                            name=AGENT_SERVER,
                            url=f'http://localhost:{process_info.port}',
                            port=process_info.port,
                        ),
                        ExposedUrl(
                            name=f'{AGENT_SERVER}_PUBLIC',
                            url=self.container_url_pattern.format(
                                port=process_info.port
                            ),
                            port=process_info.port,
                        ),
                        *worker_urls,
                    ]
                    session_api_key = process_info.session_api_key
                else:
                    status = SandboxStatus.ERROR
            except Exception:
                status = SandboxStatus.ERROR

        return SandboxInfo(
            id=sandbox_id,
            created_by_user_id=process_info.user_id,
            sandbox_spec_id=process_info.sandbox_spec_id,
            status=status,
            session_api_key=session_api_key,
            exposed_urls=exposed_urls,
            created_at=process_info.created_at,
        )

    async def search_sandboxes(
        self,
        page_id: str | None = None,
        limit: int = 100,
    ) -> SandboxPage:
        """Search for sandboxes."""
        all_processes = list(_processes.items())
        all_processes.sort(key=lambda x: x[1].created_at, reverse=True)

        start_idx = 0
        if page_id:
            try:
                start_idx = int(page_id)
            except ValueError:
                start_idx = 0

        end_idx = start_idx + limit
        paginated_processes = all_processes[start_idx:end_idx]

        items = []
        for sandbox_id, process_info in paginated_processes:
            sandbox_info = await self._process_to_sandbox_info(sandbox_id, process_info)
            items.append(sandbox_info)

        next_page_id = None
        if end_idx < len(all_processes):
            next_page_id = str(end_idx)

        return SandboxPage(items=items, next_page_id=next_page_id)

    async def get_sandbox(self, sandbox_id: str) -> SandboxInfo | None:
        """Get a single sandbox, auto-restarting if the process is dead."""
        process_info = _processes.get(sandbox_id)
        if process_info is None:
            return None
        return await self._process_to_sandbox_info(sandbox_id, process_info, auto_restart=True)

    async def batch_get_sandboxes(
        self, sandbox_ids: list[str]
    ) -> list[SandboxInfo | None]:
        """Get a batch of sandboxes WITHOUT auto-restarting dead processes.

        Batch lookups back the conversation-list / status-poll path, which the
        frontend hits frequently. The default implementation calls get_sandbox
        (auto_restart=True) for every id, which resurrects *every* dead sandbox
        on *every* poll — a thundering-herd restart storm that reshuffles ports
        and makes the frontend WebSocket flap (connect, close 1006, reconnect…).

        Restarting belongs only to single-sandbox lookups (get_sandbox), i.e.
        when a conversation is actually opened. Here we only report status.
        """
        results: list[SandboxInfo | None] = []
        for sandbox_id in sandbox_ids:
            process_info = _processes.get(sandbox_id)
            if process_info is None:
                results.append(None)
            else:
                results.append(
                    await self._process_to_sandbox_info(
                        sandbox_id, process_info, auto_restart=False
                    )
                )
        return results

    async def get_sandbox_by_session_api_key(
        self, session_api_key: str
    ) -> SandboxInfo | None:
        """Get a single sandbox by session API key, auto-restarting if dead."""
        for sandbox_id, process_info in _processes.items():
            if process_info.session_api_key == session_api_key:
                return await self._process_to_sandbox_info(
                    sandbox_id, process_info, auto_restart=True
                )
        return None

    async def start_sandbox(
        self, sandbox_spec_id: str | None = None, sandbox_id: str | None = None
    ) -> SandboxInfo:
        """Start a new sandbox."""
        if sandbox_spec_id is None:
            sandbox_spec = await self.sandbox_spec_service.get_default_sandbox_spec()
        else:
            sandbox_spec_maybe = await self.sandbox_spec_service.get_sandbox_spec(
                sandbox_spec_id
            )
            if sandbox_spec_maybe is None:
                raise ValueError('Sandbox Spec not found')
            sandbox_spec = sandbox_spec_maybe

        if sandbox_id is None:
            sandbox_id = base62.encodebytes(os.urandom(16))
        session_api_key = base62.encodebytes(os.urandom(32))

        # Serialize port allocation to prevent concurrent starts colliding on the same port.
        async with _port_allocation_lock:
            port = self._find_unused_port()
            working_dir = self._create_sandbox_directory(sandbox_id)
            process = await self._start_agent_process(
                sandbox_id=sandbox_id,
                port=port,
                working_dir=working_dir,
                session_api_key=session_api_key,
                sandbox_spec=sandbox_spec,
            )
            process_info = ProcessInfo(
                pid=process.pid,
                port=port,
                user_id=self.user_id,
                working_dir=working_dir,
                session_api_key=session_api_key,
                created_at=utc_now(),
                sandbox_spec_id=sandbox_spec.id,
            )
            _processes[sandbox_id] = process_info
            _save_process_info(sandbox_id, working_dir, process_info)
        # Lock released — next caller gets the next free port.

        if not await self._wait_for_server_ready(port):
            await self.delete_sandbox(sandbox_id)
            raise SandboxError('Agent Server Failed to start properly')

        return await self._process_to_sandbox_info(sandbox_id, process_info)

    async def resume_sandbox(self, sandbox_id: str) -> bool:
        """Resume a paused sandbox."""
        process_info = _processes.get(sandbox_id)
        if process_info is None:
            return False
        try:
            process = psutil.Process(process_info.pid)
            if process.status() == psutil.STATUS_STOPPED:
                process.resume()
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    async def pause_sandbox(self, sandbox_id: str) -> bool:
        """Pause a running sandbox."""
        process_info = _processes.get(sandbox_id)
        if process_info is None:
            return False
        try:
            process = psutil.Process(process_info.pid)
            if process.is_running():
                process.suspend()
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    async def delete_sandbox(self, sandbox_id: str) -> bool:
        """Delete a sandbox."""
        process_info = _processes.get(sandbox_id)
        if process_info is None:
            return False

        try:
            process = psutil.Process(process_info.pid)

            # Kill the entire process tree (agent server + any child processes
            # it spawned, e.g. dev servers on port 8080, database processes, etc.)
            # Without this, child processes become orphans and leak ports.
            children = []
            try:
                children = process.children(recursive=True)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            # Terminate children first (bottom-up), then the parent
            for child in reversed(children):
                try:
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            if process.is_running():
                process.terminate()

            # Wait for graceful shutdown, then force-kill survivors
            gone, alive = psutil.wait_procs(
                [process] + children, timeout=10
            )
            for survivor in alive:
                try:
                    survivor.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            if alive:
                psutil.wait_procs(alive, timeout=5)

            import shutil
            if os.path.exists(process_info.working_dir):
                shutil.rmtree(process_info.working_dir, ignore_errors=True)

            del _processes[sandbox_id]
            return True

        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as e:
            _logger.warning(f'Error deleting sandbox {sandbox_id}: {e}')
            if sandbox_id in _processes:
                del _processes[sandbox_id]
            return True


class ProcessSandboxServiceInjector(SandboxServiceInjector):
    """Dependency injector for process sandbox services."""

    base_working_dir: str = Field(
        default='/tmp/openhands-sandboxes',
        description='Base directory for sandbox working directories',
    )
    base_port: int = Field(
        default=18000,
        description=(
            'Base port number for agent servers. Starting at 18000 keeps '
            'agent-server ports well above all common dev-server ports '
            '(3000, 5173, 8000, 8080, 8888, …) so they never collide with '
            'app preview ports running inside the sandbox.'
        ),
    )
    python_executable: str = Field(
        default=sys.executable,
        description='Python executable to use for agent processes',
    )
    agent_server_module: str = Field(
        default='openhands.agent_server',
        description='Python module for the agent server',
    )
    health_check_path: str = Field(
        default='/alive', description='Health check endpoint path'
    )
    container_url_pattern: str = Field(
        default='http://localhost:{port}',
        description=(
            'URL pattern for sandbox exposed URLs. Supports {port} placeholder. '
            'Configure via OH_CONTAINER_URL_PATTERN environment variable.'
        ),
    )

    async def inject(
        self, state: InjectorState, request: Request | None = None
    ) -> AsyncGenerator[SandboxService, None]:
        from openhands.app_server.config import (
            get_httpx_client,
            get_sandbox_spec_service,
            get_user_context,
        )

        # Resolve webhook URL: explicit env var takes precedence, then auto-detect
        # from the server own port so events are always pushed back to Supabase.
        enterprise_webhook_url = os.getenv("ENTERPRISE_WEBHOOK_URL")
        if not enterprise_webhook_url:
            port = os.getenv("PORT", "3000")
            enterprise_webhook_url = f"http://localhost:{port}/api/v1/webhooks"

        async with (
            get_httpx_client(state, request) as httpx_client,
            get_sandbox_spec_service(state, request) as sandbox_spec_service,
            get_user_context(state, request) as user_context,
        ):
            user_id = await user_context.get_user_id()
            yield ProcessSandboxService(
                user_id=user_id,
                sandbox_spec_service=sandbox_spec_service,
                base_working_dir=self.base_working_dir,
                base_port=self.base_port,
                python_executable=self.python_executable,
                agent_server_module=self.agent_server_module,
                health_check_path=self.health_check_path,
                httpx_client=httpx_client,
                enterprise_webhook_url=enterprise_webhook_url,
                container_url_pattern=self.container_url_pattern,
            )
