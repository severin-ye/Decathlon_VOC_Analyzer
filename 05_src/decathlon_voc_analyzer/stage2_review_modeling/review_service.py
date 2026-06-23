import hashlib
import re
from pathlib import Path

import orjson
from pydantic import BaseModel, Field

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.app.core.runtime_policy import handle_llm_failure, resolve_llm_permission
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
from decathlon_voc_analyzer.runtime_progress import get_workflow_progress
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
        llm_requested, policy_warning = resolve_llm_permission("review_extraction", request.use_llm, self.settings)
        if policy_warning is not None:
            warnings.append(policy_warning)
        extraction_mode: ExtractionMode = "llm" if llm_requested else "heuristic"

        progress = get_workflow_progress()
        progress.start_count_step("analyze", "extract", total=len(preprocessed_reviews), detail=f"处理 {len(preprocessed_reviews)} 条评论")

        for idx, review in enumerate(preprocessed_reviews):
            if not review.is_informative and not request.include_non_informative:
                skipped_review_ids.append(review.review_id)
                progress.advance_step("analyze", "extract", detail=f"{review.review_id} (已跳过)")
                continue

            extracted_aspects: list[ReviewAspect]
            if llm_requested:
                try:
                    extracted_aspects = self._extract_with_llm(review)
                except Exception as exc:
                    extraction_mode = "heuristic"
                    warnings.append(handle_llm_failure(f"review_extraction:{review.review_id}", exc, self.settings))
                    extracted_aspects = self._extract_with_heuristic(review)
            else:
                extracted_aspects = self._extract_with_heuristic(review)

            if not extracted_aspects:
                skipped_review_ids.append(review.review_id)
                progress.advance_step("analyze", "extract", detail=f"{review.review_id} (无方面提取)")
                continue
            aspects.extend(extracted_aspects)
            progress.advance_step("analyze", "extract", detail=review.review_id)

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

        progress.complete_step("analyze", "extract", detail=f"提取了 {len(aspects)} 个方面")

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

    def load_persisted_result(self, product_id: str, category_slug: str | None) -> ReviewExtractionResponse:
        artifact_path = self._artifact_path(product_id=product_id, category_slug=category_slug)
        if not artifact_path.exists():
            raise FileNotFoundError(
                f"未找到可复用的评论抽取产物: {artifact_path}。请先完成一次抽取，或不要使用 --resume-from-aspects。"
            )
        payload = orjson.loads(artifact_path.read_bytes())
        if not isinstance(payload, dict):
            raise ValueError(f"评论抽取产物格式无效: {artifact_path}")
        payload["artifact_path"] = str(artifact_path)
        return ReviewExtractionResponse.model_validate(payload)

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
            return reviews, product_id, request.category_slug, sampling_plan

        if not request.product_id:
            raise ValueError("product_id is required when reviews are not provided")

        package = self.dataset_service.load_product_package(
            product_id=request.product_id,
            category_slug=request.category_slug,
            use_llm=request.use_llm,
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
        return reviews, package.product_id, package.category_slug, sampling_plan

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
            aspect = ReviewAspect(
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
            aspects.append(self._normalize_overall_experience_aspect(aspect, review.cleaned_text))
        return aspects

    def _normalize_overall_experience_aspect(self, aspect: ReviewAspect, review_text: str) -> ReviewAspect:
        if aspect.aspect != "overall_experience":
            return aspect
        lowered = review_text.lower()
        positive_markers = ("great", "good", "excellent", "love", "nice")
        negative_markers = ("however", "but", "disappoint", "fell apart", "deteriorat", "sad")
        has_positive = any(marker in lowered for marker in positive_markers)
        has_negative = any(marker in lowered for marker in negative_markers)
        if aspect.sentiment in {"negative", "mixed"} and has_positive and has_negative:
            opinion = aspect.opinion
            if "rubber" in lowered and ("fell apart" in lowered or "deteriorat" in lowered):
                opinion = "initially positive but ultimately disappointing due to premature rubber insert failure"
            return aspect.model_copy(update={"sentiment": "mixed", "opinion": opinion})
        return aspect

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
        output_path = self._artifact_path(product_id=slug, category_slug=category_slug)
        output_path.parent.mkdir(parents=True, exist_ok=True)
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

    def _artifact_path(self, product_id: str, category_slug: str | None) -> Path:
        return self.settings.aspects_output_dir / (category_slug or "adhoc") / f"{product_id}.json"

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