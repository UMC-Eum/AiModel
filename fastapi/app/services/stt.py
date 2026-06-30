"""오디오 파일을 GPT-4o-mini-transcribe로 전사."""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from openai import OpenAI

from app.core.config import get_settings

SUPPORTED_AUDIO_SUFFIXES = {".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".oga", ".ogg", ".wav", ".webm"}


class AudioDownloadError(Exception):
    """Presigned URL 오디오 다운로드 실패."""


def _transcribe_file(file_path: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다 (.env에 추가).")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {file_path}")

    client = OpenAI(api_key=settings.openai_api_key)

    with path.open("rb") as audio_file:
        result = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file,
        )

    # OpenAI Audio API는 text 필드를 반환함
    return {"transcript": result.text}


def _audio_suffix(audio_url: str) -> str:
    suffix = Path(urlparse(audio_url).path).suffix.lower()
    return suffix if suffix in SUPPORTED_AUDIO_SUFFIXES else ".mp3"


async def transcribe_audio_url(audio_url: str) -> dict[str, Any]:
    settings = get_settings()
    parsed = urlparse(audio_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise AudioDownloadError("audioUrl은 https URL이어야 합니다.")

    max_bytes = settings.max_audio_download_mb * 1024 * 1024
    timeout = httpx.Timeout(settings.audio_download_timeout_seconds)
    temp_path = None

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            async with client.stream("GET", audio_url) as response:
                if response.status_code != 200:
                    raise AudioDownloadError(f"audioUrl 다운로드 실패(status={response.status_code})")

                content_length = response.headers.get("content-length")
                if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                    raise AudioDownloadError(f"오디오 파일은 {settings.max_audio_download_mb}MB를 초과할 수 없습니다.")

                downloaded = 0
                with tempfile.NamedTemporaryFile(delete=False, suffix=_audio_suffix(audio_url)) as temp_file:
                    temp_path = temp_file.name
                    async for chunk in response.aiter_bytes():
                        downloaded += len(chunk)
                        if downloaded > max_bytes:
                            raise AudioDownloadError(f"오디오 파일은 {settings.max_audio_download_mb}MB를 초과할 수 없습니다.")
                        temp_file.write(chunk)

        return await asyncio.to_thread(_transcribe_file, temp_path)
    except httpx.HTTPError as exc:
        raise AudioDownloadError(f"audioUrl 다운로드 실패: {exc}") from exc
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
