from decathlon_voc_analyzer.schemas.dataset import DatasetNormalizeRequest
from decathlon_voc_analyzer.stage1_dataset.dataset_service import DatasetService


def test_dataset_overview_has_categories() -> None:
    service = DatasetService()

    overview = service.build_overview()

    assert overview.category_count >= 1
    assert overview.total_products >= 1
    assert any(category.category == "backpack" for category in overview.categories)


def test_normalize_single_product_without_persisting() -> None:
    service = DatasetService()

    result = service.normalize_dataset(
        DatasetNormalizeRequest(categories=["backpack"], max_products=1, persist_artifacts=False)
    )

    assert result.stats.scanned_products == 1
    assert result.stats.normalized_products == 1
    assert result.stats.total_reviews >= 0


def test_dataset_service_preserves_original_multilingual_product_fields(monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_VARIANT", "en")
    service = DatasetService()
    service.settings.qwen_plus_api_key = "demo-key"

    package = service.load_product_package(
        product_id="backpack_010",
        category_slug="backpack",
        use_llm=True,
    )

    assert package.product_name == "백패킹 오거나이저 여행 지갑 S"
    assert package.primary_language == "ko"
    assert any(block.language == "ko" for block in package.text_blocks)
    assert any(block.content_original == block.content for block in package.text_blocks)