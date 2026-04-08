from typing import Literal

from pydantic import BaseModel, Field

from decathlon_voc_analyzer.models.review import ReviewAspect, ReviewExtractionResponse


EvidenceRoute = Literal["text", "image"]
AnalysisMode = Literal["heuristic", "llm"]


class RetrievalQuestion(BaseModel):
    question_id: str
    source_review_id: str
    source_aspect: str
    source_aspect_id: str
    question: str
    rationale: str
    expected_evidence_routes: list[EvidenceRoute] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class RetrievedEvidence(BaseModel):
    product_id: str
    route: EvidenceRoute
    text_block_id: str | None = None
    image_id: str | None = None
    source_section: str | None = None
    image_path: str | None = None
    content_preview: str | None = None
    embedding_score: float = Field(ge=0.0, le=1.0)
    rerank_score: float | None = Field(default=None, ge=0.0, le=1.0)


class RetrievalRecord(BaseModel):
    retrieval_id: str
    product_id: str
    query: str
    source_review_id: str
    source_aspect: str
    source_question_id: str
    source_question: str
    source_evidence_span: str
    retrieved: list[RetrievedEvidence]


class AspectAggregate(BaseModel):
    aspect: str
    frequency: int
    positive_ratio: float = Field(ge=0.0, le=1.0)
    negative_ratio: float = Field(ge=0.0, le=1.0)
    neutral_ratio: float = Field(ge=0.0, le=1.0)
    scenes: dict[str, int] = Field(default_factory=dict)
    representative_review_ids: list[str] = Field(default_factory=list)


class SupportingEvidence(BaseModel):
    review_ids: list[str] = Field(default_factory=list)
    product_text_block_ids: list[str] = Field(default_factory=list)
    product_image_ids: list[str] = Field(default_factory=list)


class InsightItem(BaseModel):
    label: str
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: SupportingEvidence


class ImprovementSuggestion(BaseModel):
    suggestion: str
    suggestion_type: Literal["structural", "perception"]
    reason: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: SupportingEvidence


class ProductAnalysisReport(BaseModel):
    product_id: str
    category_slug: str | None = None
    answer: str
    strengths: list[InsightItem] = Field(default_factory=list)
    weaknesses: list[InsightItem] = Field(default_factory=list)
    controversies: list[InsightItem] = Field(default_factory=list)
    applicable_scenes: list[str] = Field(default_factory=list)
    supporting_aspects: list[str] = Field(default_factory=list)
    supporting_reviews: list[str] = Field(default_factory=list)
    supporting_product_evidence: SupportingEvidence
    confidence: float = Field(ge=0.0, le=1.0)
    suggestions: list[ImprovementSuggestion] = Field(default_factory=list)


class ProductAnalysisRequest(BaseModel):
    product_id: str
    category_slug: str | None = None
    max_reviews: int | None = Field(default=None, ge=1)
    use_llm: bool = True
    persist_artifact: bool = False
    top_k_per_route: int = Field(default=2, ge=1, le=5)
    questions_per_aspect: int = Field(default=2, ge=1, le=5)


class ProductAnalysisResponse(BaseModel):
    analysis_mode: AnalysisMode
    extraction: ReviewExtractionResponse
    questions: list[RetrievalQuestion]
    retrievals: list[RetrievalRecord]
    aggregates: list[AspectAggregate]
    report: ProductAnalysisReport
    artifact_path: str | None = None
    warnings: list[str] = Field(default_factory=list)