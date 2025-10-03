from aiogram.types import Message


class ServiceHandler:
    """Базовый класс для обработки конкретных сервисов."""
    
    @staticmethod
    async def handle_youtube(url: str, message: Message, domain: str) -> None:
        """Обработчик YouTube."""
        from src.tasks.information_worker import get_media_info
        get_media_info.delay(
            url=url,
            service="youtube",
            chat_id=message.chat.id,
            message_id=message.message_id,
        )
    
    @staticmethod
    async def handle_instagram(url: str, message: Message, domain: str) -> None:
        """Обработчик Instagram."""
        from src.tasks.information_worker import get_media_info
        get_media_info.delay(
            url=url,
            service="instagram",
            chat_id=message.chat.id,
            message_id=message.message_id,
        )
    
    @staticmethod
    async def handle_reddit(url: str, message: Message, domain: str) -> None:
        """Обработчик Reddit."""
        from src.tasks.information_worker import get_media_info
        get_media_info.delay(
            url=url,
            service="reddit",
            chat_id=message.chat.id,
            message_id=message.message_id,
        )
    
    @staticmethod
    async def handle_rutube(url: str, message: Message, domain: str) -> None:
        """Обработчик Rutube."""
        from src.tasks.information_worker import get_media_info
        get_media_info.delay(
            url=url,
            service="rutube",
            chat_id=message.chat.id,
            message_id=message.message_id,
        )
    
    @staticmethod
    async def handle_tiktok(url: str, message: Message, domain: str) -> None:
        """Обработчик TikTok."""
        from src.tasks.information_worker import get_media_info
        get_media_info.delay(
            url=url,
            service="tiktok",
            chat_id=message.chat.id,
            message_id=message.message_id,
        )
