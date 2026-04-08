from fastapi.testclient import TestClient

from decathlon_voc_analyzer.api.main import app


client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


def test_dataset_overview_endpoint() -> None:
    response = client.get("/api/v1/dataset/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_products"] > 0
    assert payload["category_count"] > 0


def test_dataset_normalize_endpoint() -> None:
    response = client.post(
        "/api/v1/dataset/normalize",
        json={"categories": ["backpack"], "max_products": 1, "persist_artifacts": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"]["scanned_products"] == 1
    assert payload["stats"]["normalized_products"] == 1