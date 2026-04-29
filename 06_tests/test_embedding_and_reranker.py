import json
from pathlib import Path

import pytest

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.app.core.runtime_policy import RuntimePolicyError
from decathlon_voc_analyzer.schemas.index import IndexedEvidence
from decathlon_voc_analyzer.stage3_retrieval.embedding_service import EmbeddingService
from decathlon_voc_analyzer.stage3_retrieval.reranker_service import RerankerService


def test_embedding_service_returns_non_empty_vector() -> None:
    service = EmbeddingService()

    vector = service.embed_text("travel wallet passport cards")

    assert vector
    assert len(vector) == service.vector_size()


def test_reranker_service_returns_sorted_candidates(tmp_path) -> None:
    service = RerankerService()
    service.settings.indexes_output_dir = tmp_path
    candidates = [
        IndexedEvidence(
            evidence_id="a",
            product_id="p1",
            category_slug="bags",
            route="text",
            text_block_id="t1",
            content="passport wallet with card storage",
            vector=[0.1, 0.2],
            score=0.9,
        ),
        IndexedEvidence(
            evidence_id="b",
            product_id="p1",
            category_slug="bags",
            route="text",
            text_block_id="t2",
            content="running shoe cushioning",
            vector=[0.1, 0.2],
            score=0.2,
        ),
    ]

    reranked = service.rerank(query="passport wallet", candidates=candidates, use_llm=False)

    assert reranked[0].evidence_id == "a"
    assert reranked[1].evidence_id == "b"


def test_reranker_service_uses_dedicated_api(monkeypatch, tmp_path) -> None:
    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "output": {
                        "results": [
                            {"index": 1, "relevance_score": 0.91},
                            {"index": 0, "relevance_score": 0.12},
                        ]
                    }
                }
            ).encode("utf-8")

    def fake_urlopen(_request, timeout=0):
        return DummyResponse()

    monkeypatch.setattr("decathlon_voc_analyzer.stage3_retrieval.reranker_service.request.urlopen", fake_urlopen)

    service = RerankerService()
    service.settings.indexes_output_dir = tmp_path
    candidates = [
        IndexedEvidence(
            evidence_id="a",
            product_id="p1",
            category_slug="bags",
            route="text",
            text_block_id="t1",
            content="passport wallet with card storage",
            vector=[0.1, 0.2],
            score=0.9,
        ),
        IndexedEvidence(
            evidence_id="b",
            product_id="p1",
            category_slug="bags",
            route="text",
            text_block_id="t2",
            content="travel organizer with passport compartment",
            vector=[0.1, 0.2],
            score=0.2,
        ),
    ]

    service.settings.reranker_backend = "api"
    service.settings.qwen_plus_api_key = "test-key"
    reranked = service.rerank(query="passport wallet", candidates=candidates, use_llm=True)

    assert reranked[0].evidence_id == "b"
    assert reranked[0].score == 0.91
    assert reranked[1].evidence_id == "a"


def test_embedding_service_uses_clip_for_image_route(monkeypatch, tmp_path) -> None:
    service = EmbeddingService()
    service.settings.image_embedding_backend = "clip"
    service.settings.indexes_output_dir = tmp_path

    monkeypatch.setattr(service, "_clip_image_embedding", lambda _path, crop_box=None: [0.0, 1.0])
    monkeypatch.setattr(service, "_clip_text_embedding", lambda _text: [1.0, 0.0])

    image_path = tmp_path / "probe.png"
    image_path.write_bytes(b"fake-image")

    image_vector = service.embed_image(image_path=image_path, text_hint="wallet")
    query_vector = service.embed_query_for_route("travel wallet", "image")

    assert image_vector == [0.0, 1.0]
    assert query_vector == [1.0, 0.0]


