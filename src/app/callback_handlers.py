from typing import Dict, List
from aiogram.types import CallbackQuery, InputMediaPhoto

from src.core.abstractions import AbstractServiceImageTypeDict
from src.tasks.app import user_session_storage, user_activity_queue


class ServiceCallbackHandler:
    
    @staticmethod
    async def handle_video(callback: CallbackQuery) -> None:
        if user_activity_queue.get_download(chat_id=callback.message.chat.id):
            await callback.answer()
            return

        from src.tasks.downloads_worker import (
            download_reddit_video, 
            download_rutube_video, 
            download_tiktok_video, 
            download_youtube_video,
        )
        session = user_session_storage.get_session(chat_id=callback.message.chat.id)
        if session is None:
            await callback.answer()
            return
            
        content_type, video_id = callback.data.split(":")
        video = [v for v in session["media_data"]["videos"] if v["id"] == video_id][0]
        
        chat_id = callback.message.chat.id
        message_id = callback.message.message_id
        url = session["url"]
        width = video.get("width")
        height = video.get("height")
        
        user_activity_queue.create_download(
            url=url,
            chat_id=chat_id,
            service=session["service"],
        )
        
        if session["service"] == "instagram":
            await callback.message.answer_video(
                video=video["url"], 
                supports_streaming=True,
                width=width,
                height=height
            )
            
            user_activity_queue.delete_download(chat_id=chat_id)
        
        else:
            # Для остальных сервисов используем Celery для асинхронной загрузки
            task_map = {
                "youtube": download_youtube_video,
                "reddit": download_reddit_video,
                "rutube": download_rutube_video,
                "tiktok": download_tiktok_video,
            }
            task = task_map.get(session["service"])
            if task:
                task.delay(
                    url=url,
                    width=width,
                    height=height,
                    chat_id=chat_id,
                    message_id=message_id,
                    video_id=video["name"],
                )

        await callback.answer()


    @staticmethod
    async def handle_image(callback: CallbackQuery) -> None:
        session = user_session_storage.get_session(chat_id=callback.message.chat.id)
        if session is None:
            await callback.answer()
            return
        
        images_by_width: Dict[int, List[AbstractServiceImageTypeDict]] = {}
        for image in session["media_data"]["images"]:
            width = image["width"]
            if width not in images_by_width:
                images_by_width[width] = []
            images_by_width[width].append(image)
        
        # Берем лучшее качество (максимальную ширину)
        max_quality = max(images_by_width.keys()) if images_by_width else 0
        best_images = images_by_width.get(max_quality, [])
        
        media = [InputMediaPhoto(media=image["url"]) for image in best_images]
        
        await callback.message.answer_media_group(media=media)
        await callback.answer()
        
    @staticmethod
    async def handle_audio(callback: CallbackQuery) -> None:
        from src.tasks.downloads_worker import download_audio

        session = user_session_storage.get_session(chat_id=callback.message.chat.id)
        if session is None:
            await callback.answer()
            return
        
        content_type, audio_id = callback.data.split(":")
        audio = [a for a in session["media_data"]["audios"] if a["id"] == audio_id][0]

        if audio["name"] == "music":
            await callback.message.answer_audio(audio=audio["url"])
            
        else:
            download_audio.delay(
                chat_id=callback.message.chat.id, 
                message_id=callback.message.message_id, 
                service=session["service"], 
                audio_id=audio["id"],
                url=session["url"],
            )

        await callback.answer()
    
    @staticmethod
    async def handle_thumbnail(callback: CallbackQuery) -> None:
        session = user_session_storage.get_session(chat_id=callback.message.chat.id)
        if session is None:
            await callback.answer()
            return
        
        content_type, thumbnail_id = callback.data.split(":")
        thumbnail = [t for t in session["media_data"]["thumbnails"] if t["id"] == thumbnail_id][0]
        
        await callback.message.answer_photo(photo=thumbnail["url"])
        await callback.answer()
        
