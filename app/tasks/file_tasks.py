from app.tasks.celery_app import celery_app


@celery_app.task
def archive_logs(path: str) -> str:
  return path
