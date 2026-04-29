import hashlib
from pathlib import Path
from typing import Any

import orjson

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.index import IndexedEvidence
from decathlon_voc_analyzer.schemas.retrieval_cache import (
    QueryEmbeddingCachePayload,
    QueryEmbeddingCacheSignature,
    RerankCachePayload,
    RerankCacheSignature,
)


class RetrievalCacheService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def load_query_embedding(self, signature: QueryEmbeddingCacheSignature) -> list[float] | None:
        path = self._query_embedding_path(signature)
        if not path.exists():
            return None
        payload = QueryEmbeddingCachePayload.model_validate(orjson.loads(path.read_bytes()))
        if payload.signature != signature:
            return None
        return list(payload.vector)

    def save_query_embedding(self, signature: QueryEmbeddingCacheSignature, vector: list[float]) -> str:
        path = self._query_embedding_path(signature)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = QueryEmbeddingCachePayload(signature=signature, vector=list(vector))
        path.write_bytes(orjson.dumps(payload.model_dump(mode="json"), option=orjson.OPT_INDENT_2))
        return str(path)

    def load_rerank(self, signature: RerankCacheSignature) -> list[IndexedEvidence] | None:
        path = self._rerank_path(signature)
        if not path.exists():
            return None
        payload = RerankCachePayload.model_validate(orjson.loads(path.read_bytes()))
        if payload.signature != signature:
            return None
        return payload.reranked

    def save_rerank(self, signature: RerankCacheSignature, reranked: list[IndexedEvidence]) -> str:
        path = self._rerank_path(signature)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = RerankCachePayload(signature=signature, reranked=reranked)
        path.write_bytes(orjson.dumps(payload.model_dump(mode="json"), option=orjson.OPT_INDENT_2))
        return str(path)

    def build_candidate_digest(self, candidates: list[IndexedEvidence]) -> str:
        payload = [self._candidate_cache_payload(candidate) for candidate in candidates]
        return hashlib.sha1(orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)).hexdigest()

    def signature_token(self, signature: QueryEmbeddingCacheSignature | RerankCacheSignature) -> str:
        return hashlib.sha1(orjson.dumps(signature.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS)).hexdigest()

    @property
    def root_dir(self) -> Path:
        return self.settings.indexes_output_dir / "retrieval_cache"

    def _query_embedding_path(self, signature: QueryEmbeddingCacheSignature) -> Path:
        return self.root_dir / "query_embeddings" / f"{self.signature_token(signature)}.json"

    def _rerank_path(self, signature: RerankCacheSignature) -> Path:
        return self.root_dir / "reranks" / f"{self.signature_token(signature)}.json"

    def _candidate_cache_payload(self, candidate: IndexedEvidence) -> dict[str, Any]:
        return {
            "evidence_id": candidate.evidence_id,
            "product_id": candidate.product_id,
            "category_slug": candidate.category_slug,
            "route": candidate.route,
            "doc_type": candidate.doc_type,
            "text_block_id": candidate.text_block_id,
            "image_id": candidate.image_id,
            "source_section": candidate.source_section,
            "image_path": candidate.image_path,
            "variant": candidate.variant,
            "region_id": candidate.region_id,
            "region_label": candidate.region_label,
            "region_box": candidate.region_box,
            "content": candidate.content,
            "language": candidate.language,
            "content_original": candidate.content_original,
            "content_normalized": candidate.content_normalized,
            "score": candidate.score,
        }