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