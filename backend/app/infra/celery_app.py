from celery import Celery
from app.infra.config import get_settings

celery_app = Celery("face", broker=get_settings().redis_url,
                    backend=get_settings().redis_url)
celery_app.conf.update(task_track_started=True, task_acks_late=True)
