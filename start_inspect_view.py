"""Start Inspect View behind Azure App Service Authentication safely.

Azure App Service / EasyAuth can reject request paths that contain encoded
slashes (for example Inspect's default /api/log-info/abfs%3A%2F%2F...).
Inspect normally exposes absolute log URIs to the browser, then the browser
sends those URIs back in path parameters.

This wrapper keeps the real Azure log URI server-side and exposes slash-free
virtual log IDs to the browser, e.g. inspect-log:<filename>. The API maps those
IDs back to the real INSPECT_LOG_DIR before reading from Blob Storage.
"""

from __future__ import annotations

import logging
import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Callable

import anyio
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_403_FORBIDDEN

from inspect_ai._display import display
from inspect_ai._util.constants import DEFAULT_VIEW_PORT
from inspect_ai._util.dotenv import init_dotenv
from inspect_ai._util.file import filesystem
from inspect_ai._util.logger import init_logger
from inspect_ai._view._dist import resolve_dist_directory
from inspect_ai._view.fastapi_server import (
    AccessPolicy,
    FileMappingPolicy,
    _InspectStaticFiles,
    filter_fastapi_log,
    view_server_app,
)

logger = logging.getLogger("fai_benchmark_app")

VIRTUAL_ROOT = "inspect-log-dir:root"
VIRTUAL_PREFIX = "inspect-log:"


def configure_application_insights() -> None:
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


def _join_uri(root: str, relative: str) -> str:
    return f"{root.rstrip('/')}/{relative.lstrip('/')}"


def _encode_relative(relative: str) -> str:
    # Do not leave '/' unescaped. The browser will encode '%' to '%25', so
    # nested paths become safe path parameters instead of encoded slashes.
    return urllib.parse.quote(relative, safe="._-")


def _decode_relative(encoded: str) -> str:
    return urllib.parse.unquote(encoded)


def _is_safe_relative(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    if not normalized or normalized.startswith("/"):
        return False
    parts = [part for part in normalized.split("/") if part]
    return all(part not in {".", ".."} for part in parts)


@dataclass
class VirtualLogPathPolicy(FileMappingPolicy, AccessPolicy):
    """Expose slash-free virtual log IDs and map them to the real log dir."""

    real_root: str

    def __post_init__(self) -> None:
        self.real_root = self.real_root.rstrip("/")

    async def map(self, request: Request, file: str) -> str:
        if file in {"", ".", VIRTUAL_ROOT}:
            return self.real_root

        if file.startswith(VIRTUAL_PREFIX):
            relative = _decode_relative(file[len(VIRTUAL_PREFIX) :])
            if not _is_safe_relative(relative):
                raise HTTPException(status_code=HTTP_403_FORBIDDEN)
            return _join_uri(self.real_root, relative)

        # Tolerate relative filenames from manually crafted URLs/tools.
        if _is_safe_relative(file):
            return _join_uri(self.real_root, file)

        raise HTTPException(status_code=HTTP_403_FORBIDDEN)

    async def unmap(self, request: Request, file: str) -> str:
        normalized = file.rstrip("/")
        if normalized == self.real_root:
            return VIRTUAL_ROOT

        prefix = f"{self.real_root}/"
        if file.startswith(prefix):
            relative = file[len(prefix) :]
            return f"{VIRTUAL_PREFIX}{_encode_relative(relative)}"

        return file

    async def can_read(self, request: Request, file: str) -> bool:
        return self._is_allowed_virtual_path(file)

    async def can_delete(self, request: Request, file: str) -> bool:
        # This app is intended as a read-only viewer.
        return False

    async def can_list(self, request: Request, dir: str) -> bool:
        return dir in {"", ".", VIRTUAL_ROOT}

    def _is_allowed_virtual_path(self, file: str) -> bool:
        if file in {"", ".", VIRTUAL_ROOT}:
            return True
        if file.startswith(VIRTUAL_PREFIX):
            return _is_safe_relative(_decode_relative(file[len(VIRTUAL_PREFIX) :]))
        return _is_safe_relative(file)


def _resolve_log_dir() -> str:
    log_dir = os.getenv("INSPECT_LOG_DIR")
    if not log_dir:
        container = os.getenv("AZURE_LOGS_CONTAINER")
        if container:
            log_dir = f"abfs://{container}"
    if not log_dir:
        log_dir = "./logs"

    # Match Inspect's normal canonicalisation. For adlfs, this usually turns
    # az://container into abfs://container.
    fs = filesystem(log_dir)
    return fs.info(log_dir).name.rstrip("/")


def main() -> None:
    init_dotenv()
    init_logger(os.getenv("INSPECT_LOG_LEVEL", "warning"))
    logging.basicConfig(level=logging.WARNING)
    configure_application_insights()

    log_dir = _resolve_log_dir()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT") or os.getenv("WEBSITES_PORT") or DEFAULT_VIEW_PORT)
    recursive = os.getenv("INSPECT_VIEW_RECURSIVE", "true").lower() not in {
        "0",
        "false",
        "no",
    }

    policy = VirtualLogPathPolicy(real_root=log_dir)
    api = view_server_app(
        mapping_policy=policy,
        access_policy=policy,
        default_dir=VIRTUAL_ROOT,
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
    display().print(f"Inspect View: {log_dir} exposed as {VIRTUAL_ROOT}")

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
