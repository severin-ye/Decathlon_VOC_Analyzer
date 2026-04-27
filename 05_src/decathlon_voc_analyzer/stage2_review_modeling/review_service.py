import hashlib
import re

import orjson
from pydantic import BaseModel, Field

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.llm import QwenChatGateway
from decathlon_voc_analyzer.schemas.review import (
    AspectSentiment,
    ExtractionMode,
    PreprocessedReview,
    ReviewAspect,
    ReviewExtractionRequest,
    ReviewExtractionResponse,
    ReviewInput,
    ReviewSamplingPlan,
)
from decathlon_voc_analyzer.prompts import get_prompt_template, get_prompt_variant
from decathlon_voc_analyzer.stage1_dataset.dataset_service import DatasetService
from decathlon_voc_analyzer.stage2_review_modeling.deduplication_service import ReviewDeduplicationService
from decathlon_voc_analyzer.stage2_review_modeling.review_sampling_service import ReviewSamplingService


LOW_SIGNAL_REVIEW_PATTERNS = {
    "ok",
    "good",
    "great",
    "top",
    "awesome",
    "ras",
    "average",
    "avrage",
}

ASPECT_KEYWORDS = {
    "capacity_storage": [
        "passport",
        "cards",
        "card",
        "storage",
        "compartment",
        "pocket",
        "capacity",
        "fit",
        "sığ",
        "scomparti",
        "porta documentos",
    ],
    "portability_size": [
        "small",
        "light",
        "lightweight",
        "compact",
        "petit",
        "hafif",
        "pocket",
    ],
    "usability": [
        "practical",
        "convenient",
        "easy",
        "ergonomic",
        "handy",
        "use",
        "daily",
        "travel",
        "travelling",
        "voyage",
        "旅行",
        "pratique",
        "comodo",
        "useful",
    ],
    "durability_quality": [
        "durable",
        "quality",
        "sturdy",
        "solid",
        "robust",
        "kaliteli",
        "dayan",
        "bonne qualité",
    ],
    "value_price": [
        "price",
        "cheap",
        "value",
        "worth",
        "gas",
        "가성비",
        "uygun fiyat",
    ],
    "material_rigidity": [
        "hard",
        "stiff",
        "s硬",
        "rigid",
        "leather",
        "non leather",
    ],
}

NEGATIVE_HINTS = ["hard", "stiff", "drawback", "bad", "poor", "not", "average", "small"]
USAGE_SCENES = {
    "travel": ["travel", "travelling", "trip", "passport", "voyage"],
    "daily_use": ["daily", "everyday", "quotidianamente", "wallet"],
    "outdoor_sports": ["bike", "biking", "camping", "outdoor", "sports"],
    "summer": ["summer"],
}


class ReviewAspectCandidate(BaseModel):
    aspect: str = "overall_experience"
    sentiment: str = "neutral"
    opinion: str = ""
    evidence_span: str = ""
    usage_scene: str | None = None
    confidence: float = Field(default=0.82, ge=0.0, le=1.0)


class ReviewExtractionPayload(BaseModel):
    aspects: list[ReviewAspectCandidate] = Field(default_factory=list)


class ReviewTranslationItem(BaseModel):
    user_id: str | None = None
    rating: int | None = None
    content: str = ""


class ReviewTranslationPayload(BaseModel):
    reviews: list[ReviewTranslationItem] = Field(default_factory=list)


