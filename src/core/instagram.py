"""
Instagram downloader module.

This module provides functionality to download media content from Instagram,
including images, videos, and carousel posts.
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


# Setup logging
logger = logging.getLogger("instagram")


# ======= EnumsClasses =======
class ContentType(Enum):
    """Enum representing different Instagram content types."""
    VIDEO = "GraphVideo"
    IMAGE = "GraphImage"
    SIDECAR = "GraphSidecar"
    
    
class ErrorCode(Enum):
    """Enum representing error codes for Instagram operations."""
    
    # Success
    SUCCESS = "SUCCESS"
    
    # Input validation errors (1xx)
    INVALID_URL = "INVALID_URL"
    INVALID_SHORTCODE = "INVALID_SHORTCODE"
    EMPTY_URL = "EMPTY_URL"
    
    # Authentication errors (2xx)
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    SESSION_LOAD_FAILED = "SESSION_LOAD_FAILED"
    SESSION_SAVE_FAILED = "SESSION_SAVE_FAILED"
    
    # Network errors (3xx)
    CONNECTION_ERROR = "CONNECTION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    BAD_RESPONSE = "BAD_RESPONSE"
    
    # Content errors (4xx)
    POST_NOT_FOUND = "POST_NOT_FOUND"
    POST_CHANGED = "POST_CHANGED"
    PROFILE_NOT_EXISTS = "PROFILE_NOT_EXISTS"
    CONTENT_NOT_SUPPORTED = "CONTENT_NOT_SUPPORTED"
    EXTRACTION_ERROR = "EXTRACTION_ERROR"
    
    # System errors (5xx)
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
    DOWNLOAD_ERROR = "DOWNLOAD_ERROR"
    

# ======= DataClasses =======
@dataclass
class InstagramData(AbstractServiceData):
    """Container for Instagram media data."""
    pass


@dataclass
class InstagramImage(AbstractServiceImage):
    """Represents an Instagram image."""
    pass


@dataclass
class InstagramVideo(AbstractServiceVideo):
    """Represents an Instagram video."""
    pass


@dataclass
class InstagramAudio(AbstractServiceAudio):
    """Represents Instagram audio (for stories and reels)."""
    pass



@dataclass
class InstagramResult(AbstractServiceResult):
    """Result of Instagram operations."""
    code: ErrorCode = field(default=ErrorCode.SUCCESS)


# ======= ExceptionClasses =======
class InstagramSessionError(Exception):
    """Exception raised for Instagram session errors."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.AUTHENTICATION_FAILED):
        super().__init__(message)
        self.code = code
        self.message = message


class InvalidInstagramUrlError(ValueError):
    """Exception raised for invalid Instagram URLs."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.INVALID_URL):
        super().__init__(message)
        self.code = code
        self.message = message


class InstagramPostNotFoundError(Exception):
    """Exception raised when post is not found."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.POST_NOT_FOUND):
        super().__init__(message)
        self.code = code
        self.message = message


class ExtractInfoNotCalledError(Exception):
    """Exception raised when download is attempted before extract_info."""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.EXTRACTION_ERROR):
        super().__init__(message)
        self.code = code
        self.message = message

    
