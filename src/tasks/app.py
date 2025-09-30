from asyncio import new_event_loop

from celery import Celery

from src.config import settings
from src.databases import UserSessionStorage, MediaCacheStorage


celery_event_loop = new_event_loop()

app = Celery(
    "src.tasks.app",
    broker=f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_broker_db}",
    backend=f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_backend_db}",
)

app.autodiscover_tasks([
    "src.tasks.downloads_worker",
    "src.tasks.monitoring_worker",
    "src.tasks.information_worker",
])

user_session_storage = UserSessionStorage(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.user_session_storage,
)

media_cache_storage = MediaCacheStorage(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.media_cache_storage,
)
