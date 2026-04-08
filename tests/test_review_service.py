from decathlon_voc_analyzer.models.review import ReviewExtractionRequest, ReviewInput
from decathlon_voc_analyzer.services.review_service import ReviewExtractionService


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