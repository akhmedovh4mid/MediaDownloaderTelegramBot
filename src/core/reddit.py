"""
Модуль загрузчика Reddit.

Этот модуль предоставляет функционал для загрузки медиа-контента с Reddit,
включая галереи изображений, видео-посты и отдельные изображения.
"""

import os
import hashlib
import logging
from enum import Enum
from uuid import uuid4
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Union

from praw import Reddit 
from yt_dlp import YoutubeDL
from praw.models import Submission
from yt_dlp.utils import DownloadError, ExtractorError

from .abstractions import (
    AbstractServiceData,
    AbstractServiceVideo,
    AbstractServiceAudio,
    AbstractServiceImage,
    AbstractServiceResult,
    AbstractServiceDownloader, 
)


# Настройка логирования
logger = logging.getLogger("reddit")


# ======= EnumsClasses =======
class ContentType(Enum):
    """Перечисление типов контента Reddit."""
    LINK = "link"
    VIDEO = "video"
    IMAGE = "image"
    GALLERY = "gallery"
    UNSUPPORTED = "unsupported"
        

class RedditErrorCode(Enum):
    """Коды ошибок для операций с Reddit."""
    
    # Успех
    SUCCESS = "SUCCESS"
    
    # Ошибки проверки входных данных (1xx)
    INVALID_URL = "INVALID_URL"
    EMPTY_URL = "EMPTY_URL"
    UNSUPPORTED_CONTENT = "UNSUPPORTED_CONTENT"
    
    # Ошибки аутентификации/API (2xx)
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    API_ERROR = "API_ERROR"
    RATELIMIT_EXCEEDED = "RATELIMIT_EXCEEDED"
    
    # Сетевые ошибки (3xx)
    CONNECTION_ERROR = "CONNECTION_ERROR"
    DOWNLOAD_ERROR = "DOWNLOAD_ERROR"
    EXTRACTOR_ERROR = "EXTRACTOR_ERROR"
    PROXY_ERROR = "PROXY_ERROR"
    
    # Ошибки контента (4xx)
    GALLERY_DATA_MISSING = "GALLERY_DATA_MISSING"
    GALLERY_EMPTY = "GALLERY_EMPTY"
    VIDEO_EXTRACTION_FAILED = "VIDEO_EXTRACTION_FAILED"
    IMAGE_EXTRACTION_FAILED = "IMAGE_EXTRACTION_FAILED"
    MEDIA_METADATA_MISSING = "MEDIA_METADATA_MISSING"
    PREVIEW_DATA_MISSING = "PREVIEW_DATA_MISSING"
    
    # Ошибки файловой системы (5xx)
    COOKIE_FILE_NOT_FOUND = "COOKIE_FILE_NOT_FOUND"
    OUTPUT_PATH_ERROR = "OUTPUT_PATH_ERROR"
    FILE_WRITE_ERROR = "FILE_WRITE_ERROR"
    
    # Системные ошибки (6xx)
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
    EXTRACT_INFO_NOT_CALLED = "EXTRACT_INFO_NOT_CALLED"


# ======= DataClasses =======
@dataclass
class RedditData(AbstractServiceData):
    """Контейнер данных о медиа с Reddit."""
    pass


@dataclass
class RedditImage(AbstractServiceImage):
    """Представление изображения с Reddit."""
    pass


@dataclass
class RedditVideo(AbstractServiceVideo):
    """Представление видео с Reddit."""
    pass


@dataclass
class RedditAudio(AbstractServiceAudio):
    """Представление аудио с Reddit."""
    pass


@dataclass
class RedditResult(AbstractServiceResult):
    """Результат операций с Reddit."""
    code: RedditErrorCode = field(default=RedditErrorCode.SUCCESS)


# ======= ExceptionClasses =======
class ExtractInfoNotCalledError(Exception):
    """Исключение при попытке загрузки до вызова extract_info()."""
    def __init__(self, message: str, code: RedditErrorCode = RedditErrorCode.EXTRACT_INFO_NOT_CALLED):
        super().__init__(message)
        self.code = code
        self.message = message


