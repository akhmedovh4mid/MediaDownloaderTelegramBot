from urllib.parse import urlparse

from aiogram.types import Message
from aiogram.filters import BaseFilter


class URLFilter(BaseFilter):
    """
    Фильтр для проверки сообщений на наличие валидных URL-адресов.
    
    Этот фильтр анализирует текст сообщения или подпись к медиафайлу
    и проверяет наличие корректных URL-адресов. Может дополнительно
    проверять поддержку доменов через DomainMatcher.
    
    Attributes:
        check_support (bool): Флаг проверки поддержки домена. 
            Если True, проверяет домен через DomainMatcher.
            Если False, проверяет только синтаксис URL.
            По умолчанию True.
    
    Examples:
        >>> # Простая проверка URL
        >>> filter = URLFilter()
        >>> await filter(message_with_url)
        
        >>> # Проверка только синтаксиса URL
        >>> filter = URLFilter(check_support=False)
        >>> await filter(message_with_url)
    """
    
    def __init__(self, check_support: bool = True):
        """
        Инициализирует фильтр URL.
        
        Args:
            check_support (bool): Определяет, нужно ли проверять 
                поддержку домена. По умолчанию True.
        """
        self.check_support = check_support
    
    async def __call__(self, message: Message) -> bool:
        """
        Вызывается при проверке сообщения фильтром.
        
        Args:
            message (Message): Объект сообщения от пользователя.
            
        Returns:
            bool: True если сообщение содержит валидный URL, 
                False в противном случае.
                
        Notes:
            Проверяет как текст сообщения, так и подпись к медиафайлу.
            Пустые сообщения или сообщения без URL сразу возвращают False.
        """
        text = message.text or message.caption or ""
        if not text.strip():
            return False
        
        return self.is_valid_url(text)
    
    def is_valid_url(self, text: str) -> bool:
        """
        Проверяет валидность URL и поддержку домена.
        
        Args:
            text (str): Текст для проверки на наличие URL.
            
        Returns:
            bool: True если текст содержит валидный URL и 
                (при включенной проверке) домен поддерживается.
                
        Raises:
            Ловит все исключения и возвращает False в случае ошибок.
            
        Steps:
            1. Парсит URL с помощью urlparse
            2. Проверяет наличие схемы (http/https) и домена
            3. При check_support=True проверяет домен через DomainMatcher
            4. Возвращает результат проверки
        """
        try:
            parsed = urlparse(text.strip())
            if not (parsed.scheme in ('http', 'https') and parsed.netloc):
                return False
            
            domain = parsed.netloc.lower()
            
            # Если требуется проверка поддержки домена
            if self.check_support:
                from src.app.patterns import DomainMatcher
                return DomainMatcher.is_domain_supported(domain)
            
            return True
            
        except Exception:
            return False
