import logging
import uuid
from collections.abc import Callable
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class JobHandle:
    """Standardized representation of a queued or completed job."""

    def __init__(
        self,
        job_id: str,
        status: str = "queued",
        result: Any = None,
        error: str | None = None,
    ):
        self.id = job_id
        self._status = status
        self.result = result
        self.error = error

    def get_status(self) -> str:
        return self._status

    @property
    def is_finished(self) -> bool:
        return self._status in ("finished", "completed")

    @property
    def is_failed(self) -> bool:
        return self._status == "failed"


# In-memory registry for inline jobs
_INLINE_JOBS: dict[str, JobHandle] = {}


def enqueue(job_fn: Callable[..., Any], *args: Any, **kwargs: Any) -> JobHandle:
    """Central job entry point across the application.

    When settings.JOBS_INLINE is True (default for local dev and tests):
      Executes job_fn synchronously in-process. Eliminates dependency on
      Unix fork (which fails on Windows) and Redis.

    When settings.JOBS_INLINE is False:
      Enqueues the job to Redis via RQ for asynchronous processing
      by worker processes in Docker or Linux/WSL.
    """
    if settings.JOBS_INLINE:
        job_id = f"job-{uuid.uuid4()}"
        logger.info("Executing inline job %s (id=%s)", job_fn.__name__, job_id)
        try:
            res = job_fn(*args, **kwargs)
            handle = JobHandle(job_id=job_id, status="finished", result=res)
        except Exception as exc:
            logger.error("Inline job %s failed: %s", job_id, exc, exc_info=True)
            handle = JobHandle(job_id=job_id, status="failed", error=str(exc))
        _INLINE_JOBS[job_id] = handle
        return handle

    # Production / Containerized asynchronous queue path
    try:
        from redis import Redis
        from rq import Queue

        redis_conn = Redis.from_url(settings.REDIS_URL)
        rq_queue = Queue("cleardata", connection=redis_conn)
        rq_job = rq_queue.enqueue(job_fn, *args, **kwargs)
        return JobHandle(job_id=rq_job.id, status="queued")
    except Exception as exc:
        logger.error("Failed to enqueue job to Redis: %s", exc, exc_info=True)
        raise


def get_job(job_id: str) -> JobHandle | None:
    """Retrieve job handle and current status by ID."""
    if job_id in _INLINE_JOBS:
        return _INLINE_JOBS[job_id]

    if not settings.JOBS_INLINE:
        try:
            from redis import Redis
            from rq.job import Job

            redis_conn = Redis.from_url(settings.REDIS_URL)
            rq_job = Job.fetch(job_id, connection=redis_conn)
            status = rq_job.get_status() or "unknown"
            return JobHandle(
                job_id=rq_job.id,
                status=status,
                result=rq_job.result,
                error=str(rq_job.exc_info) if rq_job.exc_info else None,
            )
        except Exception as exc:
            logger.warning("Could not fetch job %s from Redis: %s", job_id, exc)
            return None

    return None
