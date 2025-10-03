"""
Модуль загрузчика Rutube.

Этот модуль предоставляет функционал для загрузки медиа-контента с Rutube,
включая видео и миниатюры.
"""

import hashlib
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
logger = logging.getLogger("rutube")


# ======= EnumsClasses =======
class ContentType(Enum):
    """Перечисление, представляющее различные типы контента Rutube."""
    LIVE = "live"
    VIDEO = "video"
    SHORTS = "shorts"
    ACCOUNT = "account"
    PLAYLIST = "playlist"
    

class RutubeErrorCode(Enum):
    """Перечисление, представляющее коды ошибок для операций с Rutube."""
    
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
    NO_MEDIA_FORMATS_FOUND = "NO_MEDIA_FORMATS_FOUND"
    NO_THUMBNAILS_FOUND = "NO_THUMBNAILS_FOUND"
    
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
class RutubeData(AbstractServiceData):
    """Контейнер для данных медиа с Rutube."""
    pass


@dataclass
class RutubeImage(AbstractServiceImage):
    """Представляет миниатюру изображения Rutube."""
    pass


@dataclass
class RutubeVideo(AbstractServiceVideo):
    """Представляет видео формат Rutube."""
    pass


@dataclass
class RutubeAudio(AbstractServiceAudio):
    """Представляет аудио формат Rutube."""
    pass


@dataclass
class RutubeResult(AbstractServiceResult):
    """Результат операций с Rutube."""
    code: RutubeErrorCode = field(default=RutubeErrorCode.SUCCESS)


# ======= ExceptionClasses =======
class ExtractInfoNotCalledError(Exception):
    """Исключение при попытке загрузки до вызова extract_info."""
    def __init__(self, message: str, code: RutubeErrorCode = RutubeErrorCode.EXTRACT_INFO_NOT_CALLED):
        super().__init__(message)
        self.code = code
        self.message = message


class CookieFileNotFoundError(FileNotFoundError):
    """Исключение при отсутствии файла cookie."""
    def __init__(self, message: str, code: RutubeErrorCode = RutubeErrorCode.COOKIE_FILE_NOT_FOUND):
        super().__init__(message)
        self.code = code
        self.message = message


class UnsupportedContentTypeError(Exception):
    """Исключение для неподдерживаемых типов контента."""
    def __init__(self, message: str, code: RutubeErrorCode = RutubeErrorCode.UNSUPPORTED_CONTENT_TYPE):
        super().__init__(message)
        self.code = code
        self.message = message


