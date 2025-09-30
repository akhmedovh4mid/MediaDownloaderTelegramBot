from typing import List, Tuple
from collections import Counter

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.text_decorations import HtmlDecoration
from aiogram.types import InlineKeyboardMarkup, FSInputFile

from src.app import TelegramBot
from src.config import settings


def create_bot_for_worker() -> TelegramBot:
    """Создает экземпляр бота для использования в Celery worker."""
    telegram_bot = TelegramBot(
        token=settings.bot_token,
        server_ip=settings.bot_server_ip,
    )
    
    return telegram_bot


def _get_adjust_list(data: List[Tuple[int, str, str]]) -> List[int]:
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
    builder = InlineKeyboardBuilder()
    for _, text, callback_data in data:
        builder.button(
            text=text,
            callback_data=callback_data
        )
    builder.adjust(*_get_adjust_list(data=data))
    return builder.as_markup()


async def delete_message(
    chat_id: int,
    message_id: int,
) -> None:
    telegram = create_bot_for_worker()
    await telegram.bot.delete_message(
        chat_id=chat_id,
        message_id=message_id
    )


async def send_photo(
    chat_id: int,
    preview_url: str,
    caption: str,
    keyboard_data: List[Tuple[int, str, str]] = None,
) -> None:
    telegram_bot = create_bot_for_worker()
    
    safe_caption = None
    if caption:
        html_decoration = HtmlDecoration()
        safe_caption = html_decoration.quote(caption)
        
    
    reply_markup = _get_inline_keyboard(keyboard_data)
    
    await telegram_bot.bot.send_photo(
        chat_id=chat_id,
        photo=preview_url,
        caption=safe_caption,
        reply_markup=reply_markup
    )


async def send_video(
    chat_id: int,
    message_id: int,
    caption: str,
    path: str,
) -> None:
    telegram_bot = create_bot_for_worker()

    safe_caption = None
    if caption:
        html_decoration = HtmlDecoration()
        safe_caption = html_decoration.quote(caption)
        
    await telegram_bot.bot.send_video(
        chat_id=chat_id,
        caption=safe_caption,
        video=FSInputFile(path=path),
        supports_streaming=True,
    )
