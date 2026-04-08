import os

from decathlon_voc_analyzer.core.config import get_settings
from decathlon_voc_analyzer.services.embedding_service import EmbeddingService
from decathlon_voc_analyzer.services.index_backends import LocalIndexBackend, QdrantIndexBackend, create_index_backend


def test_create_index_backend_defaults_to_local() -> None:
    backend = create_index_backend()

    assert backend is not None


def test_create_index_backend_can_switch_to_qdrant() -> None:
    previous = os.environ.get("RETRIEVAL_BACKEND")
    try:
        os.environ["RETRIEVAL_BACKEND"] = "qdrant"
        get_settings.cache_clear()
        create_index_backend.cache_clear()
        backend = create_index_backend()
        assert isinstance(backend, QdrantIndexBackend)
    finally:
        if previous is None:
            os.environ.pop("RETRIEVAL_BACKEND", None)
        else:
            os.environ["RETRIEVAL_BACKEND"] = previous
        get_settings.cache_clear()
        create_index_backend.cache_clear()


def test_local_backend_has_searchable_location() -> None:
    embedding_service = EmbeddingService()
    backend = LocalIndexBackend(
        path=embedding_service.settings.indexes_output_dir / "test_local_backend.json",
        embedding_service=embedding_service,
    )

    assert backend.index_location().endswith("test_local_backend.json")