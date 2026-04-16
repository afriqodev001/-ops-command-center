from pathlib import Path

from django.apps import AppConfig
from django.conf import settings


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Browser session directory
        session_dir = Path(getattr(settings, "BROWSER_SESSION_DIR", ".browser_sessions"))
        session_dir.mkdir(parents=True, exist_ok=True)

        # Celery filesystem broker directories
        broker_dir = Path(getattr(settings, "BROKER_DIR", "celery_data/broker"))
        processed_dir = broker_dir.parent / "processed"
        broker_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)
