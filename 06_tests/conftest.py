import os

import pytest

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.stage3_retrieval.index_backends import create_index_backend


@pytest.fixture(autouse=True)
def isolate_runtime_backends():
    previous = {
        "EMBEDDING_BACKEND": os.environ.get("EMBEDDING_BACKEND"),
        "RERANKER_BACKEND": os.environ.get("RERANKER_BACKEND"),
        "RETRIEVAL_BACKEND": os.environ.get("RETRIEVAL_BACKEND"),
    }
    os.environ["EMBEDDING_BACKEND"] = "hash"
    os.environ["RERANKER_BACKEND"] = "heuristic"
    os.environ["RETRIEVAL_BACKEND"] = previous["RETRIEVAL_BACKEND"] or "local"
    get_settings.cache_clear()
    create_index_backend.cache_clear()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        create_index_backend.cache_clear()