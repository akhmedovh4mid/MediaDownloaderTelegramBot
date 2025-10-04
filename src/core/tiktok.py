"""
Модуль загрузчика TikTok.

Этот модуль предоставляет функционал для загрузки медиа-контента с TikTok,
включая видео, изображения и аудио.
"""

import hashlib
import logging
from enum import Enum
from uuid import uuid4
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

from yt_dlp import YoutubeDL
from gallery_dl import extractor
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
logger = logging.getLogger("tiktok")


# ======= EnumsClasses =======
class ContentType(Enum):
    """Перечисление, представляющее различные типы контента TikTok."""
    LIVE = "live"
    PHOTO = "photo"
    VIDEO = "video"
    MUSIC = "music"
    ACCOUNT = "account"
    UNKNOWN = "unknown"
    
    
class TikTokErrorCode(Enum):
    """Перечисление, представляющее коды ошибок для операций с TikTok."""
    
    # Успех
    SUCCESS = "SUCCESS"
    
    # Ошибки проверки входных данных (1xx)
    INVALID_URL = "INVALID_URL"
    EMPTY_URL = "EMPTY_URL"
    UNSUPPORTED_CONTENT_TYPE = "UNSUPPORTED_CONTENT_TYPE"
    URL_RESOLUTION_FAILED = "URL_RESOLUTION_FAILED"
    
    # Сетевые ошибки (2xx)
    CONNECTION_ERROR = "CONNECTION_ERROR"
    DOWNLOAD_ERROR = "DOWNLOAD_ERROR"
    EXTRACTOR_ERROR = "EXTRACTOR_ERROR"
    PROXY_ERROR = "PROXY_ERROR"
    
    # Ошибки контента (3xx)
    NO_EXTRACTOR_FOUND = "NO_EXTRACTOR_FOUND"
    NO_CONTENT_FOUND = "NO_CONTENT_FOUND"
    METADATA_EXTRACTION_FAILED = "METADATA_EXTRACTION_FAILED"
    VIDEO_EXTRACTION_FAILED = "VIDEO_EXTRACTION_FAILED"
    PHOTO_EXTRACTION_FAILED = "PHOTO_EXTRACTION_FAILED"
    MUSIC_EXTRACTION_FAILED = "MUSIC_EXTRACTION_FAILED"
    NO_MEDIA_FORMATS_FOUND = "NO_MEDIA_FORMATS_FOUND"
    NO_IMAGES_FOUND = "NO_IMAGES_FOUND"
    NO_THUMBNAILS_FOUND = "NO_THUMBNAILS_FOUND"
    
    # Ошибки файловой системы (4xx)
    COOKIE_FILE_NOT_FOUND = "COOKIE_FILE_NOT_FOUND"
    OUTPUT_PATH_ERROR = "OUTPUT_PATH_ERROR"
    FILE_WRITE_ERROR = "FILE_WRITE_ERROR"
    
    # Системные ошибки (5xx)
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
    EXTRACT_INFO_NOT_CALLED = "EXTRACT_INFO_NOT_CALLED"
    GALLERY_DL_ERROR = "GALLERY_DL_ERROR"
    YT_DLP_ERROR = "YT_DLP_ERROR"


# ======= DataClasses =======
@dataclass
class TikTokData(AbstractServiceData):
    """Контейнер для данных медиа с TikTok."""
    pass


@dataclass
class TikTokImage(AbstractServiceImage):
    """Представляет изображение TikTok."""
    pass


@dataclass
class TikTokVideo(AbstractServiceVideo):
    """Представляет видео формат TikTok."""
    pass


@dataclass
class TikTokAudio(AbstractServiceAudio):
    """Представляет аудио формат TikTok."""
    pass


@dataclass
class TikTokResult(AbstractServiceResult):
    """Результат операций с TikTok."""
    code: TikTokErrorCode = field(default=TikTokErrorCode.SUCCESS)


