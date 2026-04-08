import math
import re
from collections import Counter

from openai import OpenAI

from decathlon_voc_analyzer.core.config import get_settings


TOKEN_RE = re.compile(r"[\w\-\u4e00-\u9fff가-힣]+", re.UNICODE)


class EmbeddingService:
    VECTOR_DIMENSION = 64

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: OpenAI | None = None
        self._vector_size: int | None = None

    def embed_text(self, text: str) -> list[float]:
        if self.settings.embedding_backend == "api" and self.settings.qwen_plus_api_key:
            try:
                return self._api_embedding(text)
            except Exception:
                return self._hashed_embedding(text)
        return self._hashed_embedding(text)

    def embed_image_proxy_text(self, text: str) -> list[float]:
        return self.embed_text(text)

    def similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        score = sum(a * b for a, b in zip(left, right))
        return max(0.0, min(1.0, float(score)))

    def vector_size(self) -> int:
        if self._vector_size is not None:
            return self._vector_size
        if self.settings.embedding_backend == "api" and self.settings.qwen_plus_api_key:
            try:
                self._vector_size = len(self._api_embedding("dimension probe"))
                return self._vector_size
            except Exception:
                self._vector_size = self.VECTOR_DIMENSION
                return self._vector_size
        self._vector_size = self.VECTOR_DIMENSION
        return self._vector_size

    def _api_embedding(self, text: str) -> list[float]:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.settings.qwen_plus_api_key,
                base_url=self.settings.qwen_base_url,
            )
        response = self._client.embeddings.create(
            model=self.settings.qwen_embedding_model,
            input=text,
        )
        vector = list(response.data[0].embedding)
        self._vector_size = len(vector)
        return vector

    def _hashed_embedding(self, text: str) -> list[float]:
        tokens = [token.lower() for token in TOKEN_RE.findall(text.lower()) if len(token) > 1]
        counts = Counter(tokens)
        vector = [0.0] * self.VECTOR_DIMENSION
        for token, count in counts.items():
            bucket = hash(token) % self.VECTOR_DIMENSION
            vector[bucket] += float(count)
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]