"""
Модуль загрузчика YouTube.

Этот модуль предоставляет функциональность для загрузки медиа-контента с YouTube,
включая видео, аудио и миниатюры.
"""

import hashlib
import json
import logging
from enum import Enum
from uuid import uuid4
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from yt_dlp import YoutubeDL
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
logger = logging.getLogger("youtube")


# ======= Перечисления =======
class ContentType(Enum):
    """Перечисление, представляющее различные типы контента YouTube."""
    POST = "post"
    LIVE = "live"
    VIDEO = "video"
    SHORTS = "shorts"
    ACCOUNT = "account"
    PLAYLIST = "playlist"
    
    
class YoutubeErrorCode(Enum):
    """Перечисление, представляющее коды ошибок для операций с YouTube."""
    
    # Успех
    SUCCESS = "SUCCESS"
    
    # Ошибки проверки входных данных (1xx)
    INVALID_URL = "INVALID_URL"
    EMPTY_URL = "EMPTY_URL"
    UNSUPPORTED_CONTENT_TYPE = "UNSUPPORTED_CONTENT_TYPE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    
    # Сетевые ошибки (2xx)
    CONNECTION_ERROR = "CONNECTION_ERROR"
    DOWNLOAD_ERROR = "DOWNLOAD_ERROR"
    EXTRACTOR_ERROR = "EXTRACTOR_ERROR"
    PROXY_ERROR = "PROXY_ERROR"
    
    # Ошибки контента (3xx)
    LIVE_STREAM_NOT_SUPPORTED = "LIVE_STREAM_NOT_SUPPORTED"
    PLAYLIST_NOT_SUPPORTED = "PLAYLIST_NOT_SUPPORTED"
    ACCOUNT_NOT_SUPPORTED = "ACCOUNT_NOT_SUPPORTED"
    SHORTS_NOT_SUPPORTED = "SHORTS_NOT_SUPPORTED"
    POST_NOT_SUPPORTED = "POST_NOT_SUPPORTED"
    NO_VIDEO_FORMATS_FOUND = "NO_VIDEO_FORMATS_FOUND"
    NO_AUDIO_FORMATS_FOUND = "NO_AUDIO_FORMATS_FOUND"
    NO_THUMBNAILS_FOUND = "NO_THUMBNAILS_FOUND"
    NO_MEDIA_FORMATS_FOUND = "NO_MEDIA_FORMATS_FOUND"
    
    # Ошибки файловой системы (4xx)
    COOKIE_FILE_NOT_FOUND = "COOKIE_FILE_NOT_FOUND"
    OUTPUT_PATH_ERROR = "OUTPUT_PATH_ERROR"
    FILE_WRITE_ERROR = "FILE_WRITE_ERROR"
    
    # Системные ошибки (5xx)
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
    EXTRACT_INFO_NOT_CALLED = "EXTRACT_INFO_NOT_CALLED"
    YT_DLP_ERROR = "YT_DLP_ERROR"


# ======= DataClasses =======
@dataclass
class YoutubeData(AbstractServiceData):
    """Контейнер для данных медиа с YouTube."""
    pass


@dataclass
class YoutubeImage(AbstractServiceImage):
    """Представляет миниатюру YouTube."""
    pass


@dataclass
class YoutubeVideo(AbstractServiceVideo):
    """Представляет видео формат YouTube."""
    pass


@dataclass
class YoutubeAudio(AbstractServiceAudio):
    """Представляет аудио формат YouTube."""
    pass


@dataclass
class YoutubeResult(AbstractServiceResult):
    """Результат операций с YouTube."""
    code: YoutubeErrorCode = field(default=YoutubeErrorCode.SUCCESS)


# ======= ExceptionClasses =======
class ExtractInfoNotCalledError(Exception):
    """Исключение при попытке загрузки до вызова extract_info."""
    def __init__(self, message: str, code: YoutubeErrorCode = YoutubeErrorCode.EXTRACT_INFO_NOT_CALLED):
        super().__init__(message)
        self.code = code
        self.message = message


