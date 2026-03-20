"""Speech-to-text integration placeholders."""

from typing import Any


def transcribe_from_s3(object_url: str) -> dict[str, Any]:
    """Fetch audio from S3 (or pre-signed URL) and return transcript metadata."""
    raise NotImplementedError("Wire AWS Transcribe or chosen STT provider")
