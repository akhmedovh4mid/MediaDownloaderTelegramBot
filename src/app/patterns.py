from typing import Dict, List

from .common import ServiceType


class DomainMatcher:
    """Класс для точного сопоставления доменов с сервисами."""
    
    # Словарь соответствия доменных частей типам сервисов
    DOMAIN_PATTERNS: Dict[ServiceType, List[str]] = {
        ServiceType.YOUTUBE: [
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
            "www.youtu.be"
        ],
        ServiceType.INSTAGRAM: [
            "instagram.com",
            "www.instagram.com",
            "instagr.am",
            "www.instagr.am"
        ],
        ServiceType.REDDIT: [
            "reddit.com",
            "www.reddit.com",
            "old.reddit.com",
            "np.reddit.com",
            "amp.reddit.com"
        ],
        ServiceType.RUTUBE: [ 
            "rutube.ru",
            "www.rutube.ru",
            "rutu.be"
        ],
        ServiceType.TIKTOK: [
            "tiktok.com",
            "www.tiktok.com",
            "vm.tiktok.com",
            "vt.tiktok.com",
            "m.tiktok.com"
        ]
    }
    
    # Приоритетные домены для точного сопоставления
    PRIORITY_DOMAINS: Dict[str, ServiceType] = {
        "youtu.be": ServiceType.YOUTUBE,
        "rutu.be": ServiceType.RUTUBE,
        "instagr.am": ServiceType.INSTAGRAM,
        "vm.tiktok.com": ServiceType.TIKTOK,
        "vt.tiktok.com": ServiceType.TIKTOK,
    }
    
    @classmethod
    def get_service_type(cls, domain: str) -> ServiceType:
        """
        Определить тип сервиса по домену.
        
        Args:
            domain: Доменное имя (например, 'youtube.com')
            
        Returns:
            ServiceType: Тип сервиса
        """
        domain_lower = domain.lower().strip()
        
        # Сначала проверяем приоритетные домены (точное совпадение)
        if domain_lower in cls.PRIORITY_DOMAINS:
            return cls.PRIORITY_DOMAINS[domain_lower]
        
        # Затем проверяем по паттернам
        for service_type, patterns in cls.DOMAIN_PATTERNS.items():
            for pattern in patterns:
                if domain_lower == pattern or domain_lower.endswith('.' + pattern):
                    return service_type
        
        # Проверяем частичные совпадения для основных доменов
        if any(primary in domain_lower for primary in ['youtube', 'youtu']):
            return ServiceType.YOUTUBE
        elif 'instagram' in domain_lower or 'instagr.am' in domain_lower:
            return ServiceType.INSTAGRAM
        elif 'reddit' in domain_lower:
            return ServiceType.REDDIT
        elif 'rutube' in domain_lower:
            return ServiceType.RUTUBE
        elif 'tiktok' in domain_lower:
            return ServiceType.TIKTOK
        
        return ServiceType.UNSUPPORTED
    
    @classmethod
    def get_supported_domains_flat(cls) -> List[str]:
        """Получить плоский список всех поддерживаемых доменов."""
        domains = []
        for patterns in cls.DOMAIN_PATTERNS.values():
            domains.extend(patterns)
        domains.extend(cls.PRIORITY_DOMAINS.keys())
        return list(set(domains))  # Убираем дубликаты
    
    @classmethod
    def is_domain_supported(cls, domain: str) -> bool:
        """Проверить, поддерживается ли домен."""
        return cls.get_service_type(domain) != ServiceType.UNSUPPORTED
