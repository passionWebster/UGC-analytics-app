from celery import Celery

from .config import settings


celery_app = Celery("bilibili_analytics")
celery_app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    task_always_eager=settings.celery_task_always_eager,
    task_ignore_result=False,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    imports=("app.tasks",),
)
