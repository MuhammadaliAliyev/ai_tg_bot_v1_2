"""Media handlers for Aiogram bot (Photos, Voice, Audio, Documents).

Manages multimodal processing with real-time progressive streaming responses in Telegram.
"""

import io
import mimetypes
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.types import Message
from loguru import logger

from bot.services.gemini_service import gemini_service
from bot.utils.file_utils import (
    FileSizeLimitExceededError,
    download_telegram_file,
)
from bot.utils.stream_renderer import stream_response_to_telegram

router = Router(name="media_router")

SUPPORTED_DOC_EXTENSIONS = {
    # Documents
    ".pdf",
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".htm",
    # Source code & configs
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".java",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".sh",
    ".bash",
    ".sql",
    ".css",
    ".scss",
    ".toml",
    ".ini",
    ".env",
}


@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot) -> None:
    """Handle photo input: Download image and stream Gemini vision analysis."""
    if not message.photo:
        return

    photo = message.photo[-1]
    logger.info(
        f"Rasm qabul qilindi (stream): file_id={photo.file_id}, o'lcham={photo.width}x{photo.height}"
    )

    try:
        await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        image_stream = io.BytesIO()
        await bot.download(photo, destination=image_stream)
        image_bytes = image_stream.getvalue()

        stream = gemini_service.stream_image(
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            caption=message.caption,
        )
        await stream_response_to_telegram(message=message, stream=stream)

    except FileSizeLimitExceededError as err:
        await message.answer(f"⚠️ {err}")
    except Exception as exc:
        logger.error(f"Rasm yuklashda xatolik: {exc}")
        await message.answer("❌ Rasmni yuklab olishda kutilmagan xatolik yuz berdi.")


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot) -> None:
    """Handle voice messages (.ogg): Stream response to spoken input."""
    voice = message.voice
    if not voice:
        return

    logger.info(
        f"Ovozli xabar qabul qilindi (stream): file_id={voice.file_id}, davomiyligi={voice.duration}s"
    )

    try:
        await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        mime_type = voice.mime_type or "audio/ogg"
        async with download_telegram_file(
            bot=bot, file_id=voice.file_id, suffix=".ogg"
        ) as temp_file:
            stream = gemini_service.stream_audio(
                file_path=str(temp_file),
                mime_type=mime_type,
                caption=message.caption,
            )
            await stream_response_to_telegram(message=message, stream=stream)

    except FileSizeLimitExceededError as err:
        await message.answer(f"⚠️ {err}")
    except Exception as exc:
        logger.error(f"Ovozli xabarni yuklashda xatolik: {exc}")
        await message.answer("❌ Ovozli xabarni yuklab olishda xatolik yuz berdi.")


@router.message(F.audio)
async def handle_audio(message: Message, bot: Bot) -> None:
    """Handle audio files (.mp3, .wav, .m4a): Stream analysis of recorded audio."""
    audio = message.audio
    if not audio:
        return

    ext = Path(audio.file_name or "audio.mp3").suffix.lower()
    if not ext:
        ext = ".mp3"

    mime_type = (
        audio.mime_type or mimetypes.guess_type(audio.file_name or "")[0] or "audio/mp3"
    )
    logger.info(
        f"Audio fayl qabul qilindi (stream): nom={audio.file_name}, mime={mime_type}"
    )

    try:
        await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        async with download_telegram_file(
            bot=bot, file_id=audio.file_id, suffix=ext
        ) as temp_file:
            stream = gemini_service.stream_audio(
                file_path=str(temp_file),
                mime_type=mime_type,
                caption=message.caption,
            )
            await stream_response_to_telegram(message=message, stream=stream)

    except FileSizeLimitExceededError as err:
        await message.answer(f"⚠️ {err}")
    except Exception as exc:
        logger.error(f"Audio faylni yuklashda xatolik: {exc}")
        await message.answer("❌ Audio faylni yuklab olishda xatolik yuz berdi.")


@router.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    """Handle document files: Upload via File API and stream response."""
    doc = message.document
    if not doc:
        return

    file_name = doc.file_name or "document"
    ext = Path(file_name).suffix.lower()

    if ext not in SUPPORTED_DOC_EXTENSIONS:
        logger.warning(
            f"Qo'llab-quvvatlanmaydigan fayl formati: {file_name} ({ext})"
        )
        supported_list = ", ".join(
            sorted([".pdf", ".txt", ".csv", ".json", ".md", ".py", ".js", ".html", ".cpp"])
        )
        await message.answer(
            f"⚠️ <b>'{ext}' formatidagi fayllar qabul qilinmaydi.</b>\n\n"
            f"Qo'llab-quvvatlanadigan formatlar: {supported_list} va boshqa dasturlash kodlari.",
            parse_mode="HTML",
        )
        return

    mime_type = doc.mime_type
    if not mime_type or mime_type == "application/octet-stream":
        inferred = mimetypes.guess_type(file_name)[0]
        mime_type = inferred if inferred else "text/plain"

    logger.info(
        f"Hujjat qabul qilindi (stream): nom={file_name}, ext={ext}, mime={mime_type}"
    )

    try:
        await bot.send_chat_action(
            chat_id=message.chat.id, action=ChatAction.UPLOAD_DOCUMENT
        )
        async with download_telegram_file(
            bot=bot, file_id=doc.file_id, suffix=ext
        ) as temp_file:
            stream = gemini_service.stream_document(
                file_path=str(temp_file),
                mime_type=mime_type,
                caption=message.caption,
            )
            await stream_response_to_telegram(message=message, stream=stream)

    except FileSizeLimitExceededError as err:
        await message.answer(f"⚠️ {err}")
    except Exception as exc:
        logger.error(f"Hujjatni yuklashda xatolik: {exc}")
        await message.answer("❌ Hujjatni yuklab olishda xatolik yuz berdi.")
