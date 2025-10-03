from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .app import (
    app,
    celery_event_loop,
    media_cache_storage,
    user_activity_queue,
    user_session_storage,
)
from .common import get_service_downloader
from .telegram_client import send_photo, send_message, delete_message

from src.core import (
    AbstractServiceResultTypeDict, 
    AbstractServiceAudioTypeDict, 
    AbstractServiceImageTypeDict, 
    AbstractServiceVideoTypeDict,
    AbstractServiceErrorCode,
)


@dataclass
class MediaButton:
    """Универсальный класс для кнопок медиа-контента"""
    row: int
    label: str
    callback_data: str
    url: Optional[str] = None


class MediaProcessor:
    """Класс для обработки и подготовки медиа-контента"""
    
    @staticmethod
    def parse_videos(videos: List[AbstractServiceVideoTypeDict]) -> List[MediaButton]:
        """Парсит видео данные и создает кнопки для разных качеств"""
        if not videos:
            return []
            
        # Группируем видео по качеству (берем лучшее для каждого разрешения)
        video_by_quality: Dict[int, AbstractServiceVideoTypeDict] = {}
        for video in videos:
            if video["width"] is not None:
                current_best = video_by_quality.get(video["width"])
                if not current_best or video.get("total_bitrate", 0) > current_best.get("total_bitrate", 0):
                    video_by_quality[video["width"]] = video
        
        # Создаем кнопки
        buttons = []
        qualities = sorted(video_by_quality.keys(), reverse=True)
        
        if len(qualities) == 1:
            video = video_by_quality[qualities[0]]
            buttons.append(MediaButton(
                row=1,
                label="🎬 Video",
                callback_data=f"video:{video['id']}"
            ))
        else:
            for quality in qualities:
                video = video_by_quality[quality]
                buttons.append(MediaButton(
                    row=1,
                    label=f"🎬 {video['height']}p",
                    callback_data=f"video:{video['id']}"
                ))
                
        return buttons
    
    @staticmethod
    def parse_audios(audios: List[AbstractServiceAudioTypeDict]) -> Optional[MediaButton]:
        """Парсит аудио данные и создает кнопку"""
        if not audios:
            return None
            
        # Берем лучшее качество аудио (последний элемент обычно лучший)
        best_audio = audios[-1]
        return MediaButton(
            row=2,
            label="🎵 Audio",
            callback_data=f"audio:{best_audio['id']}",
            url=best_audio.get("url")
        )
    
    @staticmethod
    def parse_thumbnails(thumbnails: List[AbstractServiceImageTypeDict]) -> Optional[MediaButton]:
        """Парсит превью и создает кнопку"""
        if not thumbnails:
            return None
            
        # Берем лучшее превью (последний элемент обычно лучший)
        best_thumbnail = thumbnails[-1]
        return MediaButton(
            row=3,
            label="🖼️ Preview",
            callback_data=f"thumbnail:{best_thumbnail['id']}",
            url=best_thumbnail.get("url")
        )
    
    @staticmethod
    def parse_images(images: List[AbstractServiceImageTypeDict]) -> Optional[MediaButton]:
        """Парсит изображения и создает кнопку"""
        if not images:
            return None
        
        # Группируем изображения по высоте и берем лучшее качество
        images_by_width: Dict[int, List[AbstractServiceImageTypeDict]] = {}
        for image in images:
            width = image["width"]
            if width not in images_by_width:
                images_by_width[width] = []
            images_by_width[width].append(image)
        
        # Находим максимальное качество
        max_quality = max(images_by_width.keys()) if images_by_width else 0
        best_images = images_by_width.get(max_quality, [])
        
        if not best_images:
            return None
            
        # Берем первое изображение лучшего качества для превью
        best_image = best_images[0]
        label = "🖼️ Image" if len(best_images) == 1 else "🖼️ Images"
        
        return MediaButton(
            row=1,
            label=label,
            callback_data="image",
            url=best_image.get("url")
        )


def _create_keyboard_layout(buttons: List[Optional[MediaButton]]) -> List[Tuple[int, str, str]]:
    """Создает раскладку клавиатуры из кнопок"""
    keyboard_data = []
    for button in buttons:
        if button:
            keyboard_data.append((button.row, button.label, button.callback_data))
    return keyboard_data


