import asyncio

from src.app import TelegramBot
from src.config import settings


async def main():
    bot = TelegramBot(token=settings.bot_token, server_ip=settings.bot_server_ip)
    try:
        await bot.start()
    except KeyboardInterrupt:
        raise


if __name__ == "__main__":
    asyncio.run(main())
