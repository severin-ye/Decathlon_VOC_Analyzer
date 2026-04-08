import json

from decathlon_voc_analyzer.services.embedding_service import EmbeddingService
from decathlon_voc_analyzer.services.reranker_service import RerankerService
from decathlon_voc_analyzer.models.index import IndexedEvidence


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

    monkeypatch.setattr("decathlon_voc_analyzer.services.reranker_service.request.urlopen", fake_urlopen)

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