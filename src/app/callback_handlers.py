from aiogram.types import CallbackQuery


class ServiceCallbackHandler:
    
    @staticmethod
    async def handle_video(callback: CallbackQuery) -> None:
        _, video_id = callback.data.split(":")
        
        from src.tasks.app import user_session_storage
        session = user_session_storage.get_session(chat_id=callback.message.chat.id)
        
        if not session:
            await callback.message.edit_text("❌ Сессия не найдена. Отправьте ссылку заново.")
            return
        
        video_data = [video for video in session["media_data"]["videos"] if video["id"] == video_id]
        print(video_data)
        
        if session["service"] == "youtube":
            from src.tasks.downloads_worker import download_youtube_video
            download_youtube_video.delay(chat_id=callback.message.chat.id, message_id=callback.message.message_id, url=session["url"] ,video=video_data[0])
        
    
    @staticmethod
    async def handle_image(callback: CallbackQuery) -> None:
        print(callback.data)
        
    @staticmethod
    async def handle_auido(callback: CallbackQuery) -> None:
        print(callback.data)
    
    @staticmethod
    async def handle_thumbnail(callback: CallbackQuery) -> None:
        print(callback.data)
        
