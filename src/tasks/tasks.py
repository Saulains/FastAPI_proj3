import os
from celery import Celery
from datetime import datetime, timedelta

from config import (
    DB_HOST,
    DB_PORT,
    DB_USER,
    DB_PASS,
    DB_NAME,
    UNUSED_LINKS_DAYS,
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery = Celery("tasks", broker=REDIS_URL)

# Автоудаление истекших ссылок каждую минуту (тк точность параметра - до минуты)
celery.conf.beat_schedule = {
    "cleanup-expired-links": {
        "task": "tasks.tasks.cleanup_expired_links",
        "schedule": 60.0, # Каждую минуту (тк точность параметра - до минуты)
    },
    "cleanup-unused-links": {
        "task": "tasks.tasks.cleanup_unused_links",
        "schedule": 86400.0, # Каждый день
    },
}
celery.conf.timezone = "UTC"


def _get_sync_db_url():
    return f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# Удаление по expires_at
@celery.task
def cleanup_expired_links():
    import psycopg2
    url = _get_sync_db_url()
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM links WHERE expires_at IS NOT NULL AND expires_at < NOW()")
            deleted = cur.rowcount
        conn.commit()
        return {"deleted": deleted}
    finally:
        conn.close()


# Удаление по last_used_at более 10 дней назад
@celery.task
def cleanup_unused_links():
    import psycopg2
    days = UNUSED_LINKS_DAYS
    threshold = datetime.utcnow() - timedelta(days=days)
    url = _get_sync_db_url()
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM links WHERE last_used_at IS NOT NULL AND last_used_at < %s",
                (threshold,),
            )
            deleted = cur.rowcount
        conn.commit()
        return {"deleted": deleted, "older_than_days": days}
    finally:
        conn.close()