from celery import Celery

from app.core.config import settings


celery_app = Celery('security_robot_rl', broker=settings.redis_url)
