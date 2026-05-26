"""Start the standard Inspect View server with Application Insights/OpenTelemetry.

This does NOT apply the Azure encoded-slash workaround. It mirrors Inspect's
normal `inspect view start` behaviour, but gives us a place to initialise Azure
Monitor and add request logging middleware.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Callable

import anyio
import uvicorn
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from inspect_ai._display import display
from inspect_ai._util.constants import DEFAULT_SERVER_HOST, DEFAULT_VIEW_PORT
from inspect_ai._util.dotenv import init_dotenv
from inspect_ai._util.file import filesystem
from inspect_ai._util.logger import init_logger
from inspect_ai._view._dist import resolve_dist_directory
from inspect_ai._view.fastapi_server import (
    OnlyDirAccessPolicy,
    _InspectStaticFiles,
    filter_fastapi_log,
    view_server_app,
)

logger = logging.getLogger("fai_benchmark_app")


def configure_application_insights() -> None:
    """Enable Azure Monitor if APPLICATIONINSIGHTS_CONNECTION_STRING is set."""
    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        logger.warning("APPLICATIONINSIGHTS_CONNECTION_STRING is not set; telemetry disabled")
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor()
        logger.warning("Azure Monitor OpenTelemetry configured")
    except Exception:  # noqa: BLE001
        logger.exception("Failed to configure Azure Monitor OpenTelemetry")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request failed method=%s path=%s elapsed_ms=%.1f",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            "request method=%s path=%s status=%s elapsed_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


def instrument_fastapi(app: FastAPI) -> None:
    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.warning("FastAPI OpenTelemetry instrumentation enabled")
    except Exception:  # noqa: BLE001
        logger.exception("Failed to instrument FastAPI")


def resolve_log_dir() -> str:
    log_dir = os.getenv("INSPECT_LOG_DIR") or "./logs"
    fs = filesystem(log_dir)
    if not fs.exists(log_dir):
        fs.mkdir(log_dir, True)
    return fs.info(log_dir).name


def main() -> None:
    init_dotenv()
    init_logger(os.getenv("INSPECT_LOG_LEVEL", "warning"))
    logging.basicConfig(level=logging.WARNING)
    configure_application_insights()

    log_dir = resolve_log_dir()
    host = os.getenv("HOST", DEFAULT_SERVER_HOST)
    if host == DEFAULT_SERVER_HOST:
        host = "0.0.0.0"
    port = int(os.getenv("PORT") or os.getenv("WEBSITES_PORT") or DEFAULT_VIEW_PORT)
    recursive = os.getenv("INSPECT_VIEW_RECURSIVE", "true").lower() not in {
        "0",
        "false",
        "no",
    }

    api = view_server_app(
        access_policy=OnlyDirAccessPolicy(log_dir),
        default_dir=log_dir,
        recursive=recursive,
    )

    dist_dir = resolve_dist_directory()

    @api.get("/dist")
    async def api_dist() -> dict[str, str]:
        return {"path": dist_dir.as_posix()}

    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    app.mount("/api", api)
    app.mount(
        "/",
        _InspectStaticFiles(directory=dist_dir.as_posix(), html=True),
        name="static",
    )
    instrument_fastapi(app)

    filter_fastapi_log()
    display().print(f"Inspect View with telemetry: {log_dir}")

    async def run_server() -> None:
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_config=None,
            timeout_keep_alive=15,
        )
        server = uvicorn.Server(config)
        await server.serve()

    anyio.run(run_server)


if __name__ == "__main__":
    main()
