from unittest.mock import MagicMock, patch

from app.config import settings
from app.workers import enqueue, get_job


def sample_add_job(a: int, b: int) -> int:
    return a + b


def sample_failing_job():
    raise ValueError("Simulated job failure")


def test_enqueue_inline_success():
    """Verify inline job executes synchronously and stores result in registry."""
    with patch.object(settings, "JOBS_INLINE", True):
        handle = enqueue(sample_add_job, 10, 32)
        assert handle.is_finished is True
        assert handle.is_failed is False
        assert handle.result == 42
        assert handle.get_status() == "finished"

        # Verify lookup
        retrieved = get_job(handle.id)
        assert retrieved is not None
        assert retrieved.result == 42


def test_enqueue_inline_failure():
    """Verify inline job failure captures exception cleanly without crashing."""
    with patch.object(settings, "JOBS_INLINE", True):
        handle = enqueue(sample_failing_job)
        assert handle.is_failed is True
        assert handle.is_finished is False
        assert "Simulated job failure" in handle.error
        assert handle.get_status() == "failed"


def test_enqueue_redis_delegation():
    """Verify that when JOBS_INLINE=False, jobs are delegated to RQ Queue."""
    mock_rq_job = MagicMock()
    mock_rq_job.id = "rq-job-12345"

    with patch.object(settings, "JOBS_INLINE", False):
        with patch("rq.Queue.enqueue", return_value=mock_rq_job) as mock_enqueue:
            with patch("redis.Redis.from_url"):
                handle = enqueue(sample_add_job, 5, 15)
                assert handle.id == "rq-job-12345"
                assert handle.get_status() == "queued"
                mock_enqueue.assert_called_once_with(sample_add_job, 5, 15)
