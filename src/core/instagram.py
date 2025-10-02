"""
Модуль загрузчика Instagram.

Предоставляет функциональность для извлечения и загрузки медиа-контента 
из Instagram, включая изображения, видео и карусельные публикации.
"""

import logging
from enum import Enum
from uuid import uuid4
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from dataclasses import dataclass, field

from instaloader import Post, Instaloader
from instaloader.exceptions import (
    ConnectionException, 
    BadResponseException,
    PostChangedException,
    ProfileNotExistsException,
    QueryReturnedBadRequestException,
)

from .abstractions import (
    AbstractServiceData,
    AbstractServiceVideo,
    AbstractServiceAudio,
    AbstractServiceImage,
    AbstractServiceResult,
    AbstractServiceDownloader, 
)


# Настройка логирования
logger = logging.getLogger("instagram")


# ======= EnumsClasses =======
class ContentType(Enum):
    """Типы контента Instagram."""
    VIDEO = "GraphVideo"
    IMAGE = "GraphImage"
    SIDECAR = "GraphSidecar"
    
    
class InstagramErrorCode(Enum):
    """Коды ошибок, возникающих при работе с Instagram."""
    
    # Успех
    SUCCESS = "SUCCESS"
    
    # Ошибки валидации ввода (1xx)
    INVALID_URL = "INVALID_URL"              # Неверный URL
    INVALID_SHORTCODE = "INVALID_SHORTCODE"  # Ошибка извлечения shortcode
    EMPTY_URL = "EMPTY_URL"                  # Пустой URL
    
    # Ошибки аутентификации (2xx)
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"   # Ошибка входа
    SESSION_LOAD_FAILED = "SESSION_LOAD_FAILED"       # Ошибка загрузки сессии
    SESSION_SAVE_FAILED = "SESSION_SAVE_FAILED"       # Ошибка сохранения сессии
    
    # Сетевые ошибки (3xx)
    CONNECTION_ERROR = "CONNECTION_ERROR"    # Ошибка соединения
    TIMEOUT_ERROR = "TIMEOUT_ERROR"          # Превышен таймаут
    BAD_RESPONSE = "BAD_RESPONSE"            # Некорректный ответ
    
    # Ошибки контента (4xx)
    POST_NOT_FOUND = "POST_NOT_FOUND"        # Пост не найден
    POST_CHANGED = "POST_CHANGED"            # Пост изменился
    PROFILE_NOT_EXISTS = "PROFILE_NOT_EXISTS" # Профиль не существует
    CONTENT_NOT_SUPPORTED = "CONTENT_NOT_SUPPORTED"   # Неподдерживаемый контент
    EXTRACTION_ERROR = "EXTRACTION_ERROR"    # Ошибка извлечения
    
    # Системные ошибки (5xx)
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"    # Неожиданная ошибка
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR" # Ошибка инициализации
    DOWNLOAD_ERROR = "DOWNLOAD_ERROR"        # Ошибка загрузки
    

# ======= DataClasses =======
@dataclass
class InstagramData(AbstractServiceData):
    """Контейнер с медиа-данными Instagram."""
    pass


@dataclass
class InstagramImage(AbstractServiceImage):
    """Объект изображения Instagram."""
    pass


@dataclass
class InstagramVideo(AbstractServiceVideo):
    """Объект видео Instagram."""
    pass


@dataclass
class InstagramAudio(AbstractServiceAudio):
    """Объект аудио Instagram (например, для сторис или рилсов)."""
    pass


@dataclass
class InstagramResult(AbstractServiceResult):
    """Результат выполнения операций Instagram."""
    code: InstagramErrorCode = field(default=InstagramErrorCode.SUCCESS)


# ======= ExceptionClasses =======
class InstagramSessionError(Exception):
    """Исключение для ошибок сессии Instagram."""
    def __init__(self, message: str, code: InstagramErrorCode = InstagramErrorCode.AUTHENTICATION_FAILED):
        super().__init__(message)
        self.code = code
        self.message = message


class InvalidInstagramUrlError(ValueError):
    """Исключение для некорректных URL Instagram."""
    def __init__(self, message: str, code: InstagramErrorCode = InstagramErrorCode.INVALID_URL):
        super().__init__(message)
        self.code = code
        self.message = message


class InstagramPostNotFoundError(Exception):
    """Исключение, когда публикация не найдена."""
    def __init__(self, message: str, code: InstagramErrorCode = InstagramErrorCode.POST_NOT_FOUND):
        super().__init__(message)
        self.code = code
        self.message = message


