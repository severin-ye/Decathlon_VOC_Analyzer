from decathlon_voc_analyzer.schemas.review import ReviewExtractionRequest, ReviewInput
from decathlon_voc_analyzer.stage2_review_modeling.review_service import ReviewExtractionService


def _build_reviews(rating: int, count: int) -> list[ReviewInput]:
    return [
        ReviewInput(
            review_id=f"r{rating}_{index}",
            product_id="demo_product",
            rating=rating,
            review_text=f"Rating {rating} review {index} about travel pocket usage and storage.",
        )
        for index in range(count)
    ]


def test_review_service_marks_low_signal_reviews_as_skipped() -> None:
    service = ReviewExtractionService()

    result = service.extract(
        ReviewExtractionRequest(
            product_id="demo_product",
            use_llm=False,
            reviews=[
                ReviewInput(review_id="r1", product_id="demo_product", review_text="good"),
                ReviewInput(
                    review_id="r2",
                    product_id="demo_product",
                    rating=5,
                    review_text="Practical wallet for daily travel and passport storage.",
                ),
            ],
        )
    )

    assert result.skipped_review_ids == ["r1"]
    assert any(aspect.aspect == "capacity_storage" for aspect in result.aspects)


def test_review_service_can_extract_from_dataset_package() -> None:
    service = ReviewExtractionService()

    result = service.extract(
        ReviewExtractionRequest(
            product_id="backpack_010",
            category_slug="backpack",
            max_reviews=3,
            use_llm=False,
        )
    )

    assert result.product_id == "backpack_010"
    assert len(result.preprocessed_reviews) == 3
    assert len(result.aspects) >= 1


def test_review_service_applies_default_rating_sampling_plan() -> None:
    service = ReviewExtractionService()
    reviews = []
    for rating in [5, 4, 3, 2, 1]:
        reviews.extend(_build_reviews(rating=rating, count=8))

    result = service.extract(
        ReviewExtractionRequest(
            product_id="demo_product",
            use_llm=False,
            max_reviews=20,
            reviews=reviews,
        )
    )

    assert result.sampling_plan is not None
    selected_by_rating = {item.rating: item.selected_count for item in result.sampling_plan.allocations}
    assert selected_by_rating[5] == 2
    assert selected_by_rating[4] == 3
    assert selected_by_rating[3] == 4
    assert selected_by_rating[2] == 5
    assert selected_by_rating[1] == 6
    assert len(result.preprocessed_reviews) == 20


def test_review_service_redistributes_shortfall_to_next_lower_priority_bucket() -> None:
    service = ReviewExtractionService()
    reviews = []
    reviews.extend(_build_reviews(rating=5, count=8))
    reviews.extend(_build_reviews(rating=4, count=8))
    reviews.extend(_build_reviews(rating=3, count=8))
    reviews.extend(_build_reviews(rating=2, count=8))
    reviews.extend(_build_reviews(rating=1, count=4))

    result = service.extract(
        ReviewExtractionRequest(
            product_id="demo_product",
            use_llm=False,
            max_reviews=20,
            reviews=reviews,
        )
    )

    assert result.sampling_plan is not None
    allocation_by_rating = {item.rating: item for item in result.sampling_plan.allocations}
    assert allocation_by_rating[1].selected_count == 4
    assert allocation_by_rating[1].shortfall_count == 2
    assert allocation_by_rating[2].selected_count == 7
    assert allocation_by_rating[2].redistributed_in_count == 2


def test_review_service_cascades_shortfall_across_multiple_priority_buckets() -> None:
    service = ReviewExtractionService()
    reviews = []
    reviews.extend(_build_reviews(rating=3, count=6))
    reviews.extend(_build_reviews(rating=2, count=3))
    reviews.extend(_build_reviews(rating=1, count=1))

    result = service.extract(
        ReviewExtractionRequest(
            product_id="demo_product",
            use_llm=False,
            max_reviews=6,
            reviews=reviews,
        )
    )

    assert result.sampling_plan is not None
    allocation_by_rating = {item.rating: item for item in result.sampling_plan.allocations}
    assert allocation_by_rating[1].selected_count == 1
    assert allocation_by_rating[2].selected_count >= 2
    assert allocation_by_rating[3].selected_count >= 2
    assert len(result.preprocessed_reviews) == 6


