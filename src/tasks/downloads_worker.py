from .app import app
from .app import celery_event_loop
from .telegram_client import send_video
from .common import get_service_downloader

from src.config import settings


@app.task
def download_youtube_video(chat_id: int, message_id: int, url: str, video: dict) -> None:
    downloader = get_service_downloader(service="youtube")
    result = downloader.download_media(url=url, video_format_id=video["name"], output_path=settings.media_storage_path)
    
    if result.status == "success":
        celery_event_loop.run_until_complete(
            send_video(
                chat_id=chat_id,
                message_id=message_id,
                caption=f"Video {video["height"]}p",
                path = result.data.path
            )
        )
