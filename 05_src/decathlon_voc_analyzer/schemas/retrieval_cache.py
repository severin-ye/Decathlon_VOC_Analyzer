from typing import Literal

from pydantic import BaseModel, Field

from decathlon_voc_analyzer.schemas.index import IndexedEvidence


QueryEmbeddingBackendKind = Literal["api", "clip", "hash"]
RerankBackendKind = Literal["api", "heuristic", "qwen_vl", "local_qwen3", "local_qwen3_vl"]


class QueryEmbeddingCacheSignature(BaseModel):
    route: Literal["text", "image"]
    query: str
    backend_kind: QueryEmbeddingBackendKind
    model_name: str
    base_url: str | None = None


class QueryEmbeddingCachePayload(BaseModel):
    signature: QueryEmbeddingCacheSignature
    vector: list[float] = Field(default_factory=list)


class RerankCacheSignature(BaseModel):
    route: Literal["text", "image"]
    query: str
    use_llm: bool
    backend_kind: RerankBackendKind
    candidate_count: int = Field(ge=0)
    candidate_digest: str
    base_url: str | None = None
    reranker_model: str | None = None
    multimodal_reranker_model: str | None = None


class RerankCachePayload(BaseModel):
    signature: RerankCacheSignature
    reranked: list[IndexedEvidence] = Field(default_factory=list)