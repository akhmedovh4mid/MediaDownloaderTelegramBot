import json
import redis
from typing import Any, Optional


class RedisBase:
    """
    Base class for Redis storage implementations.
    
    Provides common serialization/deserialization methods and connection management
    for Redis-based storage classes. Handles JSON serialization and connection
    testing for derived storage classes.
    
    Attributes:
        redis_client (redis.Redis): Redis client instance
        host (str): Redis server hostname
        port (int): Redis server port
        db (int): Redis database number
        
    Example:
        >>> from src.storage.redis_base import RedisBase
        >>> 
        >>> class UserSessionStorage(RedisBase):
        ...     def __init__(self):
        ...         super().__init__(
        ...             host='localhost',
        ...             port=6379,
        ...             db=0
        ...         )
    """
    
    def __init__(self, host: str, port: int, db: int) -> None:
        """
        Initialize Redis client with connection parameters.
        
        Args:
            host: Redis server hostname or IP address
            port: Redis server port
            db: Redis database number (0-15)
            
        Raises:
            redis.ConnectionError: If connection to Redis server fails
            
        Example:
            >>> storage = RedisBase(host='localhost', port=6379, db=0)
            >>> if storage.ping():
            ...     print("Connected successfully")
        """
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
            encoding='utf-8'
        )
        self.host = host
        self.port = port
        self.db = db
    
    def _serialize(self, data: Any) -> str:
        """
        Serialize Python object to JSON string.
        
        Converts Python objects to JSON format for storage in Redis.
        Handles non-serializable objects by converting them to strings.
        
        Args:
            data: Python object to serialize (dict, list, str, int, etc.)
            
        Returns:
            JSON-formatted string representation of the data
            
        Example:
            >>> data = {'user_id': 123, 'media_url': 'https://example.com/video'}
            >>> serialized = storage._serialize(data)
            >>> print(serialized)
            '{"user_id": 123, "media_url": "https://example.com/video"}'
        """
        return json.dumps(data, ensure_ascii=False, default=str)
    
    def _deserialize(self, data: str) -> Optional[Any]:
        """
        Deserialize JSON string to Python object.
        
        Converts JSON string from Redis back to Python object.
        
        Args:
            data: JSON string to deserialize
            
        Returns:
            Deserialized Python object or None if input is empty
            
        Raises:
            json.JSONDecodeError: If input string is not valid JSON
            
        Example:
            >>> json_string = '{"user_id": 123, "media_url": "https://example.com/video"}'
            >>> deserialized = storage._deserialize(json_string)
            >>> print(deserialized)
            {'user_id': 123, 'media_url': 'https://example.com/video'}
        """
        if data:
            return json.loads(data)
        return None
    
    def ping(self) -> bool:
        """
        Test connection to Redis server.
        
        Sends a PING command to Redis server to verify connectivity.
        
        Returns:
            True if connection is successful, False if connection fails
            
        Example:
            >>> if storage.ping():
            ...     print("Redis connection: OK")
            ... else:
            ...     print("Redis connection: FAILED")
        """
        try:
            return self.redis_client.ping()
        except redis.ConnectionError:
            return False
    
    def get_connection_info(self) -> dict:
        """
        Get Redis connection parameters and status.
        
        Returns:
            Dictionary containing connection details and status
            
        Example:
            >>> info = storage.get_connection_info()
            >>> print(f"Host: {info['host']}:{info['port']}")
            >>> print(f"Database: {info['db']}")
            >>> print(f"Status: {info['status']}")
        """
        return {
            'host': self.host,
            'port': self.port,
            'db': self.db,
            'status': 'connected' if self.ping() else 'disconnected'
        }
