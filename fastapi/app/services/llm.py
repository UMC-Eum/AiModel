"""LLM prompt helpers for summary, keywords, and vibe vector."""

from typing import Any, Sequence


def summarize_transcript(transcript: str) -> str:
    """Return a concise summary for onboarding."""
    raise NotImplementedError("Connect to LLM provider and prompt")


def extract_keywords(transcript: str, fixed_keywords: Sequence[str]) -> dict[str, list[dict[str, float]]]:
    """Map free-form transcript to fixed keyword set with scores."""
    raise NotImplementedError("Implement keyword extraction logic")


def generate_vibe_vector(transcript: str) -> list[float]:
    """Produce normalized vibe vector from transcript semantics."""
    raise NotImplementedError("Generate embedding and normalization")
