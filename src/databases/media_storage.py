import logging
import hashlib
from typing import Any, Dict, Optional

from .redis_base import RedisBase

# Create logger for this module
logger = logging.getLogger(__name__)


class MediaCacheStorage(RedisBase):
    """
    Redis storage for media data cache.
    
    Stores media information with URL-based keys and automatic expiration.
    Used to cache media metadata to avoid repeated API calls.
    """
    
    def __init__(self, host: str, port: int, db: int, ttl: int = 86400):
        """
        Initialize media cache storage.
        
        Args:
            host: Redis server hostname
            port: Redis server port
            db: Redis database number
            ttl: Time-to-live for cache entries in seconds (default: 86400 = 24 hours)
        """
        super().__init__(host=host, port=port, db=db)
        self.ttl = ttl
        logger.info("MediaCacheStorage initialized: host=%s, port=%s, db=%s, ttl=%ss", host, port, db, ttl)
    
    def _get_url_hash(self, url: str) -> str:
        """
        Generate MD5 hash of URL for use as cache key.
        
        Args:
            url: Media URL
            
        Returns:
            MD5 hash string of the URL
        """
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_cache_key(self, url: str) -> str:
        """
        Generate Redis key for media cache.
        
        Args:
            url: Media URL
            
        Returns:
            Redis key string in format 'media_cache:{url_hash}'
        """
        url_hash = self._get_url_hash(url=url)
        return f"media_cache:{url_hash}"
    
    def store_media(self, url: str, media_data: Dict[str, Any]) -> bool:
        """
        Store media data in cache with TTL expiration.
        
        Args:
            url: Media URL
            media_data: Media information dictionary
            
        Returns:
            True if data stored successfully, False otherwise
        """
        try:
            key = self._get_cache_key(url=url)
            
            cache_data = {
                "url": url,
                "data": media_data,
            }
            
            result = self.redis_client.setex(
                name=key,
                time=self.ttl,
                value=self._serialize(data=cache_data)
            )
            
            if result:
                logger.info("Media cached for url=%s, ttl=%ss", url, self.ttl)
            else:
                logger.warning("Failed to cache media for url=%s", url)
                
            return result
            
        except Exception as e:
            logger.error("Error storing media cache for url=%s: %s", url, e)
            return False
    
    def get_media(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve media data from cache and refresh TTL.
        
        Args:
            url: Media URL
            
        Returns:
            Cached media data dictionary or None if not found
        """
        try:
            key = self._get_cache_key(url=url)
            data = self.redis_client.get(name=key)
            
            if data:
                cache_data = self._deserialize(data=data)
                
                self.redis_client.setex(
                    name=key,
                    time=self.ttl,
                    value=self._serialize(data=cache_data)
                )
                
                logger.debug("Media cache retrieved for url=%s, TTL refreshed", url)
                return cache_data
                
            logger.debug("Media cache not found for url=%s", url)
            return None
            
        except Exception as e:
            logger.error("Error getting media cache for url=%s: %s", url, e)
            return None
