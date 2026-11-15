"""Gemini API multimodal service integration.

Uses the modern official google-genai SDK exclusively with asynchronous calls (client.aio).
Supports multi-turn text conversations, image analysis, audio processing, document handling,
and real-time token streaming.
"""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from google import genai
from google.genai import errors, types
from loguru import logger

from bot.config import config
from bot.services.exceptions import GeminiError, GeminiRateLimitError
from bot.services.memory_service import memory_service
from bot.utils.file_utils import read_file_bytes

DEFAULT_SYSTEM_INSTRUCTION = """You are a helpful, accurate, and intelligent AI assistant integrated into a Telegram bot.
You communicate naturally, fluently, and politely in the user's preferred language (Uzbek, English, Russian, etc.).
- Structure answers clearly using Markdown (appropriate headings, lists, and code blocks).
- Provide concise, insightful, and accurate information without unnecessary boilerplate.
- For multimodal inputs (images, audio, documents), deliver thorough, helpful analysis tailored to the user's instructions.
"""


class GeminiService:
    """Asynchronous service wrapping the official google-genai Client."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION,
    ) -> None:
        """Initialize Gemini client and configuration.

        Args:
            api_key: Google Gemini API key (defaults to config.gemini_api_key).
            model_name: Gemini model name (defaults to config.gemini_model).
            system_instruction: Core system prompt guiding bot behavior.
        """
        self._api_key = api_key or config.gemini_api_key
        self._model_name = model_name or config.gemini_model
        self._client = genai.Client(api_key=self._api_key)
        self._system_instruction = system_instruction
        self._generation_config = types.GenerateContentConfig(
            system_instruction=self._system_instruction,
            temperature=0.7,
        )

    def _handle_api_error(self, err: Exception, context: str) -> None:
        """Analyze and log API exceptions, raising structured Gemini exceptions."""
        logger.error(f"Gemini API xatoligi ({context}): {err}")

        if isinstance(err, errors.APIError):
            if err.code == 429 or "RESOURCE_EXHAUSTED" in str(err):
                raise GeminiRateLimitError(
                    "So'rovlar limiti oshib ketdi. Iltimos, birozdan so'ng qayta urinib ko'ring.",
                    original_error=err,
                ) from err
            raise GeminiError(
                f"Gemini API xatoligi yuz berdi: {err.message}",
                original_error=err,
            ) from err

        raise GeminiError(
            "Sun'iy intellekt bilan bog'lanishda noma'lum xatolik yuz berdi.",
            original_error=err,
        ) from err

    async def generate_text_response(self, user_id: int, prompt: str) -> str:
        """Generate response for multi-turn text chat with user memory (non-streaming)."""
        memory_service.add_user_message(user_id=user_id, text=prompt)
        history = memory_service.get_history(user_id=user_id)

        try:
            logger.info(
                f"Gemini matn so'rovi yuborilmoqda: user_id={user_id}, model={self._model_name}, tarix={len(history)} turn"
            )
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=history,
                config=self._generation_config,
            )

            reply_text = response.text or ""
            if not reply_text:
                logger.warning(f"Foydalanuvchi [{user_id}] so'rovi uchun bo'sh javob qaytdi")
                reply_text = "Kechirasiz, ushbu so'rov bo'yicha javob hosil qilib bo'lmadi."

            memory_service.add_model_message(user_id=user_id, text=reply_text)
            return reply_text

        except Exception as exc:
            memory_service.remove_last_turn(user_id=user_id)
            self._handle_api_error(exc, context=f"generate_text_response for user {user_id}")
            return ""

    async def stream_text_response(
        self,
        user_id: int,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        """Stream response for multi-turn text chat with user memory.

        Args:
            user_id: Telegram user ID.
            prompt: User text message.

        Yields:
            Progressive text chunks as they arrive from Gemini.
        """
        history = memory_service.get_history(user_id=user_id)
        user_turn = types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )
        contents = history + [user_turn]
        full_text = ""

        try:
            logger.info(
                f"Gemini streaming matn so'rovi boshlandi: user_id={user_id}, model={self._model_name}, tarix={len(history)} turn"
            )
            response_stream = await self._client.aio.models.generate_content_stream(
                model=self._model_name,
                contents=contents,
                config=self._generation_config,
            )

            async for chunk in response_stream:
                if chunk.text:
                    full_text += chunk.text
                    yield chunk.text

            # Stream finished cleanly, save both turns to memory
            if full_text.strip():
                memory_service.add_user_message(user_id=user_id, text=prompt)
                memory_service.add_model_message(user_id=user_id, text=full_text)
                logger.info(f"Foydalanuvchi [{user_id}] streaming suhbati muvaffaqiyatli xotiraga saqlandi")

        except Exception as exc:
            self._handle_api_error(exc, context=f"stream_text_response for user {user_id}")

    async def stream_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        caption: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream analysis of an image using types.Part.from_bytes.

        Args:
            image_bytes: Raw binary content of the image.
            mime_type: Image MIME type (e.g. 'image/jpeg', 'image/png').
            caption: Optional user query or instruction accompanying the image.

        Yields:
            Progressive text chunks as they arrive from Gemini.
        """
        prompt = (
            caption.strip()
            if caption and caption.strip()
            else "Analyze and describe this image in detail in the user's preferred language."
        )

        clean_mime = mime_type.split(";")[0].strip()
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=clean_mime)
        prompt_part = types.Part.from_text(text=prompt)

        try:
            logger.info(f"Gemini streaming rasm tahlili: mime={clean_mime}, hajm={len(image_bytes)} bayt")
            response_stream = await self._client.aio.models.generate_content_stream(
                model=self._model_name,
                contents=[image_part, prompt_part],
                config=self._generation_config,
            )
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            self._handle_api_error(exc, context="stream_image")

    async def stream_audio(
        self,
        file_path: str,
        mime_type: str,
        caption: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream processing of voice messages (.ogg) and audio files (.mp3, .wav, .m4a).

        Args:
            file_path: Local path to the audio file.
            mime_type: Audio MIME type.
            caption: Optional user instruction accompanying the audio.

        Yields:
            Progressive text chunks as they arrive from Gemini.
        """
        prompt = (
            caption.strip()
            if caption and caption.strip()
            else (
                "Please listen carefully to this audio/voice message and respond directly to the "
                "question or request made by the user in the language spoken in the audio."
            )
        )

        clean_mime = mime_type.split(";")[0].strip()
        audio_bytes = await read_file_bytes(file_path)
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=clean_mime)
        prompt_part = types.Part.from_text(text=prompt)

        try:
            logger.info(f"Gemini streaming audio tahlili: fayl={file_path}, mime={clean_mime}")
            response_stream = await self._client.aio.models.generate_content_stream(
                model=self._model_name,
                contents=[audio_part, prompt_part],
                config=self._generation_config,
            )
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            self._handle_api_error(exc, context="stream_audio")

    async def stream_document(
        self,
        file_path: str,
        mime_type: str,
        caption: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Upload document via Gemini File API, stream response, and guarantee deletion.

        Args:
            file_path: Local path to the document (PDF, TXT, CSV, JSON, code, etc.).
            mime_type: MIME type of the document.
            caption: Optional user query or instruction for the document.

        Yields:
            Progressive text chunks as they arrive from Gemini.
        """
        prompt = (
            caption.strip()
            if caption and caption.strip()
            else "Analyze this document in detail and provide a comprehensive response in the user's language."
        )

        clean_mime = mime_type.split(";")[0].strip()
        uploaded_file: types.File | None = None

        try:
            logger.info(f"Gemini File API ga hujjat yuklanmoqda (stream): {file_path} (mime={clean_mime})")
            upload_config = types.UploadFileConfig(mime_type=clean_mime) if clean_mime else None
            uploaded_file = await self._client.aio.files.upload(
                file=file_path,
                config=upload_config,
            )
            logger.info(f"Hujjat yuklandi: name={uploaded_file.name}, state={uploaded_file.state}")

            poll_retries = 0
            while uploaded_file.state == types.FileState.PROCESSING and poll_retries < 30:
                await asyncio.sleep(2)
                uploaded_file = await self._client.aio.files.get(name=uploaded_file.name)
                poll_retries += 1

            if uploaded_file.state == types.FileState.FAILED:
                raise GeminiError("Faylni Gemini serverlarida qayta ishlash muvaffaqiyatsiz tugadi.")

            prompt_part = types.Part.from_text(text=prompt)
            contents = [uploaded_file, prompt_part]

            logger.info(f"Hujjat bo'yicha Gemini streaming javobi so'ralmoqda: {uploaded_file.name}")
            response_stream = await self._client.aio.models.generate_content_stream(
                model=self._model_name,
                contents=contents,
                config=self._generation_config,
            )
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text

        except Exception as exc:
            self._handle_api_error(exc, context="stream_document")

        finally:
            if uploaded_file and uploaded_file.name:
                try:
                    await self._client.aio.files.delete(name=uploaded_file.name)
                    logger.info(f"Gemini File API dan vaqtinchalik fayl o'chirildi: {uploaded_file.name}")
                except Exception as del_err:
                    logger.warning(
                        f"Gemini File API dagi faylni o'chirishda xatolik: {uploaded_file.name}, xato: {del_err}"
                    )

    async def process_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        caption: str | None = None,
    ) -> str:
        """Non-streaming helper for images."""
        result = []
        async for chunk in self.stream_image(image_bytes, mime_type, caption):
            result.append(chunk)
        return "".join(result) or "Rasm bo'yicha tahlil tayyorlab bo'lmadi."

    async def process_audio(
        self,
        file_path: str,
        mime_type: str,
        caption: str | None = None,
    ) -> str:
        """Non-streaming helper for audio."""
        result = []
        async for chunk in self.stream_audio(file_path, mime_type, caption):
            result.append(chunk)
        return "".join(result) or "Audio bo'yicha javob hosil qilib bo'lmadi."

    async def process_document(
        self,
        file_path: str,
        mime_type: str,
        caption: str | None = None,
    ) -> str:
        """Non-streaming helper for documents."""
        result = []
        async for chunk in self.stream_document(file_path, mime_type, caption):
            result.append(chunk)
        return "".join(result) or "Hujjat bo'yicha javob hosil qilib bo'lmadi."


# Global shared instance
gemini_service: GeminiService = GeminiService()
