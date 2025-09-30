from enum import Enum


class ServiceType(Enum):
    """Типы поддерживаемых сервисов."""
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    REDDIT = "reddit"
    RUTUBE = "rutube"
    TIKTOK = "tiktok"
    UNSUPPORTED = "unsupported"
