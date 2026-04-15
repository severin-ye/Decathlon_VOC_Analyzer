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


def test_reviews_extract_returns_sampling_plan() -> None:
    reviews = []
    for rating, count in [(5, 8), (4, 8), (3, 8), (2, 8), (1, 8)]:
        for index in range(count):
            reviews.append(
                {
                    "review_id": f"r{rating}_{index}",
                    "product_id": "demo_product",
                    "rating": rating,
                    "review_text": f"Rating {rating} review {index} about travel pocket usage and storage.",
                }
            )

    response = client.post(
        "/api/v1/reviews/extract",
        json={
            "product_id": "demo_product",
            "use_llm": False,
            "max_reviews": 20,
            "reviews": reviews,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sampling_plan"] is not None
    selected_by_rating = {item["rating"]: item["selected_count"] for item in payload["sampling_plan"]["allocations"]}
    assert selected_by_rating[1] == 6
    assert selected_by_rating[2] == 5


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