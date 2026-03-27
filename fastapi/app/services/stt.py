"""로컬 오디오 파일을 GPT-4o-mini-transcribe로 전사."""

from pathlib import Path
from typing import Any

from openai import OpenAI

from app.core.config import get_settings


def transcribe_local_audio(file_path: str) -> dict[str, Any]:
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
