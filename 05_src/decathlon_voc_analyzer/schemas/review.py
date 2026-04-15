from typing import Literal

from pydantic import BaseModel, Field


AspectSentiment = Literal["positive", "negative", "neutral", "mixed"]
ExtractionMode = Literal["llm", "heuristic"]


class ReviewInput(BaseModel):
    review_id: str | None = None
    product_id: str | None = None
    rating: int | None = None
    review_text: str
    language_hint: str | None = None


class PreprocessedReview(BaseModel):
    review_id: str
    product_id: str | None = None
    original_text: str
    cleaned_text: str
    rating: int | None = None
    language_hint: str | None = None
    is_informative: bool
    skip_reason: str | None = None


class ReviewAspect(BaseModel):
    aspect_id: str
    review_id: str
    product_id: str | None = None
    aspect: str
    sentiment: AspectSentiment
    opinion: str
    evidence_span: str
    usage_scene: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_mode: ExtractionMode


class ReviewExtractionRequest(BaseModel):
    product_id: str | None = None
    category_slug: str | None = None
    reviews: list[ReviewInput] | None = None
    max_reviews: int | None = Field(default=None, ge=1)
    use_llm: bool = True
    persist_artifact: bool = False
    include_non_informative: bool = False


class ReviewRatingAllocation(BaseModel):
    rating: int | None = None
    configured_ratio: float = Field(ge=0.0, le=1.0)
    target_count: int = Field(ge=0)
    available_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    redistributed_in_count: int = Field(default=0, ge=0)
    shortfall_count: int = Field(default=0, ge=0)


class ReviewSamplingPlan(BaseModel):
    profile_name: str
    requested_reviews: int = Field(ge=1)
    total_available_reviews: int = Field(ge=0)
    selected_reviews: int = Field(ge=0)
    fallback_order: list[int] = Field(default_factory=list)
    allocations: list[ReviewRatingAllocation] = Field(default_factory=list)


class ReviewExtractionResponse(BaseModel):
    product_id: str | None = None
    category_slug: str | None = None
    extraction_mode: ExtractionMode
    preprocessed_reviews: list[PreprocessedReview]
    sampling_plan: ReviewSamplingPlan | None = None
    aspects: list[ReviewAspect]
    skipped_review_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifact_path: str | None = None