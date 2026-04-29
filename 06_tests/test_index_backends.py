import pytest

from decathlon_voc_analyzer.app.core.runtime_policy import RuntimePolicyError
from decathlon_voc_analyzer.schemas.index import IndexedEvidence, ProductIndexSnapshot
from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.stage3_retrieval.embedding_service import EmbeddingService
from decathlon_voc_analyzer.stage3_retrieval.index_backends import LocalIndexBackend, QdrantIndexBackend, create_index_backend


def test_create_index_backend_defaults_to_local() -> None:
    backend = create_index_backend()

    assert backend is not None


def test_create_index_backend_can_switch_to_qdrant(tmp_path) -> None:
    import os

    os.environ["RETRIEVAL_BACKEND"] = "qdrant"
    os.environ["QDRANT_PATH"] = str(tmp_path / "qdrant_store")
    get_settings.cache_clear()
    create_index_backend.cache_clear()
    backend = create_index_backend()
    assert isinstance(backend, QdrantIndexBackend)


def test_local_backend_has_searchable_location() -> None:
    embedding_service = EmbeddingService()
    backend = LocalIndexBackend(
        path=embedding_service.settings.indexes_output_dir / "test_local_backend.json",
        embedding_service=embedding_service,
    )

    assert backend.index_location().endswith("test_local_backend.json")


def test_local_backend_invalidates_stale_query_cache_before_search(tmp_path, monkeypatch) -> None:
    embedding_service = EmbeddingService()
    embedding_service.settings.indexes_output_dir = tmp_path
    backend = LocalIndexBackend(
        path=tmp_path / "test_local_backend.json",
        embedding_service=embedding_service,
    )
    backend.save_snapshots(
        [
            ProductIndexSnapshot(
                product_id="p1",
                category_slug="bags",
                text_count=1,
                image_count=0,
                evidence=[
                    IndexedEvidence(
                        evidence_id="t1",
                        product_id="p1",
                        category_slug="bags",
                        route="text",
                        text_block_id="t1",
                        content="passport wallet with card storage",
                        vector=[0.1, 0.2, 0.3],
                    )
                ],
            )
        ]
    )

    stale_signature = embedding_service._text_query_cache_signature("passport wallet", "text")
    embedding_service.cache_service.save_query_embedding(stale_signature, [0.0] * 64)

    calls = {"fresh": 0}

    def _embed_query_for_route(text: str, route: str, force_refresh: bool = False) -> list[float]:
        if not force_refresh:
            cached = embedding_service.cache_service.load_query_embedding(stale_signature)
            return list(cached or [])
        calls["fresh"] += 1
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(embedding_service, "embed_query_for_route", _embed_query_for_route)

    hits = backend.search(product_id="p1", category_slug="bags", query="passport wallet", routes=["text"], top_k_per_route=1)

    assert calls["fresh"] == 1
    assert hits[0].evidence_id == "t1"


def test_local_backend_raises_when_refreshed_query_dimension_still_mismatches(tmp_path, monkeypatch) -> None:
    embedding_service = EmbeddingService()
    embedding_service.settings.indexes_output_dir = tmp_path
    backend = LocalIndexBackend(
        path=tmp_path / "test_local_backend.json",
        embedding_service=embedding_service,
    )
    backend.save_snapshots(
        [
            ProductIndexSnapshot(
                product_id="p1",
                category_slug="bags",
                text_count=1,
                image_count=0,
                evidence=[
                    IndexedEvidence(
                        evidence_id="t1",
                        product_id="p1",
                        category_slug="bags",
                        route="text",
                        text_block_id="t1",
                        content="passport wallet with card storage",
                        vector=[0.1, 0.2, 0.3],
                    )
                ],
            )
        ]
    )

    def _embed_query_for_route(_text: str, _route: str, force_refresh: bool = False) -> list[float]:
        return [0.0] * 64

    monkeypatch.setattr(embedding_service, "embed_query_for_route", _embed_query_for_route)

    with pytest.raises(RuntimePolicyError, match="查询向量维度与已建索引不一致"):
        backend.search(product_id="p1", category_slug="bags", query="passport wallet", routes=["text"], top_k_per_route=1)