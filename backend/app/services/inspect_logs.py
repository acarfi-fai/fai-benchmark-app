from __future__ import annotations

from datetime import datetime
from typing import Any

from inspect_ai.log import list_eval_logs, read_eval_log, read_eval_log_samples

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
    return [summarize_log(info, include_headers) for info in logs]


def run_detail(run_id: str) -> tuple[str, RunSummary, Any]:
    path = decode_id(run_id)
    header = read_eval_log(path, header_only=True)
    info = type("Info", (), {"name": path, "task": getattr(getattr(header, "eval", None), "task", None), "task_id": getattr(getattr(header, "eval", None), "task_id", None), "mtime": None, "size": None})()
    return basename(path), summarize_log(info, include_header=True), as_jsonable(header)


def sample_preview(sample: Any) -> SamplePreview:
    output = getattr(sample, "output", None)
    completion = getattr(output, "completion", None) if output else None
    attachments = getattr(sample, "attachments", None) or None
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


def run_samples(run_id: str, limit: int = 100, offset: int = 0) -> tuple[str, int, list[SamplePreview]]:
    path = decode_id(run_id)
    samples: list[SamplePreview] = []
    total_seen = 0
    for idx, sample in enumerate(read_eval_log_samples(path, all_samples_required=False)):
        total_seen += 1
        if idx < offset:
            continue
        if len(samples) >= limit:
            continue
        samples.append(sample_preview(sample))
    return basename(path), total_seen, samples


def raw_log(run_id: str) -> Any:
    return as_jsonable(read_eval_log(decode_id(run_id), header_only=False))
