"""
Reddit downloader module.

This module provides functionality to download media content from Reddit,
including image galleries, video posts, and single images.
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


# Setup logging
logger = logging.getLogger("reddit")


# ======= EnumsClasses =======
class ContentType(Enum):
        """Enum representing different Reddit content types."""
        VIDEO = "video"
        IMAGE = "image"
        GALLERY = "gallery"
        UNSUPPORTED = "unsupported"
        

class RedditErrorCode(Enum):
    """Enum representing error codes for Reddit operations."""
    
    # Success
    SUCCESS = "SUCCESS"
    
    # Input validation errors (1xx)
    INVALID_URL = "INVALID_URL"
    EMPTY_URL = "EMPTY_URL"
    UNSUPPORTED_CONTENT = "UNSUPPORTED_CONTENT"
    
    # Authentication/API errors (2xx)
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    API_ERROR = "API_ERROR"
    RATELIMIT_EXCEEDED = "RATELIMIT_EXCEEDED"
    
    # Network errors (3xx)
    CONNECTION_ERROR = "CONNECTION_ERROR"
    DOWNLOAD_ERROR = "DOWNLOAD_ERROR"
    EXTRACTOR_ERROR = "EXTRACTOR_ERROR"
    PROXY_ERROR = "PROXY_ERROR"
    
    # Content errors (4xx)
    GALLERY_DATA_MISSING = "GALLERY_DATA_MISSING"
    GALLERY_EMPTY = "GALLERY_EMPTY"
    VIDEO_EXTRACTION_FAILED = "VIDEO_EXTRACTION_FAILED"
    IMAGE_EXTRACTION_FAILED = "IMAGE_EXTRACTION_FAILED"
    MEDIA_METADATA_MISSING = "MEDIA_METADATA_MISSING"
    PREVIEW_DATA_MISSING = "PREVIEW_DATA_MISSING"
    
    # File system errors (5xx)
    COOKIE_FILE_NOT_FOUND = "COOKIE_FILE_NOT_FOUND"
    OUTPUT_PATH_ERROR = "OUTPUT_PATH_ERROR"
    FILE_WRITE_ERROR = "FILE_WRITE_ERROR"
    
    # System errors (6xx)
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
    EXTRACT_INFO_NOT_CALLED = "EXTRACT_INFO_NOT_CALLED"


# ======= DataClasses =======
@dataclass
class RedditData(AbstractServiceData):
    """Container for Reddit media data."""
    pass


@dataclass
class RedditImage(AbstractServiceImage):
    """Represents a Reddit image."""
    pass


@dataclass
class RedditVideo(AbstractServiceVideo):
    """Represents a Reddit video format."""
    pass


@dataclass
class RedditAudio(AbstractServiceAudio):
    """Represents a Reddit audio format."""
    pass


@dataclass
class RedditResult(AbstractServiceResult):
    """Result of Reddit operations."""
    code: RedditErrorCode = field(default=RedditErrorCode.SUCCESS)


# ======= ExceptionClasses =======
class ExtractInfoNotCalledError(Exception):
    """Exception raised when download is attempted before extract_info."""
    def __init__(self, message: str, code: RedditErrorCode = RedditErrorCode.EXTRACT_INFO_NOT_CALLED):
        super().__init__(message)
        self.code = code
        self.message = message


class CookieFileNotFoundError(FileNotFoundError):
    """Exception raised when cookie file is not found."""
    def __init__(self, message: str, code: RedditErrorCode = RedditErrorCode.COOKIE_FILE_NOT_FOUND):
        super().__init__(message)
        self.code = code
        self.message = message



class InvalidRedditUrlError(ValueError):
    """Exception raised for invalid Reddit URLs."""
    def __init__(self, message: str, code: RedditErrorCode = RedditErrorCode.INVALID_URL):
        super().__init__(message)
        self.code = code
        self.message = message


class UnsupportedContentTypeError(Exception):
    """Exception raised for unsupported content types."""
    def __init__(self, message: str, code: RedditErrorCode = RedditErrorCode.UNSUPPORTED_CONTENT):
        super().__init__(message)
        self.code = code
        self.message = message


# ======= MainClass =======
class RedditDownloader(AbstractServiceDownloader):
    """
    Reddit media downloader.
    
    Supports downloading:
    - Image galleries
    - Video posts
    - Single images
    """
    
    # Supported Reddit domains
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
        Initialize Reddit downloader.
        
        Args:
            client_id: Reddit API client ID
            client_secret: Reddit API client secret
            retries_count: Number of retry attempts for downloads
            proxy: Proxy server URL (optional)
            cookie_path: Path to cookies file (optional)
            concurrent_download_count: Number of concurrent fragment downloads
            user_agent: User agent string for requests
        """
        logger.info("Initializing Reddit downloader")
        
        self.proxy = proxy
        self.cookies_path = Path(cookie_path) if cookie_path else None

        # Validate cookie file
        if self.cookies_path and not self.cookies_path.exists():
            error_msg = f"Cookie file not found: {self.cookies_path}"
            logger.error(error_msg)
            raise CookieFileNotFoundError(error_msg, RedditErrorCode.COOKIE_FILE_NOT_FOUND)

        try:
            # Initialize Reddit client
            self.reddit = Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
            
            # Configure yt-dlp options
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
            
            logger.debug("Reddit downloader initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize Reddit downloader: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e
        
    def _validate_reddit_url(self, url: str) -> bool:
        """
        Validate Reddit URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid Reddit URL
        """
        try:
            parsed = urlparse(url)
            return any(domain in parsed.netloc for domain in self.SUPPORTED_DOMAINS)
        except Exception as e:
            logger.debug(f"URL validation error: {e}")
            return False
    
    def _classify_content_type(self, submission: Submission) -> ContentType:
        """
        Classify Reddit submission content type.
        
        Args:
            submission: Reddit submission object
            
        Returns:
            ContentType: The classified content type
        """
        logger.debug("Classifying content type")
        
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
        else:
            result = ContentType.UNSUPPORTED
        
        logger.debug(f"Content classified as: {result.value}")
        return result
        
    def _extract_gallery(self, submission: Submission) -> None:
        """Extract data from image gallery."""
        logger.info(f"Extracting gallery from post: {submission.id}")

        if not (hasattr(submission, "gallery_data") and submission.gallery_data):
            error_msg = "No gallery data found"
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
                error_msg = "Gallery data is empty"
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
                logger.info(f"Successfully extracted {image_count} images from gallery")
            else:
                error_msg = "No valid images found in gallery"
                logger.error(error_msg)
                self._last_result = RedditResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=RedditErrorCode.MEDIA_METADATA_MISSING,
                )
                
        except Exception as e:
            error_msg = f"Gallery extraction failed: {str(e)}"
            logger.error(error_msg)
            self._last_result = RedditResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RedditErrorCode.UNEXPECTED_ERROR,
            )
        
    def _get_extension(self, url: str) -> Tuple[str, str]:
        """
        Extract filename and extension from URL.
        
        Args:
            url: URL to extract from
            
        Returns:
            Tuple of (name, extension)
        """
        parsed = urlparse(url=url)
        filename = os.path.basename(parsed.path)
        name, ext = os.path.splitext(filename)
        return (name, ext.replace(".", "").lower())
    
    def _extract_image_from_preview(self, submission: Submission) -> bool:
        """Extract image from post preview data."""
        if not (hasattr(submission, "preview") and submission.preview):
            return False
        
        name, ext = self._get_extension(url=submission.url)
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
        """Add images from preview data."""
        # Additional resolutions
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
            
        # Main image (highest quality)
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
        """Extract data from single image post."""
        logger.info(f"Extracting image from post: {submission.id}")
        
        try:
            if self._extract_image_from_preview(submission=submission):
                self._last_result = RedditResult(data=self._data)
                logger.info(f"Successfully extracted {len(self._data.images)} image variants from preview")
                return
            
            # Fallback: use direct URL if preview is unavailable
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
            logger.info("Used direct image URL as fallback")
            
        except Exception as e:
            error_msg = f"Image extraction failed: {str(e)}"
            logger.error(error_msg)
            self._last_result = RedditResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RedditErrorCode.IMAGE_EXTRACTION_FAILED,
            )
        
    def _extract_video(self, submission: Submission) -> None:
        """Extract data from video post."""
        logger.info(f"Extracting video from post: {submission.id}")
        
        ydl_opts = self.ydl_opts.copy()
        ydl_opts['listformats'] = True

        try:
            with YoutubeDL(params=ydl_opts) as ydl:
                data = ydl.extract_info(url=submission.url, download=False)
                logger.debug("Video info extraction completed")
                
        except ExtractorError as e:
            error_msg = f"Video extractor error: {str(e)}"
            logger.error(error_msg)
            self._last_result = RedditResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RedditErrorCode.EXTRACTOR_ERROR,
            )
            return
        
        except DownloadError as e:
            error_msg = f"Video download error: {str(e)}"
            logger.error(error_msg)
            self._last_result = RedditResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RedditErrorCode.DOWNLOAD_ERROR,
            )
            return
    
        except Exception as e:
            error_msg = f"Unexpected error during video extraction: {str(e)}"
            logger.error(error_msg)
            self._last_result = RedditResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=RedditErrorCode.UNEXPECTED_ERROR,
            )
            return
        
        # Populate metadata
        self._data.title = data.get("title")
        self._data.description = data.get("fulltitle")
        
        # Extract available formats
        self._extract_media_formats(data)
        self._extract_thumbnails(data)
        
        self._last_result = RedditResult(data=self._data)
        logger.info(f"Successfully extracted video with {len(self._data.videos)} video formats and {len(self._data.audios)} audio formats")
        
    def _extract_media_formats(self, data: dict) -> None:
        """Extract available video and audio formats."""
        video_count = 0
        audio_count = 0
        
        for format in data.get("formats", []):
            if (format["ext"] == "mp4" and 
                format.get("acodec") == "none" and
                format.get("vcodec", "").startswith("avc1") and
                format.get("format_id", "").startswith("hls")):
                
                # Video formats (without audio)
                self._data.videos.append(
                    RedditVideo(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        fps=format.get("fps"),
                        width=format.get("width"),
                        height=format.get("height"),
                        duration=data.get("duration"),
                        total_bitrate=format.get("tbr"),
                        caption=format.get("format_note"),
                    )
                )
                video_count += 1
                
            # Audio formats
            elif (format["ext"] == "m4a" and 
                  format.get("vcodec") == "none" and
                  format.get("acodec", "").startswith("mp4a")):
                
                self._data.audios.append(
                    RedditAudio(
                        id=uuid4(),
                        url=format["url"],
                        name=format["format_id"],
                        duration=data.get("duration"),
                        total_bitrate=format.get("tbr"),
                        caption=format.get("format_note"),
                    )
                )
                audio_count += 1
                
        logger.debug(f"Extracted {video_count} video formats and {audio_count} audio formats")
                  
    def _extract_thumbnails(self, data: dict) -> None:
        """Extract thumbnails."""
        thumbnail_count = 0
        for idx, thumbnail in enumerate(data.get("thumbnails", [])):
            self._data.thumbnails.append(
                RedditImage(
                    id=uuid4(),
                    url=thumbnail["url"],
                    name=f"thumbnail_{idx}",
                    width=thumbnail.get("width"),
                    height=thumbnail.get("height"),
                )
            )
            thumbnail_count += 1
            
        logger.debug(f"Extracted {thumbnail_count} thumbnails")
            
    def _generate_safe_filename(self, url: str, video_format_id: str) -> str:
        """
        Generate safe filename based on URL hash.
        
        Args:
            url: Content URL
            video_format_id: Video format ID
            
        Returns:
            Safe filename string
        """
        hash_input = f"reddit_{url}_{video_format_id}"
        file_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return file_hash
    
    def extract_info(self, url: str) -> RedditResult:
        """
        Extract media information from Reddit URL.
        
        Args:
            url: Reddit URL to extract information from
            
        Returns:
            RedditResult: Result containing extracted media data
        """
        logger.info(f"Extracting info from URL: {url}")
        
        if not url or not isinstance(url, str):
            error_msg = "Invalid URL provided"
            logger.error(error_msg)
            return RedditResult(
                status="error",
                context=error_msg,
                data=RedditData(url=url),
                code=RedditErrorCode.EMPTY_URL,
            )
            
        if not self._validate_reddit_url(url):
            error_msg = "Invalid or unsupported Reddit URL"
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

            self._data.title = getattr(submission, "title", None)
            self._data.description = getattr(submission, "selftext", None)
            
            # Classify content type and process accordingly
            content_type = self._classify_content_type(submission)
            
            logger.info(f"Detected content type: {content_type.value}")
            
            if content_type == ContentType.GALLERY:
                self._data.is_image = True
                self._extract_gallery(submission=submission)
            elif content_type == ContentType.VIDEO:
                self._data.is_video = True
                self._extract_video(submission=submission)
            elif content_type == ContentType.IMAGE:
                self._data.is_image = True
                self._extract_image(submission=submission)
            else:
                error_msg = f"Unsupported content type: {content_type.value}"
                logger.error(error_msg)
                self._last_result = RedditResult(
                    status="error",
                    data=self._data,
                    context=error_msg,
                    code=RedditErrorCode.UNSUPPORTED_CONTENT,
                )
                
            return self._last_result
        
        except Exception as e:
            error_msg = f"Extraction failed: {str(e)}"
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
        Download media using previously extracted information.
        
        Args:
            url: URL of the Rutube video to download
            video_format_id: ID of the video format to download
            output_path: Directory path for saving the downloaded file
            
        Returns:
            RedditResult: Result of the download operation
            
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
            video_format_id=video_format_id,
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
            logger.info(f"Starting download to: {file_path}")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            logger.info("Download completed successfully")
            return RedditResult(data=RedditData(url=url, path=file_path, is_video=True))

        except DownloadError as e:
            error_msg = f"Download error: {e}"
            logger.error(error_msg)
            return RedditResult(
                status="error",
                context=error_msg,
                code=RedditErrorCode.DOWNLOAD_ERROR,
                data=RedditData(url=url)
            )
        except Exception as e:
            error_msg = f"Unexpected download error: {e}"
            logger.error(error_msg)
            return RedditResult(
                status="error",
                context=error_msg,
                code=RedditErrorCode.UNEXPECTED_ERROR,
                data=RedditData(url=url)
            )

    def get_error_description(self, code: RedditErrorCode) -> str:
        """
        Get human-readable description for error code.
        
        Args:
            code: Error code enum value
            
        Returns:
            Description string
        """
        descriptions = {
            RedditErrorCode.SUCCESS: "Operation completed successfully",
            RedditErrorCode.INVALID_URL: "The provided Reddit URL is invalid or not supported",
            RedditErrorCode.EMPTY_URL: "Empty or invalid URL provided",
            RedditErrorCode.UNSUPPORTED_CONTENT: "The Reddit content type is not supported",
            RedditErrorCode.AUTHENTICATION_FAILED: "Reddit API authentication failed",
            RedditErrorCode.API_ERROR: "Reddit API returned an error",
            RedditErrorCode.RATELIMIT_EXCEEDED: "Reddit API rate limit exceeded",
            RedditErrorCode.CONNECTION_ERROR: "Network connection error occurred",
            RedditErrorCode.DOWNLOAD_ERROR: "Media download failed",
            RedditErrorCode.EXTRACTOR_ERROR: "Media extraction failed",
            RedditErrorCode.PROXY_ERROR: "Proxy connection error",
            RedditErrorCode.GALLERY_DATA_MISSING: "Gallery data not found in post",
            RedditErrorCode.GALLERY_EMPTY: "Gallery contains no items",
            RedditErrorCode.VIDEO_EXTRACTION_FAILED: "Video content extraction failed",
            RedditErrorCode.IMAGE_EXTRACTION_FAILED: "Image content extraction failed",
            RedditErrorCode.MEDIA_METADATA_MISSING: "Media metadata not available",
            RedditErrorCode.PREVIEW_DATA_MISSING: "Preview data not available",
            RedditErrorCode.COOKIE_FILE_NOT_FOUND: "Cookie file not found",
            RedditErrorCode.OUTPUT_PATH_ERROR: "Output path error",
            RedditErrorCode.FILE_WRITE_ERROR: "File write error",
            RedditErrorCode.UNEXPECTED_ERROR: "An unexpected error occurred",
            RedditErrorCode.INITIALIZATION_ERROR: "Failed to initialize downloader",
            RedditErrorCode.EXTRACT_INFO_NOT_CALLED: "extract_info() must be called before download",
        }
        return descriptions.get(code, "Unknown error")
