import math
import re
from collections import Counter

from decathlon_voc_analyzer.core.config import get_settings


TOKEN_RE = re.compile(r"[\w\-\u4e00-\u9fff가-힣]+", re.UNICODE)


class EmbeddingService:
    VECTOR_DIMENSION = 64

    def __init__(self) -> None:
        self.settings = get_settings()

    def embed_text(self, text: str) -> list[float]:
        return self._hashed_embedding(text)

    def embed_image_proxy_text(self, text: str) -> list[float]:
        return self._hashed_embedding(text)

    def similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        score = sum(a * b for a, b in zip(left, right))
        return max(0.0, min(1.0, float(score)))

    def _hashed_embedding(self, text: str) -> list[float]:
        tokens = [token.lower() for token in TOKEN_RE.findall(text.lower()) if len(token) > 1]
        counts = Counter(tokens)
        vector = [0.0] * self.VECTOR_DIMENSION
        for token, count in counts.items():
            bucket = hash(token) % self.VECTOR_DIMENSION
            vector[bucket] += float(count)
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]