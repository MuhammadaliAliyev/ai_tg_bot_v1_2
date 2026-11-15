"""Text message handler for Aiogram bot.

Processes multi-turn conversation text messages with real-time streaming responses in Telegram.
"""

from aiogram import Bot, F, Router
from aiogram.types import Message
from loguru import logger

from bot.services.gemini_service import gemini_service
from bot.utils.stream_renderer import stream_response_to_telegram

router = Router(name="text_router")


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(message: Message, bot: Bot) -> None:
    """Handle regular text messages and stream AI responses with multi-turn memory."""
    if not message.text or not message.from_user:
        return

    user_id = message.from_user.id
    prompt = message.text.strip()
    logger.info(f"Matnli xabar qabul qilindi (stream): user_id={user_id}, uzunlik={len(prompt)}")

    stream = gemini_service.stream_text_response(user_id=user_id, prompt=prompt)
    await stream_response_to_telegram(message=message, stream=stream)
