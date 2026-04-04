"""
Speech-to-Text Service — uses OpenAI Whisper-1 to transcribe audio messages.

Supports audio from WhatsApp (voice notes / audio messages) and Telegram voice messages.
"""

import logging
import tempfile
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize OpenAI async client
_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def download_whatsapp_media(media_id: str, api_token: str | None = None) -> bytes:
    """
    Download media from WhatsApp Cloud API.

    WhatsApp flow:
    1. GET /{media_id} → returns a JSON with a `url` field
    2. GET that `url` with auth header → returns the raw binary file

    Args:
        media_id: The WhatsApp media ID from the incoming message.
        api_token: Per-hotel API token (falls back to global).

    Returns:
        Raw audio bytes.
    """
    token = api_token or settings.WHATSAPP_API_TOKEN
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Get the media URL
        meta_url = f"{settings.WHATSAPP_API_URL}/{media_id}"
        resp = await client.get(meta_url, headers=headers)
        resp.raise_for_status()
        media_url = resp.json().get("url")

        if not media_url:
            raise ValueError(f"No URL returned for media_id={media_id}")

        # Step 2: Download the actual file
        file_resp = await client.get(media_url, headers=headers)
        file_resp.raise_for_status()
        return file_resp.content


async def download_telegram_voice(file_id: str, bot_token: str) -> bytes:
    """
    Download a voice/audio file from Telegram Bot API.

    Telegram flow:
    1. getFile → returns file_path
    2. Download from https://api.telegram.org/file/bot{token}/{file_path}

    Args:
        file_id: The Telegram file_id from the voice message.
        bot_token: The Telegram bot token.

    Returns:
        Raw audio bytes.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Get file path
        url = f"https://api.telegram.org/bot{bot_token}/getFile"
        resp = await client.get(url, params={"file_id": file_id})
        resp.raise_for_status()
        result = resp.json().get("result", {})
        file_path = result.get("file_path")

        if not file_path:
            raise ValueError(f"No file_path returned for file_id={file_id}")

        # Step 2: Download the file
        download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        file_resp = await client.get(download_url)
        file_resp.raise_for_status()
        return file_resp.content


async def transcribe_audio(audio_bytes: bytes, file_extension: str = "ogg") -> str:
    """
    Transcribe audio bytes to text using OpenAI Whisper-1.

    Args:
        audio_bytes: Raw audio file content.
        file_extension: File extension hint (ogg, mp3, wav, m4a, etc.).

    Returns:
        Transcribed text string.
    """
    try:
        # Write to a temporary file — OpenAI SDK requires a file-like object
        with tempfile.NamedTemporaryFile(suffix=f".{file_extension}", delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            tmp.seek(0)

            transcript = await _openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=Path(tmp.name),
                language="ar",  # Default Arabic — Whisper auto-detects if wrong
            )

        text = transcript.text.strip()
        logger.info(f"Whisper transcription ({len(audio_bytes)} bytes): {text[:80]}...")
        return text

    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}", exc_info=True)
        return ""
