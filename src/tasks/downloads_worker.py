from aiogram.enums import ParseMode

from .common import get_service_downloader
from .app import app, celery_event_loop, user_activity_queue
from .telegram_client import (
    send_video, 
    send_audio, 
    send_message, 
    delete_message,
    send_chat_action,
)

from src.config import settings
from src.core import AbstractServiceResult


def _notify_user_start(
    chat_id: int
) -> int:
    """
    Отправляет сообщение пользователю о начале загрузки.
    Возвращает ID сообщения для дальнейшего удаления или обновления.
    """
    message = celery_event_loop.run_until_complete(
        send_message(
            chat_id=chat_id,
            text="⏳ Загрузка началась, подождите...",
        )
    )
    return message.message_id


def _handle_download_result(
    chat_id: int, 
    message_id: int, 
    media_type: str, 
    result: AbstractServiceResult, 
    **kwargs,
):
    """
    Обрабатывает результат загрузки: отправка медиа или сообщение об ошибке.
    """
    # Удаляем сообщение о загрузке
    celery_event_loop.run_until_complete(delete_message(chat_id=chat_id, message_id=message_id))

    if result.status == "success":
        if media_type == "video":
            celery_event_loop.run_until_complete(
                send_chat_action(chat_id, "upload_video")
            )
            celery_event_loop.run_until_complete(send_video(chat_id=chat_id, **kwargs))
            celery_event_loop.run_until_complete(
                send_message(
                    chat_id=chat_id, 
                    text="✅ Видео успешно загружено и отправлено!",
                )
            )
        elif media_type == "audio":
            celery_event_loop.run_until_complete(
                send_chat_action(chat_id, "upload_audio")
            )
            celery_event_loop.run_until_complete(send_audio(chat_id=chat_id, **kwargs))
            celery_event_loop.run_until_complete(
                send_message(
                    chat_id=chat_id, 
                    text="✅ Аудио успешно загружено и отправлено!",
                )
            )
    else:
        celery_event_loop.run_until_complete(
            send_message(chat_id=chat_id, text=f"❌ Ошибка при загрузке {media_type}!")
        )

    # Убираем задачу из очереди активности
    user_activity_queue.delete_download(chat_id=chat_id)


@app.task
def download_youtube_video(
    url: str, 
    width: int, 
    height: int,
    chat_id: int, 
    video_id: str, 
    message_id: int, 
    merge_audio: bool,
) -> None:
    msg_id = _notify_user_start(chat_id=chat_id)
    
    downloader = get_service_downloader(service="youtube")
    result: AbstractServiceResult = downloader.download_video(
        url=url, 
        merge_audio=merge_audio,
        video_format_id=video_id, 
        output_path=settings.media_storage_path,
    )
    
    _handle_download_result(
        chat_id=chat_id, 
        message_id=msg_id, 
        result=result, 
        media_type="video", 
        path=result.data.path, 
        width=width, 
        height=height
    )


@app.task
def download_reddit_video(
    url: str, 
    width: int, 
    height: int,
    chat_id: int, 
    video_id: str, 
    message_id: int, 
    merge_audio: bool,
) -> None:
    msg_id = _notify_user_start(chat_id=chat_id)
    
    downloader = get_service_downloader(service="reddit")
    result: AbstractServiceResult = downloader.download_video(
        url=url, 
        merge_audio=merge_audio,
        video_format_id=video_id, 
        output_path=settings.media_storage_path
    )
    
    _handle_download_result(
        width=width, 
        result=result, 
        height=height,
        chat_id=chat_id, 
        message_id=msg_id, 
        media_type="video", 
        path=result.data.path, 
    )

@app.task
def download_rutube_video(
    url: str, 
    width: int, 
    height: int,
    chat_id: int, 
    video_id: str, 
    message_id: int, 
    merge_audio: bool,
) -> None:
    msg_id = _notify_user_start(chat_id=chat_id)
    
    downloader = get_service_downloader(service="rutube")
    result: AbstractServiceResult = downloader.download_video(
        url=url, 
        merge_audio=merge_audio,
        video_format_id=video_id, 
        output_path=settings.media_storage_path
    )
    
    _handle_download_result(
        width=width, 
        height=height,
        result=result, 
        chat_id=chat_id, 
        message_id=msg_id, 
        media_type="video", 
        path=result.data.path, 
    )


@app.task
def download_tiktok_video(
    url: str, 
    width: int, 
    height: int,
    chat_id: int, 
    video_id: str, 
    message_id: int, 
    merge_audio: bool,
) -> None:
    msg_id = _notify_user_start(chat_id=chat_id)
    
    downloader = get_service_downloader(service="tiktok")
    result: AbstractServiceResult = downloader.download_video(
        url=url, 
        merge_audio=merge_audio,
        video_format_id=video_id, 
        output_path=settings.media_storage_path
    )

    _handle_download_result(
        width=width, 
        height=height,
        result=result, 
        chat_id=chat_id, 
        message_id=msg_id, 
        media_type="video", 
        path=result.data.path, 
    )


@app.task
def download_audio(
    url: str,
    chat_id: int, 
    service: str, 
    audio_id: str, 
    message_id: int, 
    direct: bool = False,
) -> None:
    msg_id = _notify_user_start(chat_id=chat_id)
    
    downloader = get_service_downloader(service=service)
    if not direct:
        result: AbstractServiceResult = downloader.download_audio(
            url=url, 
            audio_format_id=audio_id, 
            output_path=settings.media_storage_path
        )
    else:
        result: AbstractServiceResult = downloader.download_direct_media(
            url=url, 
            file_extension="mp3", 
            output_path=settings.media_storage_path
        )

    _handle_download_result(
        result=result, 
        chat_id=chat_id, 
        message_id=msg_id, 
        media_type="audio", 
        path=result.data.path,
    )
