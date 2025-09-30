"""
Модуль Telegram бота для обработки медиа-контента из социальных сетей.
Поддерживает YouTube, Instagram, TikTok, Reddit и другие платформы.
"""

import logging
from datetime import datetime
from urllib.parse import urlparse
from typing import Optional, Dict, Callable

from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .filters import URLFilter
from .common import ServiceType
from .patterns import DomainMatcher
from .handlers import ServiceHandler
from .callback_handlers import ServiceCallbackHandler


class TelegramBot:
    """
    Главный класс Telegram бота для обработки медиа-контента.
    
    Реализует паттерн Singleton для обеспечения единственного экземпляра бота.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs) -> 'TelegramBot':
        """Реализация паттерна Singleton."""
        if cls._instance is None:
            cls._instance = super(TelegramBot, cls).__new__(cls)
        return cls._instance

    def __init__(
        self, 
        token: str, 
        server_ip: str = "http://localhost:8081", 
        parse_mode: ParseMode = ParseMode.HTML, 
        loglevel: int = logging.INFO
    ) -> None:
        """
        Инициализация бота.
        
        Args:
            token: Токен Telegram бота
            server_ip: Адрес кастомного Telegram API сервера
            parse_mode: Режим парсинга сообщений
            loglevel: Уровень логирования
        """
        if not self._initialized:
            self.token = token
            self.server_ip = server_ip
            self.parse_mode = parse_mode
            self.loglevel = loglevel
            self.start_time = datetime.now()
            
            # Основные компоненты бота
            self.bot: Optional[Bot] = None
            self.dp: Optional[Dispatcher] = None
            self.session: Optional[AiohttpSession] = None
            
            self._setup_logging()
            self._initialize_bot()
            self._register_handlers()
            self._register_callback_handlers()
            
            self._initialized = True
            self.logger.info("🤖 Бот успешно инициализирован!")
            
    def _setup_logging(self) -> None:
        """Настройка системы логирования."""
        logging.basicConfig(
            level=self.loglevel,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
        
    def _initialize_bot(self) -> None:
        """Инициализация основных компонентов бота."""
        self.logger.info("🔄 Инициализация компонентов бота...")
        
        # Создание кастомной сессии с указанным сервером
        self.session = AiohttpSession(
            api=TelegramAPIServer.from_base(self.server_ip)
        )
        
        # Создание экземпляра бота с кастомными свойствами
        self.bot = Bot(
            token=self.token,
            session=self.session,
            default=DefaultBotProperties(parse_mode=self.parse_mode)
        )
        
        # Инициализация диспетчера
        self.dp = Dispatcher()
        
        self.logger.info("✅ Компоненты бота успешно инициализированы")
        
    def _register_handlers(self) -> None:
        """Регистрация обработчиков сообщений."""
        self.logger.info("📝 Регистрация обработчиков сообщений...")
        
        self.dp.message.register(self._handle_start, CommandStart())
        self.dp.message.register(self._handle_help, Command("help"))
        self.dp.message.register(self._handle_url_message, URLFilter(check_support=True))
        self.dp.message.register(self._handle_unknown_message)
        
        self.logger.info("✅ Обработчики сообщений зарегистрированы")
        
    def _register_callback_handlers(self) -> None:
        """Регистрация обработчиков callback запросов."""
        self.logger.info("🔄 Регистрация callback обработчиков...")
        
        callback_handlers = {
            "video": ServiceCallbackHandler.handle_video,
            "image": ServiceCallbackHandler.handle_image,
            "audio": ServiceCallbackHandler.handle_auido,
            "thumbnail": ServiceCallbackHandler.handle_thumbnail,
        }
        
        for prefix, handler in callback_handlers.items():
            self.dp.callback_query.register(handler, F.data.startswith(prefix))
            
        self.logger.info("✅ Callback обработчики зарегистрированы")
        
    async def _handle_start(self, message: types.Message) -> None:
        """Обработчик команды /start."""
        user_name = message.from_user.full_name
        user_id = message.from_user.id
        
        self.logger.info(f"👤 Новый пользователь: {user_name} (ID: {user_id})")
        
        welcome_text = (
            "🎉 <b>Добро пожаловать в Медиа Бот!</b>\n\n"
            "Я помогу вам скачать медиа-контент из популярных социальных сетей. "
            "Просто отправьте мне ссылку, и я предложу доступные варианты загрузки.\n\n"
            "💡 <b>Примеры поддерживаемых платформ:</b>\n"
            "• YouTube, Instagram, TikTok\n"
            "• Reddit, Rutube и другие\n\n"
        )
        
        await message.answer(
            welcome_text,
            parse_mode=ParseMode.HTML
        )
            
    async def _handle_help(self, message: types.Message) -> None:
        """Показать расширенную справку с поддерживаемыми доменами."""
        self.logger.info(f"Пользователь {message.from_user.full_name} запросил помощь")
        
        # Формирование списка поддерживаемых сервисов
        supported_services = []
        for service_type, domains in DomainMatcher.DOMAIN_PATTERNS.items():
            domain_examples = ", ".join(domains[:3])
            supported_services.append(
                f"• <b>{service_type.value.upper()}</b> - {domain_examples}..."
            )
            
        help_text = (
            "🤖 <b>Медиа Бот - Помощь</b>\n\n"
            "📥 <b>Как использовать:</b>\n"
            "Просто отправьте ссылку из поддерживаемой социальной сети, "
            "и я предложу варианты для скачивания контента.\n\n"
            "🌐 <b>Поддерживаемые платформы:</b>\n"
            f"{chr(10).join(supported_services)}\n\n"
            "⚡ <b>Доступные команды:</b>\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать эту справку\n"
            "💡 <b>Совет:</b> Бот работает лучше всего с публично доступным контентом."
        )
        
        await message.answer(help_text, parse_mode=ParseMode.HTML)
        
    async def _handle_url_message(self, message: types.Message) -> None:
        """Обработчик сообщений с URL."""
        url = message.text or message.caption
        if not url:
            return

        try:
            parsed = urlparse(url.strip())
            domain = parsed.netloc.lower()
            service_type = DomainMatcher.get_service_type(domain)
            
            self.logger.info(
                f"🔗 Обработка URL: {url} | "
                f"Домен: {domain} | "
                f"Сервис: {service_type.value}"
            )
            
            # Маппинг обработчиков для разных сервисов
            handler_map: Dict[ServiceType, Callable] = {
                ServiceType.YOUTUBE: ServiceHandler.handle_youtube,
                ServiceType.INSTAGRAM: ServiceHandler.handle_instagram,
                ServiceType.REDDIT: ServiceHandler.handle_reddit,
                ServiceType.RUTUBE: ServiceHandler.handle_rutube,
                ServiceType.TIKTOK: ServiceHandler.handle_tiktok,
            }
            
            if service_type in handler_map:
                await handler_map[service_type](url, message, domain)
            else:
                await self._handle_unsupported_domain(domain, message)
                
        except Exception as e:
            self.stats['errors_count'] += 1
            self.logger.error(f"❌ Ошибка обработки URL {url}: {str(e)}", exc_info=True)
            
            error_text = (
                "❌ <b>Произошла ошибка при обработке ссылки</b>\n\n"
                "Возможные причины:\n"
                "• Ссылка недействительна\n"
                "• Контент недоступен\n"
                "• Временные проблемы с сервисом\n\n"
                "Попробуйте позже или проверьте корректность ссылки."
            )
            await message.answer(error_text, parse_mode=ParseMode.HTML)
            
    async def _handle_unsupported_domain(self, domain: str, message: types.Message) -> None:
        """Обработчик неподдерживаемых доменов."""
        self.logger.warning(f"🚫 Неподдерживаемый домен: {domain}")
        
        supported_services = ", ".join(
            service_type.value for service_type in DomainMatcher.DOMAIN_PATTERNS.keys()
        )
        
        response = (
            f"❌ <b>Домен не поддерживается</b>\n\n"
            f"К сожалению, домен <code>{domain}</code> пока не поддерживается.\n\n"
            f"<b>🔄 Поддерживаемые сервисы:</b>\n"
            f"{supported_services}\n\n"
            f"💡 Используйте /help для подробной информации"
        )
        await message.answer(response, parse_mode=ParseMode.HTML)
        
    async def _handle_unknown_message(self, message: types.Message) -> None:
        """Обработчик неизвестных сообщений."""
        await message.answer(
            "🤔 <b>Не понял ваше сообщение</b>\n\n"
            "Я специализируюсь на обработке ссылок из социальных сетей. "
            "Отправьте мне ссылку или используйте команды:\n\n"
            "/start - Начать работу\n"
            "/help - Получить помощь",
            parse_mode=ParseMode.HTML
        )

    async def start(self) -> None:
        """Запуск бота."""
        self.logger.info("🚀 Запуск бота...")
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            self.logger.error(f"💥 Критическая ошибка при запуске бота: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Корректная остановка бота."""
        self.logger.info("🛑 Остановка бота...")
        if self.session:
            await self.session.close()
        self.logger.info("👋 Бот успешно остановлен")
