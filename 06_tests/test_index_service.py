from decathlon_voc_analyzer.schemas.index import IndexBuildRequest
from decathlon_voc_analyzer.stage3_retrieval.index_service import IndexService


def test_index_service_builds_local_index() -> None:
    service = IndexService()

    result = service.build_index(
        IndexBuildRequest(product_ids=["backpack_010"], persist_artifact=True)
    )

    assert result.backend == "local"
    assert result.stats.indexed_products == 1
    assert result.stats.indexed_text_blocks >= 1
    assert result.stats.indexed_images >= 1


def test_index_service_search_returns_hits() -> None:
    service = IndexService()
    service.build_index(IndexBuildRequest(product_ids=["backpack_010"], persist_artifact=True))

    hits = service.search(
        product_id="backpack_010",
        category_slug="backpack",
        query="passport storage travel wallet",
        routes=["text", "image"],
        top_k_per_route=1,
    )

    assert hits
    assert any(hit.route == "text" for hit in hits)
    assert any(hit.route == "image" for hit in hits)
    assert all(hit.score is not None for hit in hits)