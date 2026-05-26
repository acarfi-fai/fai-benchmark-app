"""Small FusionAI benchmark results viewer for Inspect logs on Azure Blob.

Uses the same INSPECT_LOG_DIR configuration as Inspect View, e.g.
INSPECT_LOG_DIR=abfs://logs. The browser never receives abfs:// paths, so this
avoids Azure App Service encoded-slash behaviour entirely.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable

import anyio
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from inspect_ai._util.dotenv import init_dotenv
from inspect_ai._util.json import to_json_safe
from inspect_ai.log import list_eval_logs, read_eval_log, read_eval_log_samples

logger = logging.getLogger("fai_results_viewer")


def configure_application_insights() -> None:
    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        logger.warning("APPLICATIONINSIGHTS_CONNECTION_STRING is not set; telemetry disabled")
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor()
        logger.warning("Azure Monitor OpenTelemetry configured")
    except Exception:
        logger.exception("Failed to configure Azure Monitor OpenTelemetry")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request failed method=%s path=%s", request.method, request.url.path)
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
    except Exception:
        logger.exception("Failed to instrument FastAPI")


def log_dir() -> str:
    return os.getenv("INSPECT_LOG_DIR") or os.getenv("LOG_DIR") or "./logs"


def encode_id(path: str) -> str:
    return base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii").rstrip("=")


def decode_id(run_id: str) -> str:
    try:
        padded = run_id + "=" * (-len(run_id) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception as ex:
        raise HTTPException(status_code=400, detail="Invalid run id") from ex


def as_jsonable(value: Any) -> Any:
    return json.loads(to_json_safe(value, indent=None).decode("utf-8"))


def basename(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").split("/")[-1]


def primary_metric(header: Any) -> dict[str, Any] | None:
    if not header.results or not header.results.scores:
        return None
    first_score = header.results.scores[0]
    if not first_score.metrics:
        return None
    name, metric = next(iter(first_score.metrics.items()))
    return {"name": name, "metric": as_jsonable(metric)}


def sample_preview(sample: Any) -> dict[str, Any]:
    output = getattr(sample, "output", None)
    completion = getattr(output, "completion", None) if output else None
    return {
        "id": sample.id,
        "epoch": sample.epoch,
        "uuid": sample.uuid,
        "input": as_jsonable(sample.input),
        "target": as_jsonable(sample.target),
        "completion": completion,
        "scores": as_jsonable(sample.scores),
        "metadata": as_jsonable(sample.metadata),
        "error": as_jsonable(sample.error),
    }


app = FastAPI(title="FusionAI Benchmark Results")
app.add_middleware(RequestLoggingMiddleware)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "log_dir": log_dir()}


@app.get("/api/runs")
def runs(limit: int = 200, include_headers: bool = True) -> dict[str, Any]:
    logs = list_eval_logs(log_dir(), recursive=True)[:limit]
    items = []
    for info in logs:
        item: dict[str, Any] = {
            "id": encode_id(info.name),
            "file": basename(info.name),
            "task": info.task,
            "task_id": info.task_id,
            "mtime": info.mtime,
            "size": info.size,
        }
        if include_headers:
            try:
                header = read_eval_log(info.name, header_only=True)
                item.update(
                    {
                        "status": header.status,
                        "model": header.eval.model,
                        "started_at": header.stats.started_at if header.stats else None,
                        "completed_at": header.stats.completed_at if header.stats else None,
                        "primary_metric": primary_metric(header),
                        "tags": header.tags,
                        "metadata": header.metadata,
                    }
                )
            except Exception as ex:
                item["header_error"] = str(ex)
        items.append(item)
    return {"log_dir": log_dir(), "runs": items}


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    path = decode_id(run_id)
    header = read_eval_log(path, header_only=True)
    return {"id": run_id, "file": basename(path), "path_id": run_id, "log": as_jsonable(header)}


@app.get("/api/runs/{run_id}/samples")
def run_samples(run_id: str, limit: int = 200, offset: int = 0) -> dict[str, Any]:
    path = decode_id(run_id)
    samples = []
    total_seen = 0
    for idx, sample in enumerate(read_eval_log_samples(path, all_samples_required=False)):
        total_seen += 1
        if idx < offset:
            continue
        if len(samples) >= limit:
            continue
        samples.append(sample_preview(sample))
    return {"id": run_id, "file": basename(path), "offset": offset, "limit": limit, "count": len(samples), "total_seen": total_seen, "samples": samples}


@app.get("/api/runs/{run_id}/raw")
def run_raw(run_id: str) -> Any:
    path = decode_id(run_id)
    return as_jsonable(read_eval_log(path, header_only=False))


INDEX_HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FusionAI Benchmark Results</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; background:#f6f7f9; color:#1f2937; }
    header { background:#111827; color:white; padding:16px 24px; }
    main { padding:20px 24px; }
    table { border-collapse: collapse; width: 100%; background:white; box-shadow: 0 1px 3px #0002; }
    th, td { text-align:left; border-bottom:1px solid #e5e7eb; padding:8px 10px; vertical-align:top; }
    th { background:#f3f4f6; position: sticky; top: 0; }
    tr:hover { background:#f9fafb; cursor:pointer; }
    .pill { display:inline-block; border-radius:999px; padding:2px 8px; background:#e5e7eb; font-size:12px; }
    .success { background:#dcfce7; color:#166534; }
    .error { background:#fee2e2; color:#991b1b; }
    .panel { background:white; padding:16px; margin-top:18px; box-shadow: 0 1px 3px #0002; border-radius:8px; }
    pre { white-space:pre-wrap; word-break:break-word; background:#111827; color:#e5e7eb; padding:12px; border-radius:6px; max-height:520px; overflow:auto; }
    button { padding:8px 12px; border:1px solid #d1d5db; border-radius:6px; background:white; cursor:pointer; }
    button:hover { background:#f3f4f6; }
    .muted { color:#6b7280; }
  </style>
</head>
<body>
<header><h2>FusionAI Benchmark Results</h2><div id="logDir" class="muted"></div></header>
<main>
  <button onclick="loadRuns()">Refresh</button>
  <div id="status" class="muted"></div>
  <div class="panel"><table id="runs"><thead><tr><th>Started</th><th>Task</th><th>Model</th><th>Status</th><th>Metric</th><th>File</th></tr></thead><tbody></tbody></table></div>
  <div id="detail" class="panel" style="display:none"></div>
</main>
<script>
const $ = sel => document.querySelector(sel);
function esc(v){ return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function metricText(m){ if(!m) return ''; const val = m.metric?.value ?? m.metric?.options?.value; return `${m.name}: ${JSON.stringify(val ?? m.metric)}`; }
async function loadRuns(){
  $('#status').textContent = 'Loading runs...';
  const data = await fetch('/api/runs').then(r=>r.json());
  $('#logDir').textContent = data.log_dir;
  const tbody = $('#runs tbody'); tbody.innerHTML = '';
  for(const run of data.runs){
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${esc(run.started_at || '')}</td><td>${esc(run.task)}</td><td>${esc(run.model || '')}</td><td><span class="pill ${run.status==='success'?'success':'error'}">${esc(run.status || '')}</span></td><td>${esc(metricText(run.primary_metric))}</td><td>${esc(run.file)}</td>`;
    tr.onclick = () => loadDetail(run.id);
    tbody.appendChild(tr);
  }
  $('#status').textContent = `${data.runs.length} runs`;
}
async function loadDetail(id){
  const el = $('#detail'); el.style.display='block'; el.innerHTML = 'Loading detail...';
  const [detail, samples] = await Promise.all([
    fetch(`/api/runs/${id}`).then(r=>r.json()),
    fetch(`/api/runs/${id}/samples?limit=50`).then(r=>r.json())
  ]);
  const log = detail.log;
  el.innerHTML = `<h3>${esc(detail.file)}</h3>
    <p><b>Task:</b> ${esc(log.eval?.task)} &nbsp; <b>Model:</b> ${esc(log.eval?.model)} &nbsp; <b>Status:</b> ${esc(log.status)}</p>
    <h4>Results</h4><pre>${esc(JSON.stringify(log.results, null, 2))}</pre>
    <h4>Samples (${samples.count}${samples.total_seen ? ' / ' + samples.total_seen : ''})</h4>
    ${samples.samples.map(s => `<div class="panel"><b>Sample ${esc(s.id)} epoch ${esc(s.epoch)}</b>
      <p><b>Completion:</b></p><pre>${esc(s.completion || '')}</pre>
      <p><b>Target:</b></p><pre>${esc(JSON.stringify(s.target, null, 2))}</pre>
      <p><b>Scores:</b></p><pre>${esc(JSON.stringify(s.scores, null, 2))}</pre>
    </div>`).join('')}`;
}
loadRuns().catch(e => { $('#status').textContent = e.stack || e; });
</script>
</body>
</html>
"""


def main() -> None:
    init_dotenv()
    logging.basicConfig(level=logging.WARNING)
    configure_application_insights()
    instrument_fastapi(app)
    port = int(os.getenv("PORT") or os.getenv("WEBSITES_PORT") or "8000")
    host = os.getenv("HOST", "0.0.0.0")
    logger.warning("Starting FusionAI results viewer on %s:%s for log_dir=%s", host, port, log_dir())
    anyio.run(lambda: uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_config=None)).serve())


if __name__ == "__main__":
    main()
