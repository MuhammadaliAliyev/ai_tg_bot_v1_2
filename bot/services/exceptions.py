"""Custom exceptions for bot services."""


class GeminiError(Exception):
    """Base exception for Gemini service operations."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


class GeminiRateLimitError(GeminiError):
    """Raised when Gemini API quota or rate limit is exceeded."""