# ======= MainClass =======
class RutubeDownloader(AbstractServiceDownloader):
    """
    Загрузчик медиа-контента с Rutube.
    
    Поддерживает загрузку видео и миниатюр с Rutube.
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
        Инициализация загрузчика Rutube.
        
        Args:
            retries_count: Количество попыток повтора для загрузок
            proxy: URL прокси-сервера (опционально)
            cookie_path: Путь к файлу cookies (опционально)
            concurrent_download_count: Количество одновременных загрузок фрагментов
        """
        logger.info("Инициализация загрузчика Rutube")
        
        self.proxy = proxy
        self.cookies_path = Path(cookie_path) if cookie_path else None

        if self.cookies_path and not self.cookies_path.exists():
            error_msg = f"Файл cookie не найден: {self.cookies_path}"
            logger.error(error_msg)
            raise CookieFileNotFoundError(error_msg, RutubeErrorCode.COOKIE_FILE_NOT_FOUND)
        
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
                ContentType.LIVE,
                ContentType.ACCOUNT,
                ContentType.PLAYLIST,
            ]
            
            self._data: Optional[RutubeData] = None
            self._last_result: Optional[RutubeResult] = None
            
            logger.debug("Загрузчик Rutube успешно инициализирован")
            
        except Exception as e:
            error_msg = f"Ошибка инициализации загрузчика Rutube: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e
        
    def _classify_url(self, url: str) -> Optional[ContentType]:
        """
        Классификация типа контента URL Rutube.
        
        Args:
            url: URL Rutube для классификации
            
        Returns:
            ContentType или None если классификация не удалась
        """
        logger.debug(f"Классификация URL: {url}")
        
        try:
            parsed = urlparse(url=url)
            path = parsed.path.lower()
            path_parts = path.strip("/").split("/")
            
            if len(path_parts) < 2:
                logger.warning(f"Невалидный путь URL: {path}")
                return None
            
            if "/channel/" in path:
                result = ContentType.ACCOUNT
            elif "/shorts/" in path:
                result = ContentType.SHORTS
            elif "/live/" in path:
                result = ContentType.LIVE
            elif "/plst/" in path:
                result = ContentType.PLAYLIST
            else:
                result = ContentType.VIDEO
                
            logger.debug(f"URL классифицирован как: {result.value if result else 'unknown'}")
            return result
        
        except Exception as e:
            logger.error(f"Ошибка классификации URL: {e}")
            return None
        
    def _validate_rutube_url(self, url: str) -> bool:
        """
        Проверка валидности URL Rutube.
        
        Args:
            url: URL для проверки
            
        Returns:
            True если URL является валидным URL Rutube
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc.endswith("rutube.ru")
        except Exception as e:
            logger.debug(f"Ошибка проверки URL: {e}")
            return False
        
    def extract_info(self, url: str) -> RutubeResult:
        """
        Извлечение информации о медиа из URL Rutube.
        
        Args:
            url: URL Rutube для извлечения информации
            
        Returns:
            RutubeResult: Результат, содержащий извлеченные данные медиа
        """
        logger.info(f"Извлечение информации из URL: {url}")
        
        # Проверка URL
        if not url or not isinstance(url, str):
            error_msg = "Предоставлен невалидный URL"
            logger.error(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RutubeErrorCode.EMPTY_URL,
            )
            return self._last_result
        
        if not self._validate_rutube_url(url):
            error_msg = "Невалидный или неподдерживаемый URL Rutube"
            logger.error(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RutubeErrorCode.INVALID_URL,
            )
            return self._last_result
        
        ydl_opts = self.ydl_opts.copy()
        ydl_opts['listformats'] = True
        
        self._data = RutubeData(url=url) 
        
        # Классификация типа контента
        content_type = self._classify_url(url=url)
        if not content_type:
            error_msg = "Не удалось классифицировать тип контента URL"
            logger.error(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RutubeErrorCode.UNSUPPORTED_CONTENT_TYPE,
            )
            return self._last_result
        
        if content_type in self.unsupported_types:
            error_msg = f"Неподдерживаемый тип контента: {content_type.value}"
            logger.warning(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RutubeErrorCode.UNSUPPORTED_CONTENT_TYPE,
            )
            return self._last_result
           
        # Извлечение информации с использованием yt-dlp
        with YoutubeDL(params=ydl_opts) as ydl:
            try:
                logger.debug("Начало извлечения информации с yt-dlp")
                data = ydl.extract_info(url=url, download=False)
                logger.debug("Извлечение информации успешно завершено")

            except ExtractorError as e:
                error_msg = f"Ошибка извлечения: {str(e)}"
                logger.error(error_msg)
                self._last_result = RutubeResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=RutubeErrorCode.EXTRACTOR_ERROR,
                )
                return self._last_result
            
            except DownloadError as e:
                error_msg = f"Ошибка загрузки при извлечении: {str(e)}"
                logger.error(error_msg)
                self._last_result = RutubeResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=RutubeErrorCode.DOWNLOAD_ERROR,
                )
                return self._last_result

            except Exception as e:
                error_msg = f"Неожиданная ошибка при извлечении: {str(e)}"
                logger.error(error_msg)
                self._last_result = RutubeResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=RutubeErrorCode.UNEXPECTED_ERROR,
                )
                return self._last_result
                
        # Проверка неподдерживаемых типов контента в извлеченных данных
        if data.get("_type") == "playlist":
            error_msg = "Плейлисты не поддерживаются"
            logger.warning(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RutubeErrorCode.PLAYLIST_NOT_SUPPORTED,
            )
            return self._last_result
        
        if data.get("is_live") == True:
            error_msg = "Прямые трансляции не поддерживаются"
            logger.warning(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RutubeErrorCode.LIVE_STREAM_NOT_SUPPORTED,
            )
            return self._last_result
        
        if data.get("media_type") == "livestream":
            error_msg = "Прямые эфиры не поддерживаются"
            logger.warning(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RutubeErrorCode.LIVE_STREAM_NOT_SUPPORTED,
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
                    RutubeVideo(
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
                    RutubeVideo(
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
                    RutubeAudio(
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
                    RutubeAudio(
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
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RutubeErrorCode.NO_MEDIA_FORMATS_FOUND,
            )
            return self._last_result
        
        if video_count == 0:
            logger.warning("Не найдено видео форматов")
            
        if audio_count == 0:
            logger.warning("Не найдено аудио форматов")
                
        # Извлечение миниатюр
        thumbnail_count = 0
        for idx, thumbnail in enumerate(data.get("thumbnails", [])):  
            self._data.thumbnails.append(
                RutubeImage(
                    id=uuid4(),
                    url=thumbnail["url"],
                    name=f"Image_{idx}",
                    width=thumbnail.get("width"),
                    height=thumbnail.get("height"),
                )
            )
            thumbnail_count += 1
            
        if thumbnail_count == 0:
            logger.warning("Для видео не найдено миниатюр")
        
        logger.info(f"Извлечено {video_count} видео форматов, {audio_count} аудио форматов, {thumbnail_count} миниатюр")
        
        self._last_result = RutubeResult(data=self._data)
        return self._last_result
    
    def _generate_safe_filename(self, url: str, format_id: str) -> str:
        """
        Генерация безопасного имени файла на основе хеша URL.
        
        Args:
            url: URL контента
            format_id: ID видео формата
            
        Returns:
            Строка с безопасным именем файла
        """
        hash_input = f"rutube_{url}_{format_id}"
        file_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return file_hash

    def download_video(
        self,
        url: str,
        video_format_id: str,
        output_path: str = "./downloads/rutube/"
    ) -> RutubeResult:
        """
        Загрузка медиа с использованием ранее извлеченной информации.
        
        Args:
            url: URL видео Rutube для загрузки
            video_format_id: ID видео формата для загрузки
            output_path: Путь к директории для сохранения загруженного файла
            
        Returns:
            RutubeResult: Результат операции загрузки
            
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
        
        # Настройка параметров загрузки
        ydl_opts = self.ydl_opts.copy()
        ydl_opts.update({
            "outtmpl": str(file_path),
            "format": f"{video_format_id}+bestaudio[ext=m4a]",
            "merge_output_format": "mp4",
        })
        
        try:
            logger.debug(f"Загрузка в: {file_path}")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            logger.info(f"Загрузка успешно завершена: {file_path}")
            return RutubeResult(data=RutubeData(url=url, path=file_path, is_video=True))
        
        except DownloadError as e:
            error_msg = f"Ошибка загрузки: {e}"
            logger.error(error_msg)
            return RutubeResult(
                status="error",
                context=error_msg,
                code=RutubeErrorCode.DOWNLOAD_ERROR,
                data=RutubeData(url=url)
            )
            
        except Exception as e:
            error_msg = f"Неожиданная ошибка загрузки: {e}"
            logger.error(error_msg)
            return RutubeResult(
                status="error",
                context=error_msg,
                code=RutubeErrorCode.UNEXPECTED_ERROR,
                data=RutubeData(url=url)
            )
            
    def download_audio(
            self,
            url: str,
            audio_format_id: str,
            output_path: str = "./downloads/rutube/",
        ) -> RutubeResult:
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
            return RutubeResult(data=RutubeData(url=url, path=file_path, is_video=False))
        
        except DownloadError as e:
            error_msg = f"Ошибка загрузки аудио: {e}"
            logger.error(error_msg)
            return RutubeResult(
                status="error",
                context=error_msg,
                code=RutubeErrorCode.DOWNLOAD_ERROR,
                data=RutubeData(url=url)
            )
        
        except Exception as e:
            error_msg = f"Неожиданная ошибка при загрузке аудио: {e}"
            logger.exception(error_msg)
            return RutubeResult(
                status="error",
                context=error_msg,
                code=RutubeErrorCode.UNEXPECTED_ERROR,
                data=RutubeData(url=url)
            )
            
    def get_error_description(self, code: RutubeErrorCode) -> str:
        """
        Получение человеко-читаемого описания для кода ошибки.
        
        Args:
            code: Значение перечисления кода ошибки
            
        Returns:
            Строка с описанием
        """
        descriptions = {
            RutubeErrorCode.SUCCESS.value: "Операция успешно завершена",
            RutubeErrorCode.INVALID_URL.value: "Предоставленный URL Rutube невалиден или не поддерживается",
            RutubeErrorCode.EMPTY_URL.value: "Предоставлен пустой или невалидный URL",
            RutubeErrorCode.UNSUPPORTED_CONTENT_TYPE.value: "Тип контента Rutube не поддерживается",
            RutubeErrorCode.UNSUPPORTED_MEDIA_TYPE.value: "Тип медиа не поддерживается",
            RutubeErrorCode.CONNECTION_ERROR.value: "Произошла ошибка сетевого соединения",
            RutubeErrorCode.DOWNLOAD_ERROR.value: "Ошибка загрузки медиа",
            RutubeErrorCode.EXTRACTOR_ERROR.value: "Ошибка извлечения медиа",
            RutubeErrorCode.PROXY_ERROR.value: "Ошибка подключения к прокси",
            RutubeErrorCode.LIVE_STREAM_NOT_SUPPORTED.value: "Прямые трансляции не поддерживаются",
            RutubeErrorCode.PLAYLIST_NOT_SUPPORTED.value: "Плейлисты не поддерживаются",
            RutubeErrorCode.ACCOUNT_NOT_SUPPORTED.value: "Контент аккаунта/канала не поддерживается",
            RutubeErrorCode.NO_MEDIA_FORMATS_FOUND.value: "Не найдено поддерживаемых медиа форматов",
            RutubeErrorCode.NO_THUMBNAILS_FOUND.value: "Миниатюры не найдены",
            RutubeErrorCode.COOKIE_FILE_NOT_FOUND.value: "Файл cookie не найден",
            RutubeErrorCode.OUTPUT_PATH_ERROR.value: "Ошибка пути вывода",
            RutubeErrorCode.FILE_WRITE_ERROR.value: "Ошибка записи файла",
            RutubeErrorCode.UNEXPECTED_ERROR.value: "Произошла непредвиденная ошибка",
            RutubeErrorCode.INITIALIZATION_ERROR.value: "Ошибка инициализации загрузчика",
            RutubeErrorCode.EXTRACT_INFO_NOT_CALLED.value: "extract_info() должен быть вызван перед загрузкой",
            RutubeErrorCode.YT_DLP_ERROR.value: "Произошла внутренняя ошибка yt-dlp",
        }
        return descriptions.get(code, "Неизвестная ошибка")

        
