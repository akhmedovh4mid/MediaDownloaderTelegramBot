from typing import List, Tuple, Optional
from collections import Counter

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.text_decorations import HtmlDecoration
from aiogram.types import InlineKeyboardMarkup, FSInputFile

from src.app import TelegramBot
from src.config import settings


def create_bot_for_worker() -> TelegramBot:
    """
    Создает экземпляр бота для использования в Celery worker.
    
    Returns:
        TelegramBot: Инициализированный экземпляр бота с настройками из конфигурации.
        
    Note:
        Используется в фоновых задачах Celery для отправки сообщений
        без доступа к оригинальному контексту бота.
    """
    telegram_bot = TelegramBot(
        token=settings.bot_token,
        server_ip=settings.bot_server_ip,
    )
    
    return telegram_bot


def _get_adjust_list(data: List[Tuple[int, str, str]]) -> List[int]:
    """
    Генерирует список для корректного размещения кнопок в клавиатуре.
    
    Args:
        data: Список кортежей (приоритет, текст, callback_data) для кнопок.
        
    Returns:
        List[int]: Список чисел, определяющих количество кнопок в каждом ряду.
        
    Example:
        >>> data = [(1, "Btn1", "cb1"), (1, "Btn2", "cb2"), (2, "Btn3", "cb3")]
        >>> _get_adjust_list(data)
        [2, 1]  # 2 кнопки в первом ряду, 1 во втором
    """
    counter = Counter(item[0] for item in data)
    adjust_list = []
    for item in counter.values():
        quotient = item // 3
        remainder = item % 3
        if quotient != 0:
            adjust_list.extend([3] * quotient)
        if remainder != 0:
            adjust_list.append(remainder)
            
    return adjust_list


def _get_inline_keyboard(data: List[Tuple[int, str, str]]) -> InlineKeyboardMarkup:
    """
    Создает inline-клавиатуру из переданных данных.
    
    Args:
        data: Список кортежей (приоритет, текст, callback_data) для кнопок.
        
    Returns:
        InlineKeyboardMarkup: Готовая разметка клавиатуры.
        
    Note:
        Приоритет используется для группировки кнопок - кнопки с одинаковым
        приоритетом размещаются вместе.
    """
    builder = InlineKeyboardBuilder()
    for _, text, callback_data in data:
        builder.button(
            text=text,
            callback_data=callback_data
        )
    builder.adjust(*_get_adjust_list(data=data))
    return builder.as_markup()


async def delete_message(chat_id: int, message_id: int) -> None:
    """
    Удаляет сообщение в указанном чате.
    
    Args:
        chat_id: ID чата, в котором нужно удалить сообщение.
        message_id: ID сообщения для удаления.
        
    Raises:
        aiogram.exceptions.TelegramAPIError: Если сообщение не найдено или нет прав для удаления.
    """
    telegram = create_bot_for_worker()
    await telegram.bot.delete_message(
        chat_id=chat_id,
        message_id=message_id
    )


async def send_message(
    chat_id: int,
    text: str,
    keyboard_data: Optional[List[Tuple[int, str, str]]] = None,
    parse_mode: str = "HTML"
) -> None:
    """
    Отправляет текстовое сообщение с возможной клавиатурой.
    
    Args:
        chat_id: ID чата для отправки сообщения.
        text: Текст сообщения.
        keyboard_data: Данные для создания inline-клавиатуры.
        parse_mode: Режим парсинга текста ("HTML" или "Markdown").
        
    Example:
        >>> await send_message(
        ...     chat_id=12345,
        ...     text="Привет, мир!",
        ...     keyboard_data=[(1, "Кнопка", "callback_data")]
        ... )
    """
    telegram_bot = create_bot_for_worker()
    
    # Экранирование HTML-символов в тексте
    if parse_mode == "HTML" and text:
        html_decoration = HtmlDecoration()
        text = html_decoration.quote(text)
    
    reply_markup = _get_inline_keyboard(keyboard_data) if keyboard_data else None
    
    await telegram_bot.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )


