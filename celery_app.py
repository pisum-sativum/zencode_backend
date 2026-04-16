from __future__ import annotations

import os

from celery import Celery

redis_url = os.getenv("REDIS_URL", "").strip()

if redis_url:
    celery_app = Celery("codezen_backend", broker=redis_url, backend=redis_url)
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        broker_connection_retry_on_startup=True,
    )
else:
    celery_app = Celery(
        "codezen_backend",
        broker="memory://",
        backend="cache+memory://",
    )
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        task_always_eager=True,
        task_store_eager_result=True,
    )
