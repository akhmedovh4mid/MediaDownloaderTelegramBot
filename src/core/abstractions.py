from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Literal, Optional


@dataclass
class AbstractServiceImage(ABC):
    id: str
    url: str
    name: str
    width: Optional[int] = None
    height: Optional[int] = None
    caption: Optional[str] = None
    
    @property
    def resolution(self) -> Optional[str]:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return None
    
    
@dataclass
class AbstractServiceVideo(ABC):
    id: str
    url: str
    name: str
    fps: Optional[int] = None
    cover: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    caption: Optional[str] = None
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    total_bitrate: Optional[int] = None
    
    @property
    def resolution(self) -> Optional[str]:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return None
    

@dataclass
class AbstractServiceAudio(ABC):
    id: str
    url: str
    name: str
    cover: Optional[str] = None
    author: Optional[str] = None
    caption: Optional[str] = None
    duration: Optional[str] = None
    total_bitrate: Optional[int] = None
    

@dataclass
class AbstractServiceData(ABC):
    url: str
    path: Optional[Path] = None
    title: Optional[str] = None
    description: Optional[str] = None
    videos: List[AbstractServiceVideo] = field(default_factory=list)
    images: List[AbstractServiceImage] = field(default_factory=list)
    audios: List[AbstractServiceAudio] = field(default_factory=list)
    thumbnails: List[AbstractServiceImage] = field(default_factory=list)


@dataclass
class AbstractServiceResult(ABC):
    status: Literal["success", "error"] = "success"
    context: Optional[str] = None
    data: Optional[AbstractServiceData] = None


class AbstractServiceDownloader(ABC):
    @abstractmethod
    def extract_info(self, url: str) -> AbstractServiceResult:
        """Извлекает информацию о медиа по URL без скачивания."""
        pass
        
    # @abstractmethod
    # def download_media(self, url: str) -> AbstractServiceResult:
    #     """Скачивает медиа по URL и возвращает информацию о скачанных файлах."""
    #     pass
