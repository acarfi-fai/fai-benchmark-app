from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.config import log_dir
from app.schemas import RunDetailResponse, RunsResponse, SampleResponse, SamplesResponse
from app.services.inspect_logs import list_runs, raw_log, run_detail, run_sample, run_samples

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "log_dir": log_dir()}


@router.get("/runs", response_model=RunsResponse)
def runs(limit: int = Query(200, ge=1, le=1000), include_headers: bool = True) -> RunsResponse:
    return RunsResponse(
        log_dir=log_dir(), runs=list_runs(limit=limit, include_headers=include_headers)
    )


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
def detail(run_id: str) -> RunDetailResponse:
    file, summary, log = run_detail(run_id)
    return RunDetailResponse(id=run_id, file=file, summary=summary, log=log)


@router.get("/runs/{run_id}/samples", response_model=SamplesResponse)
def samples(
    run_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> SamplesResponse:
    file, total_seen, items = run_samples(run_id, limit=limit, offset=offset)
    return SamplesResponse(
        id=run_id,
        file=file,
        offset=offset,
        limit=limit,
        count=len(items),
        total_seen=total_seen,
        samples=items,
    )


@router.get("/runs/{run_id}/samples/{sample_offset}", response_model=SampleResponse)
def sample(run_id: str, sample_offset: int) -> SampleResponse:
    try:
        file, item = run_sample(run_id, offset=sample_offset)
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SampleResponse(id=run_id, file=file, offset=sample_offset, sample=item)


@router.get("/runs/{run_id}/raw")
def raw(run_id: str) -> Any:
    return raw_log(run_id)