# ======= ExceptionClasses =======
class ExtractInfoNotCalledError(Exception):
    """Исключение при попытке загрузки до вызова extract_info."""
    def __init__(self, message: str, code: TikTokErrorCode = TikTokErrorCode.EXTRACT_INFO_NOT_CALLED):
        super().__init__(message)
        self.code = code
        self.message = message


class CookieFileNotFoundError(FileNotFoundError):
    """Исключение при отсутствии файла cookie."""
    def __init__(self, message: str, code: TikTokErrorCode = TikTokErrorCode.COOKIE_FILE_NOT_FOUND):
        super().__init__(message)
        self.code = code
        self.message = message


class UnsupportedContentTypeError(Exception):
    """Исключение для неподдерживаемых типов контента."""
    def __init__(self, message: str, code: TikTokErrorCode = TikTokErrorCode.UNSUPPORTED_CONTENT_TYPE):
        super().__init__(message)
        self.code = code
        self.message = message
    

# ======= MainClass =======
class TikTokDownloader(AbstractServiceDownloader):
    """
    Загрузчик медиа-контента с TikTok.
    
    Поддерживает загрузку видео и изображений с TikTok.
    Обрабатывает разрешение URL и классификацию типов контента.
    """

    def __init__(
        self,
        retries_count: int = 10,
        proxy: Optional[str] = None,
        cookie_path: Optional[str] = None,
        concurrent_download_count: int = 2,
    ) -> None:
        """
        Инициализация загрузчика TikTok.
        
        Args:
            retries_count: Количество попыток повтора для загрузок
            proxy: URL прокси-сервера (опционально)
            cookie_path: Путь к файлу cookies (опционально)
            concurrent_download_count: Количество одновременных загрузок фрагментов
        """
        logger.info("Инициализация загрузчика TikTok")
        
        self.proxy = proxy
        self.cookies_path = Path(cookie_path) if cookie_path else None

        if self.cookies_path and not self.cookies_path.exists():
            error_msg = f"Файл cookie не найден: {self.cookies_path}"
            logger.error(error_msg)
            raise CookieFileNotFoundError(error_msg, TikTokErrorCode.COOKIE_FILE_NOT_FOUND)

        try:
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
            
            self.unsupported_types: List[ContentType] = [
                ContentType.ACCOUNT,
                ContentType.LIVE,
                ContentType.MUSIC,
                ContentType.UNKNOWN
            ]
            
            self._data: Optional[TikTokData] = None
            self._last_result: Optional[TikTokResult] = None
            
            logger.debug("Загрузчик TikTok успешно инициализирован")

        except Exception as e:
            error_msg = f"Ошибка инициализации загрузчика TikTok: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

    def _resolve_vm_url(self, url: str) -> Optional[str]:
        """
        Разрешение сокращенных URL TikTok (vm.tiktok.com, vt.tiktok.com).
        
        Args:
            url: Сокращенный URL TikTok
            
        Returns:
            Разрешенный URL или None если разрешение не удалось
        """
        logger.debug(f"Разрешение сокращенного URL: {url}")
        
        try:
            extr = extractor.find(url=url)
            if not extr:
                logger.warning(f"Экстрактор не найден для URL: {url}")
                return None
            
            extr.initialize()
            items = list(extr.items())
            
            if not items or len(items[0]) < 2:
                logger.warning(f"Элементы не извлечены из URL: {url}")
                return None
                
            resolved_url = items[0][1]
            logger.debug(f"URL разрешен в: {resolved_url}")
            return resolved_url
            
        except Exception as e:
            logger.error(f"Ошибка разрешения URL {url}: {e}")
            return None

    def _classify_url(self, url: str) -> ContentType:
        """
        Классификация типа контента URL TikTok.
        
        Args:
            url: URL TikTok для классификации
            
        Returns:
            ContentType: Классифицированный тип контента
        """
        logger.debug(f"Классификация URL: {url}")
        
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.strip("/").split("/")
            
            if not path_parts:
                return ContentType.UNKNOWN
            
            if "live" in path_parts:
                result = ContentType.LIVE
            elif "photo" in path_parts:
                result = ContentType.PHOTO 
            elif "video" in path_parts:
                result = ContentType.VIDEO
            elif "music" in path_parts:
                result = ContentType.MUSIC
            elif len(path_parts) == 1 and path_parts[0].startswith("@"):
                result = ContentType.ACCOUNT
            else:
                result = ContentType.UNKNOWN
                
            logger.debug(f"URL классифицирован как: {result.value}")
            return result
        
        except Exception as e:
            logger.error(f"Ошибка классификации URL: {e}")
            return ContentType.UNKNOWN
        
    def _validate_tiktok_url(self, url: str) -> bool:
        """
        Проверка валидности URL TikTok.
        
        Args:
            url: URL для проверки
            
        Returns:
            True если URL является валидным URL TikTok
        """
        try:
            parsed = urlparse(url)
            return any(domain in parsed.netloc for domain in ["tiktok.com", "vm.tiktok.com", "vt.tiktok.com"])
        except Exception as e:
            logger.debug(f"Ошибка проверки URL: {e}")
            return False
    
    def classify_url(self, url: str) -> Tuple[ContentType, str]:
        """
        Классификация URL и разрешение сокращенных URL при необходимости.
        
        Args:
            url: URL TikTok для классификации
            
        Returns:
            Кортеж (ContentType, resolved_url)
        """
        logger.debug(f"Классификация и разрешение URL: {url}")
        
        if self._classify_url(url=url) == ContentType.UNKNOWN:
            resolved_url = self._resolve_vm_url(url)
            if resolved_url:
                url = resolved_url
                logger.info(f"Сокращенный URL разрешен в: {url}")
            else:
                logger.warning("Не удалось разрешить сокращенный URL")
                return (ContentType.UNKNOWN, url)
        
        content_type = self._classify_url(url=url)
        return (content_type, url)
    
    def _extract_music(self, metadata: dict) -> None:
        """Извлечение информации о музыке из метаданных."""
        music = metadata.get("music")
        if music:
            logger.debug("Извлечение информации о музыке")
            self._data.audios.append(
                TikTokAudio(
                    id=uuid4(),
                    name="music",
                    url=music["playUrl"],
                    author=music.get("authorName"),
                )
            )
    
    def _extract_video(self, metadata: dict) -> TikTokResult:
        """Извлечение информации о видео контенте."""
        logger.debug("Извлечение видео контента")
        
        ydl_opts = self.ydl_opts.copy()
        ydl_opts["listformats"] = True
        
        with YoutubeDL(params=ydl_opts) as ydl:
            try:
                data = ydl.extract_info(url=self._data.url, download=False)
                logger.debug("Извлечение информации о видео завершено")
                
            except ExtractorError as e:
                error_msg = f"Ошибка извлечения видео: {str(e)}"
                logger.error(error_msg)
                self._last_result = TikTokResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=TikTokErrorCode.EXTRACTOR_ERROR,
                )
                return self._last_result
            
            except DownloadError as e:
                error_msg = f"Ошибка загрузки видео: {str(e)}"
                logger.error(error_msg)
                self._last_result = TikTokResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=TikTokErrorCode.DOWNLOAD_ERROR,
                )
                return self._last_result
            
            except Exception as e:
                error_msg = f"Неожиданная ошибка извлечения видео: {str(e)}"
                logger.error(error_msg)
                self._last_result = TikTokResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=TikTokErrorCode.UNEXPECTED_ERROR,
                )
                return self._last_result
            
        # Заполнение данных
        self._data.title = data.get("title")
        self._data.author_name = data.get("uploader")
        self._data.description = data.get("description")

        # Извлечение видео форматов
        video_count = 0
        audio_count = 0
        for format in data.get("formats", []):
            if (
                format["ext"] == "mp4"
                and format["vcodec"] == "h264"
            ):
                self._data.videos.append(
                    TikTokVideo(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        has_audio=False if format["acodec"] == "none" else True,
                        fps=format.get("fps"),
                        width=format.get("width"),
                        height=format.get("height"),
                        language=format.get("language"),
                        total_bitrate=format.get("tbr"),
                        language_preference=format.get("language_preference"),
                    )
                )
                video_count += 1
                
            elif (
                format.get("ext") == "mp4" 
                and format.get("vcodec", "").startswith("avc1")
            ):
                self._data.videos.append(
                    TikTokVideo(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        has_audio=False if format["acodec"] == "none" else True,
                        fps=format.get("fps"),
                        width=format.get("width"),
                        height=format.get("height"),
                        language=format.get("language"),
                        total_bitrate=format.get("tbr"),
                        language_preference=format.get("language_preference"),
                    )
                )
                video_count += 1
                
            elif (
                format.get("ext") == "m4a"
                and format.get("vcodec") == "none"
                and format.get("acodec").startswith("mp4a")
            ):
                self._data.audios.append(
                    TikTokAudio(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        language=format.get("language"),
                        language_preference=format.get("language_preference"),
                    )
                )
                audio_count += 1
                
            elif (
                format.get("ext") == "m4a"
                and format.get("vcodec") == "none"
                and format.get("acodec").startswith("aac")
            ):
                self._data.audios.append(
                    TikTokAudio(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        language=format.get("language"),
                        language_preference=format.get("language_preference"),
                    )
                )
                audio_count += 1
                
        if audio_count == 0 and video_count == 0:
            error_msg = "Не найдено поддерживаемых медиа форматов"
            logger.warning(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=TikTokErrorCode.NO_MEDIA_FORMATS_FOUND,
            )
            return self._last_result
        
        if video_count == 0:
            logger.warning("Не найдено видео форматов")
            
        if audio_count == 0:
            logger.warning("Не найдено аудио форматов")
        
        # Извлечение миниатюр
        thumbnail_count = 0
        for thumbnail in data.get("thumbnails", []):
            self._data.thumbnails.append(
                TikTokImage(
                    id=uuid4(),
                    url=thumbnail["url"],
                    name=thumbnail["id"],
                    width=thumbnail.get("width"),
                    height=thumbnail.get("height"),
                )
            )
            thumbnail_count += 1
            
        # Извлечение музыки
        self._extract_music(metadata=metadata)
        
        logger.info(f"Извлечено {video_count} видео форматов, {thumbnail_count} миниатюр")
        self._last_result = TikTokResult(data=self._data)
        return self._last_result
    
    def _extract_photo(self, metadata: dict) -> TikTokResult:
        """Извлечение информации о фото контенте."""
        logger.debug("Извлечение фото контента")
        
        self._data.title = metadata.get("title")
        self._data.description = metadata.get("desc")
        self._data.author_name = metadata.get("author", {}).get("uniqueId")
        
        if image_post := metadata.get("imagePost"):
            image_count = 0
            for idx, image in enumerate(image_post.get("images", [])):
                self._data.images.append(
                    TikTokImage(
                        id=uuid4(),
                        url=image["imageURL"]["urlList"][0],
                        name=f"Image_{idx}",
                        width=image.get("imageWidth"),
                        height=image.get("imageHeight"),
                    )
                )
                image_count += 1
            logger.info(f"Извлечено {image_count} изображений из фото поста")
            
        if image_count == 0:
            error_msg = "Изображения не найдены в фото посте"
            logger.warning(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=TikTokErrorCode.NO_IMAGES_FOUND,
            )
            return self._last_result
                
        self._extract_music(metadata=metadata)
        self._last_result = TikTokResult(data=self._data)
        return self._last_result
    
    def _generate_safe_filename(self, url: str, format_id: str) -> str:
        """
        Генерация безопасного имени файла на основе хэша URL.
        
        Args:
            url: URL контента
            format_id: ID видео формата
            
        Returns:
            Безопасное имя файла
        """
        hash_input = f"tiktok_{url}_{format_id}"
        file_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return file_hash
        
    def extract_info(self, url: str) -> TikTokResult:
        """
        Извлечение медиа информации из URL TikTok.
        
        Args:
            url: URL TikTok для извлечения информации
            
        Returns:
            TikTokResult: Результат, содержащий извлеченные медиа данные
        """
        logger.info(f"Извлечение информации из URL: {url}")
        
        # Проверка URL
        if not url or not isinstance(url, str):
            error_msg = "Предоставлен неверный URL"
            logger.error(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=TikTokErrorCode.EMPTY_URL,
            )
            return self._last_result
        
        if not self._validate_tiktok_url(url):
            error_msg = "Неверный или неподдерживаемый URL TikTok"
            logger.error(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=TikTokErrorCode.INVALID_URL,
            )
            return self._last_result
        
        # Классификация и разрешение URL
        content_type, url = self.classify_url(url=url)
        self._data = TikTokData(url=url)
        
        if content_type in self.unsupported_types:
            error_msg = f"Неподдерживаемый тип контента: {content_type.value}"
            logger.warning(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=TikTokErrorCode.UNSUPPORTED_CONTENT_TYPE,
            )
            return self._last_result
            
        # Поиск подходящего экстрактора
        extr = extractor.find(url=url)
        if extr is None:
            error_msg = "Экстрактор не найден для данного URL"
            logger.error(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=TikTokErrorCode.NO_EXTRACTOR_FOUND,
            )
            return self._last_result
        
        try:
            extr.initialize()
            extr_items = list(extr.items())
            
            if not extr_items:
                error_msg = "Контент не найден для данного URL"
                logger.error(error_msg)
                self._last_result = TikTokResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=TikTokErrorCode.NO_CONTENT_FOUND,
                )
                return self._last_result
            
            metadata = extr_items[0][-1]
            logger.debug("Метаданные успешно извлечены")
        
        except Exception as e:
            error_msg = f"Ошибка извлечения метаданных: {e}"
            logger.error(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=TikTokErrorCode.METADATA_EXTRACTION_FAILE,
            )
            return self._last_result

        # Извлечение на основе типа контента
        if content_type == ContentType.VIDEO:
            self._data.is_video = True
            return self._extract_video(metadata=metadata)

        elif content_type == ContentType.PHOTO:
            self._data.is_image = True
            return self._extract_photo(metadata=metadata)
        
        error_msg = f"Неожиданный тип контента: {content_type.value}"
        logger.error(error_msg)
        return TikTokResult(
            status="error",
            data=self._data,
            context=error_msg,
            code=TikTokErrorCode.UNSUPPORTED_CONTENT_TYPE,
        )
        
    def download_direct_media(
        self,
        url: str,
        file_extension: str,
        output_path: str = "./downloads/tiktok/",
    ) -> TikTokResult:
        """
        Прямое скачивание медиа по готовой ссылке без использования yt-dlp.
        
        Args:
            direct_url: Прямая ссылка на медиафайл
            output_path: Путь к директории для сохранения файла
            file_extension: Расширение файла (mp4, mp3, m4a и т.д.)
            
        Returns:
            TikTokResult: Результат операции загрузки
        """
        logger.info(f"Прямое скачивание медиа: url={url}")
        
        # Подготовка выходной директории
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Генерация безопасного имени файла
        safe_filename = self._generate_safe_filename(
            url=url,
            format_id="direct"
        )
        file_path = output_dir / f"{safe_filename}.{file_extension}"
        
        # Настройка параметров загрузки
        ydl_opts = self.ydl_opts.copy()
        ydl_opts.update({
            "outtmpl": str(file_path),
            "merge_output_format": file_extension,
        })
        
        try:
            logger.debug(f"Загрузка в: {file_path}")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            logger.info(f"Загрузка успешно завершена: {file_path}")
            return TikTokResult(data=TikTokData(url=url, path=file_path))

        except DownloadError as e:
            error_msg = f"Ошибка загрузки: {e}"
            logger.error(error_msg)
            return TikTokResult(
                status="error",
                context=error_msg,
                code=TikTokErrorCode.DOWNLOAD_ERROR,
                data=TikTokData(url=url)
            )
            
        except Exception as e:
            error_msg = f"Неожиданная ошибка загрузки: {e}"
            logger.error(error_msg)
            return TikTokResult(
                status="error",
                context=error_msg,
                code=TikTokErrorCode.UNEXPECTED_ERROR,
                data=TikTokData(url=url),
            )

    def download_video(
        self,
        url: str,
        video_format_id: str,
        merge_audio: bool = False,
        output_path: str = "./downloads/tiktok/",
    ) -> TikTokResult:
        """
        Загрузка медиа с использованием ранее извлеченной информации.
        
        Args:
            url: URL видео TikTok для загрузки
            video_format_id: ID видео формата для загрузки
            output_path: Путь к директории для сохранения файла
            
        Returns:
            TikTokResult: Результат операции загрузки
            
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
            format_id=video_format_id
        )
        file_path = output_dir / f"{safe_filename}.mp4"
        
        # Формируем формат
        format_str = video_format_id
        if merge_audio:
            # Добавляем аудио дорожку если видео без звука
            format_str += "+bestaudio[ext=m4a]"
            logger.info("Добавление аудио дорожки к видео")
        else:
            logger.info("Загрузка только выбранного видео формата")
        
        # Настройка параметров загрузки
        ydl_opts = self.ydl_opts.copy()
        ydl_opts.update({
            "outtmpl": str(file_path),
            "format": format_str,
            "merge_output_format": "mp4",
        })
        
        try:
            logger.debug(f"Загрузка в: {file_path}")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            logger.info(f"Загрузка успешно завершена: {file_path}")
            return TikTokResult(data=TikTokData(url=url, path=file_path, is_video=True))

        except DownloadError as e:
            error_msg = f"Ошибка загрузки: {e}"
            logger.error(error_msg)
            return TikTokResult(
                status="error",
                context=error_msg,
                code=TikTokErrorCode.DOWNLOAD_ERROR,
                data=TikTokData(url=url)
            )
            
        except Exception as e:
            error_msg = f"Неожиданная ошибка загрузки: {e}"
            logger.error(error_msg)
            return TikTokResult(
                status="error",
                context=error_msg,
                code=TikTokErrorCode.UNEXPECTED_ERROR,
                data=TikTokData(url=url),
            )
            
    def download_audio(
            self,
            url: str,
            audio_format_id: str,
            output_path: str = "./downloads/tiktok/",
        ) -> TikTokResult:
        """
        Загрузка аудио с использованием ранее извлеченной информации.
        
        Args:
            url: URL видео/аудио для загрузки
            audio_format_id: ID аудио формата для загрузки
            output_path: Путь к директории для сохранения файла
            
        Returns:
            YoutubeResult: Результат операции загрузки
        """
        logger.info(f"Начало загрузки аудио: url={url}, audio_format={audio_format_id}")
        
        # Подготовка выходной директории
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Создание безопасного имени файла
        safe_filename = self._generate_safe_filename(
            url=url,
            format_id=audio_format_id,
        )
        file_path = output_dir / f"{safe_filename}.mp3"
        
        # Настройка параметров загрузки
        ydl_opts = self.ydl_opts.copy()
        ydl_opts.update({
            "outtmpl": str(file_path),
            "format": audio_format_id,
        })
        
        try:
            logger.debug(f"Загрузка в: {file_path}")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            logger.info(f"Аудио успешно загружено: {file_path}")
            return TikTokResult(data=TikTokData(url=url, path=file_path, is_video=False))
        
        except DownloadError as e:
            error_msg = f"Ошибка загрузки аудио: {e}"
            logger.error(error_msg)
            return TikTokResult(
                status="error",
                context=error_msg,
                code=TikTokErrorCode.DOWNLOAD_ERROR,
                data=TikTokData(url=url)
            )
        
        except Exception as e:
            error_msg = f"Неожиданная ошибка при загрузке аудио: {e}"
            logger.exception(error_msg)
            return TikTokResult(
                status="error",
                context=error_msg,
                code=TikTokErrorCode.UNEXPECTED_ERROR,
                data=TikTokData(url=url)
            )
            
    def get_error_description(self, code: TikTokErrorCode) -> str:
        """
        Получение человеко-читаемого описания для кода ошибки.
        
        Args:
            code: Значение перечисления кода ошибки
            
        Returns:
            Строка описания
        """
        descriptions = {
            TikTokErrorCode.SUCCESS.value: "Операция успешно завершена",
            TikTokErrorCode.INVALID_URL.value: "Предоставленный URL TikTok неверен или не поддерживается",
            TikTokErrorCode.EMPTY_URL.value: "Предоставлен пустой или неверный URL",
            TikTokErrorCode.UNSUPPORTED_CONTENT_TYPE.value: "Тип контента TikTok не поддерживается",
            TikTokErrorCode.URL_RESOLUTION_FAILED.value: "Не удалось разрешить сокращенный URL TikTok",
            TikTokErrorCode.CONNECTION_ERROR.value: "Произошла ошибка сетевого соединения",
            TikTokErrorCode.DOWNLOAD_ERROR.value: "Не удалось загрузить медиа",
            TikTokErrorCode.EXTRACTOR_ERROR.value: "Не удалось извлечь медиа",
            TikTokErrorCode.PROXY_ERROR.value: "Ошибка подключения к прокси",
            TikTokErrorCode.NO_EXTRACTOR_FOUND.value: "Не найден подходящий экстрактор для URL",
            TikTokErrorCode.NO_CONTENT_FOUND.value: "Контент не найден для данного URL",
            TikTokErrorCode.METADATA_EXTRACTION_FAILED.value: "Не удалось извлечь метаданные",
            TikTokErrorCode.VIDEO_EXTRACTION_FAILED.value: "Не удалось извлечь видео контент",
            TikTokErrorCode.PHOTO_EXTRACTION_FAILED.value: "Не удалось извлечь фото контент",
            TikTokErrorCode.MUSIC_EXTRACTION_FAILED.value: "Не удалось извлечь музыку",
            TikTokErrorCode.NO_MEDIA_FORMATS_FOUND.value: "Не найдено поддерживаемых медиа форматов",
            TikTokErrorCode.NO_IMAGES_FOUND.value: "Изображения не найдены в фото посте",
            TikTokErrorCode.NO_THUMBNAILS_FOUND.value: "Миниатюры не найдены",
            TikTokErrorCode.COOKIE_FILE_NOT_FOUND.value: "Файл cookie не найден",
            TikTokErrorCode.OUTPUT_PATH_ERROR.value: "Ошибка выходного пути",
            TikTokErrorCode.FILE_WRITE_ERROR.value: "Ошибка записи файла",
            TikTokErrorCode.UNEXPECTED_ERROR.value: "Произошла непредвиденная ошибка",
            TikTokErrorCode.INITIALIZATION_ERROR.value: "Не удалось инициализировать загрузчик",
            TikTokErrorCode.EXTRACT_INFO_NOT_CALLED.value: "extract_info() должен быть вызван перед загрузкой",
            TikTokErrorCode.GALLERY_DL_ERROR.value: "Произошла внутренняя ошибка gallery-dl",
            TikTokErrorCode.YT_DLP_ERROR.value: "Произошла внутренняя ошибка yt-dlp",
        }
        return descriptions.get(code, "Неизвестная ошибка")
