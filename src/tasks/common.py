from typing import Union

from .app import (
    reddit_downloader,
    rutube_downloader,
    tiktok_downloader,
    youtube_downloader,
    instagram_downloader,
)
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
        "instagram": instagram_downloader,
        "youtube": youtube_downloader,
        "reddit": reddit_downloader,
        "rutube": rutube_downloader,
        "tiktok": tiktok_downloader,
    }
    
    if service not in downloaders:
        raise ValueError(f"Unsupported service: {service}")
    
    return downloaders[service]
