from __future__ import annotations

from celery import Celery

from backend.core.config import settings

celery_app = Celery("boring_financial", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_always_eager=settings.task_always_eager, task_ignore_result=False)
