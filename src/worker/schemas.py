"""Request/response models for the job admin endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobEnqueuedResponse(BaseModel):
    job_id: str
    """arq job id — pass it to GET /v1/admin/jobs/{job_id} to poll progress."""

    function: str
    """Name of the job function that was enqueued."""


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    """One of arq's JobStatus values: deferred, queued, in_progress, complete."""

    function: str | None = None
    enqueue_time: datetime | None = None
    job_try: int | None = None

    success: bool | None = None
    """Only set once the job has finished."""

    result: Any = None
    """Job return value on success, stringified exception on failure."""

    start_time: datetime | None = None
    finish_time: datetime | None = None
