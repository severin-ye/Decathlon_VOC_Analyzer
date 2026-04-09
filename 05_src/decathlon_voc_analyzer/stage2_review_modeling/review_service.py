import hashlib
import json
import re

import orjson
from openai import OpenAI

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.review import (
    AspectSentiment,
    ExtractionMode,
    PreprocessedReview,
    ReviewAspect,
    ReviewExtractionRequest,
    ReviewExtractionResponse,
    ReviewInput,
)
from decathlon_voc_analyzer.prompts import build_review_extraction_user_prompt, get_prompt
from decathlon_voc_analyzer.stage1_dataset.dataset_service import DatasetService


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


class ReviewExtractionService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.dataset_service = DatasetService()

    def extract(self, request: ReviewExtractionRequest) -> ReviewExtractionResponse:
        reviews, product_id, category_slug = self._resolve_reviews(request)
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
        if request.persist_artifact:
            artifact_path = self._persist_result(
                product_id=product_id,
                category_slug=category_slug,
                extraction_mode=extraction_mode,
                preprocessed_reviews=preprocessed_reviews,
                aspects=aspects,
                skipped_review_ids=skipped_review_ids,
                warnings=warnings,
            )

        return ReviewExtractionResponse(
            product_id=product_id,
            category_slug=category_slug,
            extraction_mode=extraction_mode,
            preprocessed_reviews=preprocessed_reviews,
            aspects=aspects,
            skipped_review_ids=skipped_review_ids,
            warnings=warnings,
            artifact_path=artifact_path,
        )

    def _resolve_reviews(
        self, request: ReviewExtractionRequest
    ) -> tuple[list[ReviewInput], str | None, str | None]:
        if request.reviews:
            reviews = request.reviews[: request.max_reviews] if request.max_reviews else request.reviews
            product_id = request.product_id or next(
                (review.product_id for review in reviews if review.product_id),
                None,
            )
            return reviews, product_id, request.category_slug

        if not request.product_id:
            raise ValueError("product_id is required when reviews are not provided")

        package = self.dataset_service.load_product_package(
            product_id=request.product_id,
            category_slug=request.category_slug,
        )
        reviews = [
            ReviewInput(
                review_id=review.review_id,
                product_id=review.product_id,
                rating=review.rating,
                review_text=review.review_text,
                language_hint=review.language_hint,
            )
            for review in package.reviews[: request.max_reviews]
        ]
        return reviews, package.product_id, package.category_slug

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
        client = OpenAI(api_key=self.settings.qwen_plus_api_key, base_url=self.settings.qwen_base_url)
        payload = {
            "review_id": review.review_id,
            "product_id": review.product_id,
            "rating": review.rating,
            "language_hint": review.language_hint,
            "review_text": review.cleaned_text,
        }
        response = client.chat.completions.create(
            model=self.settings.qwen_plus_model,
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": get_prompt("review_extraction_system")},
                {"role": "user", "content": build_review_extraction_user_prompt(payload)},
            ],
        )
        content = response.choices[0].message.content or "{\"aspects\": []}"
        parsed = json.loads(content)
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