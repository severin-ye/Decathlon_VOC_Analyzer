import json

import pytest

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.app.core.runtime_policy import (
    RuntimePolicyError,
    get_runtime_execution_policy,
    resolve_llm_permission,
    validate_full_power_prerequisites,
)


def test_runtime_policy_loads_config_file(tmp_path) -> None:
    policy_path = tmp_path / "runtime_execution_policy.json"
    policy_path.write_text(
        json.dumps({"allow_degradation": False, "full_power": True}),
        encoding="utf-8",
    )

    settings = get_settings()
    settings.runtime_execution_policy_path = policy_path

    policy = get_runtime_execution_policy(settings)

    assert policy.allow_degradation is False
    assert policy.full_power is True


def test_runtime_policy_warns_when_degradation_is_allowed(tmp_path) -> None:
    policy_path = tmp_path / "runtime_execution_policy.json"
    policy_path.write_text(
        json.dumps({"allow_degradation": True, "full_power": False}),
        encoding="utf-8",
    )

    settings = get_settings()
    settings.runtime_execution_policy_path = policy_path
    settings.qwen_plus_api_key = None

    llm_requested, warning = resolve_llm_permission("question_generation", True, settings)

    assert llm_requested is False
    assert warning is not None
    assert "QWEN_PLUS_API_KEY" in warning
    assert "已降级为 heuristic" in warning


def test_runtime_policy_blocks_full_power_when_api_backends_are_configured(tmp_path) -> None:
    policy_path = tmp_path / "runtime_execution_policy.json"
    policy_path.write_text(
        json.dumps({"allow_degradation": False, "full_power": True}),
        encoding="utf-8",
    )

    settings = get_settings()
    settings.runtime_execution_policy_path = policy_path
    settings.qwen_plus_api_key = "dummy-key"
    settings.embedding_backend = "api"
    settings.reranker_backend = "api"
    settings.multimodal_reranker_backend = "qwen_vl"

    with pytest.raises(RuntimePolicyError) as exc_info:
        validate_full_power_prerequisites(
            use_llm=True,
            retrieval_backend="qdrant",
            settings=settings,
        )

    message = str(exc_info.value)
    assert "workflow_preflight" in message
    assert "embedding_backend=api" in message
    assert "reranker_backend=api" in message
    assert "multimodal_reranker_backend=qwen_vl" in message
    assert "严格模式期望 local_qwen3" in message
    assert "严格模式期望 local_qwen3_vl" in message
    assert "补齐上述依赖后重新运行" in message


def test_runtime_policy_allows_local_qwen3_backends_without_key(tmp_path) -> None:
    policy_path = tmp_path / "runtime_execution_policy.json"
    policy_path.write_text(
        json.dumps({"allow_degradation": False, "full_power": True}),
        encoding="utf-8",
    )

    settings = get_settings()
    settings.runtime_execution_policy_path = policy_path
    settings.qwen_plus_api_key = None
    settings.embedding_backend = "local_qwen3"
    settings.reranker_backend = "local_qwen3"
    settings.multimodal_reranker_backend = "local_qwen3_vl"

    policy = validate_full_power_prerequisites(
        use_llm=True,
        retrieval_backend="qdrant",
        settings=settings,
    )

    assert policy.allow_degradation is False
    assert policy.full_power is True