"""Main application entry point for the Gemini Telegram Bot.

Configures logging, initializes Bot and Dispatcher, registers middlewares and routers,
and executes asynchronous polling with graceful shutdown handling.
"""

import asyncio
from pathlib import Path
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from bot.config import config
from bot.handlers import commands_router, media_router, text_router
from bot.middlewares import ThrottlingMiddleware


def setup_logging() -> None:
    """Configure loguru logging with stdout and daily rotating log files."""
    logger.remove()

    # Log format
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # Console logging
    logger.add(
        sys.stdout,
        format=log_format,
        level="INFO",
        colorize=True,
    )

    # File logging
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "bot.log",
        format=log_format,
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
    )
    logger.info("Loguru log tizimi sozlandi")


async def on_startup(bot: Bot) -> None:
    """Execute actions upon dispatcher startup."""
    try:
        bot_user = await bot.get_me()
        logger.info(
            f"Telegram bot muvaffaqiyatli ishga tushdi: @{bot_user.username} (ID: {bot_user.id})"
        )
    except Exception as err:
        logger.warning(f"Bot ma'lumotlarini olishda ogohlantirish: {err}")

    # Drop any pending updates accumulated while the bot was offline
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Eski kutilayotgan yangilanishlar (pending updates) tozalandi")
    except Exception as err:
        logger.warning(f"Webhook/pending updates tozalashda ogohlantirish: {err}")


async def on_shutdown(bot: Bot) -> None:
    """Execute graceful shutdown cleanup."""
    logger.info("Bot to'xtatilmoqda...")
    await bot.session.close()
    logger.info("Bot seansi yopildi. Graceful shutdown yakunlandi.")


import os
from aiohttp import web

async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main() -> None:
    """Initialize and run the Telegram bot polling engine."""
    setup_logging()
    logger.info(f"Ishga tushirilayotgan Gemini modeli: {config.gemini_model}")

    # Initialize Bot with default HTML parse mode
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Initialize Dispatcher
    dp = Dispatcher()

    # Register lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Register middlewares
    dp.message.middleware(ThrottlingMiddleware(rate_limit=1.5))
    logger.info("ThrottlingMiddleware (anti-spam) ro'yxatdan o'tkazildi")

    # Register routers in priority order
    dp.include_router(commands_router)
    dp.include_router(media_router)
    dp.include_router(text_router)
    logger.info("Barcha routerlar (commands, media, text) ro'yxatdan o'tkazildi")

    try:
        await start_web_server()
        logger.info("Polling boshlanmoqda...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot qo'lda to'xtatildi")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur yakunlandi")
