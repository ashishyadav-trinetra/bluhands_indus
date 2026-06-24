"""Request/response schemas for the agent service HTTP API.

These mirror the control-plane ``BluHandsAgentClientProtocol`` exactly:
  start_build(build_id, prompt, tenant_id, industry) -> job_id
  get_status(job_id) -> {status, preview_url, error}
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agent.clarify import Answer, Question
from agent.enhance import EnhancedSpec


class JobStatus(str, Enum):
    """Lifecycle of an agent build job."""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class StartBuildRequest(BaseModel):
    """Payload to start a build (sent by the control-plane worker or driver).

    The first four fields are the original contract. The rest are the build
    context the live pipeline needs (manifest, brand, products, backend
    connection). All optional with safe defaults so the basic contract still
    works and the DryRunRunner is unaffected.
    """

    build_id: str = Field(min_length=1)
    prompt: str = ""
    tenant_id: str = Field(min_length=1)
    industry: str = ""

    # --- live build context ---
    manifest: dict[str, Any] | None = None
    brand: dict[str, Any] | None = None
    business: dict[str, Any] | None = None
    products: list[dict[str, Any]] | None = None
    feature_flags: list[str] | None = None

    # backend connection (the tenant's provisioned industry backend)
    backend_url: str | None = None
    publishable_key: str = ""
    admin_email: str = ""
    admin_password: str = ""

    # build inputs / outputs
    starter_dir: str | None = None
    preview_port: int | None = None

    # answers to the pre-build clarification popup (folded into the build prompt)
    clarifications: list[Answer] | None = None
    # the enhanced/planned prompt from the PLAN step (replaces the raw one-liner)
    enhanced_prompt: str | None = None
    # LLM model chosen by the control-plane from the requester's role (per-role gating)
    llm_model: str | None = None


class EnhanceRequest(BaseModel):
    """Payload for the PLAN step: enhance the one-liner + answers into a spec."""

    prompt: str = ""
    industry: str = ""
    clarifications: list[Answer] | None = None


class EnhanceResponse(EnhancedSpec):
    """The structured, production-shaped build spec (+ rendered enhanced_prompt)."""


class ClarifyRequest(BaseModel):
    """Payload for the pre-build clarification popup.

    Sent the moment the merchant submits their prompt, BEFORE a build starts. The
    agent reasons over what is known and returns a small set of questions.
    """

    prompt: str = ""
    industry: str = ""
    manifest: dict[str, Any] | None = None
    brand: dict[str, Any] | None = None
    business: dict[str, Any] | None = None
    products: list[dict[str, Any]] | None = None
    max_questions: int = Field(default=5, ge=1, le=5)


class ClarifyResponse(BaseModel):
    """The questions to render in the popup (multiple-choice + free-text escape)."""

    questions: list[Question]


class StartBuildResponse(BaseModel):
    """Returns the opaque job id the worker polls on."""

    job_id: str


class StatusResponse(BaseModel):
    """Job status — shape required by the control-plane executor."""

    status: JobStatus
    preview_url: str | None = None
    error: str | None = None
