from typing import Union

from src.config import settings
from src.core import (
    InstagramDownloader,
    YoutubeDownloader, 
    RedditDownloader, 
    RutubeDownloader, 
    TikTokDownloader,
)


def get_service_downloader(
    service: str,
) -> Union[
    InstagramDownloader, 
    YoutubeDownloader, 
    RedditDownloader, 
    RutubeDownloader, 
    TikTokDownloader,
]:
    """Создает и возвращает загрузчик для указанного сервиса"""
    downloaders = {
        "instagram": InstagramDownloader,
        "youtube": YoutubeDownloader,
        "reddit": RedditDownloader,
        "rutube": RutubeDownloader,
        "tiktok": TikTokDownloader,
    }
    
    # Конфигурации для разных сервисов
    service_configs = {
        "instagram": {
            "username": settings.instagram_username,
            "password": settings.instagram_password,
            "cookie_path": settings.instagram_cookie_path,            
        },
        "reddit": {
            "client_id": settings.reddit_client_id,
            "client_secret": settings.reddit_client_secret,
            "cookie_path": settings.browser_cookie_path,
        },
        "youtube": {
            "cookie_path": settings.browser_cookie_path,        
        },
        "rutube": {
            "cookie_path": settings.browser_cookie_path,        
        },
        "tiktok": {
            "cookie_path": settings.browser_cookie_path,        
        }
    }
    
    if service not in downloaders:
        raise ValueError(f"Unsupported service: {service}")
    
    config = service_configs.get(service, {})
    return downloaders[service](**config)
