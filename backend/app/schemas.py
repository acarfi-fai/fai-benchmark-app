from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PrimaryMetric(BaseModel):
    name: str
    metric: Any


class RunSummary(BaseModel):
    id: str
    file: str
    task: str | None = None
    task_id: str | None = None
    status: str | None = None
    model: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    primary_metric: PrimaryMetric | None = None
    sample_count: int | None = None
    tags: list[str] | None = None
    metadata: Any | None = None
    mtime: float | None = None
    size: int | None = None
    header_error: str | None = None


class RunsResponse(BaseModel):
    log_dir: str
    runs: list[RunSummary]


class RunDetailResponse(BaseModel):
    id: str
    file: str
    summary: RunSummary
    log: Any


class SamplePreview(BaseModel):
    id: Any
    epoch: int | None = None
    uuid: str | None = None
    input: Any = None
    target: Any = None
    completion: str | None = None
    scores: Any = None
    metadata: Any = None
    error: Any = None
    attachments: dict[str, str] | None = None


class SamplesResponse(BaseModel):
    id: str
    file: str
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    count: int
    total_seen: int
    samples: list[SamplePreview]
