from typing import Literal

from pydantic import BaseModel, Field

from decathlon_voc_analyzer.schemas.index import IndexedEvidence
from decathlon_voc_analyzer.schemas.analysis import RetrievalQuestion, RetrievalRecord, RetrievalQualityMetrics


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


# ---------- Per-question retrieval / quality / corrective checkpoints ---------- #


class RetrievalStageCheckpointSignature(BaseModel):
    question_id: str
    question_digest: str
    top_k_per_route: int
    use_llm: bool
    ablation_no_image: bool
    ablation_no_reranking: bool
    index_digest: str
    embedding_backend: str
    reranker_backend: str
    prompt_variant: str


class RetrievalStageCheckpointPayload(BaseModel):
    product_id: str
    category_slug: str | None = None
    stage: Literal["initial", "quality", "corrective", "final"]
    created_at: str
    signature: RetrievalStageCheckpointSignature
    question: RetrievalQuestion | None = None
    initial_retrieval: RetrievalRecord | None = None
    quality_metrics: RetrievalQualityMetrics | None = None
    corrective_question: RetrievalQuestion | None = None
    corrective_retrieval: RetrievalRecord | None = None
    corrective_metric: RetrievalQualityMetrics | None = None
    corrective_applied: bool = False
    final_retrieval: RetrievalRecord | None = None
    final_quality: RetrievalQualityMetrics | None = None
