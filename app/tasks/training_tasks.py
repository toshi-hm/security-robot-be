from app.tasks.celery_app import celery_app


@celery_app.task
def run_training_job(config: dict) -> dict:
  return {'status': 'queued', 'config': config}