def test_embedding_service_caches_text_query_embeddings_and_invalidates_on_model_change(monkeypatch, tmp_path) -> None:
    service = EmbeddingService()
    service.settings.embedding_backend = "api"
    service.settings.qwen_plus_api_key = "test-key"
    service.settings.qwen_embedding_model = "embed-a"
    service.settings.indexes_output_dir = tmp_path

    calls: list[tuple[str, str]] = []

    def fake_api_embedding(text: str) -> list[float]:
        calls.append((service.settings.qwen_embedding_model, text))
        return [1.0, 0.0]

    monkeypatch.setattr(service, "_api_embedding", fake_api_embedding)

    first = service.embed_query_for_route("travel wallet", "text")
    second = service.embed_query_for_route("travel wallet", "text")

    service.settings.qwen_embedding_model = "embed-b"
    third = service.embed_query_for_route("travel wallet", "text")

    assert first == [1.0, 0.0]
    assert second == [1.0, 0.0]
    assert third == [1.0, 0.0]
    assert calls == [("embed-a", "travel wallet"), ("embed-b", "travel wallet")]


def test_embedding_service_does_not_cache_failed_api_query_fallback(monkeypatch, tmp_path) -> None:
    service = EmbeddingService()
    service.settings.embedding_backend = "api"
    service.settings.qwen_plus_api_key = "test-key"
    service.settings.indexes_output_dir = tmp_path

    calls = {"api": 0, "hash": 0}

    def fake_api_embedding(_text: str) -> list[float]:
        calls["api"] += 1
        if calls["api"] == 1:
            raise RuntimeError("temporary embedding failure")
        return [0.8, 0.6]

    def fake_hashed_embedding(_text: str) -> list[float]:
        calls["hash"] += 1
        return [0.0, 1.0]

    monkeypatch.setattr(service, "_api_embedding", fake_api_embedding)
    monkeypatch.setattr(service, "_hashed_embedding", fake_hashed_embedding)

    first = service.embed_query_for_route("travel wallet", "text")
    second = service.embed_query_for_route("travel wallet", "text")

    assert first == [0.0, 1.0]
    assert second == [0.8, 0.6]
    assert calls == {"api": 2, "hash": 1}


def test_embedding_service_caches_clip_query_embeddings_and_invalidates_on_model_change(monkeypatch, tmp_path) -> None:
    service = EmbeddingService()
    service.settings.image_embedding_backend = "clip"
    service.settings.clip_vl_embedding_model = "clip-a"
    service.settings.indexes_output_dir = tmp_path

    calls: list[tuple[str, str]] = []

    def fake_clip_embedding(text: str) -> list[float]:
        calls.append((service.settings.clip_vl_embedding_model, text))
        return [0.2, 0.9]

    monkeypatch.setattr(service, "_clip_text_embedding", fake_clip_embedding)

    first = service.embed_query_for_route("travel wallet", "image")
    second = service.embed_query_for_route("travel wallet", "image")

    service.settings.clip_vl_embedding_model = "clip-b"
    third = service.embed_query_for_route("travel wallet", "image")

    assert first == [0.2, 0.9]
    assert second == [0.2, 0.9]
    assert third == [0.2, 0.9]
    assert calls == [("clip-a", "travel wallet"), ("clip-b", "travel wallet")]


def test_embedding_service_reuses_persisted_query_embedding_across_instances(tmp_path, monkeypatch) -> None:
    first = EmbeddingService()
    first.settings.embedding_backend = "api"
    first.settings.qwen_plus_api_key = "test-key"
    first.settings.qwen_embedding_model = "embed-a"
    first.settings.indexes_output_dir = tmp_path

    monkeypatch.setattr(first, "_api_embedding", lambda _text: [0.6, 0.8])

    persisted = first.embed_query_for_route("travel wallet", "text")

    second = EmbeddingService()
    second.settings.embedding_backend = "api"
    second.settings.qwen_plus_api_key = "test-key"
    second.settings.qwen_embedding_model = "embed-a"
    second.settings.indexes_output_dir = tmp_path

    def _fail(_text: str) -> list[float]:
        raise AssertionError("persisted query embedding should be reused before recomputing")

    monkeypatch.setattr(second, "_api_embedding", _fail)

    reused = second.embed_query_for_route("travel wallet", "text")

    assert persisted == [0.6, 0.8]
    assert reused == [0.6, 0.8]


