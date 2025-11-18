from celery import Celery

from app.core.config import settings

celery_app = Celery("security_robot_rl", broker=settings.redis_url)

# Ensure task modules are registered when the worker starts. Auto-discovery
# alone will not pick up nested modules like ``app.tasks.training_tasks`` when
# packaged as a namespace, so we explicitly import them for their side effects.
celery_app.autodiscover_tasks(
  [
    "app.tasks.training_tasks",
    "app.tasks.file_tasks",
  ]
)

# Eager imports so decorated task functions register with this app in both the
# API process and worker process contexts.
try:
  from app.tasks import file_tasks as _file_tasks  # noqa: F401
  from app.tasks import training_tasks as _training_tasks  # noqa: F401
except Exception:  # pragma: no cover - defensive: worker still starts even if optional modules fail
  pass
