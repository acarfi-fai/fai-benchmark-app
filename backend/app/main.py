from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import router as api_router
from app.core.config import frontend_dist_dir

logger = logging.getLogger("fusionai_eval_console")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request failed method=%s path=%s", request.method, request.url.path)
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request method=%s path=%s status=%s elapsed_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


def configure_application_insights() -> None:
    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor()
        logger.info("Azure Monitor OpenTelemetry configured")
    except Exception:
        logger.exception("Failed to configure Azure Monitor OpenTelemetry")


def instrument_fastapi(app: FastAPI) -> None:
    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI OpenTelemetry instrumentation enabled")
    except Exception:
        logger.exception("Failed to instrument FastAPI")


def configure_logging() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    # Keep Azure SDK HTTP wire logs quiet by default. adlfs/azure-storage-blob
    # emits one INFO log per Blob HEAD/GET/range request when the root log level
    # is INFO, which is very noisy while reading Inspect logs from az://.
    azure_log_level = os.getenv("AZURE_SDK_LOG_LEVEL", "WARNING").upper()
    for name in (
        "azure.core.pipeline.policies.http_logging_policy",
        "azure.storage",
        "adlfs",
    ):
        logging.getLogger(name).setLevel(azure_log_level)


def create_app() -> FastAPI:
    configure_logging()
    configure_application_insights()

    app = FastAPI(title="FusionAI Eval Console")
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(api_router)
    instrument_fastapi(app)

    dist = frontend_dist_dir()
    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    def angular_app(full_path: str):
        index = dist / "index.html"
        requested = (dist / full_path).resolve() if full_path else index
        try:
            requested.relative_to(dist.resolve())
        except ValueError:
            requested = index

        if full_path and requested.is_file():
            return FileResponse(requested)
        if index.exists():
            return FileResponse(index)
        return {
            "message": "FusionAI Eval Console API is running. Angular build not found.",
            "expected_frontend_dist": str(dist),
        }

    return app


app = create_app()
