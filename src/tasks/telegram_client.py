from typing import List, Tuple, Optional
from collections import Counter

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.text_decorations import HtmlDecoration
from aiogram.types import InlineKeyboardMarkup, FSInputFile, Message

from src.app import TelegramBot
from src.config import settings


def create_bot_for_worker() -> TelegramBot:
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
        builder.button(text=text, callback_data=callback_data)
    builder.adjust(*_get_adjust_list(data=data))
    return builder.as_markup()


async def delete_message(chat_id: int, message_id: int) -> None:
    telegram = create_bot_for_worker()
    await telegram.bot.delete_message(chat_id=chat_id, message_id=message_id)


async def send_message(
    chat_id: int,
    text: str,
    keyboard_data: Optional[List[Tuple[int, str, str]]] = None,
    parse_mode: str = "HTML",
    reply_to_message_id: Optional[int] = None,
) -> Message:
    telegram_bot = create_bot_for_worker()

    if parse_mode == "HTML" and text:
        html_decoration = HtmlDecoration()
        text = html_decoration.quote(text)

    reply_markup = _get_inline_keyboard(keyboard_data) if keyboard_data else None

    send_params = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": reply_markup,
        "parse_mode": parse_mode,
    }
    if reply_to_message_id:
        send_params["reply_to_message_id"] = reply_to_message_id

    return await telegram_bot.bot.send_message(**send_params)


async def send_photo(
    chat_id: int,
    preview_url: str,
    caption: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    keyboard_data: Optional[List[Tuple[int, str, str]]] = None,
    reply_to_message_id: Optional[int] = None,
) -> Message:
    telegram_bot = create_bot_for_worker()

    safe_caption = ""
    if caption:
        html_decoration = HtmlDecoration()
        safe_caption = html_decoration.quote(caption)

    reply_markup = _get_inline_keyboard(keyboard_data) if keyboard_data else None

    send_params = {
        "chat_id": chat_id,
        "photo": preview_url,
        "caption": safe_caption,
        "reply_markup": reply_markup,
        "parse_mode": "HTML",
    }
    if width:
        send_params["width"] = width
    if height:
        send_params["height"] = height
    if reply_to_message_id:
        send_params["reply_to_message_id"] = reply_to_message_id

    return await telegram_bot.bot.send_photo(**send_params)


async def send_video(
    chat_id: int,
    path: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    caption: str = "",
    reply_to_message_id: Optional[int] = None,
    supports_streaming: bool = True,
) -> Message:
    telegram_bot = create_bot_for_worker()

    safe_caption = ""
    if caption:
        html_decoration = HtmlDecoration()
        safe_caption = html_decoration.quote(caption)

    video = FSInputFile(path=path)

    send_params = {
        "chat_id": chat_id,
        "video": video,
        "caption": safe_caption,
        "supports_streaming": supports_streaming,
        "parse_mode": "HTML",
    }
    if width:
        send_params["width"] = width
    if height:
        send_params["height"] = height
    if reply_to_message_id:
        send_params["reply_to_message_id"] = reply_to_message_id

    return await telegram_bot.bot.send_video(**send_params)


async def send_audio(
    chat_id: int,
    audio_path: str,
    caption: str = "",
    title: Optional[str] = None,
    performer: Optional[str] = None,
    reply_to_message_id: Optional[int] = None,
    thumbnail_path: Optional[str] = None,  # локальный путь к миниатюре
    keyboard_data: Optional[List[Tuple[int, str, str]]] = None,
) -> Message:
    telegram_bot = create_bot_for_worker()

    safe_caption = HtmlDecoration().quote(caption) if caption else ""

    reply_markup = _get_inline_keyboard(keyboard_data) if keyboard_data else None

    audio_file = FSInputFile(audio_path)
    send_params = {
        "chat_id": chat_id,
        "audio": audio_file,
        "caption": safe_caption,
        "reply_markup": reply_markup,
        "parse_mode": "HTML",
    }

    if title:
        send_params["title"] = title
    if performer:
        send_params["performer"] = performer
    if reply_to_message_id:
        send_params["reply_to_message_id"] = reply_to_message_id
    if thumbnail_path:
        send_params["thumbnail"] = FSInputFile(thumbnail_path)

    return await telegram_bot.bot.send_audio(**send_params)