def test_embedding_service_rejects_persisted_query_embedding_when_signature_changes(tmp_path, monkeypatch) -> None:
    first = EmbeddingService()
    first.settings.embedding_backend = "api"
    first.settings.qwen_plus_api_key = "test-key"
    first.settings.qwen_embedding_model = "embed-a"
    first.settings.indexes_output_dir = tmp_path
    monkeypatch.setattr(first, "_api_embedding", lambda _text: [0.6, 0.8])
    first.embed_query_for_route("travel wallet", "text")

    second = EmbeddingService()
    second.settings.embedding_backend = "api"
    second.settings.qwen_plus_api_key = "test-key"
    second.settings.qwen_embedding_model = "embed-b"
    second.settings.indexes_output_dir = tmp_path

    calls = {"api": 0}

    def _api_embedding(_text: str) -> list[float]:
        calls["api"] += 1
        return [1.0, 0.0]

    monkeypatch.setattr(second, "_api_embedding", _api_embedding)

    vector = second.embed_query_for_route("travel wallet", "text")

    assert vector == [1.0, 0.0]
    assert calls["api"] == 1


def test_reranker_service_reuses_persisted_heuristic_rerank_across_instances(tmp_path, monkeypatch) -> None:
    first = RerankerService()
    first.settings.reranker_backend = "heuristic"
    first.settings.indexes_output_dir = tmp_path
    candidates = [
        IndexedEvidence(
            evidence_id="a",
            product_id="p1",
            category_slug="bags",
            route="text",
            text_block_id="t1",
            content="passport wallet with card storage",
            vector=[0.1, 0.2],
            score=0.9,
        ),
        IndexedEvidence(
            evidence_id="b",
            product_id="p1",
            category_slug="bags",
            route="text",
            text_block_id="t2",
            content="running shoe cushioning",
            vector=[0.1, 0.2],
            score=0.2,
        ),
    ]

    first_result = first.rerank(query="passport wallet", candidates=candidates, use_llm=False)

    second = RerankerService()
    second.settings.reranker_backend = "heuristic"
    second.settings.indexes_output_dir = tmp_path

    def _fail(_candidates: list[IndexedEvidence]) -> list[IndexedEvidence]:
        raise AssertionError("persisted rerank should be reused before recomputing")

    monkeypatch.setattr(second, "_rerank_heuristic", _fail)

    reused = second.rerank(query="passport wallet", candidates=candidates, use_llm=False)

    assert [item.evidence_id for item in first_result] == ["a", "b"]
    assert [item.evidence_id for item in reused] == ["a", "b"]


def test_reranker_service_invalidates_cache_when_candidate_signature_changes(tmp_path, monkeypatch) -> None:
    first = RerankerService()
    first.settings.reranker_backend = "heuristic"
    first.settings.indexes_output_dir = tmp_path
    original_candidates = [
        IndexedEvidence(
            evidence_id="a",
            product_id="p1",
            category_slug="bags",
            route="text",
            text_block_id="t1",
            content="passport wallet with card storage",
            vector=[0.1, 0.2],
            score=0.9,
        ),
        IndexedEvidence(
            evidence_id="b",
            product_id="p1",
            category_slug="bags",
            route="text",
            text_block_id="t2",
            content="running shoe cushioning",
            vector=[0.1, 0.2],
            score=0.2,
        ),
    ]
    first.rerank(query="passport wallet", candidates=original_candidates, use_llm=False)

    second = RerankerService()
    second.settings.reranker_backend = "heuristic"
    second.settings.indexes_output_dir = tmp_path
    changed_candidates = [
        IndexedEvidence.model_validate({**original_candidates[0].model_dump(mode="json"), "score": 0.1}),
        original_candidates[1],
    ]
    calls = {"heuristic": 0}

    def _rerank_heuristic(candidates: list[IndexedEvidence]) -> list[IndexedEvidence]:
        calls["heuristic"] += 1
        return sorted(candidates, key=lambda item: item.score or 0.0, reverse=True)

    monkeypatch.setattr(second, "_rerank_heuristic", _rerank_heuristic)

    reranked = second.rerank(query="passport wallet", candidates=changed_candidates, use_llm=False)

    assert calls["heuristic"] == 1
    assert [item.evidence_id for item in reranked] == ["b", "a"]


