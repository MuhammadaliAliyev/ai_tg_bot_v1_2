"""Throttling (anti-spam) middleware for Aiogram 3.x.

Restricts the rate of requests per user to prevent flooding and protect API quotas.
"""

from collections.abc import Awaitable, Callable
import time
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from loguru import logger


class ThrottlingMiddleware(BaseMiddleware):
    """Rate-limiting middleware ensuring a minimum time delta between user requests."""

    def __init__(self, rate_limit: float = 1.5) -> None:
        """Initialize throttling middleware.

        Args:
            rate_limit: Minimum interval in seconds between consecutive requests from the same user.
        """
        super().__init__()
        self.rate_limit: float = rate_limit
        self._user_timestamps: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Process incoming telegram event and apply throttling rules."""
        if not isinstance(event, Message) or event.from_user is None:
            return await handler(event, data)

        user_id = event.from_user.id
        now = time.monotonic()
        last_request = self._user_timestamps.get(user_id, 0.0)
        elapsed = now - last_request

        if elapsed < self.rate_limit:
            remaining = self.rate_limit - elapsed
            logger.warning(
                f"Throttling faollashdi: user_id={user_id}, o'tgan_vaqt={elapsed:.2f}s, qolgan={remaining:.2f}s"
            )
            # Notify user gently about the cooldown
            await event.answer("⚠️ Iltimos, xabarlarni juda tez yubormang! Biroz kuting.")
            return None

        # Record this request timestamp
        self._user_timestamps[user_id] = now

        # Prune old cache entries to maintain low memory footprint
        if len(self._user_timestamps) > 5000:
            threshold = now - 60.0
            self._user_timestamps = {
                uid: ts for uid, ts in self._user_timestamps.items() if ts > threshold
            }

        return await handler(event, data)
