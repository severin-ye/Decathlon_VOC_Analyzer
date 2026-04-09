from fastapi.testclient import TestClient

from decathlon_voc_analyzer.app.api.main import app


client = TestClient(app)


def test_index_build_endpoint() -> None:
    response = client.post(
        "/api/v1/index/build",
        json={"categories": ["backpack"], "max_products": 2, "persist_artifact": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"]["indexed_products"] == 2
    assert payload["stats"]["indexed_text_blocks"] >= 1
    assert payload["stats"]["indexed_images"] >= 1
    assert payload["index_path"]


def test_index_overview_endpoint() -> None:
    response = client.get("/api/v1/index/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "local"
    assert payload["indexed_products"] >= 0