"""Tests for Celery configuration and document task composition."""

from app.core.settings import settings
from app.tasks.document_tasks import run_document_processing
from app.worker import celery_app


class FakeService:
    """Fake processing service recording the document ID."""

    def __init__(self) -> None:
        self.document_ids: list[int] = []

    async def process(self, document_id: int) -> None:
        """Record a processing request without external services."""
        self.document_ids.append(document_id)


class FakeSession:
    """Fake database session recording cleanup."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        """Record session cleanup."""
        self.closed = True


def test_celery_uses_configured_redis_url() -> None:
    """Verify Celery uses the configured Redis broker and result backend."""
    assert celery_app.conf.broker_url == settings.redis_url
    assert celery_app.conf.result_backend == settings.redis_url


def test_run_document_processing_closes_worker_session() -> None:
    """Verify the task runner executes the service and closes its session."""
    service = FakeService()
    session = FakeSession()

    def service_factory() -> tuple[FakeService, FakeSession]:
        return service, session

    run_document_processing(42, service_factory)

    assert service.document_ids == [42]
    assert session.closed is True