"""File management utilities for Telegram bot.

Provides asynchronous file downloading, size validation, and guaranteed cleanup of temporary files.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import os
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING

import aiofiles
from loguru import logger

from bot.config import config

if TYPE_CHECKING:
    from aiogram import Bot


class FileSizeLimitExceededError(Exception):
    """Raised when an uploaded file exceeds the configured size limit."""

    def __init__(self, file_size_mb: float, max_size_mb: float) -> None:
        self.file_size_mb = file_size_mb
        self.max_size_mb = max_size_mb
        super().__init__(
            f"Fayl hajmi ({file_size_mb:.2f} MB) belgilangan cheklovdan ({max_size_mb:.2f} MB) oshib ketdi."
        )


def validate_file_size(
    file_size_bytes: int | None,
    max_size_mb: float | None = None,
) -> bool:
    """Validate whether file size is within acceptable threshold.

    Args:
        file_size_bytes: Size of the file in bytes.
        max_size_mb: Optional override for max size in MB (defaults to config.max_file_size_mb).

    Returns:
        True if valid.

    Raises:
        FileSizeLimitExceededError: If file size exceeds maximum allowed size.
    """
    if file_size_bytes is None:
        return True

    allowed_mb = max_size_mb if max_size_mb is not None else config.max_file_size_mb
    max_bytes = allowed_mb * 1024 * 1024

    if file_size_bytes > max_bytes:
        actual_mb = file_size_bytes / (1024 * 1024)
        logger.warning(
            f"Fayl hajmi cheklovdan oshdi: {actual_mb:.2f} MB > {allowed_mb:.2f} MB"
        )
        raise FileSizeLimitExceededError(file_size_mb=actual_mb, max_size_mb=allowed_mb)

    return True


@asynccontextmanager
async def create_temp_file(
    suffix: str = "",
    prefix: str = "gemini_bot_",
) -> AsyncIterator[Path]:
    """Asynchronously create a temporary file and guarantee its deletion upon exit.

    Yields:
        Path to the temporary file.
    """
    fd, raw_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    temp_path = Path(raw_path)

    try:
        yield temp_path
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
                logger.debug(f"Vaqtinchalik fayl o'chirildi: {temp_path}")
        except Exception as err:
            logger.error(f"Vaqtinchalik faylni o'chirishda xatolik: {temp_path}, xato: {err}")


@asynccontextmanager
async def download_telegram_file(
    bot: "Bot",
    file_id: str,
    suffix: str = "",
    max_size_mb: float | None = None,
) -> AsyncIterator[Path]:
    """Download a file from Telegram servers into a temporary file and ensure cleanup.

    Args:
        bot: Aiogram Bot instance.
        file_id: Telegram file ID.
        suffix: File extension/suffix (e.g. '.ogg', '.pdf').
        max_size_mb: Optional maximum file size in megabytes.

    Yields:
        Path to the downloaded temporary file.

    Raises:
        FileSizeLimitExceededError: If file exceeds maximum allowed size.
    """
    tg_file = await bot.get_file(file_id)

    # Determine extension from Telegram file_path if suffix not explicitly provided
    if not suffix and tg_file.file_path:
        suffix = Path(tg_file.file_path).suffix

    # Validate file size
    validate_file_size(tg_file.file_size, max_size_mb=max_size_mb)

    async with create_temp_file(suffix=suffix) as temp_path:
        logger.info(
            f"Telegram fayli yuklab olinmoqda: file_id={file_id}, path={tg_file.file_path}, size={tg_file.file_size}"
        )
        await bot.download_file(tg_file.file_path, destination=temp_path)
        yield temp_path


async def read_file_bytes(file_path: Path | str) -> bytes:
    """Read binary data from a file asynchronously using aiofiles.

    Args:
        file_path: Path to the target file.

    Returns:
        Bytes contents of the file.
    """
    async with aiofiles.open(file_path, mode="rb") as f:
        return await f.read()
