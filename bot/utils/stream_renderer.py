"""Safe Telegram stream renderer.

Progressively updates Telegram messages with rate-limiting, live cursors,
exception handling, and intelligent message splitting for long responses.
"""

import asyncio
from collections.abc import AsyncGenerator
import time

from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import Message
from loguru import logger

from bot.services.exceptions import GeminiError, GeminiRateLimitError
from bot.utils.text_formatter import split_message

THROTTLE_INTERVAL: float = 1.3
MAX_STREAM_CHUNK_LENGTH: int = 4000
CURSOR: str = " ▌"


async def stream_response_to_telegram(
    message: Message,
    stream: AsyncGenerator[str, None],
) -> None:
    """Stream AI response chunks progressively to Telegram chat.

    Handles Telegram edit rate limits, renders a live cursor, caps intermediate message
    length to avoid MessageTooLong errors, and splits final long messages into multiple chunks.

    Args:
        message: Incoming Telegram message from user.
        stream: AsyncGenerator yielding partial text chunks.
    """
    # 1. Initial placeholder
    sent_msg = await message.answer("💭 ...")
    full_text = ""
    last_edit_time = 0.0

    try:
        async for chunk in stream:
            full_text += chunk
            now = time.monotonic()

            # 2. Throttled edits: at least 1.3s between edit calls
            if now - last_edit_time >= THROTTLE_INTERVAL and full_text.strip():
                # 3. Live Cursor & Length Cap
                if len(full_text) > MAX_STREAM_CHUNK_LENGTH:
                    display_text = full_text[:MAX_STREAM_CHUNK_LENGTH] + f"…{CURSOR}"
                else:
                    display_text = full_text + CURSOR

                try:
                    await sent_msg.edit_text(display_text)
                    last_edit_time = now
                except TelegramRetryAfter as err:
                    logger.warning(
                        f"Telegram edit limiti: {err.retry_after}s kutilmoqda"
                    )
                    await asyncio.sleep(err.retry_after)
                    last_edit_time = time.monotonic()
                except TelegramBadRequest as err:
                    # Safely ignore "message is not modified"
                    err_msg = str(err).lower()
                    if "message is not modified" in err_msg:
                        pass
                    else:
                        logger.debug(f"Oraliq tahrirda xatolik: {err}")
                except Exception as err:
                    logger.debug(f"Oraliq tahrir xatoligi: {err}")

    except (GeminiRateLimitError, GeminiError) as api_err:
        logger.warning(f"Streaming paytida Gemini xatoligi: {api_err}")
        full_text += f"\n\n⚠️ <i>{api_err}</i>"
    except Exception as exc:
        logger.exception(f"Streaming paytida kutilmagan xatolik: {exc}")
        full_text += "\n\n⚠️ <i>Javobni yuklashda xatolik yuz berdi.</i>"

    # 4. Final Render & Splitting
    cleaned_text = full_text.strip()
    if not cleaned_text:
        await sent_msg.edit_text("Kechirasiz, javob hosil qilib bo'lmadi.")
        return

    chunks = split_message(cleaned_text)
    if not chunks:
        return

    # Update sent_msg with the first chunk (without the cursor)
    first_chunk = chunks[0]
    try:
        await sent_msg.edit_text(first_chunk)
    except TelegramBadRequest as err:
        err_msg = str(err).lower()
        if "message is not modified" in err_msg:
            pass
        else:
            logger.warning(
                f"Yakuniy tahrirda parse xatoligi ({err}), oddiy formatda jo'natiladi"
            )
            await sent_msg.edit_text(first_chunk, parse_mode=None)
    except Exception as err:
        logger.warning(f"Yakuniy tahrirda xatolik: {err}")

    # Send remaining chunks as new messages if length exceeded limit
    for chunk in chunks[1:]:
        try:
            await message.answer(chunk)
        except Exception as err:
            logger.warning(
                f"Qo'shimcha bo'lakni yuborishda xatolik ({err}), oddiy formatda jo'natiladi"
            )
            await message.answer(chunk, parse_mode=None)
