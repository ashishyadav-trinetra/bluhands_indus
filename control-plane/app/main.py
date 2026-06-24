"""FastAPI application factory.

Wires middleware, routers, global exception handlers (structured error
envelopes, no internals leaked), Prometheus metrics, and graceful shutdown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app import __version__
from app.api.v1.router import api_router
from app.api.v1.routes import health
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, RateLimitError
from app.core.logging import configure_logging, get_logger
from app.core.metrics import PrometheusMiddleware
from app.core.metrics import render as render_metrics
from app.core.middleware import RequestContextMiddleware
from app.core.observability import init_sentry
from app.db.session import dispose_engine
from app.providers.redis_client import close_redis
from app.schemas.common import ErrorBody, ErrorResponse

_logger = get_logger("app")


def _request_id(request: Request) -> str:
    """Return the current request id (set by RequestContextMiddleware)."""
    return getattr(request.state, "request_id", "unknown")


def _register_exception_handlers(app: FastAPI) -> None:
    """Install global handlers that emit the error envelope only."""

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorBody(code=exc.code, message=exc.message),
            request_id=_request_id(request),
        )
        headers = {}
        if isinstance(exc, RateLimitError):
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.http_status,
            content=body.model_dump(),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorBody(code="VALIDATION_ERROR", message="Request validation failed"),
            request_id=_request_id(request),
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log the real error server-side; expose nothing to the client.
        _logger.error("unhandled_exception", error=str(exc), error_type=type(exc).__name__)
        body = ErrorResponse(
            error=ErrorBody(code="INTERNAL_ERROR", message="An internal error occurred"),
            request_id=_request_id(request),
        )
        return JSONResponse(status_code=500, content=body.model_dump())


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle. Cleans up pools on graceful shutdown."""
    _logger.info("startup", version=__version__)
    try:
        yield
    finally:
        await dispose_engine()
        await close_redis()
        _logger.info("shutdown_complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory. Returns a fully configured FastAPI instance."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    init_sentry(settings)

    app = FastAPI(
        title="Forge Control Plane",
        version=__version__,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=_lifespan,
    )

    # Middleware (order matters: context first so it wraps everything).
    app.add_middleware(RequestContextMiddleware)
    if settings.prometheus_enabled:
        app.add_middleware(PrometheusMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_exception_handlers(app)

    # Health probes at the root; versioned API under the configured prefix.
    app.include_router(health.router, tags=["health"])
    app.include_router(api_router, prefix=settings.api_prefix)

    if settings.prometheus_enabled:

        @app.get("/metrics", include_in_schema=False)
        async def metrics() -> PlainTextResponse:
            """Prometheus scrape endpoint."""
            payload, content_type = render_metrics()
            return PlainTextResponse(payload, media_type=content_type)

    return app


app = create_app()