class ReviewExtractionService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.dataset_service = DatasetService()
        self.chat_gateway = QwenChatGateway()
        self.deduplication_service = ReviewDeduplicationService()
        self.review_sampling_service = ReviewSamplingService()

    def extract(self, request: ReviewExtractionRequest) -> ReviewExtractionResponse:
        reviews, product_id, category_slug, sampling_plan = self._resolve_reviews(request)
        preprocessed_reviews = [self._preprocess_review(review) for review in reviews]

        aspects: list[ReviewAspect] = []
        skipped_review_ids: list[str] = []
        warnings: list[str] = []
        llm_requested = request.use_llm and bool(self.settings.qwen_plus_api_key)
        extraction_mode: ExtractionMode = "llm" if llm_requested else "heuristic"

        for review in preprocessed_reviews:
            if not review.is_informative and not request.include_non_informative:
                skipped_review_ids.append(review.review_id)
                continue

            extracted_aspects: list[ReviewAspect]
            if llm_requested:
                try:
                    extracted_aspects = self._extract_with_llm(review)
                except Exception as exc:
                    extraction_mode = "heuristic"
                    warnings.append(f"{review.review_id}: llm extraction failed, fallback to heuristic ({exc})")
                    extracted_aspects = self._extract_with_heuristic(review)
            else:
                extracted_aspects = self._extract_with_heuristic(review)

            if not extracted_aspects:
                skipped_review_ids.append(review.review_id)
                continue
            aspects.extend(extracted_aspects)

        artifact_path: str | None = None
        aspects = self.deduplication_service.deduplicate(aspects)
        if request.persist_artifact:
            artifact_path = self._persist_result(
                product_id=product_id,
                category_slug=category_slug,
                extraction_mode=extraction_mode,
                preprocessed_reviews=preprocessed_reviews,
                sampling_plan=sampling_plan,
                aspects=aspects,
                skipped_review_ids=skipped_review_ids,
                warnings=warnings,
            )

        return ReviewExtractionResponse(
            product_id=product_id,
            category_slug=category_slug,
            extraction_mode=extraction_mode,
            preprocessed_reviews=preprocessed_reviews,
            sampling_plan=sampling_plan,
            aspects=aspects,
            skipped_review_ids=skipped_review_ids,
            warnings=warnings,
            artifact_path=artifact_path,
        )

    def _resolve_reviews(
        self, request: ReviewExtractionRequest
    ) -> tuple[list[ReviewInput], str | None, str | None, ReviewSamplingPlan | None]:
        if request.reviews:
            reviews, sampling_plan = self.review_sampling_service.select_reviews(
                reviews=request.reviews,
                max_reviews=request.max_reviews,
            )
            product_id = request.product_id or next(
                (review.product_id for review in reviews if review.product_id),
                None,
            )
            if self._should_project_reviews_to_english(request):
                reviews = self._project_reviews_to_english(reviews)
            return reviews, product_id, request.category_slug, sampling_plan

        if not request.product_id:
            raise ValueError("product_id is required when reviews are not provided")

        package = self.dataset_service.load_product_package(
            product_id=request.product_id,
            category_slug=request.category_slug,
        )
        source_reviews = [
            ReviewInput(
                review_id=review.review_id,
                product_id=review.product_id,
                rating=review.rating,
                review_text=review.review_text,
                language_hint=review.language_hint,
            )
            for review in package.reviews
        ]
        reviews, sampling_plan = self.review_sampling_service.select_reviews(
            reviews=source_reviews,
            max_reviews=request.max_reviews,
        )
        if self._should_project_reviews_to_english(request):
            reviews = self._project_reviews_to_english(reviews)
        return reviews, package.product_id, package.category_slug, sampling_plan

    def _should_project_reviews_to_english(self, request: ReviewExtractionRequest) -> bool:
        return (
            get_prompt_variant() == "main"
            and bool(self.settings.qwen_plus_api_key)
            and request.use_llm
        )

    def _project_reviews_to_english(self, reviews: list[ReviewInput], batch_size: int = 25) -> list[ReviewInput]:
        translated_reviews: list[ReviewInput] = []
        for start in range(0, len(reviews), batch_size):
            batch = reviews[start:start + batch_size]
            payload = {
                "start_index": start,
                "reviews": [
                    {
                        "user_id": review.review_id or review.product_id,
                        "rating": review.rating,
                        "content": review.review_text,
                    }
                    for review in batch
                ],
            }
            try:
                parsed = self.chat_gateway.invoke_json(
                    prompt_template=get_prompt_template("review_translation_system"),
                    variables={"payload": payload},
                    schema=ReviewTranslationPayload,
                    temperature=0,
                )
            except Exception:
                return reviews
            translated_batch = parsed.get("reviews") or []
            if len(translated_batch) != len(batch):
                return reviews
            for source_review, translated_item in zip(batch, translated_batch, strict=True):
                translated_reviews.append(
                    ReviewInput(
                        review_id=source_review.review_id,
                        product_id=source_review.product_id,
                        rating=source_review.rating,
                        review_text=str(translated_item.get("content") or source_review.review_text),
                        language_hint="en",
                    )
                )
        return translated_reviews

    def _preprocess_review(self, review: ReviewInput) -> PreprocessedReview:
        original_text = review.review_text
        cleaned_text = self._clean_text(original_text)
        lowered = cleaned_text.lower()
        is_informative = bool(cleaned_text)
        skip_reason: str | None = None

        if not cleaned_text:
            is_informative = False
            skip_reason = "empty_review"
        elif lowered in LOW_SIGNAL_REVIEW_PATTERNS and len(cleaned_text) <= 12:
            is_informative = False
            skip_reason = "low_signal_review"
        elif len(cleaned_text) < 4:
            is_informative = False
            skip_reason = "too_short"

        return PreprocessedReview(
            review_id=review.review_id or self._make_id(review.product_id or "unknown", original_text),
            product_id=review.product_id,
            original_text=original_text,
            cleaned_text=cleaned_text,
            rating=review.rating,
            language_hint=review.language_hint or self._guess_language(cleaned_text),
            is_informative=is_informative,
            skip_reason=skip_reason,
        )

    def _extract_with_llm(self, review: PreprocessedReview) -> list[ReviewAspect]:
        payload = {
            "review_id": review.review_id,
            "product_id": review.product_id,
            "rating": review.rating,
            "language_hint": review.language_hint,
            "review_text": review.cleaned_text,
        }
        parsed = self.chat_gateway.invoke_json(
            prompt_template=get_prompt_template("review_extraction_system"),
            variables={"payload": payload},
            schema=ReviewExtractionPayload,
        )
        raw_aspects = parsed.get("aspects") or []
        aspects: list[ReviewAspect] = []
        for index, item in enumerate(raw_aspects, start=1):
            if not isinstance(item, dict):
                continue
            aspect_name = str(item.get("aspect") or "overall_experience").strip() or "overall_experience"
            opinion = self._clean_text(str(item.get("opinion") or review.cleaned_text)) or review.cleaned_text
            evidence_span = self._clean_text(str(item.get("evidence_span") or review.cleaned_text)) or review.cleaned_text
            confidence = self._clamp_confidence(item.get("confidence"), default=0.82)
            aspects.append(
                ReviewAspect(
                    aspect_id=f"{review.review_id}_aspect_{index:02d}",
                    review_id=review.review_id,
                    product_id=review.product_id,
                    aspect=aspect_name,
                    sentiment=self._normalize_sentiment(item.get("sentiment")),
                    opinion=opinion,
                    evidence_span=evidence_span,
                    usage_scene=self._clean_text(item.get("usage_scene")),
                    confidence=confidence,
                    extraction_mode="llm",
                )
            )
        return aspects

    def _extract_with_heuristic(self, review: PreprocessedReview) -> list[ReviewAspect]:
        text = review.cleaned_text
        lowered = text.lower()
        matched_aspects: list[str] = []
        for aspect_name, keywords in ASPECT_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                matched_aspects.append(aspect_name)

        if not matched_aspects:
            matched_aspects = ["overall_experience"]

        usage_scene = self._detect_usage_scene(lowered)
        sentiment = self._infer_sentiment(review.rating, lowered)
        confidence = 0.56 if matched_aspects == ["overall_experience"] else 0.68

        return [
            ReviewAspect(
                aspect_id=f"{review.review_id}_aspect_{index:02d}",
                review_id=review.review_id,
                product_id=review.product_id,
                aspect=aspect_name,
                sentiment=sentiment,
                opinion=text,
                evidence_span=text,
                usage_scene=usage_scene,
                confidence=confidence,
                extraction_mode="heuristic",
            )
            for index, aspect_name in enumerate(dict.fromkeys(matched_aspects), start=1)
        ]

    def _persist_result(
        self,
        product_id: str | None,
        category_slug: str | None,
        extraction_mode: ExtractionMode,
        preprocessed_reviews: list[PreprocessedReview],
        sampling_plan: ReviewSamplingPlan | None,
        aspects: list[ReviewAspect],
        skipped_review_ids: list[str],
        warnings: list[str],
    ) -> str:
        slug = product_id or "adhoc_reviews"
        target_dir = self.settings.aspects_output_dir / (category_slug or "adhoc")
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"{slug}.json"
        payload = {
            "product_id": product_id,
            "category_slug": category_slug,
            "extraction_mode": extraction_mode,
            "preprocessed_reviews": [item.model_dump(mode="json") for item in preprocessed_reviews],
            "sampling_plan": sampling_plan.model_dump(mode="json") if sampling_plan is not None else None,
            "aspects": [item.model_dump(mode="json") for item in aspects],
            "skipped_review_ids": skipped_review_ids,
            "warnings": warnings,
        }
        output_path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
        return str(output_path)

    def _clean_text(self, text: str | None) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"<[^>]+>", " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _guess_language(self, text: str) -> str | None:
        if not text:
            return None
        if re.search(r"[ㄱ-ㅎ가-힣]", text):
            return "ko"
        if re.search(r"[\u4e00-\u9fff]", text):
            return "zh"
        if re.search(r"[Α-Ωα-ω]", text):
            return "el"
        if re.search(r"[а-яА-Я]", text):
            return "ru"
        return "latin"

    def _make_id(self, product_id: str, text: str) -> str:
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
        return f"{product_id}_review_{digest}"

    def _detect_usage_scene(self, text: str) -> str | None:
        for scene, keywords in USAGE_SCENES.items():
            if any(keyword in text for keyword in keywords):
                return scene
        return None

    def _infer_sentiment(self, rating: int | None, text: str) -> AspectSentiment:
        if rating is not None:
            if rating <= 2:
                return "negative"
            if rating >= 4 and not any(hint in text for hint in NEGATIVE_HINTS):
                return "positive"
        if any(hint in text for hint in NEGATIVE_HINTS):
            return "negative"
        if any(keyword in text for keyword in ["love", "excellent", "perfect", "great", "good", "pratique"]):
            return "positive"
        return "neutral"

    def _normalize_sentiment(self, value: object) -> AspectSentiment:
        raw = str(value or "neutral").lower()
        if raw in {"positive", "negative", "neutral", "mixed"}:
            return raw
        return "neutral"

    def _clamp_confidence(self, value: object, default: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, numeric))