@app.task(name="information_worker.get_media_info", queue="information_queue")
def get_media_info(chat_id: int, message_id: int, url: str, service: str) -> None:
    if user_activity_queue.get_extract(chat_id=chat_id):
        return
    
    user_activity_queue.create_extract(chat_id=chat_id, url=url, service=service)
    
    message = celery_event_loop.run_until_complete(
        send_message(
            chat_id=chat_id,
            text="📥 Получил ссылку! Сейчас проверю и подготовлю данные..."
        )
    )
    
    celery_event_loop.run_until_complete(
        delete_message(
            chat_id=chat_id,
            message_id=message.message_id,
        )
    )
    
    message = celery_event_loop.run_until_complete(
        send_message(
            chat_id=chat_id,
            text="🔍 Ищу медиа-контент... пожалуйста, подождите ⏳"
        )
    )
    
    if media := media_cache_storage.get_media(url=url):
        response = AbstractServiceResultTypeDict(
            data=media["data"],
            context=None, 
            status="success", 
            code=AbstractServiceErrorCode.SUCCESS.value, 
        )
    else:
        downloader = get_service_downloader(service=service)
        response = downloader.extract_info(url=url).to_dict()
    
    if response["status"] == "success":
        _handle_success_response(
            response=response,
            url=url,
            service=service,
            chat_id=chat_id,
            message_id=message.message_id
        )
    else:
        _handle_error_response(
            response=response,
            url=url,
            service=service,
            chat_id=chat_id,
            message_id=message.message_id
        )
        
    user_activity_queue.delete_extract(chat_id=chat_id)
        


def _handle_success_response(
    response: AbstractServiceResultTypeDict,
    url: str,
    service: str,
    chat_id: int,
    message_id: int,
) -> None:
    media_data = response["data"]
    
    # Сохраняем сессию и кешируем медиа
    user_session_storage.create_session(
        chat_id=chat_id,
        url=url,
        service=service,
        media_data=media_data,
    )
    
    media_cache_storage.store_media(
        url=url,
        media_data=media_data,
    )
    
    # Подготавливаем кнопки в зависимости от типа контента
    processor = MediaProcessor()
    buttons = []
    preview_url = None
    
    if media_data["is_video"]:
        # Видео контент
        buttons.extend(processor.parse_videos(media_data.get("videos", [])))
        
        if audio_button := processor.parse_audios(media_data.get("audios", [])):
            buttons.append(audio_button)
            
        if thumbnail_button := processor.parse_thumbnails(media_data.get("thumbnails", [])):
            buttons.append(thumbnail_button)
            preview_url = thumbnail_button.url
            
    elif media_data["is_image"]:
        # Изображения
        if image_button := processor.parse_images(media_data.get("images", [])):
            buttons.append(image_button)
            preview_url = image_button.url
            
        if audio_button := processor.parse_audios(media_data.get("audios", [])):
            buttons.append(audio_button)
    
    # Отправляем результат пользователю
    keyboard_data = _create_keyboard_layout(buttons)
    
    caption = (
        f"✅ Медиа готово!\n\n"
        f"📹 Сервис: {service}\n"
        f"👤 Автор: {media_data['author_name']}\n"
        f"📝 Заголовок: {media_data['title']}\n\n"
        "👇 Выберите действие:"
    )
    
    celery_event_loop.run_until_complete(
        delete_message(
            chat_id=chat_id,
            message_id=message_id,
        )
    )
    
    celery_event_loop.run_until_complete(
        send_photo(
            chat_id=chat_id,
            caption=caption,
            preview_url=preview_url,
            keyboard_data=keyboard_data
        )
    )


def _handle_error_response(
    response: AbstractServiceResultTypeDict,
    url: str,
    service: str,
    chat_id: int,
    message_id: int,
) -> None:
    downloader = get_service_downloader(service=service)
    
    celery_event_loop.run_until_complete(
        delete_message(
            chat_id=chat_id,
            message_id=message_id,
        )
    )
    
    celery_event_loop.run_until_complete(
        send_message(
            chat_id=chat_id,
            text=f"❌ Ой! Не удалось обработать ссылку.\nПричина: {downloader.get_error_description(response['code'])}\n\nПопробуйте другую ссылку 😉"
        )
    )