class CookieFileNotFoundError(FileNotFoundError):
    """Исключение при отсутствии файла cookie."""
    def __init__(self, message: str, code: YoutubeErrorCode = YoutubeErrorCode.COOKIE_FILE_NOT_FOUND):
        super().__init__(message)
        self.code = code
        self.message = message


class UnsupportedContentTypeError(Exception):
    """Исключение для неподдерживаемых типов контента."""
    def __init__(self, message: str, code: YoutubeErrorCode = YoutubeErrorCode.UNSUPPORTED_CONTENT_TYPE):
        super().__init__(message)
        self.code = code
        self.message = message


# ======= MainClass =======
class YoutubeDownloader(AbstractServiceDownloader):
    """
    Загрузчик медиа-контента с YouTube.
    
    Поддерживает загрузку видео, аудио и миниатюр с YouTube.
    Обрабатывает различные типы контента, включая shorts и обычные видео.
    """
    
    def __init__(
        self,
        retries_count: int = 10,
        proxy: Optional[str] = None,
        cookie_path: Optional[str] = None,
        concurrent_download_count: int = 2,
    ) -> None:
        """
        Инициализация загрузчика YouTube.
        
        Args:
            retries_count: Количество попыток повтора для загрузок
            proxy: URL прокси-сервера (опционально)
            cookie_path: Путь к файлу cookies (опционально)
            concurrent_download_count: Количество одновременных загрузок фрагментов
        """
        logger.info("Инициализация загрузчика YouTube")
        
        self.proxy = proxy
        self.cookies_path = Path(cookie_path) if cookie_path else None

        if self.cookies_path and not self.cookies_path.exists():
            error_msg = f"Файл cookie не найден: {self.cookies_path}"
            logger.error(error_msg)
            raise CookieFileNotFoundError(error_msg, YoutubeErrorCode.COOKIE_FILE_NOT_FOUND)


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
                ContentType.POST,
                ContentType.LIVE,
                ContentType.ACCOUNT,
                ContentType.PLAYLIST,
            ]
            
            self._data: Optional[YoutubeData] = None
            self._last_result: Optional[YoutubeResult] = None
            
            logger.debug("Загрузчик YouTube успешно инициализирован")
            
        except Exception as e:
            error_msg = f"Ошибка инициализации загрузчика YouTube: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e
        
    def _classify_url(self, url: str) -> ContentType:
        """
        Классификация типа контента URL YouTube.
        
        Args:
            url: URL YouTube для классификации
            
        Returns:
            ContentType: Классифицированный тип контента
        """
        logger.debug(f"Классификация URL: {url}")
        
        try:
            parsed = urlparse(url=url)
            path = parsed.path.lower()
            path_parts = path.strip("/").split("/")
            
            if "/shorts/" in path:
                result = ContentType.SHORTS
            elif "/playlist" in path:
                result = ContentType.PLAYLIST
            elif "/live" in path:
                result = ContentType.LIVE
            elif "/post" in path:
                result = ContentType.POST
            elif path_parts[-1].startswith("@"):
                result = ContentType.ACCOUNT
            else:
                result = ContentType.VIDEO
                
            logger.debug(f"URL классифицирован как: {result.value}")
            return result
        
        except Exception as e:
            logger.error(f"Ошибка классификации URL: {e}")
            return None
        
    def _validate_youtube_url(self, url: str) -> bool:
        """
        Проверка валидности URL YouTube.
        
        Args:
            url: URL для проверки
            
        Returns:
            True если URL является валидным URL YouTube
        """
        try:
            parsed = urlparse(url)
            return any(domain in parsed.netloc for domain in ["youtube.com", "youtu.be", "www.youtube.com"])
        except Exception as e:
            logger.debug(f"Ошибка проверки URL: {e}")
            return False
        
    def extract_info(self, url: str) -> YoutubeResult:
        """
        Извлечение медиа информации из URL YouTube.
        
        Args:
            url: URL YouTube для извлечения информации
            
        Returns:
            YoutubeResult: Результат, содержащий извлеченные медиа данные
        """
        logger.info(f"Извлечение информации из URL: {url}")
        
        # Проверка URL
        if not url or not isinstance(url, str):
            error_msg = "Предоставлен неверный URL"
            logger.error(error_msg)
            self._last_result = YoutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=YoutubeErrorCode.EMPTY_URL,
            )
            return self._last_result
            
        if not self._validate_youtube_url(url):
            error_msg = "Неверный или неподдерживаемый URL YouTube"
            logger.error(error_msg)
            self._last_result = YoutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=YoutubeErrorCode.INVALID_URL,
            )
            return self._last_result
        
        ydl_opts = self.ydl_opts.copy()
        ydl_opts['listformats'] = True
        
        self._data = YoutubeData(url=url) 
        
        # Классификация типа контента
        content_type = self._classify_url(url=url)
        if not content_type:
            error_msg = "Не удалось классифицировать тип контента URL"
            logger.error(error_msg)
            self._last_result = YoutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=YoutubeErrorCode.UNSUPPORTED_CONTENT_TYPE,
            )
            return self._last_result

        if content_type in self.unsupported_types:
            error_msg = f"Неподдерживаемый тип контента: {content_type.value}"
            logger.warning(error_msg)
            self._last_result = YoutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=YoutubeErrorCode.UNSUPPORTED_CONTENT_TYPE,
            )
            return self._last_result
        
        # Извлечение информации с помощью yt-dlp   
        with YoutubeDL(params=ydl_opts) as ydl:
            try:
                logger.debug("Начало извлечения информации с yt-dlp")
                data = ydl.extract_info(url=url, download=False)
                logger.debug("Извлечение информации успешно завершено")
                
            except ExtractorError as e:
                error_msg = f"Ошибка извлечения: {str(e)}"
                logger.error(error_msg)
                self._last_result = YoutubeResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=YoutubeErrorCode.EXTRACTOR_ERROR,
                )
                return self._last_result
            
            except DownloadError as e:
                error_msg = f"Ошибка загрузки при извлечении: {str(e)}"
                logger.error(error_msg)
                self._last_result = YoutubeResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=YoutubeErrorCode.DOWNLOAD_ERROR,
                )
                return self._last_result
            
            except Exception as e:
                error_msg = f"Неожиданная ошибка при извлечении: {str(e)}"
                logger.error(error_msg)
                self._last_result = YoutubeResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=YoutubeErrorCode.UNEXPECTED_ERROR,
                )
                return self._last_result
            
        # Проверка неподдерживаемых типов контента в извлеченных данных
        if data.get("is_live") == True:
            error_msg = "Прямые трансляции не поддерживаются"
            logger.warning(error_msg)
            self._last_result = YoutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=YoutubeErrorCode.LIVE_STREAM_NOT_SUPPORTED,
            )
            return self._last_result
        
        if data.get("_type") == "playlist":
            error_msg = "Плейлисты не поддерживаются"
            logger.warning(error_msg)
            self._last_result = YoutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=YoutubeErrorCode.PLAYLIST_NOT_SUPPORTED,
            )
            return self._last_result
        
        if data.get("media_type") == "livestream":
            error_msg = "Прямые эфиры не поддерживаются"
            logger.warning(error_msg)
            self._last_result = YoutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=YoutubeErrorCode.LIVE_STREAM_NOT_SUPPORTED,
            )
            return self._last_result
            
        # Заполнение объекта данных
        self._data.is_video = True
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
                    YoutubeVideo(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        has_audio=False if format["acodec"] == "none" else True,
                        fps=format.get("fps"),
                        width=format.get("width"),
                        height=format.get("height"),
                        language=format.get("language"),
                        total_bitrate=format.get("tbr"),
                    )
                )
                video_count += 1
                
            elif (
                format.get("ext") == "mp4" 
                and format.get("vcodec", "").startswith("avc1")
            ):
                self._data.videos.append(
                    YoutubeVideo(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        has_audio=False if format["acodec"] == "none" else True,
                        fps=format.get("fps"),
                        width=format.get("width"),
                        height=format.get("height"),
                        language=format.get("language"),
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
                    YoutubeAudio(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        language=format.get("language"),
                    )
                )
                audio_count += 1
                
            elif (
                format.get("ext") == "m4a"
                and format.get("vcodec") == "none"
                and format.get("acodec").startswith("aac")
            ):
                self._data.audios.append(
                    YoutubeAudio(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        language=format.get("language"),
                    )
                )
                audio_count += 1
                
        if audio_count == 0 and video_count == 0:
            error_msg = "Не найдено поддерживаемых медиа форматов"
            logger.warning(error_msg)
            self._last_result = YoutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=YoutubeErrorCode.NO_MEDIA_FORMATS_FOUND,
            )
            return self._last_result
        
        if video_count == 0:
            logger.warning("Не найдено видео форматов")
            
        if audio_count == 0:
            logger.warning("Не найдено аудио форматов")
        
        # Извлечение миниатюр
        thumbnail_count = 0 
        for thumbnail in data.get("thumbnails", []):
            if (
                thumbnail.get("height") 
                and thumbnail.get("width")
            ):
                self._data.thumbnails.append(
                    YoutubeImage(
                        id=uuid4(),
                        url=thumbnail["url"],
                        name=thumbnail["id"],
                        width=thumbnail.get("width"),
                        height=thumbnail.get("height"),
                    )
                )
                thumbnail_count += 1
                
        if thumbnail_count == 0:
            logger.warning("Миниатюры не найдены")
                
        logger.info(f"Извлечено {video_count} видео, {audio_count} аудио, {thumbnail_count} миниатюр")
            
        self._last_result = YoutubeResult(data=self._data)
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
        hash_input = f"youtube_{url}_{format_id}"
        file_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return file_hash

    def download_video(
        self,
        url: str,
        video_format_id: str,
        output_path: str = "./downloads/youtube/",
    ) -> YoutubeResult:
        """
        Загрузка медиа с использованием ранее извлеченной информации.
        
        Args:
            url: URL видео для загрузки
            video_format_id: ID видео формата для загрузки
            output_path: Путь к директории для сохранения файла
            
        Returns:
            YoutubeResult: Результат операции загрузки
            
        Raises:
            ExtractInfoNotCalledError: Если extract_info не был вызван первым
        """
        logger.info(f"Начало загрузки медиа: url={url}, video_format={video_format_id}")
          
        # Подготовка выходной директории
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Создание безопасного имени файла
        safe_filename = self._generate_safe_filename(
            url=url,
            format_id=video_format_id,
        )
        file_path = output_dir / f"{safe_filename}.mp4"
        
        # Настройка параметров загрузки
        ydl_opts = self.ydl_opts.copy()
        ydl_opts.update({
            "outtmpl": str(file_path),
            "format": f'{video_format_id}+bestaudio[ext=m4a]',
            "merge_output_format": "mp4",
        })
        
        try:
            logger.debug(f"Загрузка в: {file_path}")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            logger.info(f"Загрузка успешно завершена: {file_path}")
            return YoutubeResult(data=YoutubeData(url=url, path=file_path, is_video=True))
        
        except DownloadError as e:
            error_msg = f"Ошибка загрузки: {e}"
            logger.error(error_msg)
            return YoutubeResult(
                status="error",
                context=error_msg,
                code=YoutubeErrorCode.DOWNLOAD_ERROR,
                data=YoutubeData(url=url)
            )
        
        except Exception as e:
            error_msg = f"Неожиданная ошибка загрузки: {e}"
            logger.exception(error_msg)
            return YoutubeResult(
                status="error",
                context=error_msg,
                code=YoutubeErrorCode.UNEXPECTED_ERROR,
                data=YoutubeData(url=url)
            )
            
    def download_audio(
            self,
            url: str,
            audio_format_id: str,
            output_path: str = "./downloads/youtube/",
        ) -> YoutubeResult:
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
            return YoutubeResult(data=YoutubeData(url=url, path=file_path, is_video=False))
        
        except DownloadError as e:
            error_msg = f"Ошибка загрузки аудио: {e}"
            logger.error(error_msg)
            return YoutubeResult(
                status="error",
                context=error_msg,
                code=YoutubeErrorCode.DOWNLOAD_ERROR,
                data=YoutubeData(url=url)
            )
        
        except Exception as e:
            error_msg = f"Неожиданная ошибка при загрузке аудио: {e}"
            logger.exception(error_msg)
            return YoutubeResult(
                status="error",
                context=error_msg,
                code=YoutubeErrorCode.UNEXPECTED_ERROR,
                data=YoutubeData(url=url)
            )
            
    def get_error_description(self, code: YoutubeErrorCode) -> str:
        """
        Получение человеко-читаемого описания для кода ошибки.
        
        Args:
            code: Значение перечисления кода ошибки
            
        Returns:
            Строка описания
        """
        descriptions = {
            YoutubeErrorCode.SUCCESS.value: "Операция успешно завершена",
            YoutubeErrorCode.INVALID_URL.value: "Предоставленный URL YouTube неверен или не поддерживается",
            YoutubeErrorCode.EMPTY_URL.value: "Предоставлен пустой или неверный URL",
            YoutubeErrorCode.UNSUPPORTED_CONTENT_TYPE.value: "Тип контента YouTube не поддерживается",
            YoutubeErrorCode.UNSUPPORTED_MEDIA_TYPE.value: "Тип медиа не поддерживается",
            YoutubeErrorCode.CONNECTION_ERROR.value: "Произошла ошибка сетевого соединения",
            YoutubeErrorCode.DOWNLOAD_ERROR.value: "Не удалось загрузить медиа",
            YoutubeErrorCode.EXTRACTOR_ERROR.value: "Не удалось извлечь медиа",
            YoutubeErrorCode.PROXY_ERROR.value: "Ошибка подключения к прокси",
            YoutubeErrorCode.LIVE_STREAM_NOT_SUPPORTED.value: "Прямые трансляции не поддерживаются",
            YoutubeErrorCode.PLAYLIST_NOT_SUPPORTED.value: "Плейлисты не поддерживаются",
            YoutubeErrorCode.ACCOUNT_NOT_SUPPORTED.value: "Контент аккаунта/канала не поддерживается",
            YoutubeErrorCode.SHORTS_NOT_SUPPORTED.value: "YouTube Shorts не поддерживаются",
            YoutubeErrorCode.POST_NOT_SUPPORTED.value: "Сообщества не поддерживаются",
            YoutubeErrorCode.NO_VIDEO_FORMATS_FOUND.value: "Поддерживаемые видео форматы не найдены",
            YoutubeErrorCode.NO_AUDIO_FORMATS_FOUND.value: "Поддерживаемые аудио форматы не найдены",
            YoutubeErrorCode.NO_THUMBNAILS_FOUND.value: "Миниатюры не найдены",
            YoutubeErrorCode.NO_MEDIA_FORMATS_FOUND.value: "Поддерживаемые медиа форматы не найдены",
            YoutubeErrorCode.COOKIE_FILE_NOT_FOUND.value: "Файл cookie не найден",
            YoutubeErrorCode.OUTPUT_PATH_ERROR.value: "Ошибка выходного пути",
            YoutubeErrorCode.FILE_WRITE_ERROR.value: "Ошибка записи файла",
            YoutubeErrorCode.UNEXPECTED_ERROR.value: "Произошла непредвиденная ошибка",
            YoutubeErrorCode.INITIALIZATION_ERROR.value: "Не удалось инициализировать загрузчик",
            YoutubeErrorCode.EXTRACT_INFO_NOT_CALLED.value: "extract_info() должен быть вызван перед загрузкой",
            YoutubeErrorCode.YT_DLP_ERROR.value: "Произошла внутренняя ошибка yt-dlp",
        }
        return descriptions.get(code, "Неизвестная ошибка")

        
