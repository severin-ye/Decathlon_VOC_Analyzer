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