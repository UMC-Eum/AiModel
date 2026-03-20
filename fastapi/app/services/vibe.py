"""Vector math utilities for vibe scoring."""

from typing import Sequence
import math


def normalize_vector(values: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in values)) or 1.0
    return [x / norm for x in values]


def score_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Compute cosine similarity between two vectors."""
    denom = (math.sqrt(sum(x * x for x in a)) or 1.0) * (math.sqrt(sum(y * y for y in b)) or 1.0)
    return sum(x * y for x, y in zip(a, b)) / denom
