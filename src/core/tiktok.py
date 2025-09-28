"""
TikTok downloader module.

This module provides functionality to download media content from TikTok,
including videos, images, and audio.
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


# Setup logging
logger = logging.getLogger("tiktok")


# ======= EnumsClasses =======
class ContentType(Enum):
    """Enum representing different TikTok content types."""
    LIVE = "live"
    PHOTO = "photo"
    VIDEO = "video"
    MUSIC = "music"
    ACCOUNT = "account"
    UNKNOWN = "unknown"
    
    
class ErrorCode(Enum):
    """Enum representing error codes for TikTok operations."""
    
    # Success
    SUCCESS = "SUCCESS"
    
    # Input validation errors (1xx)
    INVALID_URL = "INVALID_URL"
    EMPTY_URL = "EMPTY_URL"
    UNSUPPORTED_CONTENT_TYPE = "UNSUPPORTED_CONTENT_TYPE"
    URL_RESOLUTION_FAILED = "URL_RESOLUTION_FAILED"
    
    # Network errors (2xx)
    CONNECTION_ERROR = "CONNECTION_ERROR"
    DOWNLOAD_ERROR = "DOWNLOAD_ERROR"
    EXTRACTOR_ERROR = "EXTRACTOR_ERROR"
    PROXY_ERROR = "PROXY_ERROR"
    
    # Content errors (3xx)
    NO_EXTRACTOR_FOUND = "NO_EXTRACTOR_FOUND"
    NO_CONTENT_FOUND = "NO_CONTENT_FOUND"
    METADATA_EXTRACTION_FAILED = "METADATA_EXTRACTION_FAILED"
    VIDEO_EXTRACTION_FAILED = "VIDEO_EXTRACTION_FAILED"
    PHOTO_EXTRACTION_FAILED = "PHOTO_EXTRACTION_FAILED"
    MUSIC_EXTRACTION_FAILED = "MUSIC_EXTRACTION_FAILED"
    NO_VIDEO_FORMATS_FOUND = "NO_VIDEO_FORMATS_FOUND"
    NO_IMAGES_FOUND = "NO_IMAGES_FOUND"
    NO_THUMBNAILS_FOUND = "NO_THUMBNAILS_FOUND"
    
    # File system errors (4xx)
    COOKIE_FILE_NOT_FOUND = "COOKIE_FILE_NOT_FOUND"
    OUTPUT_PATH_ERROR = "OUTPUT_PATH_ERROR"
    FILE_WRITE_ERROR = "FILE_WRITE_ERROR"
    
    # System errors (5xx)
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
    EXTRACT_INFO_NOT_CALLED = "EXTRACT_INFO_NOT_CALLED"
    GALLERY_DL_ERROR = "GALLERY_DL_ERROR"
    YT_DLP_ERROR = "YT_DLP_ERROR"


# ======= DataClasses =======
@dataclass
class TikTokData(AbstractServiceData):
    """Container for TikTok media data."""
    pass


@dataclass
class TikTokImage(AbstractServiceImage):
    """Represents a TikTok image."""
    pass


@dataclass
class TikTokVideo(AbstractServiceVideo):
    """Represents a TikTok video format."""
    pass


@dataclass
class TikTokAudio(AbstractServiceAudio):
    """Represents a TikTok audio format."""
    pass


@dataclass
class TikTokResult(AbstractServiceResult):
    """Result of TikTok operations."""
    code: ErrorCode = field(default=ErrorCode.SUCCESS)


# ======= ExceptionClasses =======
class ExtractInfoNotCalledError(Exception):
    """Exception raised when download is attempted before extract_info."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.EXTRACT_INFO_NOT_CALLED):
        super().__init__(message)
        self.code = code
        self.message = message


class CookieFileNotFoundError(FileNotFoundError):
    """Exception raised when cookie file is not found."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.COOKIE_FILE_NOT_FOUND):
        super().__init__(message)
        self.code = code
        self.message = message


class UnsupportedContentTypeError(Exception):
    """Exception raised for unsupported content types."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.UNSUPPORTED_CONTENT_TYPE):
        super().__init__(message)
        self.code = code
        self.message = message
    

