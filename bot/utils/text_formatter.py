"""Text formatting utilities for Telegram messages.

Provides smart message splitting that respects paragraph boundaries, line breaks,
and keeps Markdown code blocks intact across message splits.
"""

import re
from loguru import logger

TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def _find_unclosed_code_block(text: str) -> str | None:
    """Check if the text contains an unclosed markdown code block.

    Returns:
        The code block language specifier (e.g., 'python') if unclosed,
        or None if all code blocks are properly closed.
    """
    pattern = re.compile(r"```([a-zA-Z0-9_\-\+]*)\n?")
    matches = list(pattern.finditer(text))
    if len(matches) % 2 != 0:
        return matches[-1].group(1).strip()
    return None


def split_message(
    text: str,
    max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH,
) -> list[str]:
    """Smartly split long messages into chunks that fit within Telegram's limit.

    Splits along paragraph boundaries (double newline), line boundaries (single newline),
    or word boundaries (whitespace). If a code block is bisected, closes the block
    in the first chunk and re-opens it in the subsequent chunk.

    Args:
        text: The complete message text to split.
        max_length: Maximum allowed length per chunk (default 4096 for Telegram).

    Returns:
        A list of string chunks, each <= max_length.
    """
    if not text:
        return []

    text = text.strip()
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text

    # Reserve buffer for code block fences if needed
    safety_buffer = 15

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Slicing limit considering potential code fence closing
        effective_max = max(max_length - safety_buffer, 100)
        candidate = remaining[:effective_max]

        # 1. Try splitting at paragraph boundary
        split_idx = candidate.rfind("\n\n")
        delimiter_len = 2

        # 2. Try splitting at line boundary
        if split_idx == -1:
            split_idx = candidate.rfind("\n")
            delimiter_len = 1

        # 3. Try splitting at space boundary
        if split_idx == -1:
            split_idx = candidate.rfind(" ")
            delimiter_len = 1

        # 4. Fallback: hard cut
        if split_idx <= 0:
            split_idx = effective_max
            delimiter_len = 0

        chunk = remaining[:split_idx].rstrip()
        next_remaining = remaining[split_idx + delimiter_len :].lstrip()

        # Handle unclosed code blocks
        unclosed_lang = _find_unclosed_code_block(chunk)
        if unclosed_lang is not None:
            chunk = f"{chunk}\n```"
            prefix = f"```{unclosed_lang}\n" if unclosed_lang else "```\n"
            next_remaining = prefix + next_remaining

        if chunk:
            chunks.append(chunk)

        remaining = next_remaining

    logger.debug(f"Matn {len(chunks)} ta bo'lakka bo'lindi (asl uzunligi: {len(text)})")
    return chunks
