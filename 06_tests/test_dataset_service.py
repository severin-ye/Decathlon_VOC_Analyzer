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


def test_dataset_service_normalizes_prompt_variant_alias_for_projection(monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_VARIANT", "en")
    service = DatasetService()
    service.settings.qwen_plus_api_key = "demo-key"

    assert service._should_project_main_to_english() is True