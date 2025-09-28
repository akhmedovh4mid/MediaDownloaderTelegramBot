from enum import Enum
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class AbstractServiceImage(ABC):
    """
    Abstract base class representing an image in a service.
    
    Attributes:
        id: Unique identifier for the image
        url: Direct URL to the image resource
        name: Display name or filename of the image
        width: Width of the image in pixels (optional)
        height: Height of the image in pixels (optional)
        caption: Descriptive caption for the image (optional)
    """
    id: str
    url: str
    name: str
    width: Optional[int] = None
    height: Optional[int] = None
    caption: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the image instance to a dictionary representation.
        
        Returns:
            Dictionary containing all image attributes
        """
        return {
            "id": str(self.id),
            "url": self.url,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "caption": self.caption
        }
    
    
@dataclass
class AbstractServiceVideo(ABC):
    """
    Abstract base class representing a video in a service.
    
    Attributes:
        id: Unique identifier for the video
        url: Direct URL to the video resource
        name: Display name or filename of the video
        fps: Frames per second of the video (optional)
        cover: URL to video cover image (optional)
        width: Width of the video in pixels (optional)
        height: Height of the video in pixels (optional)
        caption: Descriptive caption for the video (optional)
        duration: Duration of the video in seconds (optional)
        thumbnail: URL to video thumbnail (optional)
        total_bitrate: Total bitrate of the video in kbps (optional)
    """
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
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the video instance to a dictionary representation.
        
        Returns:
            Dictionary containing all video attributes
        """
        return {
            "id": str(self.id),
            "url": self.url,
            "name": self.name,
            "fps": self.fps,
            "cover": self.cover,
            "width": self.width,
            "height": self.height,
            "caption": self.caption,
            "duration": self.duration,
            "thumbnail": self.thumbnail,
            "total_bitrate": self.total_bitrate,
        }
    

@dataclass
class AbstractServiceAudio(ABC):
    """
    Abstract base class representing an audio file in a service.
    
    Attributes:
        id: Unique identifier for the audio
        url: Direct URL to the audio resource
        name: Display name or filename of the audio
        cover: URL to audio cover image (optional)
        author: Author or artist of the audio (optional)
        caption: Descriptive caption for the audio (optional)
        duration: Duration of the audio (format varies by service) (optional)
        total_bitrate: Total bitrate of the audio in kbps (optional)
    """
    id: str
    url: str
    name: str
    cover: Optional[str] = None
    author: Optional[str] = None
    caption: Optional[str] = None
    duration: Optional[str] = None
    total_bitrate: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the audio instance to a dictionary representation.
        
        Returns:
            Dictionary containing all audio attributes
        """
        return {
            "id": str(self.id),
            "url": self.url,
            "name": self.name,
            "cover": self.cover,
            "author": self.author,
            "caption": self.caption,
            "duration": self.duration,
            "total_bitrate": self.total_bitrate,
        }
        
    

@dataclass
class AbstractServiceData(ABC):
    """
    Abstract base class representing collected data from a service.
    
    Attributes:
        url: Original URL that was processed
        is_video: Flag indicating if the content is primarily video
        is_image: Flag indicating if the content is primarily image
        path: Local filesystem path where content is stored (optional)
        title: Title of the content (optional)
        description: Description of the content (optional)
        videos: List of video objects found in the content
        images: List of image objects found in the content
        audios: List of audio objects found in the content
        thumbnails: List of thumbnail images for the content
    """
    url: str
    is_video: bool = False
    is_image: bool = False
    path: Optional[Path] = None
    title: Optional[str] = None
    description: Optional[str] = None
    videos: List[AbstractServiceVideo] = field(default_factory=list)
    images: List[AbstractServiceImage] = field(default_factory=list)
    audios: List[AbstractServiceAudio] = field(default_factory=list)
    thumbnails: List[AbstractServiceImage] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the data instance to a dictionary representation.
        
        Returns:
            Dictionary containing all data attributes with nested objects converted to dicts
        """
        return {
            "url": self.url,
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
    Abstract base enum for service error codes.
    
    This enum should be extended by specific service implementations
    to define their own error codes.
    """
    SUCCESS = "SUCCESS"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    

@dataclass
class AbstractServiceResult(ABC):
    """
    Abstract base class representing the result of a service operation.
    
    Attributes:
        status: Operation status - either "success" or "error"
        context: Additional context or error message (optional)
        code: Error code indicating the specific result type
        data: Extracted data from the service (optional)
    """
    status: Literal["success", "error"] = "success"
    context: Optional[str] = None
    code: AbstractServiceErrorCode = field(default=AbstractServiceErrorCode.SUCCESS)
    data: Optional[AbstractServiceData] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the result instance to a dictionary representation.
        
        Returns:
            Dictionary containing result status, context, code, and data
        """
        return {
            "status": self.status,
            "context": self.context,
            "code": self.code.value,
            "data": self.data.to_dict(),
        }


class AbstractServiceDownloader(ABC):
    """
    Abstract base class for service downloaders.
    
    This class defines the interface that all service-specific downloaders
    must implement to provide consistent media extraction functionality.
    """
    
    @abstractmethod
    def extract_info(self, url: str) -> AbstractServiceResult:
        """
        Extract media information from a URL without downloading.
        
        Args:
            url: The URL to extract information from
            
        Returns:
            ServiceResult containing extracted media information
        """
        pass
        
    # @abstractmethod
    # def download_media(self, url: str) -> AbstractServiceResult:
    #     """
    #     Download media from a URL and return information about downloaded files.
        
    #     Args:
    #         url: The URL to download media from
            
    #     Returns:
    #         ServiceResult containing information about downloaded files
    #     """
    #     pass
