"""Chat utility functions for Aiogram handlers.

Provides background typing indicator tasks and message splitting helpers.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.types import Message
from loguru import logger

from bot.utils.text_formatter import split_message


@asynccontextmanager
async def typing_indicator(
    bot: Bot,
    chat_id: int,
    interval: float = 4.0,
) -> AsyncIterator[asyncio.Task]:
    """Maintain an active typing status in chat via a background asyncio task.

    Args:
        bot: Aiogram Bot instance.
        chat_id: Target chat identifier.
        interval: Periodic interval in seconds between action refreshes.

    Yields:
        The spawned asyncio.Task running the loop.
    """
    async def _typing_loop() -> None:
        try:
            while True:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        except Exception as err:
            logger.debug(f"Typing indikatorida kutilmagan to'xtash: {err}")

    task = asyncio.create_task(_typing_loop())
    try:
        yield task
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def send_split_message(
    message: Message,
    text: str,
    parse_mode: str | None = None,
) -> None:
    """Send text split into Telegram-compliant chunks.

    Args:
        message: Incoming Telegram message to reply to.
        text: Response content to send.
        parse_mode: Optional ParseMode (e.g. 'Markdown' or None).
    """
    chunks = split_message(text)
    if not chunks:
        return

    for chunk in chunks:
        try:
            await message.answer(chunk, parse_mode=parse_mode)
        except Exception as err:
            logger.warning(
                f"Xabarni parse_mode={parse_mode} bilan yuborishda xatolik ({err}), oddiy matn ko'rinishida qayta yuborilmoqda"
            )
            # Fallback to plain text without parse mode if formatting fails
            await message.answer(chunk, parse_mode=None)
