from __future__ import annotations

from functools import lru_cache
from math import floor
from pathlib import Path

import orjson
from pydantic import BaseModel, Field

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.review import ReviewInput, ReviewRatingAllocation, ReviewSamplingPlan


RATINGS = (1, 2, 3, 4, 5)
DISPLAY_RATINGS = (5, 4, 3, 2, 1)
DEFAULT_FALLBACK_ORDER = [1, 2, 3, 4, 5]
DEFAULT_WEIGHTS = {
    5: 0.10,
    4: 0.15,
    3: 0.20,
    2: 0.25,
    1: 0.30,
}


class ReviewSamplingProfile(BaseModel):
    description: str = ""
    weights: dict[int, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    fallback_order: list[int] = Field(default_factory=lambda: list(DEFAULT_FALLBACK_ORDER))


class ReviewSamplingConfig(BaseModel):
    active_profile: str = "problem_first_default"
    profiles: dict[str, ReviewSamplingProfile] = Field(default_factory=dict)


class ReviewSamplingService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def select_reviews(
        self,
        reviews: list[ReviewInput],
        max_reviews: int | None,
        profile_name: str | None = None,
    ) -> tuple[list[ReviewInput], ReviewSamplingPlan | None]:
        if max_reviews is None:
            return reviews, None

        profile_key, profile = self._resolve_profile(profile_name)
        buckets = {rating: [] for rating in RATINGS}
        buckets[None] = []
        for review in reviews:
            buckets[self._normalize_rating(review.rating)].append(review)

        normalized_weights = self._normalize_weights(profile.weights)
        target_counts = self._build_target_counts(
            requested_reviews=max_reviews,
            weights=normalized_weights,
            fallback_order=profile.fallback_order,
        )
        selected_counts = {rating: min(target_counts[rating], len(buckets[rating])) for rating in RATINGS}
        shortfall_counts = {rating: target_counts[rating] - selected_counts[rating] for rating in RATINGS}
        redistributed_in_counts = {rating: 0 for rating in RATINGS}

        missing_reviews = max_reviews - sum(selected_counts.values())
        if missing_reviews > 0:
            for rating in profile.fallback_order:
                remaining_capacity = len(buckets[rating]) - selected_counts[rating]
                if remaining_capacity <= 0:
                    continue
                take_count = min(remaining_capacity, missing_reviews)
                selected_counts[rating] += take_count
                redistributed_in_counts[rating] += take_count
                missing_reviews -= take_count
                if missing_reviews == 0:
                    break

        unrated_selected_count = 0
        if missing_reviews > 0 and buckets[None]:
            unrated_selected_count = min(len(buckets[None]), missing_reviews)
            missing_reviews -= unrated_selected_count

        selected_reviews = self._materialize_selected_reviews(
            reviews=reviews,
            selected_counts=selected_counts,
            unrated_selected_count=unrated_selected_count,
        )
        sampling_plan = ReviewSamplingPlan(
            profile_name=profile_key,
            requested_reviews=max_reviews,
            total_available_reviews=len(reviews),
            selected_reviews=len(selected_reviews),
            fallback_order=profile.fallback_order,
            allocations=self._build_allocations(
                target_counts=target_counts,
                selected_counts=selected_counts,
                shortfall_counts=shortfall_counts,
                redistributed_in_counts=redistributed_in_counts,
                normalized_weights=normalized_weights,
                buckets=buckets,
                unrated_selected_count=unrated_selected_count,
            ),
        )
        return selected_reviews, sampling_plan

    def _resolve_profile(self, profile_name: str | None) -> tuple[str, ReviewSamplingProfile]:
        config = self._load_config(self.settings.review_sampling_config_path)
        resolved_profile_name = profile_name or self.settings.review_sampling_profile or config.active_profile
        profile = config.profiles.get(resolved_profile_name)
        if profile is None:
            fallback_profile_name = config.active_profile if config.active_profile in config.profiles else "problem_first_default"
            profile = config.profiles.get(fallback_profile_name, ReviewSamplingProfile())
            return fallback_profile_name, profile
        return resolved_profile_name, profile

    def _normalize_weights(self, raw_weights: dict[int, float]) -> dict[int, float]:
        normalized = {rating: max(0.0, float(raw_weights.get(rating, 0.0))) for rating in RATINGS}
        total = sum(normalized.values())
        if total <= 0:
            return dict(DEFAULT_WEIGHTS)
        return {rating: normalized[rating] / total for rating in RATINGS}

    def _build_target_counts(
        self,
        requested_reviews: int,
        weights: dict[int, float],
        fallback_order: list[int],
    ) -> dict[int, int]:
        if requested_reviews <= 0:
            return {rating: 0 for rating in RATINGS}

        fractional_targets = {rating: requested_reviews * weights[rating] for rating in RATINGS}
        target_counts = {rating: floor(fractional_targets[rating]) for rating in RATINGS}
        remaining = requested_reviews - sum(target_counts.values())
        priority_lookup = {rating: index for index, rating in enumerate(fallback_order)}
        while remaining > 0:
            ranked_ratings = sorted(
                RATINGS,
                key=lambda rating: (
                    -(fractional_targets[rating] - target_counts[rating]),
                    priority_lookup.get(rating, len(priority_lookup)),
                ),
            )
            for rating in ranked_ratings:
                if remaining == 0:
                    break
                target_counts[rating] += 1
                remaining -= 1
        return target_counts

    def _materialize_selected_reviews(
        self,
        reviews: list[ReviewInput],
        selected_counts: dict[int, int],
        unrated_selected_count: int,
    ) -> list[ReviewInput]:
        remaining_by_rating = dict(selected_counts)
        remaining_unrated = unrated_selected_count
        selected_reviews: list[ReviewInput] = []
        for review in reviews:
            rating = self._normalize_rating(review.rating)
            if rating is None:
                if remaining_unrated <= 0:
                    continue
                selected_reviews.append(review)
                remaining_unrated -= 1
                continue
            if remaining_by_rating[rating] <= 0:
                continue
            selected_reviews.append(review)
            remaining_by_rating[rating] -= 1
        return selected_reviews

    def _build_allocations(
        self,
        target_counts: dict[int, int],
        selected_counts: dict[int, int],
        shortfall_counts: dict[int, int],
        redistributed_in_counts: dict[int, int],
        normalized_weights: dict[int, float],
        buckets: dict[int | None, list[ReviewInput]],
        unrated_selected_count: int,
    ) -> list[ReviewRatingAllocation]:
        allocations = [
            ReviewRatingAllocation(
                rating=rating,
                configured_ratio=normalized_weights[rating],
                target_count=target_counts[rating],
                available_count=len(buckets[rating]),
                selected_count=selected_counts[rating],
                redistributed_in_count=redistributed_in_counts[rating],
                shortfall_count=shortfall_counts[rating],
            )
            for rating in DISPLAY_RATINGS
        ]
        if buckets[None] or unrated_selected_count:
            allocations.append(
                ReviewRatingAllocation(
                    rating=None,
                    configured_ratio=0.0,
                    target_count=0,
                    available_count=len(buckets[None]),
                    selected_count=unrated_selected_count,
                    redistributed_in_count=unrated_selected_count,
                    shortfall_count=0,
                )
            )
        return allocations

    def _normalize_rating(self, rating: int | None) -> int | None:
        if rating in RATINGS:
            return rating
        return None

    @staticmethod
    @lru_cache(maxsize=4)
    def _load_config(path: Path) -> ReviewSamplingConfig:
        if path.exists():
            payload = orjson.loads(path.read_bytes())
            return ReviewSamplingConfig.model_validate(payload)
        return ReviewSamplingConfig(
            active_profile="problem_first_default",
            profiles={"problem_first_default": ReviewSamplingProfile()},
        )
