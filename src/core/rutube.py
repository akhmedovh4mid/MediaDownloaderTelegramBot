"""
Rutube downloader module.

This module provides functionality to download media content from Rutube,
including videos and thumbnails.
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


# Setup logging
logger = logging.getLogger("rutube")


# ======= EnumsClasses =======
class ContentType(Enum):
    """Enum representing different Rutube content types."""
    LIVE = "live"
    VIDEO = "video"
    SHORTS = "shorts"
    ACCOUNT = "account"
    PLAYLIST = "playlist"
    

class ErrorCode(Enum):
    """Enum representing error codes for Rutube operations."""
    
    # Success
    SUCCESS = "SUCCESS"
    
    # Input validation errors (1xx)
    INVALID_URL = "INVALID_URL"
    EMPTY_URL = "EMPTY_URL"
    UNSUPPORTED_CONTENT_TYPE = "UNSUPPORTED_CONTENT_TYPE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    
    # Network errors (2xx)
    CONNECTION_ERROR = "CONNECTION_ERROR"
    DOWNLOAD_ERROR = "DOWNLOAD_ERROR"
    EXTRACTOR_ERROR = "EXTRACTOR_ERROR"
    PROXY_ERROR = "PROXY_ERROR"
    
    # Content errors (3xx)
    LIVE_STREAM_NOT_SUPPORTED = "LIVE_STREAM_NOT_SUPPORTED"
    PLAYLIST_NOT_SUPPORTED = "PLAYLIST_NOT_SUPPORTED"
    ACCOUNT_NOT_SUPPORTED = "ACCOUNT_NOT_SUPPORTED"
    NO_VIDEO_FORMATS_FOUND = "NO_VIDEO_FORMATS_FOUND"
    NO_THUMBNAILS_FOUND = "NO_THUMBNAILS_FOUND"
    
    # File system errors (4xx)
    COOKIE_FILE_NOT_FOUND = "COOKIE_FILE_NOT_FOUND"
    OUTPUT_PATH_ERROR = "OUTPUT_PATH_ERROR"
    FILE_WRITE_ERROR = "FILE_WRITE_ERROR"
    
    # System errors (5xx)
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
    EXTRACT_INFO_NOT_CALLED = "EXTRACT_INFO_NOT_CALLED"
    YT_DLP_ERROR = "YT_DLP_ERROR"
    

# ======= DataClasses =======
@dataclass
class RutubeData(AbstractServiceData):
    """Container for Rutube media data."""
    pass


@dataclass
class RutubeImage(AbstractServiceImage):
    """Represents a Rutube thumbnail image."""
    pass


@dataclass
class RutubeVideo(AbstractServiceVideo):
    """Represents a Rutube video format."""
    pass


@dataclass
class RutubeAudio(AbstractServiceAudio):
    """Represents a Rutube audio format."""
    pass


@dataclass
class RutubeResult(AbstractServiceResult):
    """Result of Rutube operations."""
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
class RutubeDownloader(AbstractServiceDownloader):
    """
    Rutube media downloader.
    
    Supports downloading videos and thumbnails from Rutube.
    Handles various content types including shorts and regular videos.
    """
    
    def __init__(
        self,
        retries_count: int = 10,
        proxy: Optional[str] = None,
        cookie_path: Optional[str] = None,
        concurrent_download_count: int = 2,
    ) -> None:
        """
        Initialize Rutube downloader.
        
        Args:
            retries_count: Number of retry attempts for downloads
            proxy: Proxy server URL (optional)
            cookie_path: Path to cookies file (optional)
            concurrent_download_count: Number of concurrent fragment downloads
        """
        logger.info("Initializing Rutube downloader")
        
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
                ContentType.LIVE,
                ContentType.ACCOUNT,
                ContentType.PLAYLIST,
            ]
            
            self._data: Optional[RutubeData] = None
            self._last_result: Optional[RutubeResult] = None
            
            logger.debug("Rutube downloader initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize Rutube downloader: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e
        
    def _classify_url(self, url: str) -> Optional[ContentType]:
        """
        Classify Rutube URL content type.
        
        Args:
            url: Rutube URL to classify
            
        Returns:
            ContentType or None if classification fails
        """
        logger.debug(f"Classifying URL: {url}")
        
        try:
            parsed = urlparse(url=url)
            path = parsed.path.lower()
            path_parts = path.strip("/").split("/")
            
            if len(path_parts) < 2:
                logger.warning(f"Invalid URL path: {path}")
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
                
            logger.debug(f"URL classified as: {result.value if result else 'unknown'}")
            return result
        
        except Exception as e:
            logger.error(f"URL classification error: {e}")
            return None
        
    def _validate_rutube_url(self, url: str) -> bool:
        """
        Validate Rutube URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid Rutube URL
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc.endswith("rutube.ru")
        except Exception as e:
            logger.debug(f"URL validation error: {e}")
            return False
        
    def extract_info(self, url: str) -> RutubeResult:
        """
        Extract media information from Rutube URL.
        
        Args:
            url: Rutube URL to extract information from
            
        Returns:
            RutubeResult: Result containing extracted media data
        """
        logger.info(f"Extracting info from URL: {url}")
        
        # Validate URL
        if not url or not isinstance(url, str):
            error_msg = "Invalid URL provided"
            logger.error(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.EMPTY_URL,
            )
            return self._last_result
        
        if not self._validate_rutube_url(url):
            error_msg = "Invalid or unsupported Rutube URL"
            logger.error(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.INVALID_URL,
            )
            return self._last_result
        
        ydl_opts = self.ydl_opts.copy()
        ydl_opts['listformats'] = True
        
        self._data = RutubeData(url=url) 
        
        # Classify content type
        content_type = self._classify_url(url=url)
        if not content_type:
            error_msg = "Could not classify URL content type"
            logger.error(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.UNSUPPORTED_CONTENT_TYPE,
            )
            return self._last_result
        
        if content_type in self.unsupported_types:
            error_msg = f"Unsupported content type: {content_type.value}"
            logger.warning(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.UNSUPPORTED_CONTENT_TYPE,
            )
            return self._last_result
           
        # Extract information using yt-dlp
        with YoutubeDL(params=ydl_opts) as ydl:
            try:
                logger.debug("Starting info extraction with yt-dlp")
                data = ydl.extract_info(url=url, download=False)
                logger.debug("Info extraction completed successfully")

            except ExtractorError as e:
                error_msg = f"Extraction error: {str(e)}"
                logger.error(error_msg)
                self._last_result = RutubeResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=ErrorCode.EXTRACTOR_ERROR,
                )
                return self._last_result
            
            except DownloadError as e:
                error_msg = f"Download error during extraction: {str(e)}"
                logger.error(error_msg)
                self._last_result = RutubeResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=ErrorCode.DOWNLOAD_ERROR,
                )
                return self._last_result

            except Exception as e:
                error_msg = f"Unexpected error during extraction: {str(e)}"
                logger.error(error_msg)
                self._last_result = RutubeResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=ErrorCode.UNEXPECTED_ERROR,
                )
                return self._last_result
                
        # Check for unsupported content types in extracted data
        if data.get("_type") == "playlist":
            error_msg = "Playlists are not supported"
            logger.warning(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.PLAYLIST_NOT_SUPPORTED,
            )
            return self._last_result
        
        if data.get("is_live") == True:
            error_msg = "Live streams are not supported"
            logger.warning(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.LIVE_STREAM_NOT_SUPPORTE,
            )
            return self._last_result
        
        if data.get("media_type") == "livestream":
            error_msg = "Livestreams are not supported"
            logger.warning(error_msg)
            self._last_result = RutubeResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.LIVE_STREAM_NOT_SUPPORTE,
            )
            return self._last_result

        # Populate data object
        self._data.is_video = True
        self._data.title = data.get("title")
        self._data.description = data.get("description")

        # Extract video formats
        video_count = 0
        for format in data.get("formats", []):
            if (
                format.get("ext") == "mp4" 
                and format.get("vcodec", "").startswith("avc1")
                and format.get("acodec", "").startswith("mp4a")
            ):
                self._data.videos.append(
                    RutubeVideo(
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
            self._last_result = RutubeResult(
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
                RutubeImage(
                    id=uuid4(),
                    url=thumbnail["url"],
                    name=thumbnail["id"],
                    width=thumbnail.get("width"),
                    height=thumbnail.get("height"),
                )
            )
            thumbnail_count += 1
            
        if thumbnail_count == 0:
            logger.warning("No thumbnails found for the video")
        
        logger.info(f"Extracted {video_count} video formats, {thumbnail_count} thumbnails")
        
        self._last_result = RutubeResult(data=self._data)
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
        hash_input = f"rutube_{url}_{video_format_id}"
        file_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return file_hash

    def download_media(
        self,
        url: str,
        video_format_id: str,
        output_path: str = "./downloads/rutube/"
    ) -> RutubeResult:
        """
        Download media using previously extracted information.
        
        Args:
            url: URL of the Rutube video to download
            video_format_id: ID of the video format to download
            output_path: Directory path for saving the downloaded file
            
        Returns:
            RutubeResult: Result of the download operation
            
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
            "format": f"{video_format_id}+bestaudio[ext=m4a]",
            "merge_output_format": "mp4",
        })
        
        try:
            logger.debug(f"Downloading to: {file_path}")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            logger.info(f"Download completed successfully: {file_path}")
            return RutubeResult(data=RutubeData(url=url, path=file_path, is_video=True))
        
        except DownloadError as e:
            error_msg = f"Download error: {e}"
            logger.error(error_msg)
            return RutubeResult(
                status="error",
                context=error_msg,
                code=ErrorCode.DOWNLOAD_ERROR,
                data=RutubeData(url=url)
            )
            
        except Exception as e:
            error_msg = f"Unexpected download error: {e}"
            logger.error(error_msg)
            return RutubeResult(
                status="error",
                context=error_msg,
                code=ErrorCode.UNEXPECTED_ERROR,
                data=RutubeData(url=url)
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
            ErrorCode.INVALID_URL: "The provided Rutube URL is invalid or not supported",
            ErrorCode.EMPTY_URL: "Empty or invalid URL provided",
            ErrorCode.UNSUPPORTED_CONTENT_TYPE: "The Rutube content type is not supported",
            ErrorCode.UNSUPPORTED_MEDIA_TYPE: "The media type is not supported",
            ErrorCode.CONNECTION_ERROR: "Network connection error occurred",
            ErrorCode.DOWNLOAD_ERROR: "Media download failed",
            ErrorCode.EXTRACTOR_ERROR: "Media extraction failed",
            ErrorCode.PROXY_ERROR: "Proxy connection error",
            ErrorCode.LIVE_STREAM_NOT_SUPPORTED: "Live streams are not supported",
            ErrorCode.PLAYLIST_NOT_SUPPORTED: "Playlists are not supported",
            ErrorCode.ACCOUNT_NOT_SUPPORTED: "Account/channel content is not supported",
            ErrorCode.NO_VIDEO_FORMATS_FOUND: "No supported video formats found",
            ErrorCode.NO_THUMBNAILS_FOUND: "No thumbnails found",
            ErrorCode.COOKIE_FILE_NOT_FOUND: "Cookie file not found",
            ErrorCode.OUTPUT_PATH_ERROR: "Output path error",
            ErrorCode.FILE_WRITE_ERROR: "File write error",
            ErrorCode.UNEXPECTED_ERROR: "An unexpected error occurred",
            ErrorCode.INITIALIZATION_ERROR: "Failed to initialize downloader",
            ErrorCode.EXTRACT_INFO_NOT_CALLED: "extract_info() must be called before download",
            ErrorCode.YT_DLP_ERROR: "yt-dlp internal error occurred",
        }
        return descriptions.get(code, "Unknown error")

        
