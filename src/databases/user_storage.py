import logging
from typing import Any, Dict, Optional

from .redis_base import RedisBase

# Create logger for this module
logger = logging.getLogger(__name__)


class UserSessionStorage(RedisBase):
    """
    Redis-based storage for user sessions with configurable TTL.
    
    Provides methods to create, retrieve, and manage user sessions
    with automatic expiration. Each session stores media information
    and service data for quick access.
    """
    
    def __init__(self, host: str, port: int, db: int, ttl: int = 7200):
        """
        Initialize user session storage.
        
        Args:
            host: Redis server hostname
            port: Redis server port
            db: Redis database number
            ttl: Time-to-live for sessions in seconds (default: 7200 = 2 hours)
        """
        super().__init__(host=host, port=port, db=db)
        self.ttl = ttl
        logger.info("UserSessionStorage initialized: host=%s, port=%s, db=%s, ttl=%ss", host, port, db, ttl)
    
    def _get_session_key(self, chat_id: int) -> str:
        """
        Generate Redis key for user session.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Redis key string in format 'user_session:{chat_id}'
        """
        return f"user_session:{chat_id}"
    
    def create_session(self, chat_id: int, url: str, service: str, media_data: Dict[str, Any]) -> bool:
        """
        Create a new user session with TTL expiration.
        
        Args:
            chat_id: Telegram chat ID
            url: Media URL that user requested
            service: Service name (youtube, instagram, etc.)
            media_data: Media information including formats, thumbnails, etc.
            
        Returns:
            True if session created successfully, False otherwise
        """
        try:
            key = self._get_session_key(chat_id=chat_id)
            
            session_data = {
                "url": url,
                "service": service,
                "media_data": media_data,
            }
            
            result = self.redis_client.setex(
                name=key, 
                time=self.ttl,
                value=self._serialize(session_data)
            )
            
            if result:
                logger.info("Session created for chat_id=%s, service=%s, ttl=%ss", chat_id, service, self.ttl)
            else:
                logger.warning("Failed to create session for chat_id=%s", chat_id)
                
            return result
            
        except Exception as e:
            logger.error("Error creating session for chat_id=%s: %s", chat_id, e)
            return False
    
    def get_session(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve user session and refresh TTL.
        
        When a session is accessed, its TTL is reset to maintain
        the session alive for active users.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Session data dictionary or None if session doesn't exist
        """
        try:
            key = self._get_session_key(chat_id=chat_id)
            data = self.redis_client.get(name=key)
            
            if data:
                session_data = self._deserialize(data=data)
                self.redis_client.setex(name=key, time=self.ttl, value=self._serialize(session_data))
                logger.debug("Session retrieved for chat_id=%s, TTL refreshed", chat_id)
                return session_data
                
            logger.debug("Session not found for chat_id=%s", chat_id)
            return None
            
        except Exception as e:
            logger.error("Error getting session for chat_id=%s: %s", chat_id, e)
            return None
