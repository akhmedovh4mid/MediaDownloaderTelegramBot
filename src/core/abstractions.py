from enum import Enum
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, TypedDict, NotRequired


# ======= Image =======
class AbstractServiceImageTypeDict(TypedDict):
    id: str
    url: str
    name: str
    width: NotRequired[Optional[int]]
    height: NotRequired[Optional[int]]


@dataclass
class AbstractServiceImage(ABC):
    """
    Базовый абстрактный класс, описывающий изображение в сервисе.
    
    Атрибуты:
        id: Уникальный идентификатор изображения
        url: Прямая ссылка на изображение
        name: Имя файла или отображаемое название изображения
        width: Ширина изображения в пикселях (опционально)
        height: Высота изображения в пикселях (опционально)
    """
    id: str
    url: str
    name: str
    width: Optional[int] = None
    height: Optional[int] = None
    
    def to_dict(self) -> AbstractServiceImageTypeDict:
        """
        Преобразует объект изображения в словарь.
        
        Возвращает:
            Словарь со всеми атрибутами изображения
        """
        return {
            "id": str(self.id),
            "url": self.url,
            "name": self.name,
            "width": self.width,
            "height": self.height,
        }
    

# ======= Video ======= 
class AbstractServiceVideoTypeDict(TypedDict):
    id: str
    url: str
    name: str
    has_audio: bool
    fps: NotRequired[Optional[int]]
    width: NotRequired[Optional[int]]
    height: NotRequired[Optional[int]]
    language: NotRequired[Optional[str]]
    total_bitrate: NotRequired[Optional[int]]
    language_preference: NotRequired[Optional[int]]


@dataclass
class AbstractServiceVideo(ABC):
    """
    Базовый абстрактный класс, описывающий видео в сервисе.
    
    Атрибуты:
        id: Уникальный идентификатор видео
        url: Прямая ссылка на видео
        name: Имя файла или отображаемое название видео
        has_audio: Присутсвие аудио дорожки
        fps: Количество кадров в секунду (опционально)
        width: Ширина видео в пикселях (опционально)
        height: Высота видео в пикселях (опционально)
        language: Язык audio дорожки (опционально)
        language_preference: Приоритет языка (опционально)
        total_bitrate: Общий битрейт видео в kbps (опционально)
    """
    id: str
    url: str
    name: str
    has_audio: bool = False
    fps: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    language: Optional[str] = None
    total_bitrate: Optional[int] = None
    language_preference: Optional[int] = None
    
    def to_dict(self) -> AbstractServiceVideoTypeDict:
        """
        Преобразует объект видео в словарь.
        
        Возвращает:
            Словарь со всеми атрибутами видео
        """
        return {
            "id": str(self.id),
            "url": self.url,
            "name": self.name,
            "has_audio": self.has_audio, 
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "language": self.language,
            "total_bitrate": self.total_bitrate,
            "language_preference": self.language_preference,
        }
    

# ======= Audio =======
class AbstractServiceAudioTypeDict(TypedDict):
    id: str
    url: str
    name: str
    author: NotRequired[Optional[str]]
    language: NotRequired[Optional[str]]
    total_bitrate: NotRequired[Optional[int]]
    language_preference: NotRequired[Optional[int]]


@dataclass
class AbstractServiceAudio(ABC):
    """
    Базовый абстрактный класс, описывающий аудиофайл в сервисе.
    
    Атрибуты:
        id: Уникальный идентификатор аудио
        url: Прямая ссылка на аудио
        name: Имя файла или отображаемое название
        author: Автор или исполнитель (опционально)
        language: Язык audio дорожки (опционально)
        language_preference: Приоритет языка (опционально)
        total_bitrate: Общий битрейт аудио в kbps (опционально)
    """
    id: str
    url: str
    name: str
    author: Optional[str] = None
    language: Optional[str] = None
    total_bitrate: Optional[int] = None
    language_preference: Optional[int] = None
    
    def to_dict(self) -> AbstractServiceAudioTypeDict:
        """
        Преобразует объект аудио в словарь.
        
        Возвращает:
            Словарь со всеми атрибутами аудио
        """
        return {
            "id": str(self.id),
            "url": self.url,
            "name": self.name,
            "author": self.author,
            "language": self.language,
            "total_bitrate": self.total_bitrate,
            "language_preference": self.language_preference,
        }
        
    
