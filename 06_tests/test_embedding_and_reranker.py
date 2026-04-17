import json
from pathlib import Path

from decathlon_voc_analyzer.schemas.index import IndexedEvidence
from decathlon_voc_analyzer.stage3_retrieval.embedding_service import EmbeddingService
from decathlon_voc_analyzer.stage3_retrieval.reranker_service import RerankerService


def test_embedding_service_returns_non_empty_vector() -> None:
    service = EmbeddingService()

    vector = service.embed_text("travel wallet passport cards")

    assert vector
    assert len(vector) == service.vector_size()


def test_reranker_service_returns_sorted_candidates() -> None:
    service = RerankerService()
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


def test_reranker_service_uses_dedicated_api(monkeypatch) -> None:
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

    monkeypatch.setattr(service, "_clip_image_embedding", lambda _path: [0.0, 1.0])
    monkeypatch.setattr(service, "_clip_text_embedding", lambda _text: [1.0, 0.0])

    image_path = tmp_path / "probe.png"
    image_path.write_bytes(b"fake-image")

    image_vector = service.embed_image(image_path=image_path, text_hint="wallet")
    query_vector = service.embed_query_for_route("travel wallet", "image")

    assert image_vector == [0.0, 1.0]
    assert query_vector == [1.0, 0.0]


def test_reranker_service_uses_multimodal_backend_for_image_candidates(monkeypatch) -> None:
    service = RerankerService()
    service.settings.multimodal_reranker_backend = "qwen_vl"
    service.settings.qwen_plus_api_key = "test-key"

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