# ======= MainClass =======
class InstagramDownloader(AbstractServiceDownloader):
    """
    Instagram media downloader.
    
    Supports downloading:
    - Single images
    - Video posts
    - Carousel albums
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
        Initialize Instagram downloader.
        
        Args:
            username: Instagram username
            password: Instagram password
            timeout: Request timeout in seconds
            max_retries: Maximum number of connection retries
            cookie_path: Path for storing cookies and session
        """
        logger.info("Initializing Instagram downloader")
        
        self.timeout = timeout
        self.username = username
        self.password = password
        self.max_retries = max_retries
        
        # Initialize Instaloader
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
        """Initialize and authenticate with Instagram."""
        try:
            if self.session_file.exists():
                logger.info(f"Loading session from: {self.session_file}")
                self.loader.load_session_from_file(
                    username=self.username,
                    filename=str(self.session_file)
                )
                logger.info("Session loaded successfully")
            else:
                logger.info("Creating new session...")
                self.cookie_path.mkdir(parents=True, exist_ok=True)
                self.loader.login(user=self.username, passwd=self.password)
                self.loader.save_session_to_file(filename=str(self.session_file))
                logger.info("Session created and saved successfully")
                
        except ConnectionException as e:
            error_msg = f"Connection error during login: {e}"
            logger.error(error_msg)
            raise InstagramSessionError(error_msg, ErrorCode.CONNECTION_ERROR)
        
        except QueryReturnedBadRequestException as e:
            error_msg = f"Authentication failed: {e}"
            logger.error(error_msg)
            raise InstagramSessionError(error_msg, ErrorCode.AUTHENTICATION_FAILED)
        
        except Exception as e:
            error_msg = f"Unexpected error during initialization: {e}"
            logger.error(error_msg)
            raise InstagramSessionError(error_msg, ErrorCode.INITIALIZATION_ERROR)
        
    def _validate_instagram_url(self, url: str) -> bool:
        """
        Validate Instagram URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid Instagram URL
        """
        try:
            parsed_url = urlparse(url=url)
            return parsed_url.netloc.endswith("instagram.com")
        except Exception as e:
            logger.debug(f"URL validation error: {e}")
            return False

    def _get_shortcode(self, url: str) -> Optional[str]:
        """
        Extract shortcode from Instagram URL.
        
        Args:
            url: Instagram URL
            
        Returns:
            Shortcode string or None if extraction fails
        """
        try:
            parsed_url = urlparse(url=url)
            path_parts = parsed_url.path.strip("/").split("/")
            
            if (len(path_parts) >= 2 and 
                path_parts[0] in ["p", "tv", "reel", "reels"]):
                shortcode = path_parts[1]
                logger.debug(f"Extracted shortcode: {shortcode}")
                return shortcode
            
            if len(path_parts) == 1 and len(path_parts[0]) == 11:
                shortcode = path_parts[0]
                logger.debug(f"Extracted shortcode: {shortcode}")
                return shortcode
                
            logger.warning(f"Could not extract shortcode from URL: {url}")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting shortcode from URL {url}: {e}")
            return None
        
    def _extract_media_info(self, post: Post) -> None:
        """Extract media information from Instagram post."""
        logger.debug("Extracting media info from post")
        
        data = post._node
        if data is None:
            error_msg = "Post data not found"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.EXTRACTION_ERROR,
            )
            return
        
        # Extract caption
        caption = data.get("accessibility_caption")
        if caption and caption != "None":
            self._data.title = caption
            
        content_type = data["__typename"]
        logger.debug(f"Content type: {content_type}")
        
        # Handle different content types
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
            error_msg = f"Unsupported content type: {content_type}"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                data=self._data,
                context=error_msg,
                code=ErrorCode.CONTENT_NOT_SUPPORTED,
            )
    
    def _extract_video_content(self, data: dict) -> None:
        """Extract video content information."""
        logger.debug("Extracting video content")
        
        # Add video
        self._data.videos.append(
            InstagramVideo(
                id=uuid4(),
                url=data["video_url"],
                name=f"{ContentType.VIDEO.value}_{data['shortcode']}",
                width=data["dimensions"]["width"],
                height=data["dimensions"]["height"],
                duration=data["video_duration"],
            )
        )
        
        # Add thumbnails
        thumbnail_count = 0
        for image in data.get("display_resources", []):
            self._data.thumbnails.append(
                InstagramImage(
                    id=uuid4(),
                    url=image["src"],
                    name=f"{ContentType.IMAGE.value}_{image['config_width']}x{image['config_height']}",
                    width=image.get("config_width"),
                    height=image.get("config_height"),
                )
            )
            thumbnail_count += 1
            
        logger.debug(f"Extracted 1 video and {thumbnail_count} thumbnails")
        self._last_result = InstagramResult(data=self._data)
    
    def _extract_image_content(self, data: dict) -> None:
        """Extract image content information."""
        logger.debug("Extracting image content")
        
        image_count = 0
        for image in data.get("display_resources", []):
            self._data.images.append(
                InstagramImage(
                    id=uuid4(),
                    url=image["src"],
                    name=f"{ContentType.IMAGE.value}_{image['config_width']}x{image['config_height']}",
                    width=image.get("config_width"),
                    height=image.get("config_height"),
                )
            )
            image_count += 1
            
        logger.debug(f"Extracted {image_count} images")
        self._last_result = InstagramResult(data=self._data)
    
    def _extract_sidecar_content(self, data: dict) -> None:
        """Extract sidecar (carousel) content information."""
        logger.debug("Extracting sidecar content")
        
        image_count = 0
        video_count = 0
        
        for idx, media_item in enumerate(data["edge_sidecar_to_children"]["edges"]):
            media_item_node = media_item["node"]
            media_content_type = media_item_node["__typename"]
            
            if media_content_type.endswith(ContentType.IMAGE.value):
                for image in media_item_node.get("display_resources", []):
                    self._data.images.append(
                        InstagramImage(
                            id=uuid4(),
                            url=image["src"],
                            name=f"{ContentType.IMAGE.value}_{image['config_width']}x{image['config_height']}_{idx}",
                            width=image["config_width"],
                            height=image["config_height"],
                        )
                    )
                    image_count += 1
                    
            elif media_content_type.endswith(ContentType.VIDEO.value):
                self._data.videos.append(
                    InstagramVideo(
                        id=uuid4(),
                        url=media_item_node["video_url"],
                        name=f"{ContentType.VIDEO.value}_{media_item_node['shortcode']}",
                        width=media_item_node["dimensions"]["width"],
                        height=media_item_node["dimensions"]["height"],
                        duration=media_item_node["video_duration"],
                    )
                )
                video_count += 1
                    
        logger.debug(f"Extracted {image_count} images and {video_count} videos from sidecar")
        self._last_result = InstagramResult(data=self._data)
    
    def extract_info(self, url: str) -> InstagramResult:
        """
        Extract media information from Instagram URL.
        
        Args:
            url: Instagram URL to extract information from
            
        Returns:
            InstagramResult: Result containing extracted media data
        """
        logger.info(f"Extracting info from URL: {url}")
        
        # Validate URL
        if not url or not isinstance(url, str):
            error_msg = "Invalid URL provided"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                code=ErrorCode.EMPTY_URL,
                data=InstagramData(url=url),
            )
            return self._last_result
        
        if not self._validate_instagram_url(url):
            error_msg = "Invalid or unsupported Instagram URL"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                code=ErrorCode.INVALID_URL,
                data=InstagramData(url=url),
            )
            return self._last_result
        
        # Extract shortcode
        shortcode = self._get_shortcode(url)
        if not shortcode:
            error_msg = "Could not extract shortcode from URL"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                data=InstagramData(url=url),
                code=ErrorCode.INVALID_SHORTCODE,
            )
            return self._last_result
        
        try:
            logger.info(f"Extracting info for shortcode: {shortcode}")
            
            # Load post
            post = Post.from_shortcode(self.loader.context, shortcode)
            
            # Initialize data
            self._data = InstagramData(url=url)
            
            # Extract media information
            self._extract_media_info(post)
            
            if self._last_result and self._last_result.status != "error":
                logger.info(f"Successfully extracted info: {len(self._data.images)} images, "
                           f"{len(self._data.videos)} videos")
            else:
                logger.warning("Info extraction completed with errors")
            
            return self._last_result
            
        except PostChangedException as e:
            error_msg = f"Post has changed or is not available: {e}"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                code=ErrorCode.POST_CHANGED,
                data=InstagramData(url=url),
            )
            return self._last_result
        
        except ProfileNotExistsException as e:
            error_msg = f"Profile not found: {e}"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                data=InstagramData(url=url),
                code=ErrorCode.PROFILE_NOT_EXISTS,
            )
            return self._last_result
        
        except ConnectionException as e:
            error_msg = f"Connection error: {e}"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                data=InstagramData(url=url),
                code=ErrorCode.CONNECTION_ERROR,
            )
            return self._last_result
        
        except BadResponseException as e:
            error_msg = f"Bad API response: {e}"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                code=ErrorCode.BAD_RESPONSE,
                data=InstagramData(url=url),
            )
            return self._last_result
            
        except Exception as e:
            error_msg = f"Unexpected error during extraction: {e}"
            logger.error(error_msg)
            self._last_result = InstagramResult(
                status="error",
                context=error_msg,
                data=InstagramData(url=url),
                code=ErrorCode.UNEXPECTED_ERROR,
            )
            return self._last_result

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
            ErrorCode.INVALID_URL: "The provided URL is invalid or not supported",
            ErrorCode.INVALID_SHORTCODE: "Could not extract shortcode from URL",
            ErrorCode.EMPTY_URL: "Empty or invalid URL provided",
            ErrorCode.AUTHENTICATION_FAILED: "Instagram authentication failed",
            ErrorCode.SESSION_LOAD_FAILED: "Failed to load session from file",
            ErrorCode.SESSION_SAVE_FAILED: "Failed to save session to file",
            ErrorCode.CONNECTION_ERROR: "Network connection error occurred",
            ErrorCode.TIMEOUT_ERROR: "Request timeout exceeded",
            ErrorCode.BAD_RESPONSE: "Received bad response from Instagram API",
            ErrorCode.POST_NOT_FOUND: "The requested post was not found",
            ErrorCode.POST_CHANGED: "The post has changed or is no longer available",
            ErrorCode.PROFILE_NOT_EXISTS: "The requested profile does not exist",
            ErrorCode.CONTENT_NOT_SUPPORTED: "The content type is not supported",
            ErrorCode.EXTRACTION_ERROR: "Error occurred during content extraction",
            ErrorCode.UNEXPECTED_ERROR: "An unexpected error occurred",
            ErrorCode.INITIALIZATION_ERROR: "Failed to initialize downloader",
            ErrorCode.DOWNLOAD_ERROR: "Error occurred during download",
        }
        return descriptions.get(code, "Unknown error")
