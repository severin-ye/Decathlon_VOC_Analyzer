from typing import Literal

from pydantic import BaseModel, Field

from decathlon_voc_analyzer.schemas.review import ReviewAspect, ReviewExtractionResponse


EvidenceRoute = Literal["text", "image"]
AnalysisMode = Literal["heuristic", "llm"]
IssueOwner = Literal["product_issue", "content_presentation", "evidence_gap", "expectation_mismatch"]
EvidenceLevel = Literal["review_only", "partial_product_support", "product_supported", "missing_product_evidence"]
AnswerStatus = Literal["none", "partial", "supported", "contradicted", "unsupported"]
ProcessTraceType = Literal["observation", "evidence_check", "owner_judgement", "action_generation"]
EvidenceSourceType = Literal["review", "product_text", "product_image"]
EvidenceModality = Literal["text", "visual"]
ClaimSource = Literal["strength", "weakness", "controversy", "suggestion", "evidence_gap"]
ClaimSupportStatus = Literal["supported", "partial", "unsupported", "contradicted"]
ClaimSupportType = Literal["review", "product_text", "image", "mixed"]
ClaimRevisionAction = Literal["keep", "downgrade", "remove", "flag"]
RetrievalQualityLabel = Literal["good", "mixed", "bad"]
RetrievalFailureReason = Literal["none", "no_evidence", "modality_miss", "low_recall", "low_precision", "evidence_conflict"]
RetrievalCorrectiveAction = Literal["keep_current", "rewrite_query", "expand_topk", "add_multimodal_route", "filter_noise"]


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
    region_id: str | None = None
    region_label: str | None = None
    region_box: list[int] | None = Field(default=None, min_length=4, max_length=4)
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
    expected_evidence_routes: list[EvidenceRoute] = Field(default_factory=list)
    retrieved: list[RetrievedEvidence]


class RetrievalQualityMetrics(BaseModel):
    retrieval_id: str
    source_aspect: str
    top_k_count: int = Field(ge=0)
    route_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    answer_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    answer_status: AnswerStatus = "none"
    answer_value: str | None = None
    answer_source: EvidenceRoute | None = None
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    score_drift: float = Field(ge=0.0, le=1.0)
    text_coverage: bool = False
    image_coverage: bool = False
    conflict_risk: float = Field(ge=0.0, le=1.0)
    retrieval_quality_label: RetrievalQualityLabel = "mixed"
    failure_reason: RetrievalFailureReason = "none"
    corrective_action: RetrievalCorrectiveAction = "keep_current"
    evaluator_explanation: str | None = None


class RetrievalRuntimeProfile(BaseModel):
    text_embedding_backend: str
    text_embedding_model: str
    image_embedding_backend: str
    image_embedding_model: str | None = None
    reranker_backend: str
    reranker_model: str
    multimodal_reranker_backend: str
    multimodal_reranker_model: str | None = None
    native_multimodal_enabled: bool = False
    summary: str


class AnalysisArtifactBundle(BaseModel):
    analysis_path: str
    feedback_path: str | None = None
    replay_path: str | None = None


class ReplayContinuationSummary(BaseModel):
    replay_path: str
    feedback_path: str | None = None
    previous_analysis_mode: AnalysisMode | None = None
    applied: bool = False
    reviewed_slot_count: int = Field(default=0, ge=0)
    pending_slot_count: int = Field(default=0, ge=0)
    accepted_issue_labels: list[str] = Field(default_factory=list)
    rejected_issue_labels: list[str] = Field(default_factory=list)
    persistent_issue_labels: list[str] = Field(default_factory=list)
    persistent_issue_keys: list[str] = Field(default_factory=list)
    resolved_issue_labels: list[str] = Field(default_factory=list)
    resolved_issue_keys: list[str] = Field(default_factory=list)
    new_issue_labels: list[str] = Field(default_factory=list)
    new_issue_keys: list[str] = Field(default_factory=list)


class AspectAggregate(BaseModel):
    aspect: str
    frequency: int
    positive_ratio: float = Field(ge=0.0, le=1.0)
    negative_ratio: float = Field(ge=0.0, le=1.0)
    neutral_ratio: float = Field(ge=0.0, le=1.0)
    mixed_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    scenes: dict[str, int] = Field(default_factory=dict)
    representative_review_ids: list[str] = Field(default_factory=list)


class ProductImpressionItem(BaseModel):
    aspect: str
    aspect_frequency: int = Field(ge=0)
    positive_ratio: float = Field(ge=0.0, le=1.0)
    negative_ratio: float = Field(ge=0.0, le=1.0)
    mixed_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    scene_distribution: dict[str, int] = Field(default_factory=dict)
    representative_review_ids: list[str] = Field(default_factory=list)


class CustomerImpressionItem(BaseModel):
    segment_label: str
    scene: str
    review_count: int = Field(ge=0)
    focus_aspects: list[str] = Field(default_factory=list)
    positive_aspects: list[str] = Field(default_factory=list)
    negative_aspects: list[str] = Field(default_factory=list)
    representative_review_ids: list[str] = Field(default_factory=list)


