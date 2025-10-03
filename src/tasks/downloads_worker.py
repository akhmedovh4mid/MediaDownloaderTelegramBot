from .common import get_service_downloader
from .app import app, celery_event_loop, user_activity_queue
from .telegram_client import send_video, send_message, send_audio, delete_message

from src.config import settings


def _notify_user_start(chat_id: int, media_type: str) -> int:
    """
    Отправляет сообщение пользователю о начале загрузки.
    Возвращает ID сообщения для дальнейшего удаления или обновления.
    """
    message = celery_event_loop.run_until_complete(
        send_message(
            chat_id=chat_id,
            text=f"📥 Начинаю загрузку {media_type}... Пожалуйста, подождите ⏳"
        )
    )
    return message.message_id


def _handle_download_result(chat_id: int, message_id: int, result, media_type: str, **kwargs):
    """
    Обрабатывает результат загрузки: отправка медиа или сообщение об ошибке.
    """
    # Удаляем сообщение о загрузке
    celery_event_loop.run_until_complete(delete_message(chat_id=chat_id, message_id=message_id))

    if result.status == "success":
        if media_type == "video":
            celery_event_loop.run_until_complete(send_video(chat_id=chat_id, **kwargs))
        elif media_type == "audio":
            celery_event_loop.run_until_complete(send_audio(chat_id=chat_id, **kwargs))
    else:
        celery_event_loop.run_until_complete(
            send_message(chat_id=chat_id, text=f"❌ Ошибка при загрузке {media_type}!")
        )

    # Убираем задачу из очереди активности
    user_activity_queue.delete_download(chat_id=chat_id)


@app.task
def download_youtube_video(chat_id: int, message_id: int, video_id: str, url: str, width: int, height: int) -> None:
    msg_id = _notify_user_start(chat_id, "видео YouTube")
    
    downloader = get_service_downloader(service="youtube")
    result = downloader.download_video(
        url=url, 
        video_format_id=video_id, 
        output_path=settings.media_storage_path
    )
    
    _handle_download_result(
        chat_id, 
        msg_id, 
        result, 
        media_type="video", 
        path=result.data.path, 
        width=width, 
        height=height
    )


@app.task
def download_reddit_video(chat_id: int, message_id: int, video_id: str, url: str, width: int, height: int) -> None:
    msg_id = _notify_user_start(chat_id, "видео Reddit")
    
    downloader = get_service_downloader(service="reddit")
    result = downloader.download_video(
        url=url, 
        video_format_id=video_id, 
        output_path=settings.media_storage_path
    )
    
    _handle_download_result(
        chat_id, 
        msg_id, 
        result, 
        media_type="video", 
        path=result.data.path, 
        width=width, 
        height=height
    )


@app.task
def download_rutube_video(chat_id: int, message_id: int, video_id: str, url: str, width: int, height: int) -> None:
    msg_id = _notify_user_start(chat_id, "видео RuTube")
    
    downloader = get_service_downloader(service="rutube")
    result = downloader.download_video(
        url=url, 
        video_format_id=video_id, 
        output_path=settings.media_storage_path
    )
    
    _handle_download_result(
        chat_id, 
        msg_id, 
        result, 
        media_type="video", 
        path=result.data.path, 
        width=width, 
        height=height
    )


@app.task
def download_tiktok_video(chat_id: int, message_id: int, video_id: str, url: str, width: int, height: int) -> None:
    msg_id = _notify_user_start(chat_id, "видео TikTok")
    
    downloader = get_service_downloader(service="tiktok")
    result = downloader.download_video(
        url=url, 
        video_format_id=video_id, 
        output_path=settings.media_storage_path
    )

    _handle_download_result(
        chat_id, 
        msg_id, 
        result, 
        media_type="video", 
        path=result.data.path, 
        width=width, 
        height=height
    )


@app.task
def download_audio(chat_id: int, message_id: int, service: str, audio_id: str, url: str) -> None:
    msg_id = _notify_user_start(chat_id, "аудио")
    
    downloader = get_service_downloader(service=service)
    result = downloader.download_audio(
        url=url, 
        audio_format_id=audio_id, 
        output_path=settings.media_storage_path
    )

    _handle_download_result(
        chat_id, 
        msg_id, 
        result, 
        media_type="audio", 
        path=result.data.path
    )
