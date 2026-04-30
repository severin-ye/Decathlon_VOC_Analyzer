from pathlib import Path
import hashlib

import orjson

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.question_cache import (
    QuestionGenerationCachePayload,
    QuestionGenerationCacheSignature,
)


class QuestionGenerationCacheService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def load(self, signature: QuestionGenerationCacheSignature) -> QuestionGenerationCachePayload | None:
        path = self._cache_path(signature)
        if not path.exists():
            return None
        payload = QuestionGenerationCachePayload.model_validate(orjson.loads(path.read_bytes()))
        if payload.signature != signature:
            return None
        return payload

    def save(self, signature: QuestionGenerationCacheSignature, payload: QuestionGenerationCachePayload) -> str:
        path = self._cache_path(signature)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(orjson.dumps(payload.model_dump(mode="json"), option=orjson.OPT_INDENT_2))
        return str(path)

    def _cache_root(self) -> Path:
        return self.settings.reports_output_dir / "question_cache"

    def _cache_path(self, signature: QuestionGenerationCacheSignature) -> Path:
        return self._cache_root() / f"{self.signature_token(signature)}.json"

    def signature_token(self, signature: QuestionGenerationCacheSignature) -> str:
        return hashlib.sha1(
            orjson.dumps(signature.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS)
        ).hexdigest()