class ExtractInfoNotCalledError(Exception):
    """Исключение при попытке загрузки до вызова extract_info()."""
    def __init__(self, message: str, code: InstagramErrorCode = InstagramErrorCode.EXTRACTION_ERROR):
        super().__init__(message)
        self.code = code
        self.message = message

    
# ======= MainClass =======
class InstagramDownloader(AbstractServiceDownloader):
    """
    Загрузчик медиа из Instagram.
    
    Поддерживает:
    - отдельные изображения
    - публикации с видео
    - альбомы (карусели)
    - Reels
    - IGTV
    """

    def __init__(
        self, 
        username: str, 
        password: str, 
        timeout: int = 300,
        max_retries: int = 3,
        cookie_path: str = "cookies",
    ) -> None:
        """
        Инициализация загрузчика Instagram.
        
        Аргументы:
            username: Имя пользователя Instagram
            password: Пароль пользователя Instagram
            timeout: Время ожидания запроса в секундах
            max_retries: Максимальное количество повторных попыток подключения
            cookie_path: Путь для хранения cookies и сессии
        """
        logger.info("Инициализация загрузчика Instagram")
        
        self.timeout = timeout
        self.username = username
        self.password = password
        self.max_retries = max_retries
        
        # Инициализация Instaloader
        self.loader = Instaloader(
            request_timeout=self.timeout,
            max_connection_attempts=self.max_retries,
            quiet=True,
        )
        
        self.cookie_path: Optional[Path] = Path(cookie_path)
        self.session_file: Optional[Path] = self.cookie_path.joinpath("instagram-session")
        
        self._data: Optional[InstagramData] = None
        self._last_result: Optional[InstagramResult] = None
        
        self._init_loader()
        
    def _init_loader(self) -> None:
        """Инициализация и аутентификация в Instagram."""
        try:
            if self.session_file.exists():
                logger.info(f"Загрузка сессии из файла: {self.session_file}")
                self.loader.load_session_from_file(
                    username=self.username,
                    filename=str(self.session_file)
                )
                logger.info("Сессия успешно загружена")
            else:
                logger.info("Создание новой сессии...")
                self.cookie_path.mkdir(parents=True, exist_ok=True)
                self.loader.login(user=self.username, passwd=self.password)
                self.loader.save_session_to_file(filename=str(self.session_file))
                logger.info("Сессия успешно создана и сохранена")
                
        except ConnectionException as e:
            error_msg = f"Ошибка соединения при входе: {e}"
            logger.error(error_msg)
            raise InstagramSessionError(error_msg, InstagramErrorCode.CONNECTION_ERROR)
        
        except QueryReturnedBadRequestException as e:
            error_msg = f"Аутентификация не удалась: {e}"
            logger.error(error_msg)
            raise InstagramSessionError(error_msg, InstagramErrorCode.AUTHENTICATION_FAILED)
        
        except Exception as e:
            error_msg = f"Неожиданная ошибка при инициализации: {e}"
            logger.error(error_msg)
            raise InstagramSessionError(error_msg, InstagramErrorCode.INITIALIZATION_ERROR)
        
    def _validate_instagram_url(self, url: str) -> bool:
        """
        Проверка корректности URL Instagram.
        
        Аргументы:
            url: URL для проверки
            
        Возвращает:
            True, если URL корректный
        """
        try:
            parsed_url = urlparse(url=url)
            return parsed_url.netloc.endswith("instagram.com")
        except Exception as e:
            logger.debug(f"Ошибка при проверке URL: {e}")
            return False

    def _get_shortcode(self, url: str) -> Optional[str]:
        """
        Извлечение shortcode из URL Instagram.
        
        Аргументы:
            url: URL Instagram
            
        Возвращает:
            Shortcode поста или None, если извлечение не удалось
        """
        try:
            parsed_url = urlparse(url=url)
            path_parts = parsed_url.path.strip("/").split("/")
            
            if (len(path_parts) >= 2 and 
                path_parts[0] in ["p", "tv", "reel", "reels"]):
                shortcode = path_parts[1]
                logger.debug(f"Извлечён shortcode: {shortcode}")
                return shortcode
            
            if len(path_parts) == 1 and len(path_parts[0]) == 11:
                shortcode = path_parts[0]
                logger.debug(f"Извлечён shortcode: {shortcode}")
                return shortcode
                
            logger.warning(f"Не удалось извлечь shortcode из URL: {url}")
            return None
        
        except Exception as e:
            logger.error(f"Ошибка при извлечении shortcode из URL {url}: {e}")
            return None
        
    def _extract_media_info(self, post: Post) -> None:
        """Извлечение информации о медиа из поста Instagram."""
        logger.debug("Извлечение информации о медиа из поста")
        
        data = post._node
        
        if data is None:
            error_msg = "Данные поста не найдены"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=InstagramErrorCode.EXTRACTION_ERROR,
            )
            return
        
        # Извлечение подписи
        caption = data.get("accessibility_caption")
        if caption and caption != "None":
            self._data.title = caption
        
        # Извлечение имени владельца
        owner_data = data.get("owner")
        if owner_data and owner_data.get("username"):
            self._data.author_name = owner_data.get("username")
            
        content_type = data["__typename"]
        logger.debug(f"Тип контента: {content_type}")
        
        # Обработка разных типов контента
        if content_type.endswith(ContentType.VIDEO.value):
            self._data.is_video = True
            self._extract_video_content(data)
        elif content_type.endswith(ContentType.IMAGE.value):
            self._data.is_image = True
            self._extract_image_content(data)
        elif content_type.endswith(ContentType.SIDECAR.value):
            self._data.is_image = True
            self._extract_sidecar_content(data)
        else:
            error_msg = f"Тип контента не поддерживается: {content_type}"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=InstagramErrorCode.CONTENT_NOT_SUPPORTED,
            )
    
    def _extract_video_content(self, data: dict) -> None:
        """Извлечение информации о видео."""
        logger.debug("Извлечение видео")
        
        # Извлечение видео
        dimensions = data.get("dimensions")
        self._data.videos.append(
            InstagramVideo(
                id=uuid4(),
                url=data["video_url"],
                name=f"Video_{data['shortcode']}",
                width=dimensions.get("width") if dimensions else None,
                height=dimensions.get("height") if dimensions else None,
            )
        )
        
        # Извлечение миниатюр
        thumbnail_count = 0
        for idx, image in enumerate(data.get("display_resources", [])):
            self._data.thumbnails.append(
                InstagramImage(
                    id=uuid4(),
                    url=image["src"],
                    name=f"Thumbnail_{idx}",
                    width=image.get("config_width"),
                    height=image.get("config_height"),
                )
            )
            thumbnail_count += 1
            
        logger.debug(f"Извлечено 1 видео и {thumbnail_count} миниатюр")
        self._last_result = InstagramResult(data=self._data)
    
    def _extract_image_content(self, data: dict) -> None:
        """Извлечение информации об изображениях."""
        logger.debug("Извлечение изображений")
        
        image_count = 0
        for idx, image in enumerate(data.get("display_resources", [])):
            self._data.images.append(
                InstagramImage(
                    id=uuid4(),
                    url=image["src"],
                    name=f"Image_{idx}",
                    width=image.get("config_width"),
                    height=image.get("config_height"),
                )
            )
            image_count += 1
            
        logger.debug(f"Извлечено {image_count} изображений")
        self._last_result = InstagramResult(data=self._data)
    
    def _extract_sidecar_content(self, data: dict) -> None:
        """Извлечение информации о карусели (альбоме)."""
        logger.debug("Извлечение карусели")
        
        image_count = 0
        video_count = 0
        
        children_sidecar = data.get("edge_sidecar_to_children")
        for idx, media_item in enumerate(children_sidecar.get("edges", []) if children_sidecar else []):
            media_item_node = media_item.get("node")
            if media_item_node:
                media_content_type = media_item_node["__typename"]
                
                if media_content_type.endswith(ContentType.IMAGE.value):
                    for jdx, image in enumerate(media_item_node.get("display_resources", [])):
                        self._data.images.append(
                            InstagramImage(
                                id=uuid4(),
                                url=image["src"],
                                name=f"Image_{jdx}_{idx}",
                                width=image.get("config_width"),
                                height=image.get("config_height"),
                            )
                        )
                        image_count += 1
    
                elif media_content_type.endswith(ContentType.VIDEO.value):
                    dimensions = media_item_node.get("dimensions")
                    self._data.videos.append(
                        InstagramVideo(
                            id=uuid4(),
                            url=media_item_node["video_url"],
                            name=f"Video_{media_item_node["shortcode"]}",
                            width=dimensions.get("width") if dimensions else None,
                            height=dimensions.get("height") if dimensions else None,
                        )
                    )
                    video_count += 1
                    
        logger.debug(f"Извлечено {image_count} изображений и {video_count} видео из карусели")
        self._last_result = InstagramResult(data=self._data)
    
    def extract_info(self, url: str) -> InstagramResult:
        """
        Извлечение информации о медиа из URL Instagram.
        
        Аргументы:
            url: URL поста Instagram
            
        Возвращает:
            InstagramResult с извлечёнными данными о медиа
        """
        logger.info(f"Извлечение информации из URL: {url}")
        
        # Проверка URL
        if not url or not isinstance(url, str):
            error_msg = "Некорректный URL"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                code=InstagramErrorCode.EMPTY_URL,
                data=InstagramData(url=url),
            )
            return self._last_result
        
        if not self._validate_instagram_url(url):
            error_msg = "Некорректный или неподдерживаемый URL Instagram"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                code=InstagramErrorCode.INVALID_URL,
                data=InstagramData(url=url),
            )
            return self._last_result
        
        # Извлечение shortcode
        shortcode = self._get_shortcode(url)
        if not shortcode:
            error_msg = "Не удалось извлечь shortcode из URL"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                data=InstagramData(url=url),
                code=InstagramErrorCode.INVALID_SHORTCODE,
            )
            return self._last_result
        
        try:
            logger.info(f"Извлечение информации для shortcode: {shortcode}")
            
            post = Post.from_shortcode(self.loader.context, shortcode)
            self._data = InstagramData(url=url)
            self._extract_media_info(post)
            
            if self._last_result and self._last_result.status != "error":
                logger.info(f"Информация успешно извлечена: {len(self._data.images)} изображений, "
                           f"{len(self._data.videos)} видео")
            else:
                logger.warning("Извлечение информации завершилось с ошибками")
            
            return self._last_result
            
        except PostChangedException as e:
            error_msg = f"Пост изменён или недоступен: {e}"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                code=InstagramErrorCode.POST_CHANGED,
                data=InstagramData(url=url),
            )
            return self._last_result
        
        except ProfileNotExistsException as e:
            error_msg = f"Профиль не найден: {e}"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                data=InstagramData(url=url),
                code=InstagramErrorCode.PROFILE_NOT_EXISTS,
            )
            return self._last_result
        
        except ConnectionException as e:
            error_msg = f"Ошибка соединения: {e}"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                data=InstagramData(url=url),
                code=InstagramErrorCode.CONNECTION_ERROR,
            )
            return self._last_result
        
        except BadResponseException as e:
            error_msg = f"Некорректный ответ API: {e}"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                code=InstagramErrorCode.BAD_RESPONSE,
                data=InstagramData(url=url),
            )
            return self._last_result
            
        except Exception as e:
            error_msg = f"Неожиданная ошибка при извлечении: {e}"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                data=InstagramData(url=url),
                code=InstagramErrorCode.UNEXPECTED_ERROR,
            )
            return self._last_result

    def get_error_description(self, code: InstagramErrorCode) -> str:
        """
        Получение описания ошибки по коду.
        
        Аргументы:
            code: Код ошибки
            
        Возвращает:
            Строку с описанием ошибки
        """
        descriptions = {
            InstagramErrorCode.SUCCESS: "Операция выполнена успешно",
            InstagramErrorCode.INVALID_URL: "Неправильный или неподдерживаемый URL",
            InstagramErrorCode.INVALID_SHORTCODE: "Не удалось извлечь shortcode из URL",
            InstagramErrorCode.EMPTY_URL: "Пустой или некорректный URL",
            InstagramErrorCode.AUTHENTICATION_FAILED: "Ошибка аутентификации в Instagram",
            InstagramErrorCode.SESSION_LOAD_FAILED: "Не удалось загрузить сессию из файла",
            InstagramErrorCode.SESSION_SAVE_FAILED: "Не удалось сохранить сессию в файл",
            InstagramErrorCode.CONNECTION_ERROR: "Ошибка сетевого соединения",
            InstagramErrorCode.TIMEOUT_ERROR: "Превышено время ожидания запроса",
            InstagramErrorCode.BAD_RESPONSE: "Некорректный ответ API Instagram",
            InstagramErrorCode.POST_NOT_FOUND: "Пост не найден",
            InstagramErrorCode.POST_CHANGED: "Пост изменён или недоступен",
            InstagramErrorCode.PROFILE_NOT_EXISTS: "Профиль не существует",
            InstagramErrorCode.CONTENT_NOT_SUPPORTED: "Тип контента не поддерживается",
            InstagramErrorCode.EXTRACTION_ERROR: "Ошибка при извлечении контента",
            InstagramErrorCode.UNEXPECTED_ERROR: "Произошла непредвиденная ошибка",
            InstagramErrorCode.INITIALIZATION_ERROR: "Ошибка инициализации загрузчика",
            InstagramErrorCode.DOWNLOAD_ERROR: "Ошибка при скачивании контента",
        }
        return descriptions.get(code, "Неизвестная ошибка")
