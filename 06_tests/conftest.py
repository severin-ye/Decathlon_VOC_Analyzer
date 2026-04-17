import os

import pytest

from decathlon_voc_analyzer.app.api.routes import analysis as analysis_route
from decathlon_voc_analyzer.app.api.routes import reviews as reviews_route
from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.stage3_retrieval.index_backends import create_index_backend
from decathlon_voc_analyzer.stage2_review_modeling.review_service import ReviewExtractionService
from decathlon_voc_analyzer.stage4_generation.analysis_service import ProductAnalysisService


@pytest.fixture(autouse=True)
def isolate_runtime_backends():
    previous = {
        "EMBEDDING_BACKEND": os.environ.get("EMBEDDING_BACKEND"),
        "IMAGE_EMBEDDING_BACKEND": os.environ.get("IMAGE_EMBEDDING_BACKEND"),
        "RERANKER_BACKEND": os.environ.get("RERANKER_BACKEND"),
        "MULTIMODAL_RERANKER_BACKEND": os.environ.get("MULTIMODAL_RERANKER_BACKEND"),
        "RETRIEVAL_BACKEND": os.environ.get("RETRIEVAL_BACKEND"),
    }
    os.environ["EMBEDDING_BACKEND"] = "hash"
    os.environ["IMAGE_EMBEDDING_BACKEND"] = "proxy_text"
    os.environ["RERANKER_BACKEND"] = "heuristic"
    os.environ["MULTIMODAL_RERANKER_BACKEND"] = "disabled"
    os.environ["RETRIEVAL_BACKEND"] = previous["RETRIEVAL_BACKEND"] or "local"
    get_settings.cache_clear()
    create_index_backend.cache_clear()
    reviews_route.service = ReviewExtractionService()
    analysis_route.service = ProductAnalysisService()
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
        reviews_route.service = ReviewExtractionService()
        analysis_route.service = ProductAnalysisService()