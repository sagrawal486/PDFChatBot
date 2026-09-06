"""Celery application configuration for background document processing."""

from celery import Celery

from app.core.settings import settings


celery_app = Celery(
    "ai_pdf_chatbot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.document_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
