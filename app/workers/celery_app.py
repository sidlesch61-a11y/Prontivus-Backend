"""
Celery configuration for background tasks.
"""

from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "prontivus",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Periodic tasks
celery_app.conf.beat_schedule = {
    "license-check": {
        "task": "app.workers.tasks.check_license_status",
        "schedule": 3600.0,  # Every hour
    },
    "cleanup-expired-sessions": {
        "task": "app.workers.tasks.cleanup_expired_sessions",
        "schedule": 86400.0,  # Daily
    },
    "send-appointment-reminders": {
        "task": "app.workers.tasks.send_appointment_reminders",
        "schedule": 1800.0,  # Every 30 minutes
    },
    "process-tiss-guides": {
        "task": "app.workers.tasks.process_tiss_guides",
        "schedule": 300.0,  # Every 5 minutes
    },
}

if __name__ == "__main__":
    celery_app.start()