class CookieFileNotFoundError(FileNotFoundError):
    """Исключение при отсутствии файла cookie."""
    def __init__(self, message: str, code: RedditErrorCode = RedditErrorCode.COOKIE_FILE_NOT_FOUND):
        super().__init__(message)
        self.code = code
        self.message = message


class InvalidRedditUrlError(ValueError):
    """Исключение при некорректном URL Reddit."""
    def __init__(self, message: str, code: RedditErrorCode = RedditErrorCode.INVALID_URL):
        super().__init__(message)
        self.code = code
        self.message = message


class UnsupportedContentTypeError(Exception):
    """Исключение для неподдерживаемого типа контента."""
    def __init__(self, message: str, code: RedditErrorCode = RedditErrorCode.UNSUPPORTED_CONTENT):
        super().__init__(message)
        self.code = code
        self.message = message


# ======= MainClass =======
class RedditDownloader(AbstractServiceDownloader):
    """
    Загрузчик медиа-контента с Reddit.
    
    Поддерживает загрузку:
    - Галерей изображений
    - Видео-постов
    - Отдельных изображений
    """
    
    # Поддерживаемые домены Reddit
    SUPPORTED_DOMAINS = {"reddit.com", "i.redd.it", "v.redd.it"}

    def __init__(
        self,
        client_id: str, 
        client_secret: str,
        retries_count: int = 10,
        proxy: Optional[str] = None,
        cookie_path: Optional[str] = None,
        concurrent_download_count: int = 2,
        user_agent: str = "bot/1.0 by TelegramDownloader",
    ) -> None:
        """
        Инициализация загрузчика Reddit.
        
        Args:
            client_id: ID клиента Reddit API
            client_secret: Секрет клиента Reddit API
            retries_count: Количество попыток повтора для загрузок
            proxy: URL прокси-сервера (опционально)
            cookie_path: Путь к файлу cookies (опционально)
            concurrent_download_count: Количество одновременных загрузок фрагментов
            user_agent: Строка User-Agent для запросов
        """
        logger.info("Инициализация загрузчика Reddit")
        
        self.proxy = proxy
        self.cookies_path = Path(cookie_path) if cookie_path else None

        # Проверка существования файла cookie
        if self.cookies_path and not self.cookies_path.exists():
            error_msg = f"Файл cookie не найден: {self.cookies_path}"
            logger.error(error_msg)
            raise CookieFileNotFoundError(error_msg, RedditErrorCode.COOKIE_FILE_NOT_FOUND)

        try:
            # Инициализация клиента Reddit
            self.reddit = Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
            
            # Настройка параметров yt-dlp
            self.ydl_opts: Dict[str, Optional[Union[bool, str, Path]]] = {
                "quiet": True,
                "proxy": self.proxy,
                "no_warnings": False,
                "cookiefile": self.cookies_path,
                
                "playlistend": 1,
                "noplaylist": True,
                
                "retries": retries_count,
                "fragment_retries": retries_count,
                
                "concurrent_fragment_downloads": concurrent_download_count,
            }
            
            self._data: Optional[RedditData] = None
            self._last_result: Optional[RedditResult] = None
            
            logger.debug("Загрузчик Reddit успешно инициализирован")
            
        except Exception as e:
            error_msg = f"Ошибка инициализации загрузчика Reddit: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e
        
    def _validate_reddit_url(self, url: str) -> bool:
        """
        Проверка валидности URL Reddit.
        
        Args:
            url: URL для проверки
            
        Returns:
            True если URL является валидным URL Reddit
        """
        try:
            parsed = urlparse(url)
            return any(domain in parsed.netloc for domain in self.SUPPORTED_DOMAINS)
        except Exception as e:
            logger.debug(f"Ошибка проверки URL: {e}")
            return False
    
    def _classify_content_type(self, submission: Submission) -> ContentType:
        """
        Классификация типа контента публикации Reddit.
        
        Args:
            submission: Объект публикации Reddit
            
        Returns:
            ContentType: Классифицированный тип контента
        """
        logger.debug("Классификация типа контента")
        
        if hasattr(submission, "is_gallery") and submission.is_gallery:
            result = ContentType.GALLERY
        elif hasattr(submission, "is_video") and submission.is_video:
            result = ContentType.VIDEO
        elif (hasattr(submission, "post_hint") and 
              submission.post_hint == "image"):
            result = ContentType.IMAGE
        elif (hasattr(submission, "domain") and 
              submission.domain == "i.redd.it"):
            result = ContentType.IMAGE
        elif (hasattr(submission, "domain") and 
              submission.domain == "v.redd.it"):
            result = ContentType.VIDEO
        elif (hasattr(submission, "post_hint") and 
              submission.post_hint == "link"):
            result = ContentType.LINK
        else:
            result = ContentType.UNSUPPORTED
        
        logger.debug(f"Контент классифицирован как: {result.value}")
        return result
        
    def _extract_gallery(self, submission: Submission) -> None:
        """Извлечение данных из галереи изображений."""
        logger.info(f"Извлечение галереи из поста: {submission.id}")

        if not (hasattr(submission, "gallery_data") and submission.gallery_data):
            error_msg = "Данные галереи не найдены"
            logger.error(error_msg)
            self._last_result = RedditResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RedditErrorCode.GALLERY_DATA_MISSING,
            )
            return
        
        try:
            gallery_items = submission.gallery_data.get("items", [])
            if not gallery_items:
                error_msg = "Данные галереи пусты"
                logger.error(error_msg)
                self._last_result = RedditResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=RedditErrorCode.GALLERY_EMPTY,
                )
                return
            
            image_count = 0
            for idx, item in enumerate(gallery_items):
                media_id = item["media_id"]
                
                if (hasattr(submission, "media_metadata") and 
                    media_id in submission.media_metadata):
                    
                    metadata = submission.media_metadata[media_id]
                    
                    if metadata.get("status") == "valid":
                        for image in metadata.get("p", []):
                            name = f"{metadata.get('e', 'Image')}_{image.get('x', 0)}x{image.get('y', 0)}_{idx}"
                            self._data.images.append(
                                RedditImage(
                                    id=uuid4(),
                                    url=image["u"],
                                    name=name,
                                    width=image.get("x"),
                                    height=image.get("y"),
                                )
                            )
                            image_count += 1
                            
            if image_count > 0:
                self._last_result = RedditResult(data=self._data)
                logger.info(f"Успешно извлечено {image_count} изображений из галереи")
            else:
                error_msg = "В галерее не найдено валидных изображений"
                logger.error(error_msg)
                self._last_result = RedditResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=RedditErrorCode.MEDIA_METADATA_MISSING,
                )
                
        except Exception as e:
            error_msg = f"Ошибка извлечения галереи: {str(e)}"
            logger.error(error_msg)
            self._last_result = RedditResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RedditErrorCode.UNEXPECTED_ERROR,
            )
        
    def _get_extension(self, url: str) -> Tuple[str, str]:
        """
        Извлечение имени файла и расширения из URL.
        
        Args:
            url: URL для извлечения
            
        Returns:
            Кортеж (имя, расширение)
        """
        parsed = urlparse(url=url)
        filename = os.path.basename(parsed.path)
        name, ext = os.path.splitext(filename)
        return (name, ext.replace(".", "").lower())
    
    def _extract_image_from_preview(self, submission: Submission) -> bool:
        """Извлечение изображения из данных предпросмотра поста."""
        if not (hasattr(submission, "preview") and submission.preview):
            return False
        
        name, ext = self._get_extension(url=submission.url)
        if not submission.preview:
            return False
        
        images = submission.preview.get("images", [])
        if not images:
            return False
        
        for image in images:
            variants = image.get("variants", {})
            target_variant = variants.get(ext) if ext in variants else None
            
            if target_variant:
                self._add_image_from_data(target_variant, f"{name}_{ext}")
            else:
                self._add_image_from_data(image, name)
                
        return True
    
    def _add_image_from_data(self, image_data: dict, base_name: str) -> None:
        """Добавление изображений из данных предпросмотра."""
        # Дополнительные разрешения
        for idx, resolution in enumerate(image_data.get("resolutions", [])):
            self._data.images.append(
                RedditImage(
                    id=uuid4(),
                    url=resolution["url"],
                    name=f"{base_name}_res_{idx}",
                    width=resolution["width"],
                    height=resolution["height"],
                )
            )
            
        # Основное изображение (наивысшее качество)
        if "source" in image_data:
            source = image_data["source"]
            self._data.images.append(
                RedditImage(
                    id=uuid4(),
                    url=source["url"],
                    name=f"{base_name}_source",
                    width=source["width"],
                    height=source["height"],
                )
            )
    
    def _extract_image(self, submission: Submission) -> None:
        """Извлечение данных из поста с одним изображением."""
        logger.info(f"Извлечение изображения из поста: {submission.id}")
        
        try:
            if self._extract_image_from_preview(submission=submission):
                self._last_result = RedditResult(data=self._data)
                logger.info(f"Успешно извлечено {len(self._data.images)} вариантов изображения из предпросмотра")
                return
            
            # Резервный вариант: использование прямого URL если предпросмотр недоступен
            self._data.images.append(
                RedditImage(
                    id=uuid4(),
                    url=submission.url,
                    name="direct_image",
                    width=None,
                    height=None,
                )
            )
            self._last_result = RedditResult(data=self._data)
            logger.info("Использован прямой URL изображения как резервный вариант")
            
        except Exception as e:
            error_msg = f"Ошибка извлечения изображения: {str(e)}"
            logger.error(error_msg)
            self._last_result = RedditResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RedditErrorCode.IMAGE_EXTRACTION_FAILED,
            )
        
    def _extract_video(self, submission: Submission) -> None:
        """Извлечение данных из видео-поста."""
        logger.info(f"Извлечение видео из поста: {submission.id}")
        
        ydl_opts = self.ydl_opts.copy()
        ydl_opts['listformats'] = True

        try:
            with YoutubeDL(params=ydl_opts) as ydl:
                data = ydl.extract_info(url=submission.url, download=False)
                logger.debug("Извлечение информации о видео завершено")
                
        except ExtractorError as e:
            error_msg = f"Ошибка экстрактора видео: {str(e)}"
            logger.error(error_msg)
            self._last_result = RedditResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RedditErrorCode.EXTRACTOR_ERROR,
            )
            return
        
        except DownloadError as e:
            error_msg = f"Ошибка загрузки видео: {str(e)}"
            logger.error(error_msg)
            self._last_result = RedditResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RedditErrorCode.DOWNLOAD_ERROR,
            )
            return
    
        except Exception as e:
            error_msg = f"Неожиданная ошибка при извлечении видео: {str(e)}"
            logger.error(error_msg)
            self._last_result = RedditResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RedditErrorCode.UNEXPECTED_ERROR,
            )
            return
        
        if data.get("_type") == "playlist":
            for item in data["entries"]:
                self._extract_media_formats(item)
                self._extract_thumbnails(item)
                
        else:
            self._extract_media_formats(data)
            self._extract_thumbnails(data)
        
        self._last_result = RedditResult(data=self._data)
        logger.info(f"Успешно извлечено видео с {len(self._data.videos)} видео-форматами и {len(self._data.audios)} аудио-форматами")

    def _extract_media_formats(self, data: dict) -> None:
        """Извлечение доступных видео и аудио форматов."""
        for format in data.get("formats", []):
            if (
                format["ext"] == "mp4"
                and format["vcodec"] == "h264"
            ):
                self._data.videos.append(
                    RedditVideo(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        fps=format.get("fps"),
                        width=format.get("width"),
                        height=format.get("height"),
                        total_bitrate=format.get("tbr"),
                    )
                )
                video_count += 1
                
            elif (
                format.get("ext") == "mp4" 
                and format.get("vcodec", "").startswith("avc1")
            ):
                self._data.videos.append(
                    RedditVideo(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        fps=format.get("fps"),
                        width=format.get("width"),
                        height=format.get("height"),
                        total_bitrate=format.get("tbr"),
                    )
                )
                video_count += 1
                
            elif (
                format.get("ext") == "m4a"
                and format.get("vcodec") == "none"
                and format.get("acodec").startswith("mp4a")
            ):
                self._data.audios.append(
                    RedditAudio(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                    )
                )
                audio_count += 1
                
            elif (
                format.get("ext") == "m4a"
                and format.get("vcodec") == "none"
                and format.get("acodec").startswith("aac")
            ):
                self._data.audios.append(
                    RedditAudio(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                    )
                )
                audio_count += 1
                
        logger.debug(f"Извлечено {video_count} видео-форматов и {audio_count} аудио-форматов")
                  
    def _extract_thumbnails(self, data: dict) -> None:
        """Извлечение миниатюр."""
        thumbnail_count = 0
        for idx, thumbnail in enumerate(data.get("thumbnails", [])):
            self._data.thumbnails.append(
                RedditImage(
                    id=uuid4(),
                    url=thumbnail["url"],
                    name=f"Thumbnail_{idx}",
                    width=thumbnail.get("width"),
                    height=thumbnail.get("height"),
                )
            )
            thumbnail_count += 1
            
        logger.debug(f"Извлечено {thumbnail_count} миниатюр")
            
    def _generate_safe_filename(self, url: str, video_format_id: str) -> str:
        """
        Генерация безопасного имени файла на основе хеша URL.
        
        Args:
            url: URL контента
            video_format_id: ID видео формата
            
        Returns:
            Строка с безопасным именем файла
        """
        hash_input = f"reddit_{url}_{video_format_id}"
        file_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return file_hash
    
    def extract_info(self, url: str) -> RedditResult:
        """
        Извлечение информации о медиа из URL Reddit.
        
        Args:
            url: URL Reddit для извлечения информации
            
        Returns:
            RedditResult: Результат, содержащий извлеченные данные медиа
        """
        logger.info(f"Извлечение информации из URL: {url}")
        
        if not url or not isinstance(url, str):
            error_msg = "Предоставлен невалидный URL"
            logger.error(error_msg)
            return RedditResult(
                status="error",
                context=error_msg,
                data=RedditData(url=url),
                code=RedditErrorCode.EMPTY_URL,
            )
            
        if not self._validate_reddit_url(url):
            error_msg = "Невалидный или неподдерживаемый URL Reddit"
            logger.error(error_msg)
            return RedditResult(
                status="error",
                context=error_msg,
                data=RedditData(url=url),
                code=RedditErrorCode.INVALID_URL,
            )
            
        try:
            self._data = RedditData(url=url)
            submission = self.reddit.submission(url=url)
            print(submission._fetch_data())

            self._data.title = getattr(submission, "title", None)
            self._data.description = getattr(submission, "selftext", None)
            self._data.author_name = getattr(submission, "subreddit_name_prefixed", None)
            
            # Классификация типа контента и соответствующая обработка
            content_type = self._classify_content_type(submission)
            
            logger.info(f"Обнаружен тип контента: {content_type.value}")
            
            if content_type == ContentType.GALLERY:
                self._data.is_image = True
                self._extract_gallery(submission=submission)
            elif content_type == ContentType.VIDEO:
                self._data.is_video = True
                self._extract_video(submission=submission)
            elif content_type == ContentType.IMAGE or content_type == ContentType.LINK:
                self._data.is_image = True
                self._extract_image(submission=submission)
            else:
                error_msg = f"Неподдерживаемый тип контента: {content_type.value}"
                logger.error(error_msg)
                self._last_result = RedditResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=RedditErrorCode.UNSUPPORTED_CONTENT,
                )
                
            return self._last_result
        
        except Exception as e:
            error_msg = f"Ошибка извлечения: {str(e)}"
            logger.error(error_msg)
            return RedditResult(
                status="error",
                context=error_msg,
                data=RedditData(url=url),
                code=RedditErrorCode.UNEXPECTED_ERROR,
            )
        
    def download_media(
        self,
        url: str,
        video_format_id: str,
        output_path: str = "./downloads/reddit/",
    ) -> RedditResult:
        """
        Загрузка медиа с использованием ранее извлеченной информации.
        
        Args:
            url: URL видео Reddit для загрузки
            video_format_id: ID видео формата для загрузки
            output_path: Путь к директории для сохранения загруженного файла
            
        Returns:
            RedditResult: Результат операции загрузки
            
        Raises:
            ExtractInfoNotCalledError: Если extract_info не был вызван первым
        """
        logger.info(f"Начало загрузки медиа: url={url}, format={video_format_id}")
         
        # Подготовка выходной директории
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Генерация безопасного имени файла
        safe_filename = self._generate_safe_filename(
            url=url,
            video_format_id=video_format_id,
        )
        file_path = output_dir / f"{safe_filename}.mp4"
        
        # Настройка параметров загрузки
        ydl_opts = self.ydl_opts.copy()
        ydl_opts.update({
            "outtmpl": str(file_path),
            "format": f"{video_format_id}+bestaudio[ext=m4a]",
            "merge_output_format": "mp4",
        })
        
        try:
            logger.info(f"Начало загрузки в: {file_path}")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            logger.info("Загрузка успешно завершена")
            return RedditResult(data=RedditData(url=url, path=file_path, is_video=True))

        except DownloadError as e:
            error_msg = f"Ошибка загрузки: {e}"
            logger.error(error_msg)
            return RedditResult(
                status="error",
                context=error_msg,
                code=RedditErrorCode.DOWNLOAD_ERROR,
                data=RedditData(url=url)
            )
        except Exception as e:
            error_msg = f"Неожиданная ошибка загрузки: {e}"
            logger.error(error_msg)
            return RedditResult(
                status="error",
                context=error_msg,
                code=RedditErrorCode.UNEXPECTED_ERROR,
                data=RedditData(url=url)
            )

    def get_error_description(self, code: RedditErrorCode) -> str:
        """
        Получение человеко-читаемого описания для кода ошибки.
        
        Args:
            code: Значение перечисления кода ошибки
            
        Returns:
            Строка с описанием
        """
        descriptions = {
            RedditErrorCode.SUCCESS: "Операция успешно завершена",
            RedditErrorCode.INVALID_URL: "Предоставленный URL Reddit невалиден или не поддерживается",
            RedditErrorCode.EMPTY_URL: "Предоставлен пустой или невалидный URL",
            RedditErrorCode.UNSUPPORTED_CONTENT: "Тип контента Reddit не поддерживается",
            RedditErrorCode.AUTHENTICATION_FAILED: "Ошибка аутентификации Reddit API",
            RedditErrorCode.API_ERROR: "Reddit API вернул ошибку",
            RedditErrorCode.RATELIMIT_EXCEEDED: "Превышен лимит запросов Reddit API",
            RedditErrorCode.CONNECTION_ERROR: "Произошла ошибка сетевого соединения",
            RedditErrorCode.DOWNLOAD_ERROR: "Ошибка загрузки медиа",
            RedditErrorCode.EXTRACTOR_ERROR: "Ошибка извлечения медиа",
            RedditErrorCode.PROXY_ERROR: "Ошибка подключения к прокси",
            RedditErrorCode.GALLERY_DATA_MISSING: "Данные галереи не найдены в посте",
            RedditErrorCode.GALLERY_EMPTY: "Галерея не содержит элементов",
            RedditErrorCode.VIDEO_EXTRACTION_FAILED: "Ошибка извлечения видео контента",
            RedditErrorCode.IMAGE_EXTRACTION_FAILED: "Ошибка извлечения изображения",
            RedditErrorCode.MEDIA_METADATA_MISSING: "Метаданные медиа недоступны",
            RedditErrorCode.PREVIEW_DATA_MISSING: "Данные предпросмотра недоступны",
            RedditErrorCode.COOKIE_FILE_NOT_FOUND: "Файл cookie не найден",
            RedditErrorCode.OUTPUT_PATH_ERROR: "Ошибка пути вывода",
            RedditErrorCode.FILE_WRITE_ERROR: "Ошибка записи файла",
            RedditErrorCode.UNEXPECTED_ERROR: "Произошла непредвиденная ошибка",
            RedditErrorCode.INITIALIZATION_ERROR: "Ошибка инициализации загрузчика",
            RedditErrorCode.EXTRACT_INFO_NOT_CALLED: "extract_info() должен быть вызван перед загрузкой",
        }
        return descriptions.get(code, "Неизвестная ошибка")
