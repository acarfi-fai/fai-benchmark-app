from __future__ import annotations

import base64
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from inspect_ai.log import list_eval_logs, read_eval_log

from app.core.config import log_dir
from app.core.ids import decode_id, encode_id
from app.core.json import as_jsonable
from app.schemas import PrimaryMetric, RunSummary, SamplePreview


def basename(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").split("/")[-1]


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _duration_seconds(stats: Any) -> float | None:
    if not stats:
        return None
    started = _parse_datetime(getattr(stats, "started_at", None))
    completed = _parse_datetime(getattr(stats, "completed_at", None))
    if not started or not completed:
        return None
    return max(0.0, (completed - started).total_seconds())


def _primary_metric(header: Any) -> PrimaryMetric | None:
    if not getattr(header, "results", None) or not header.results.scores:
        return None
    first_score = header.results.scores[0]
    if not first_score.metrics:
        return None
    name, metric = next(iter(first_score.metrics.items()))
    return PrimaryMetric(name=name, metric=as_jsonable(metric))


def _sample_count_from_header(header: Any) -> int | None:
    # Keep this cheap: only read fields already available in the header/log object.
    stats = getattr(header, "stats", None)
    for attr in ("samples", "sample_count", "completed_samples"):
        value = getattr(stats, attr, None) if stats else None
        if isinstance(value, int):
            return value
    results = getattr(header, "results", None)
    value = getattr(results, "total_samples", None) if results else None
    return value if isinstance(value, int) else None


def summarize_log(info: Any, include_header: bool = True) -> RunSummary:
    summary = RunSummary(
        id=encode_id(info.name),
        file=basename(info.name),
        task=getattr(info, "task", None),
        task_id=getattr(info, "task_id", None),
        mtime=getattr(info, "mtime", None),
        size=getattr(info, "size", None),
    )
    if not include_header:
        return summary

    try:
        header = read_eval_log(info.name, header_only=True)
        summary.status = getattr(header, "status", None)
        summary.model = getattr(getattr(header, "eval", None), "model", None)
        stats = getattr(header, "stats", None)
        summary.started_at = getattr(stats, "started_at", None)
        summary.completed_at = getattr(stats, "completed_at", None)
        summary.duration_seconds = _duration_seconds(stats)
        summary.primary_metric = _primary_metric(header)
        summary.sample_count = _sample_count_from_header(header)
        summary.tags = getattr(header, "tags", None)
        summary.metadata = as_jsonable(getattr(header, "metadata", None))
    except Exception as ex:
        summary.header_error = str(ex)
    return summary


def list_runs(limit: int = 200, include_headers: bool = True) -> list[RunSummary]:
    logs = list_eval_logs(log_dir(), recursive=True)[:limit]
    if not include_headers or len(logs) <= 1:
        return [summarize_log(info, include_headers) for info in logs]

    # Azure-backed logs are latency-bound. Reading every header sequentially makes the
    # runs page wait on one blob request per log; Inspect's viewer does this work more
    # lazily/cached. Parallelize the cheap header reads so the page is not dominated by
    # round-trip latency.
    workers = min(len(logs), int(os.getenv("INSPECT_LOG_HEADER_WORKERS", "16")))
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        return list(executor.map(summarize_log, logs, [include_headers] * len(logs)))


def _normalize_log_sample_attachments(log_json: Any) -> Any:
    if not isinstance(log_json, dict):
        return log_json
    samples = log_json.get("samples")
    if not isinstance(samples, list):
        return log_json
    for sample in samples:
        if isinstance(sample, dict):
            sample["attachments"] = _normalize_attachments(sample.get("attachments"))
    return log_json


def run_detail(run_id: str) -> tuple[str, RunSummary, Any]:
    path = decode_id(run_id)
    log = read_eval_log(path, header_only=False, resolve_attachments=False)
    info = type(
        "Info",
        (),
        {
            "name": path,
            "task": getattr(getattr(log, "eval", None), "task", None),
            "task_id": getattr(getattr(log, "eval", None), "task_id", None),
            "mtime": None,
            "size": None,
        },
    )()
    return (
        basename(path),
        summarize_log(info, include_header=True),
        _normalize_log_sample_attachments(as_jsonable(log)),
    )


def _normalize_data_image_uri(value: str) -> str:
    if not value.startswith("data:image/") or ";base64," not in value[:64]:
        return value
    header, encoded = value.split(",", 1)
    try:
        prefix = base64.b64decode(encoded[:64] + "===")[:16]
    except Exception:
        return value

    mime = None
    if prefix.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif prefix.startswith(b"GIF87a") or prefix.startswith(b"GIF89a"):
        mime = "image/gif"
    elif prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP":
        mime = "image/webp"

    if mime is None or header.startswith(f"data:{mime};"):
        return value
    return f"data:{mime};base64,{encoded}"


def _normalize_attachments(attachments: Any) -> Any:
    if not isinstance(attachments, dict):
        return attachments
    return {
        key: _normalize_data_image_uri(value) if isinstance(value, str) else value
        for key, value in attachments.items()
    }


def sample_preview(sample: Any, include_attachments: bool = False) -> SamplePreview:
    output = getattr(sample, "output", None)
    completion = getattr(output, "completion", None) if output else None
    attachments = (getattr(sample, "attachments", None) or None) if include_attachments else None
    attachments = _normalize_attachments(attachments)
    return SamplePreview(
        id=getattr(sample, "id", None),
        epoch=getattr(sample, "epoch", None),
        uuid=getattr(sample, "uuid", None),
        input=as_jsonable(getattr(sample, "input", None)),
        target=as_jsonable(getattr(sample, "target", None)),
        completion=completion,
        scores=as_jsonable(getattr(sample, "scores", None)),
        metadata=as_jsonable(getattr(sample, "metadata", None)),
        error=as_jsonable(getattr(sample, "error", None)),
        attachments=as_jsonable(attachments),
    )


def run_samples(
    run_id: str, limit: int = 100, offset: int = 0
) -> tuple[str, int, list[SamplePreview]]:
    path = decode_id(run_id)

    # Read the log once and slice the already-materialized samples. The previous
    # implementation asked Inspect to read each visible sample individually, which
    # made a 50-row page perform 50 separate sample reads against remote .eval logs.
    # Keep the list payload light: multimedia attachments are read from the full
    # run detail JSON already loaded by the frontend.
    log = read_eval_log(path, header_only=False, resolve_attachments=False)
    samples = log.samples or []
    page = samples[offset : offset + limit]
    return basename(path), len(samples), [sample_preview(sample) for sample in page]


def raw_log(run_id: str) -> Any:
    return as_jsonable(read_eval_log(decode_id(run_id), header_only=False))
