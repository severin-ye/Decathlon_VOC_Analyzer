from decathlon_voc_analyzer.schemas.analysis import RetrievalQuestion
from decathlon_voc_analyzer.schemas.dataset import ProductEvidencePackage
from decathlon_voc_analyzer.schemas.index import IndexedEvidence
import decathlon_voc_analyzer.stage3_retrieval.retrieval_service as retrieval_service_module
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


def test_retrieval_service_balances_languages_within_same_route(monkeypatch) -> None:
    service = RetrievalService()
    package = ProductEvidencePackage(
        product_id="backpack_010",
        category_slug="backpack",
        source_dir=".",
    )
    question = RetrievalQuestion(
        question_id="q_lang",
        source_review_id="r1",
        source_aspect="storage",
        source_aspect_id="a1",
        question="What storage evidence exists across languages?",
        rationale="Need multilingual storage support",
        expected_evidence_routes=["text"],
        confidence=0.8,
    )
    reranked_hits = [
        IndexedEvidence(
            evidence_id="text_ko",
            product_id="backpack_010",
            category_slug="backpack",
            route="text",
            doc_type="title",
            text_block_id="t_ko",
            source_section="product_name",
            content="백패킹 오거나이저 여행 지갑 S",
            content_original="백패킹 오거나이저 여행 지갑 S",
            content_normalized="백패킹 오거나이저 여행 지갑 S",
            language="ko",
            vector=[0.1, 0.2],
            score=0.98,
        ),
        IndexedEvidence(
            evidence_id="text_en",
            product_id="backpack_010",
            category_slug="backpack",
            route="text",
            doc_type="description",
            text_block_id="t_en",
            source_section="review_quote",
            content="great for travelling as it fits your passport and everything you need",
            content_original="great for travelling as it fits your passport and everything you need",
            content_normalized="great for travelling as it fits your passport and everything you need",
            language="latin",
            vector=[0.1, 0.2],
            score=0.92,
        ),
        IndexedEvidence(
            evidence_id="text_en_2",
            product_id="backpack_010",
            category_slug="backpack",
            route="text",
            doc_type="category",
            text_block_id="t_en_2",
            source_section="category",
            content="travel wallet passport storage",
            content_original="travel wallet passport storage",
            content_normalized="travel wallet passport storage",
            language="latin",
            vector=[0.1, 0.2],
            score=0.85,
        ),
    ]

    monkeypatch.setattr(service.index_service, "search", lambda **_: reranked_hits)
    monkeypatch.setattr(service.reranker_service, "rerank", lambda **kwargs: kwargs["candidates"])

    result = service.retrieve_for_package(
        package=package,
        questions=[question],
        top_k_per_route=2,
        use_llm=False,
    )[0]

    assert len(result.retrieved) == 2
    assert {item.language for item in result.retrieved} == {"ko", "latin"}
    assert result.retrieved[0].content_original is not None


def test_retrieval_service_updates_current_activity_before_advancing(monkeypatch) -> None:
    class FakeProgress:
        def __init__(self) -> None:
            self.updated: list[str] = []
            self.advanced: list[str] = []

        def start_count_step(self, *args, **kwargs) -> None:
            return None

        def update_step(self, module_key: str, step_key: str, detail: str | None = None) -> None:
            if detail is not None:
                self.updated.append(detail)

        def advance_step(self, module_key: str, step_key: str, amount: float = 1.0, detail: str | None = None) -> None:
            if detail is not None:
                self.advanced.append(detail)

        def complete_step(self, *args, **kwargs) -> None:
            return None

    progress = FakeProgress()
    service = RetrievalService()
    package = ProductEvidencePackage(
        product_id="backpack_010",
        category_slug="backpack",
        source_dir=".",
    )
    question = RetrievalQuestion(
        question_id="q_progress",
        source_review_id="r1",
        source_aspect="storage",
        source_aspect_id="a1",
        question="Where is the front pocket shown?",
        rationale="Need visual confirmation",
        expected_evidence_routes=["image"],
        confidence=0.8,
    )
    image_hit = IndexedEvidence(
        evidence_id="img_a",
        product_id="backpack_010",
        category_slug="backpack",
        route="image",
        image_id="img1",
        image_path="images/img1.png",
        content="front pocket image",
        vector=[0.1, 0.2],
        score=0.7,
    )

    monkeypatch.setattr(retrieval_service_module, "get_workflow_progress", lambda: progress)
    monkeypatch.setattr(service.index_service, "search", lambda **_: [image_hit])

    def fake_rerank(**kwargs):
        kwargs["progress_status_callback"]("正在进行图像重排（1 条候选）")
        kwargs["progress_callback"]("图像重排完成: 1 条候选")
        return kwargs["candidates"]

    monkeypatch.setattr(service.reranker_service, "rerank", fake_rerank)

    service.retrieve_for_package(
        package=package,
        questions=[question],
        top_k_per_route=1,
        use_llm=False,
    )

    assert progress.updated[0].startswith("[1/1] 正在执行 search（若索引缺失会按需建索引）")
    assert any("正在进行图像重排（1 条候选）" in detail for detail in progress.updated)
    assert any("正在汇总最终证据" in detail for detail in progress.updated)
    assert any("search 完成，召回候选 1 条" in detail for detail in progress.advanced)
    assert any("图像重排完成: 1 条候选" in detail for detail in progress.advanced)
    assert any("汇总完成，证据 1 条" in detail for detail in progress.advanced)