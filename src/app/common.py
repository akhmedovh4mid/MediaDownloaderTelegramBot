from enum import Enum


class ServiceType(Enum):
    """
    Перечисление типов поддерживаемых сервисов.
    
    Используется для идентификации типа сервиса по домену URL
    и соответствующей обработки контента.
    
    Examples:
        >>> ServiceType.YOUTUBE
        <ServiceType.YOUTUBE: 'youtube'>
        
        >>> ServiceType.YOUTUBE.value
        'youtube'
        
        >>> ServiceType('youtube')
        <ServiceType.YOUTUBE: 'youtube'>
    """
    
    YOUTUBE = "youtube"
    """YouTube - видеохостинг."""
    
    INSTAGRAM = "instagram"
    """Instagram - социальная сеть для фото и видео."""
    
    REDDIT = "reddit"
    """Reddit - социальный новостной сайт."""
    
    RUTUBE = "rutube"
    """Rutube - российский видеохостинг."""
    
    TIKTOK = "tiktok"
    """TikTok - платформа для коротких видео."""
    
    UNSUPPORTED = "unsupported"
    """Неподдерживаемый сервис."""
