from fastapi.testclient import TestClient

from decathlon_voc_analyzer.app.api.main import app


client = TestClient(app)


def test_reviews_extract_from_inline_reviews() -> None:
    response = client.post(
        "/api/v1/reviews/extract",
        json={
            "product_id": "demo_product",
            "use_llm": False,
            "reviews": [
                {
                    "review_id": "r1",
                    "product_id": "demo_product",
                    "rating": 5,
                    "review_text": "Great for travel, fits passport and cards, very practical.",
                },
                {
                    "review_id": "r2",
                    "product_id": "demo_product",
                    "rating": 1,
                    "review_text": "Too stiff and hard to use.",
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["extraction_mode"] == "heuristic"
    assert len(payload["aspects"]) >= 2
    assert payload["skipped_review_ids"] == []


def test_reviews_extract_from_dataset_product() -> None:
    response = client.post(
        "/api/v1/reviews/extract",
        json={
            "product_id": "backpack_010",
            "category_slug": "backpack",
            "max_reviews": 5,
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["product_id"] == "backpack_010"
    assert len(payload["preprocessed_reviews"]) == 5
    assert len(payload["aspects"]) >= 1