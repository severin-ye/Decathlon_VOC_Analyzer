import os
from pathlib import Path

import pytest

from decathlon_voc_analyzer.app.api.routes import analysis as analysis_route
from decathlon_voc_analyzer.app.api.routes import index as index_route
from decathlon_voc_analyzer.app.api.routes import reviews as reviews_route
from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.stage3_retrieval.index_backends import create_index_backend
from decathlon_voc_analyzer.stage3_retrieval.index_service import IndexService
from decathlon_voc_analyzer.stage2_review_modeling.review_service import ReviewExtractionService
from decathlon_voc_analyzer.stage4_generation.analysis_service import ProductAnalysisService


@pytest.fixture(autouse=True)
def isolate_runtime_backends(tmp_path_factory):
    runtime_policy_path = tmp_path_factory.mktemp("runtime-policy") / "runtime_execution_policy.json"
    runtime_policy_path.write_text(
        '{"allow_degradation": true, "full_power": false}',
        encoding="utf-8",
    )
    previous = {
        "EMBEDDING_BACKEND": os.environ.get("EMBEDDING_BACKEND"),
        "IMAGE_EMBEDDING_BACKEND": os.environ.get("IMAGE_EMBEDDING_BACKEND"),
        "RERANKER_BACKEND": os.environ.get("RERANKER_BACKEND"),
        "MULTIMODAL_RERANKER_BACKEND": os.environ.get("MULTIMODAL_RERANKER_BACKEND"),
        "RETRIEVAL_BACKEND": os.environ.get("RETRIEVAL_BACKEND"),
        "RUNTIME_EXECUTION_POLICY_PATH": os.environ.get("RUNTIME_EXECUTION_POLICY_PATH"),
        "QWEN_PLUS_API_KEY": os.environ.get("QWEN_PLUS_API_KEY"),
        "qwen-plus_api": os.environ.get("qwen-plus_api"),
        "DEEPSEEK_V3_API_KEY": os.environ.get("DEEPSEEK_V3_API_KEY"),
        "DeepSeek-V3_api": os.environ.get("DeepSeek-V3_api"),
        "OPENAI_GPT5_API_KEY": os.environ.get("OPENAI_GPT5_API_KEY"),
        "openai-gpt5_api": os.environ.get("openai-gpt5_api"),
    }
    os.environ["EMBEDDING_BACKEND"] = "hash"
    os.environ["IMAGE_EMBEDDING_BACKEND"] = "proxy_text"
    os.environ["RERANKER_BACKEND"] = "heuristic"
    os.environ["MULTIMODAL_RERANKER_BACKEND"] = "disabled"
    os.environ["RETRIEVAL_BACKEND"] = previous["RETRIEVAL_BACKEND"] or "local"
    os.environ["RUNTIME_EXECUTION_POLICY_PATH"] = str(runtime_policy_path)
    os.environ["QWEN_PLUS_API_KEY"] = ""
    os.environ["qwen-plus_api"] = ""
    os.environ["DEEPSEEK_V3_API_KEY"] = ""
    os.environ["DeepSeek-V3_api"] = ""
    os.environ["OPENAI_GPT5_API_KEY"] = ""
    os.environ["openai-gpt5_api"] = ""
    get_settings.cache_clear()
    create_index_backend.cache_clear()
    index_route.service = IndexService()
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
        index_route.service = IndexService()
        reviews_route.service = ReviewExtractionService()
        analysis_route.service = ProductAnalysisService()