class AspectRelationItem(BaseModel):
    relation_type: str
    source_aspect: str
    target_aspect: str
    summary: str
    review_ids: list[str] = Field(default_factory=list)


class SupportingEvidence(BaseModel):
    review_ids: list[str] = Field(default_factory=list)
    product_text_block_ids: list[str] = Field(default_factory=list)
    product_image_ids: list[str] = Field(default_factory=list)


class EvidenceNode(BaseModel):
    evidence_node_id: str
    source_type: EvidenceSourceType
    source_id: str
    modality: EvidenceModality
    content: str | None = None
    aspect_tags: list[str] = Field(default_factory=list)
    route: EvidenceRoute | None = None
    source_section: str | None = None
    region_id: str | None = None
    region_label: str | None = None
    image_path: str | None = None


class ConfidenceBreakdown(BaseModel):
    extract_confidence: float = Field(ge=0.0, le=1.0)
    question_confidence: float = Field(ge=0.0, le=1.0)
    evidence_confidence: float = Field(ge=0.0, le=1.0)
    consistency_confidence: float = Field(ge=0.0, le=1.0)
    final_confidence: float = Field(ge=0.0, le=1.0)


class ClaimAttribution(BaseModel):
    claim_id: str
    claim_text: str
    claim_source: ClaimSource
    support_status: ClaimSupportStatus
    support_type: ClaimSupportType | None = None
    support_ids: list[str] = Field(default_factory=list)
    route_sources: list[EvidenceRoute] = Field(default_factory=list)
    evidence_gap: str | None = None
    revision_action: ClaimRevisionAction = "keep"
    revised_claim: str | None = None


class EvidenceGapItem(BaseModel):
    label: str
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_aspect: str | None = None
    supporting_evidence: SupportingEvidence = Field(default_factory=SupportingEvidence)
    owner: IssueOwner = "evidence_gap"
    evidence_level: EvidenceLevel = "missing_product_evidence"
    confidence_breakdown: ConfidenceBreakdown | None = None


class ProcessTraceItem(BaseModel):
    trace_type: ProcessTraceType
    aspect: str
    summary: str
    suggestion_id: str | None = None
    owner: IssueOwner | None = None
    supporting_evidence: SupportingEvidence = Field(default_factory=SupportingEvidence)
    confidence_breakdown: ConfidenceBreakdown | None = None


class InsightItem(BaseModel):
    label: str
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: SupportingEvidence
    owner: IssueOwner = "product_issue"
    evidence_level: EvidenceLevel = "review_only"
    confidence_breakdown: ConfidenceBreakdown | None = None


class ImprovementSuggestion(BaseModel):
    suggestion: str
    suggestion_type: Literal["structural", "perception"]
    reason: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: SupportingEvidence
    owner: IssueOwner = "content_presentation"
    replay_note: str | None = None
    confidence_breakdown: ConfidenceBreakdown | None = None


class ProductAnalysisReport(BaseModel):
    product_id: str
    category_slug: str | None = None
    answer: str
    strengths: list[InsightItem] = Field(default_factory=list)
    weaknesses: list[InsightItem] = Field(default_factory=list)
    controversies: list[InsightItem] = Field(default_factory=list)
    evidence_gaps: list[EvidenceGapItem] = Field(default_factory=list)
    product_impressions: list[ProductImpressionItem] = Field(default_factory=list)
    customer_impressions: list[CustomerImpressionItem] = Field(default_factory=list)
    aspect_relations: list[AspectRelationItem] = Field(default_factory=list)
    applicable_scenes: list[str] = Field(default_factory=list)
    supporting_aspects: list[str] = Field(default_factory=list)
    supporting_reviews: list[str] = Field(default_factory=list)
    supporting_review_evidence: SupportingEvidence = Field(default_factory=SupportingEvidence)
    supporting_product_evidence: SupportingEvidence
    evidence_nodes: list[EvidenceNode] = Field(default_factory=list)
    claim_attributions: list[ClaimAttribution] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    suggestions: list[ImprovementSuggestion] = Field(default_factory=list)


class ProductAnalysisRequest(BaseModel):
    product_id: str
    category_slug: str | None = None
    max_reviews: int | None = Field(default=None, ge=1)
    use_llm: bool = True
    persist_artifact: bool = False
    use_replay: bool = False
    top_k_per_route: int = Field(default=2, ge=1, le=5)
    questions_per_aspect: int = Field(default=2, ge=1, le=5)


class ProductAnalysisResponse(BaseModel):
    schema_version: str = "1.1.0"
    analysis_mode: AnalysisMode
    extraction: ReviewExtractionResponse
    questions: list[RetrievalQuestion]
    retrievals: list[RetrievalRecord]
    retrieval_quality: list[RetrievalQualityMetrics] = Field(default_factory=list)
    retrieval_runtime: RetrievalRuntimeProfile
    aggregates: list[AspectAggregate]
    report: ProductAnalysisReport
    trace: list[ProcessTraceItem] = Field(default_factory=list)
    replay_summary: ReplayContinuationSummary | None = None
    artifact_bundle: AnalysisArtifactBundle | None = None
    artifact_path: str | None = None
    warnings: list[str] = Field(default_factory=list)