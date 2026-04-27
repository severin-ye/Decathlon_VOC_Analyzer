from decathlon_voc_analyzer.schemas.analysis import RetrievalQuestion
from decathlon_voc_analyzer.schemas.dataset import ProductEvidencePackage
from decathlon_voc_analyzer.schemas.index import IndexedEvidence
from decathlon_voc_analyzer.stage3_retrieval.retrieval_service import RetrievalService


def test_retrieval_service_preserves_route_coverage_for_multiroute_questions(monkeypatch) -> None:
    service = RetrievalService()
    package = ProductEvidencePackage(
        product_id="backpack_010",
        category_slug="backpack",
        source_dir=".",
    )
    question = RetrievalQuestion(
        question_id="q1",
        source_review_id="r1",
        source_aspect="storage",
        source_aspect_id="a1",
        question="Is there both textual and visual evidence for storage?",
        rationale="storage concern",
        expected_evidence_routes=["text", "image"],
        confidence=0.8,
    )
    reranked_hits = [
        IndexedEvidence(
            evidence_id="text_a",
            product_id="backpack_010",
            category_slug="backpack",
            route="text",
            text_block_id="t1",
            content="Storage compartments and pockets overview",
            vector=[0.1, 0.2],
            score=0.98,
        ),
        IndexedEvidence(
            evidence_id="text_b",
            product_id="backpack_010",
            category_slug="backpack",
            route="text",
            text_block_id="t2",
            content="Extra zipper pocket description",
            vector=[0.1, 0.2],
            score=0.92,
        ),
        IndexedEvidence(
            evidence_id="img_a",
            product_id="backpack_010",
            category_slug="backpack",
            route="image",
            image_id="img1",
            image_path="images/img1.png",
            content="Open backpack showing internal compartments",
            vector=[0.1, 0.2],
            score=0.67,
        ),
    ]

    monkeypatch.setattr(service.index_service, "search", lambda **_: reranked_hits)
    monkeypatch.setattr(service.reranker_service, "rerank", lambda **_: reranked_hits)

    result = service.retrieve_for_package(
        package=package,
        questions=[question],
        top_k_per_route=1,
        use_llm=False,
    )[0]

    assert len(result.retrieved) == 2
    assert {item.route for item in result.retrieved} == {"text", "image"}
    assert result.retrieved[0].text_block_id == "t1"


def test_retrieval_service_preserves_region_metadata(monkeypatch) -> None:
    service = RetrievalService()
    package = ProductEvidencePackage(
        product_id="backpack_010",
        category_slug="backpack",
        source_dir=".",
    )
    question = RetrievalQuestion(
        question_id="q_region",
        source_review_id="r1",
        source_aspect="storage",
        source_aspect_id="a1",
        question="Show the storage compartment detail.",
        rationale="storage concern",
        expected_evidence_routes=["image"],
        confidence=0.8,
    )
    region_hit = IndexedEvidence(
        evidence_id="img_region_a",
        product_id="backpack_010",
        category_slug="backpack",
        route="image",
        image_id="img1",
        image_path="images/img1.png",
        region_id="img1_region_center",
        region_label="center_focus",
        region_box=[10, 20, 80, 120],
        content="Storage compartment center detail",
        vector=[0.1, 0.2],
        score=0.88,
    )

    monkeypatch.setattr(service.index_service, "search", lambda **_: [region_hit])
    monkeypatch.setattr(service.reranker_service, "rerank", lambda **_: [region_hit])

    result = service.retrieve_for_package(
        package=package,
        questions=[question],
        top_k_per_route=1,
        use_llm=False,
    )[0]

    assert len(result.retrieved) == 1
    assert result.retrieved[0].region_id == "img1_region_center"
    assert result.retrieved[0].region_label == "center_focus"
    assert result.retrieved[0].region_box == [10, 20, 80, 120]