def test_review_service_uses_active_profile_from_config_file(tmp_path) -> None:
        service = ReviewExtractionService()
        config_path = tmp_path / "review_sampling_profiles.json"
        config_path.write_text(
                """
{
    "active_profile": "praise_first",
    "profiles": {
        "problem_first": {
            "description": "problem first",
            "weights": {"5": 0.1, "4": 0.15, "3": 0.2, "2": 0.25, "1": 0.3},
            "fallback_order": [1, 2, 3, 4, 5]
        },
        "praise_first": {
            "description": "praise first",
            "weights": {"5": 0.3, "4": 0.25, "3": 0.2, "2": 0.15, "1": 0.1},
            "fallback_order": [5, 4, 3, 2, 1]
        }
    }
}
                """.strip(),
                encoding="utf-8",
        )
        service.review_sampling_service.settings.review_sampling_config_path = config_path

        reviews = []
        for rating in [5, 4, 3, 2, 1]:
                reviews.extend(_build_reviews(rating=rating, count=8))

        result = service.extract(
                ReviewExtractionRequest(
                        product_id="demo_product",
                        use_llm=False,
                        max_reviews=20,
                        reviews=reviews,
                )
        )

        assert result.sampling_plan is not None
        assert result.sampling_plan.profile_name == "praise_first"
        selected_by_rating = {item.rating: item.selected_count for item in result.sampling_plan.allocations}
        assert selected_by_rating[5] == 6
        assert selected_by_rating[4] == 5
        assert selected_by_rating[1] == 2


def test_review_service_samples_from_full_review_pool_before_rating_balancing() -> None:
    service = ReviewExtractionService()
    reviews = []
    reviews.extend(_build_reviews(rating=5, count=25))
    reviews.extend(_build_reviews(rating=1, count=10))

    result = service.extract(
        ReviewExtractionRequest(
            product_id="demo_product",
            use_llm=False,
            max_reviews=10,
            reviews=reviews,
        )
    )

    assert result.sampling_plan is not None
    allocation_by_rating = {item.rating: item.selected_count for item in result.sampling_plan.allocations}
    assert allocation_by_rating[1] >= 1
    selected_review_ids = {review.review_id for review in result.preprocessed_reviews}
    assert any(review_id.startswith("r1_") for review_id in selected_review_ids)


def test_review_service_preserves_original_multilingual_reviews(monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_VARIANT", "en")
    service = ReviewExtractionService()
    service.settings.qwen_plus_api_key = "demo-key"

    reviews, product_id, category_slug, sampling_plan = service._resolve_reviews(
        ReviewExtractionRequest(
            product_id="demo_product",
            category_slug="backpack",
            use_llm=True,
            reviews=[
                ReviewInput(
                    review_id="r_ko",
                    product_id="demo_product",
                    rating=5,
                    review_text="한글 리뷰 원문",
                    language_hint="ko",
                )
            ],
        )
    )

    assert product_id == "demo_product"
    assert category_slug == "backpack"
    assert sampling_plan is None
    assert reviews[0].review_text == "한글 리뷰 원문"
    assert reviews[0].language_hint == "ko"


def test_review_service_normalizes_mixed_overall_experience_from_contrastive_review() -> None:
    service = ReviewExtractionService()

    normalized = service._normalize_overall_experience_aspect(
        aspect=service._extract_with_heuristic(
            service._preprocess_review(
                ReviewInput(
                    review_id="r1",
                    product_id="demo_product",
                    rating=1,
                    review_text="The sunglasses are great! However, the rubber insert near the ear deteriorates and fell apart. Sad...",
                )
            )
        )[0].model_copy(update={"aspect": "overall_experience", "sentiment": "negative"}),
        review_text="The sunglasses are great! However, the rubber insert near the ear deteriorates and fell apart. Sad...",
    )

    assert normalized.sentiment == "mixed"
    assert normalized.opinion == "initially positive but ultimately disappointing due to premature rubber insert failure"


def test_review_service_keeps_mixed_overall_experience_but_upgrades_opinion_text() -> None:
    service = ReviewExtractionService()
    review_text = "The sunglasses are great! However, the rubber insert near the ear deteriorates and fell apart. Sad..."

    normalized = service._normalize_overall_experience_aspect(
        aspect=service._extract_with_heuristic(
            service._preprocess_review(
                ReviewInput(
                    review_id="r2",
                    product_id="demo_product",
                    rating=1,
                    review_text=review_text,
                )
            )
        )[0].model_copy(update={"aspect": "overall_experience", "sentiment": "mixed", "opinion": "disappointing due to premature failure"}),
        review_text=review_text,
    )

    assert normalized.sentiment == "mixed"
    assert normalized.opinion == "initially positive but ultimately disappointing due to premature rubber insert failure"