# ======= Data =======
class AbstractServiceDataTypeDict(TypedDict):
    url: str
    is_video: bool
    is_image: bool
    path: NotRequired[Optional[str]]
    title: NotRequired[Optional[str]]
    author_name: NotRequired[Optional[str]]
    description: NotRequired[Optional[str]]
    videos: List[AbstractServiceVideoTypeDict]
    images: List[AbstractServiceImageTypeDict]
    audios: List[AbstractServiceAudioTypeDict]
    thumbnails: List[AbstractServiceImageTypeDict]
    

@dataclass
class AbstractServiceData(ABC):
    """
    Базовый абстрактный класс, представляющий данные, собранные из сервиса.
    
    Атрибуты:
        url: Исходный URL, который был обработан
        author_name: Имя автора или владельца контента
        is_video: Флаг, указывающий, что контент — это видео
        is_image: Флаг, указывающий, что контент — это изображение
        path: Локальный путь к файлу (опционально)
        title: Заголовок контента (опционально)
        description: Описание контента (опционально)
        videos: Список объектов видео
        images: Список объектов изображений
        audios: Список объектов аудио
        thumbnails: Список превью-изображений
    """
    url: str
    is_video: bool = False
    is_image: bool = False
    path: Optional[str] = None
    title: Optional[str] = None
    author_name: Optional[str] = None
    description: Optional[str] = None
    videos: List[AbstractServiceVideo] = field(default_factory=list)
    images: List[AbstractServiceImage] = field(default_factory=list)
    audios: List[AbstractServiceAudio] = field(default_factory=list)
    thumbnails: List[AbstractServiceImage] = field(default_factory=list)
    
    def to_dict(self) -> AbstractServiceDataTypeDict:
        """
        Преобразует объект данных в словарь.
        
        Возвращает:
            Словарь со всеми атрибутами данных (вложенные объекты также преобразуются в словари)
        """
        return {
            "url": self.url,
            "author_name": self.author_name,
            "is_video": self.is_video,
            "is_image": self.is_image,
            "path": self.path,
            "title": self.title,
            "description": self.description,
            "videos": [video.to_dict() for video in self.videos],
            "images": [image.to_dict() for image in self.images],
            "audios": [audio.to_dict() for audio in self.audios],
            "thumbnails": [thumbnail.to_dict() for thumbnail in self.thumbnails],
        }


class AbstractServiceErrorCode(Enum):
    """
    Базовый класс для кодов ошибок сервиса.
    
    Этот enum должен быть расширен конкретными реализациями сервисов,
    чтобы задавать свои собственные коды ошибок.
    """
    SUCCESS = "SUCCESS"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


# ======= Result ======= 
class AbstractServiceResultTypeDict(TypedDict):
    status: Literal["success", "error"]
    context: NotRequired[Optional[str]]
    code: AbstractServiceErrorCode
    data: NotRequired[Optional[AbstractServiceDataTypeDict]]


@dataclass
class AbstractServiceResult(ABC):
    """
    Базовый абстрактный класс, представляющий результат выполнения операции сервиса.
    
    Атрибуты:
        status: Статус операции — "success" или "error"
        context: Дополнительное описание ошибки или контекста (опционально)
        code: Код ошибки, указывающий на конкретный результат
        data: Извлечённые данные (опционально)
    """
    status: Literal["success", "error"] = "success"
    context: Optional[str] = None
    code: AbstractServiceErrorCode = field(default=AbstractServiceErrorCode.SUCCESS)
    data: Optional[AbstractServiceData] = None
    
    def to_dict(self) -> AbstractServiceResultTypeDict:
        """
        Преобразует объект результата в словарь.
        
        Возвращает:
            Словарь со статусом, контекстом, кодом и данными
        """
        return {
            "status": self.status,
            "context": self.context,
            "code": self.code.value,
            "data": self.data.to_dict(),
        }


class AbstractServiceDownloader(ABC):
    """
    Базовый абстрактный класс для загрузчиков из сервисов.
    
    Определяет интерфейс, который должны реализовать конкретные загрузчики,
    чтобы предоставлять единый способ извлечения медиа-данных.
    """
    
    @abstractmethod
    def extract_info(self, url: str) -> AbstractServiceResult:
        """
        Извлекает информацию о медиа по URL без загрузки файлов.
        
        Аргументы:
            url: Ссылка для извлечения информации
            
        Возвращает:
            AbstractServiceResult с собранными данными
        """
        pass
        
    # @abstractmethod
    # def download_media(self, url: str) -> AbstractServiceResult:
    #     """
    #     Загружает медиа по указанному URL и возвращает информацию о загруженных файлах.
        
    #     Аргументы:
    #         url: Ссылка для загрузки медиа
        
    #     Возвращает:
    #         AbstractServiceResult с информацией о загруженных файлах
    #     """
    #     pass

