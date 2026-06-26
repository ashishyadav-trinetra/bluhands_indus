"""FastAPI app for the BluHands agent service.

Exposes exactly the contract the control-plane worker expects:
  POST /builds        -> {job_id}           (start_build)
  GET  /builds/{id}   -> {status,preview_url,error}   (get_status)
  GET  /health        -> liveness
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from agent import __version__
from agent.clarify import generate_questions
from agent.config import Settings, get_settings
from agent.enhance import enhance
from agent.jobs import CapacityError, JobStore
from agent.llm import make_completion
from agent.runner import BuildSpec, get_runner
from agent.schemas import (
    ClarifyRequest,
    ClarifyResponse,
    EnhanceRequest,
    EnhanceResponse,
    StartBuildRequest,
    StartBuildResponse,
    StatusResponse,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory; builds the job store with the configured runner."""
    settings = settings or get_settings()
    app = FastAPI(title="BluHands Agent", version=__version__)
    store = JobStore(
        get_runner(settings),
        max_concurrent=settings.max_concurrent_builds,
        redis_url=settings.redis_url,
    )
    app.state.store = store

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__, "dry_run": settings.dry_run}

    @app.post("/clarify", response_model=ClarifyResponse)
    async def clarify(payload: ClarifyRequest) -> ClarifyResponse:
        """Reason about the request and return a few smart clarifying questions.

        Called right after the merchant submits their prompt, before any build.
        Uses the LLM when a key is configured; deterministic defaults otherwise.
        """
        # Clarify/enhance are cheap LLM calls — use the LLM whenever a key exists,
        # even in dry_run (which only governs whether real BUILDS run). None when
        # no key → deterministic fallback.
        llm_complete = make_completion(settings)
        result = generate_questions(
            prompt=payload.prompt,
            industry=payload.industry,
            business=payload.business,
            brand=payload.brand,
            products=payload.products,
            manifest=payload.manifest,
            llm_complete=llm_complete,
            max_questions=payload.max_questions,
        )
        return ClarifyResponse(questions=result.questions)

    @app.post("/enhance", response_model=EnhanceResponse)
    async def enhance_prompt(payload: EnhanceRequest) -> EnhanceResponse:
        """PLAN step: turn the one-liner + answers into a production build spec.

        Runs after clarification, before the build. Uses the LLM when configured;
        a deterministic heuristic otherwise. The UI can show the plan for
        confirmation, then send ``enhanced_prompt`` with the build request.
        """
        # Clarify/enhance are cheap LLM calls — use the LLM whenever a key exists,
        # even in dry_run (which only governs whether real BUILDS run). None when
        # no key → deterministic fallback.
        llm_complete = make_completion(settings)
        spec = enhance(
            prompt=payload.prompt,
            clarifications=payload.clarifications,
            industry=payload.industry,
            llm_complete=llm_complete,
        )
        return EnhanceResponse(**spec.model_dump())

    @app.post("/builds", response_model=StartBuildResponse, status_code=202)
    async def start_build(payload: StartBuildRequest) -> StartBuildResponse:
        from agent.manifests import load_manifest

        # Load the industry capability manifest; caller may override individual fields.
        manifest = payload.manifest or load_manifest(payload.industry)

        # Inject the tenant's live backend URL into the manifest so the agent
        # prompt includes the correct base URL for this build.
        if payload.backend_url and manifest:
            manifest = {**manifest, "apiBaseUrlTemplate": payload.backend_url}

        # Resolve the starter directory: caller override → settings default.
        starter_dir = payload.starter_dir or (
            str(settings.starter_dir) if settings.starter_dir else None
        )

        spec = BuildSpec(
            build_id=payload.build_id,
            prompt=payload.prompt,
            tenant_id=payload.tenant_id,
            industry=payload.industry,
            manifest=manifest,
            brand=payload.brand,
            business=payload.business,
            products=payload.products,
            feature_flags=payload.feature_flags,
            backend_url=payload.backend_url,
            publishable_key=payload.publishable_key,
            admin_email=payload.admin_email,
            admin_password=payload.admin_password,
            starter_dir=starter_dir,
            preview_port=payload.preview_port,
            clarifications=payload.clarifications,
            enhanced_prompt=payload.enhanced_prompt,
            llm_model=payload.llm_model,
            github_repo_url=payload.github_repo_url,
            github_token=payload.github_token,
            github_branch=payload.github_branch,
            github_push=payload.github_push,
            github_pull=payload.github_pull,
        )
        try:
            job_id = await store.start(spec)
        except CapacityError as exc:
            # Backpressure: shed load so the control-plane queue retries later.
            raise HTTPException(
                status_code=429, detail=str(exc), headers={"Retry-After": "30"}
            ) from exc
        return StartBuildResponse(job_id=job_id)

    @app.get("/builds/{job_id}", response_model=StatusResponse)
    async def get_status(job_id: str) -> StatusResponse:
        status = await store.get(job_id)
        if status is None:
            raise HTTPException(status_code=404, detail="job not found")
        return status

    return app


app = create_app()
