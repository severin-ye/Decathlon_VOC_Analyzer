from fastapi.testclient import TestClient

from decathlon_voc_analyzer.app.api.main import app


client = TestClient(app)


def test_product_analysis_endpoint_runs_end_to_end() -> None:
    response = client.post(
        "/api/v1/analysis/product",
        json={
            "product_id": "backpack_010",
            "category_slug": "backpack",
            "max_reviews": 8,
            "use_llm": False,
            "top_k_per_route": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_mode"] == "heuristic"
    assert payload["report"]["product_id"] == "backpack_010"
    assert len(payload["questions"]) >= 1
    assert len(payload["retrievals"]) >= 1
    assert payload["retrievals"][0]["source_question_id"]
    assert payload["retrievals"][0]["source_question"]
    assert len(payload["aggregates"]) >= 1
    assert payload["report"]["answer"]
    assert payload["report"]["supporting_product_evidence"]["product_text_block_ids"]
    assert payload["trace"]
    assert payload["retrieval_quality"]
    assert payload["retrieval_runtime"]["image_embedding_backend"] == "proxy_text"
    assert payload["retrieval_runtime"]["native_multimodal_enabled"] is False
    assert payload["replay_summary"] is None
    assert payload["artifact_bundle"] is None
    assert payload["report"]["strengths"][0]["owner"]
    assert payload["report"]["strengths"][0]["confidence_breakdown"]["final_confidence"] >= 0.0
    assert payload["retrieval_quality"][0]["top_k_count"] >= 1
