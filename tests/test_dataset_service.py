from decathlon_voc_analyzer.models.dataset import DatasetNormalizeRequest
from decathlon_voc_analyzer.services.dataset_service import DatasetService


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