def test_reranker_service_uses_multimodal_backend_for_image_candidates(monkeypatch, tmp_path) -> None:
    service = RerankerService()
    service.settings.multimodal_reranker_backend = "qwen_vl"
    service.settings.qwen_plus_api_key = "test-key"
    service.settings.indexes_output_dir = tmp_path

    candidates = [
        IndexedEvidence(
            evidence_id="img_a",
            product_id="backpack_010",
            category_slug="backpack",
            route="image",
            image_id="img_a",
            image_path="images/8512010/img1.png",
            content="zippered travel wallet",
            vector=[0.1, 0.2],
            score=0.2,
        ),
        IndexedEvidence(
            evidence_id="img_b",
            product_id="backpack_010",
            category_slug="backpack",
            route="image",
            image_id="img_b",
            image_path="images/8512010/img2.png",
            content="passport compartment close-up",
            vector=[0.2, 0.1],
            score=0.1,
        ),
    ]

    def fake_multimodal_rerank(query: str, image_candidates: list[IndexedEvidence]) -> list[IndexedEvidence]:
        assert query == "passport wallet"
        return [
            IndexedEvidence.model_validate({**image_candidates[1].model_dump(mode="json"), "score": 0.93}),
            IndexedEvidence.model_validate({**image_candidates[0].model_dump(mode="json"), "score": 0.11}),
        ]

    monkeypatch.setattr(service, "_rerank_image_candidates_with_vl", fake_multimodal_rerank)

    reranked = service.rerank(query="passport wallet", candidates=candidates, use_llm=True)

    assert reranked[0].evidence_id == "img_b"
    assert reranked[0].score == 0.93


def test_embedding_service_raises_when_strict_policy_forbids_api_fallback(tmp_path, monkeypatch) -> None:
    policy_path = tmp_path / "runtime_execution_policy.json"
    policy_path.write_text('{"allow_degradation": false, "full_power": true}', encoding="utf-8")
    monkeypatch.setenv("RUNTIME_EXECUTION_POLICY_PATH", str(policy_path))
    get_settings.cache_clear()

    service = EmbeddingService()
    service.settings.embedding_backend = "api"
    service.settings.qwen_plus_api_key = "test-key"
    service.settings.indexes_output_dir = tmp_path

    def _fail(_text: str) -> list[float]:
        raise RuntimeError("embedding backend down")

    monkeypatch.setattr(service, "_api_embedding", _fail)

    with pytest.raises(RuntimePolicyError, match="query_embedding"):
        service.embed_query_for_route("travel wallet", "text")


def test_reranker_service_raises_when_strict_policy_forbids_api_fallback(tmp_path, monkeypatch) -> None:
    policy_path = tmp_path / "runtime_execution_policy.json"
    policy_path.write_text('{"allow_degradation": false, "full_power": true}', encoding="utf-8")
    monkeypatch.setenv("RUNTIME_EXECUTION_POLICY_PATH", str(policy_path))
    get_settings.cache_clear()

    service = RerankerService()
    service.settings.reranker_backend = "api"
    service.settings.qwen_plus_api_key = "test-key"
    service.settings.indexes_output_dir = tmp_path

    candidates = [
        IndexedEvidence(
            evidence_id="a",
            product_id="p1",
            category_slug="bags",
            route="text",
            text_block_id="t1",
            content="passport wallet with card storage",
            vector=[0.1, 0.2],
            score=0.9,
        )
    ]

    def _fail_api(_query: str, _candidates: list[IndexedEvidence]) -> list[IndexedEvidence]:
        raise RuntimeError("reranker backend down")

    monkeypatch.setattr(service, "_rerank_with_api", _fail_api)

    with pytest.raises(RuntimePolicyError, match="text_rerank"):
        service.rerank(query="passport wallet", candidates=candidates, use_llm=True)