# ======= MainClass =======
class TikTokDownloader(AbstractServiceDownloader):
    """
    TikTok media downloader.
    
    Supports downloading videos and images from TikTok.
    Handles URL resolution and content type classification.
    """

    def __init__(
        self,
        retries_count: int = 10,
        proxy: Optional[str] = None,
        cookie_path: Optional[str] = None,
        concurrent_download_count: int = 2,
    ) -> None:
        """
        Initialize TikTok downloader.
        
        Args:
            retries_count: Number of retry attempts for downloads
            proxy: Proxy server URL (optional)
            cookie_path: Path to cookies file (optional)
            concurrent_download_count: Number of concurrent fragment downloads
        """
        logger.info("Initializing TikTok downloader")
        
        self.proxy = proxy
        self.cookies_path = Path(cookie_path) if cookie_path else None

        if self.cookies_path and not self.cookies_path.exists():
            error_msg = f"Cookie file not found: {self.cookies_path}"
            logger.error(error_msg)
            raise CookieFileNotFoundError(error_msg, ErrorCode.COOKIE_FILE_NOT_FOUND)

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
            
            logger.debug("TikTok downloader initialized successfully")

        except Exception as e:
            error_msg = f"Failed to initialize TikTok downloader: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

    def _resolve_vm_url(self, url: str) -> Optional[str]:
        """
        Resolve shortened TikTok URLs (vm.tiktok.com, vt.tiktok.com).
        
        Args:
            url: Shortened TikTok URL
            
        Returns:
            Resolved URL or None if resolution fails
        """
        logger.debug(f"Resolving shortened URL: {url}")
        
        try:
            extr = extractor.find(url=url)
            if not extr:
                logger.warning(f"No extractor found for URL: {url}")
                return None
            
            extr.initialize()
            items = list(extr.items())
            
            if not items or len(items[0]) < 2:
                logger.warning(f"No items extracted from URL: {url}")
                return None
                
            resolved_url = items[0][1]
            logger.debug(f"URL resolved to: {resolved_url}")
            return resolved_url
            
        except Exception as e:
            logger.error(f"Error resolving URL {url}: {e}")
            return None

    def _classify_url(self, url: str) -> ContentType:
        """
        Classify TikTok URL content type.
        
        Args:
            url: TikTok URL to classify
            
        Returns:
            ContentType: The classified content type
        """
        logger.debug(f"Classifying URL: {url}")
        
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
                
            logger.debug(f"URL classified as: {result.value}")
            return result
        
        except Exception as e:
            logger.error(f"URL classification error: {e}")
            return ContentType.UNKNOWN
        
    def _validate_tiktok_url(self, url: str) -> bool:
        """
        Validate TikTok URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid TikTok URL
        """
        try:
            parsed = urlparse(url)
            return any(domain in parsed.netloc for domain in ["tiktok.com", "vm.tiktok.com", "vt.tiktok.com"])
        except Exception as e:
            logger.debug(f"URL validation error: {e}")
            return False
    
    def classify_url(self, url: str) -> Tuple[ContentType, str]:
        """
        Classify URL and resolve shortened URLs if necessary.
        
        Args:
            url: TikTok URL to classify
            
        Returns:
            Tuple of (ContentType, resolved_url)
        """
        logger.debug(f"Classifying and resolving URL: {url}")
        
        parsed = urlparse(url)
        
        if "vm.tiktok.com" in parsed.netloc or "vt.tiktok.com" in parsed.netloc:
            resolved_url = self._resolve_vm_url(url)
            if resolved_url:
                url = resolved_url
                logger.info(f"Resolved shortened URL to: {url}")
            else:
                logger.warning("Failed to resolve shortened URL")
                return (ContentType.UNKNOWN, url)
        
        content_type = self._classify_url(url=url)
        return (content_type, url)
    
    def _extract_music(self, metadata: dict) -> None:
        """Extract music information from metadata."""
        music = metadata.get("music")
        if music:
            logger.debug("Extracting music information")
            self._data.audios.append(
                TikTokAudio(
                    id=uuid4(),
                    url=music["playUrl"],
                    name=music["title"],
                    cover=music.get("coverThumb"),
                    author=music.get("authorName"),
                    duration=music.get("duration"),
                )
            )
    
    def _extract_video(self, metadata: dict) -> TikTokResult:
        """Extract video content information."""
        logger.debug("Extracting video content")
        
        ydl_opts = self.ydl_opts.copy()
        ydl_opts['listformats'] = True
        
        with YoutubeDL(params=ydl_opts) as ydl:
            try:
                data = ydl.extract_info(url=self._data.url, download=False)
                logger.debug("Video info extraction completed")
                
            except ExtractorError as e:
                error_msg = f"Video extraction error: {str(e)}"
                logger.error(error_msg)
                self._last_result = TikTokResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=ErrorCode.EXTRACTOR_ERROR,
                )
                return self._last_result
            
            except DownloadError as e:
                error_msg = f"Video download error: {str(e)}"
                logger.error(error_msg)
                self._last_result = TikTokResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=ErrorCode.DOWNLOAD_ERROR,
                )
                return self._last_result
            
            except Exception as e:
                error_msg = f"Unexpected video extraction error: {str(e)}"
                logger.error(error_msg)
                self._last_result = TikTokResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=ErrorCode.UNEXPECTED_ERROR,
                )
                return self._last_result

        # Populate data
        self._data.title = data.get("title")
        self._data.description = data.get("description")

        # Extract video formats
        video_count = 0
        for format in data.get("formats", []):
            if (
                format["ext"] == "mp4"
                and format["vcodec"] == "h264"
                and format["format_id"].endswith("-0")
            ):
                self._data.videos.append(
                    TikTokVideo(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        fps=format.get("fps"),
                        width=format.get("width"),
                        height=format.get("height"),
                        caption=format.get("format"),
                        duration=data.get("duration"),
                        total_bitrate=format.get("tbr"),
                    )
                )
                video_count += 1
                
        if video_count == 0:
            error_msg = "No supported video formats found"
            logger.warning(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.NO_VIDEO_FORMATS_FOUND,
            )
            return self._last_result
        
        # Extract thumbnails
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
            
        # Extract music
        self._extract_music(metadata=metadata)
        
        logger.info(f"Extracted {video_count} video formats, {thumbnail_count} thumbnails")
        self._last_result = TikTokResult(data=self._data)
        return self._last_result
    
    def _extract_photo(self, metadata: dict) -> TikTokResult:
        """Extract photo content information."""
        logger.debug("Extracting photo content")
        
        self._data.title = metadata.get("title")
        self._data.description = metadata.get("desc")
        
        if image_post := metadata.get("imagePost"):
            image_count = 0
            for idx, image in enumerate(image_post.get("images", [])):
                self._data.images.append(
                    TikTokImage(
                        id=uuid4(),
                        url=image["imageURL"]["urlList"][0],
                        name=f"{ContentType.PHOTO.value}_{image.get('imageWidth')}x{image.get('imageHeight')}_{idx}",
                        width=image.get("imageWidth"),
                        height=image.get("imageHeight"),
                    )
                )
                image_count += 1
            logger.info(f"Extracted {image_count} images from photo post")
            
        if image_count == 0:
            error_msg = "No images found in photo post"
            logger.warning(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.NO_IMAGES_FOUND,
            )
            return self._last_result
                
        self._extract_music(metadata=metadata)
        self._last_result = TikTokResult(data=self._data)
        return self._last_result
    
    def _generate_safe_filename(self, url: str, video_format_id: str) -> str:
        """
        Generate safe filename based on URL hash.
        
        Args:
            url: Content URL
            video_format_id: Video format ID
            
        Returns:
            Safe filename string
        """
        hash_input = f"tiktok_{url}_{video_format_id}"
        file_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return file_hash
        
    def extract_info(self, url: str) -> TikTokResult:
        """
        Extract media information from TikTok URL.
        
        Args:
            url: TikTok URL to extract information from
            
        Returns:
            TikTokResult: Result containing extracted media data
        """
        logger.info(f"Extracting info from URL: {url}")
        
        # Validate URL
        if not url or not isinstance(url, str):
            error_msg = "Invalid URL provided"
            logger.error(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.EMPTY_URL,
            )
            return self._last_result
        
        if not self._validate_tiktok_url(url):
            error_msg = "Invalid or unsupported TikTok URL"
            logger.error(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.INVALID_URL,
            )
            return self._last_result
        
        # Classify and resolve URL
        content_type, url = self.classify_url(url=url)
        self._data = TikTokData(url=url)
        
        if content_type in self.unsupported_types:
            error_msg = f"Unsupported content type: {content_type.value}"
            logger.warning(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.UNSUPPORTED_CONTENT_TYPE,
            )
            return self._last_result
            
        # Find appropriate extractor
        extr = extractor.find(url=url)
        if extr is None:
            error_msg = "No extractor found for this URL"
            logger.error(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.NO_EXTRACTOR_FOUND,
            )
            return self._last_result
        
        try:
            extr.initialize()
            extr_items = list(extr.items())
            
            if not extr_items:
                error_msg = "No content found for this URL"
                logger.error(error_msg)
                self._last_result = TikTokResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=ErrorCode.NO_CONTENT_FOUND,
                )
                return self._last_result
            
            metadata = extr_items[0][-1]
            logger.debug("Successfully extracted metadata")
        
        except Exception as e:
            error_msg = f"Metadata extraction failed: {e}"
            logger.error(error_msg)
            self._last_result = TikTokResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.METADATA_EXTRACTION_FAILE,
            )
            return self._last_result

        # Extract based on content type
        if content_type == ContentType.VIDEO:
            self._data.is_video = True
            return self._extract_video(metadata=metadata)

        elif content_type == ContentType.PHOTO:
            self._data.is_image = True
            return self._extract_photo(metadata=metadata)
        
        error_msg = f"Unexpected content type: {content_type.value}"
        logger.error(error_msg)
        return TikTokResult(
            status="error",
            data=self._data,
            context=error_msg,
            code=ErrorCode.UNSUPPORTED_CONTENT_TYPE,
        )

    def download_media(
        self,
        url: str,
        video_format_id: str,
        output_path: str = "./downloads/tiktok/",
    ) -> TikTokResult:
        """
        Download media using previously extracted information.
        
        Args:
            url: URL of the TikTok video to download
            video_format_id: ID of the video format to download
            output_path: Directory path for saving the downloaded file
            
        Returns:
            TikTokResult: Result of the download operation
            
        Raises:
            ExtractInfoNotCalledError: If extract_info wasn't called first
        """
        logger.info(f"Starting media download: url={url}, format={video_format_id}")
         
        # Prepare output directory
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate safe filename
        safe_filename = self._generate_safe_filename(
            url=url,
            video_format_id=video_format_id
        )
        file_path = output_dir / f"{safe_filename}.mp4"
        
        # Configure download options
        ydl_opts = self.ydl_opts.copy()
        ydl_opts.update({
            "outtmpl": str(file_path),
            "format": video_format_id,
            "merge_output_format": "mp4",
        })
        
        try:
            logger.debug(f"Downloading to: {file_path}")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            logger.info(f"Download completed successfully: {file_path}")
            return TikTokResult(data=TikTokData(url=url, path=file_path, is_video=True))

        except DownloadError as e:
            error_msg = f"Download error: {e}"
            logger.error(error_msg)
            return TikTokResult(
                status="error",
                context=error_msg,
                code=ErrorCode.DOWNLOAD_ERROR,
                data=TikTokData(url=url)
            )
            
        except Exception as e:
            error_msg = f"Unexpected download error: {e}"
            logger.error(error_msg)
            return TikTokResult(
                status="error",
                context=error_msg,
                code=ErrorCode.UNEXPECTED_ERROR,
                data=TikTokData(url=url),
            )
            
    def get_error_description(self, code: ErrorCode) -> str:
        """
        Get human-readable description for error code.
        
        Args:
            code: Error code enum value
            
        Returns:
            Description string
        """
        descriptions = {
            ErrorCode.SUCCESS: "Operation completed successfully",
            ErrorCode.INVALID_URL: "The provided TikTok URL is invalid or not supported",
            ErrorCode.EMPTY_URL: "Empty or invalid URL provided",
            ErrorCode.UNSUPPORTED_CONTENT_TYPE: "The TikTok content type is not supported",
            ErrorCode.URL_RESOLUTION_FAILED: "Failed to resolve shortened TikTok URL",
            ErrorCode.CONNECTION_ERROR: "Network connection error occurred",
            ErrorCode.DOWNLOAD_ERROR: "Media download failed",
            ErrorCode.EXTRACTOR_ERROR: "Media extraction failed",
            ErrorCode.PROXY_ERROR: "Proxy connection error",
            ErrorCode.NO_EXTRACTOR_FOUND: "No suitable extractor found for the URL",
            ErrorCode.NO_CONTENT_FOUND: "No content found for the URL",
            ErrorCode.METADATA_EXTRACTION_FAILED: "Failed to extract metadata",
            ErrorCode.VIDEO_EXTRACTION_FAILED: "Video content extraction failed",
            ErrorCode.PHOTO_EXTRACTION_FAILED: "Photo content extraction failed",
            ErrorCode.MUSIC_EXTRACTION_FAILED: "Music extraction failed",
            ErrorCode.NO_VIDEO_FORMATS_FOUND: "No supported video formats found",
            ErrorCode.NO_IMAGES_FOUND: "No images found in photo post",
            ErrorCode.NO_THUMBNAILS_FOUND: "No thumbnails found",
            ErrorCode.COOKIE_FILE_NOT_FOUND: "Cookie file not found",
            ErrorCode.OUTPUT_PATH_ERROR: "Output path error",
            ErrorCode.FILE_WRITE_ERROR: "File write error",
            ErrorCode.UNEXPECTED_ERROR: "An unexpected error occurred",
            ErrorCode.INITIALIZATION_ERROR: "Failed to initialize downloader",
            ErrorCode.EXTRACT_INFO_NOT_CALLED: "extract_info() must be called before download",
            ErrorCode.GALLERY_DL_ERROR: "gallery-dl internal error occurred",
            ErrorCode.YT_DLP_ERROR: "yt-dlp internal error occurred",
        }
        return descriptions.get(code, "Unknown error")
