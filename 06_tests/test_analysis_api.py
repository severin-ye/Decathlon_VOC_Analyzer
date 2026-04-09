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