async def send_photo(
    chat_id: int,
    preview_url: str,
    caption: str,
    keyboard_data: Optional[List[Tuple[int, str, str]]] = None,
) -> None:
    """
    Отправляет фото с подписью и inline-клавиатурой.
    
    Args:
        chat_id: ID чата для отправки сообщения.
        preview_url: URL изображения для отправки.
        caption: Подпись к изображению.
        keyboard_data: Данные для создания inline-клавиатуры.
        
    Note:
        Подпись автоматически экранируется от HTML-символов.
    """
    telegram_bot = create_bot_for_worker()
    
    safe_caption = ""
    if caption:
        html_decoration = HtmlDecoration()
        safe_caption = html_decoration.quote(caption)
    
    reply_markup = _get_inline_keyboard(keyboard_data) if keyboard_data else None
    
    await telegram_bot.bot.send_photo(
        chat_id=chat_id,
        photo=preview_url,
        caption=safe_caption,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def send_video(
    chat_id: int,
    path: str,
    caption: str = "",
    message_id: Optional[int] = None,
    supports_streaming: bool = True,
) -> None:
    """
    Отправляет видеофайл с подписью.
    
    Args:
        chat_id: ID чата для отправки сообщения.
        path: Путь к видеофайлу на сервере.
        caption: Подпись к видео (опционально).
        message_id: ID сообщения для ответа (опционально).
        supports_streaming: Разрешить потоковое воспроизведение видео.
        
    Note:
        Если передан message_id, видео будет отправлено как ответ на указанное сообщение.
    """
    telegram_bot = create_bot_for_worker()

    safe_caption = ""
    if caption:
        html_decoration = HtmlDecoration()
        safe_caption = html_decoration.quote(caption)
    
    video = FSInputFile(path=path)
    
    send_params = {
        "chat_id": chat_id,
        "caption": safe_caption,
        "video": video,
        "supports_streaming": supports_streaming,
        "parse_mode": "HTML"
    }
    
    if message_id:
        send_params["reply_to_message_id"] = message_id
        
    await telegram_bot.bot.send_video(**send_params)


async def send_audio(
    chat_id: int,
    audio_url: str,
    caption: str = "",
    title: Optional[str] = None,
    performer: Optional[str] = None,
    message_id: Optional[int] = None,
    thumbnail_url: Optional[str] = None,
    keyboard_data: Optional[List[Tuple[int, str, str]]] = None,
) -> None:
    """
    Отправляет аудио по URL с дополнительной информацией.
    
    Args:
        chat_id: ID чата для отправки сообщения.
        audio_url: Публичный URL аудиофайла.
        caption: Подпись к аудио (опционально).
        title: Название аудио (опционально).
        performer: Исполнитель (опционально).
        message_id: ID сообщения для ответа (опционально).
        thumbnail_url: URL обложки аудио (опционально).
        keyboard_data: Данные для создания inline-клавиатуры.
        
    Note:
        - URL должен быть публично доступным
        - Если передан message_id, аудио будет отправлено как ответ на указанное сообщение
        - Максимальный размер файла: 50MB для URL
    """
    telegram_bot = create_bot_for_worker()

    safe_caption = ""
    if caption:
        html_decoration = HtmlDecoration()
        safe_caption = html_decoration.quote(caption)
    
    reply_markup = _get_inline_keyboard(keyboard_data) if keyboard_data else None
    
    send_params = {
        "chat_id": chat_id,
        "audio": audio_url,
        "caption": safe_caption,
        "reply_markup": reply_markup,
        "parse_mode": "HTML"
    }
    
    if title:
        send_params["title"] = title
    if performer:
        send_params["performer"] = performer
    if message_id:
        send_params["reply_to_message_id"] = message_id
    if thumbnail_url:
        send_params["thumbnail"] = thumbnail_url
        
    await telegram_bot.bot.send_audio(**send_params)


async def send_media_group(
    chat_id: int,
    photo_urls: List[str],
    caption: str = "",
    message_id: Optional[int] = None,
) -> None:
    """
    Отправляет группу изображений (альбом) по URL.
    
    Args:
        chat_id: ID чата для отправки сообщения.
        photo_urls: Список публичных URL изображений.
        caption: Подпись для альбома (опционально). 
                Будет показана только под первым изображением.
        message_id: ID сообщения для ответа (опционально).
        
    Note:
        - Все URL должны быть публично доступными
        - Максимальное количество изображений в группе: 10
        - Форматы: JPEG, PNG, WEBP
        - Максимальный размер каждого файла: 5MB
        
    Example:
        >>> await send_media_group(
        ...     chat_id=12345,
        ...     photo_urls=[
        ...         "https://example.com/photo1.jpg",
        ...         "https://example.com/photo2.jpg"
        ...     ],
        ...     caption="Мой фотоальбом"
        ... )
    """
    telegram_bot = create_bot_for_worker()
    
    safe_caption = ""
    if caption:
        html_decoration = HtmlDecoration()
        safe_caption = html_decoration.quote(caption)
    
    from aiogram.types import InputMediaPhoto
    
    # Ограничиваем количество фото до 10 (ограничение Telegram)
    photo_urls = photo_urls[:10]
    
    media_group = []
    for i, url in enumerate(photo_urls):
        # Подпись добавляется только к первому изображению
        media_item = InputMediaPhoto(
            media=url, 
            caption=safe_caption if i == 0 else ""
        )
        media_group.append(media_item)
    
    if not media_group:
        return
    
    send_params = {
        "chat_id": chat_id,
        "media": media_group
    }
    
    if message_id:
        send_params["reply_to_message_id"] = message_id
        
    await telegram_bot.bot.send_media_group(**send_params)
