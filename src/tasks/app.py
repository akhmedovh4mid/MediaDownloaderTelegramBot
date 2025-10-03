from asyncio import new_event_loop

from celery import Celery

from src.config import settings
from src.databases import (
    UserSessionStorage, 
    MediaCacheStorage,
    UserActivityQueue,
)


celery_event_loop = new_event_loop()

app = Celery(
    "src.tasks.app",
    broker=f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_broker_db}",
    backend=f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_backend_db}",
)

app.autodiscover_tasks([
    "src.tasks.downloads_worker",
    "src.tasks.information_worker",
])


app.conf.update(
    task_routes={
        # Очередь для информации
        "src.tasks.information_worker.get_media_info": {"queue": "information_queue"},
        # Очереди для загрузки видео/аудио
        "src.tasks.downloads_worker.download_youtube_video": {"queue": "youtube_queue"},
        "src.tasks.downloads_worker.download_reddit_video": {"queue": "reddit_queue"},
        "src.tasks.downloads_worker.download_rutube_video": {"queue": "rutube_queue"},
        "src.tasks.downloads_worker.download_tiktok_video": {"queue": "tiktok_queue"},
        "src.tasks.downloads_worker.download_audio": {"queue": "audio_queue"},
    }
)

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

user_activity_queue = UserActivityQueue(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.user_activity_queue,
)
