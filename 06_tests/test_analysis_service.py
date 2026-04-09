from decathlon_voc_analyzer.schemas.analysis import ProductAnalysisRequest
from decathlon_voc_analyzer.stage4_generation.analysis_service import ProductAnalysisService


def test_product_analysis_service_returns_report_and_retrievals() -> None:
    service = ProductAnalysisService()

    result = service.analyze(
        ProductAnalysisRequest(
            product_id="backpack_010",
            category_slug="backpack",
            max_reviews=6,
            use_llm=False,
            top_k_per_route=2,
        )
    )

    assert result.analysis_mode == "heuristic"
    assert result.report.product_id == "backpack_010"
    assert len(result.questions) >= 1
    assert len(result.retrievals) >= 1
    assert result.retrievals[0].source_question_id
    assert result.retrievals[0].source_question
    assert len(result.aggregates) >= 1
    assert len(result.report.supporting_aspects) >= 1
    assert result.report.supporting_product_evidence.product_image_ids
    assert result.report.supporting_product_evidence.product_text_block_ids


def test_product_analysis_service_builds_improvement_suggestions() -> None:
    service = ProductAnalysisService()

    result = service.analyze(
        ProductAnalysisRequest(
            product_id="backpack_010",
            category_slug="backpack",
            max_reviews=12,
            use_llm=False,
            top_k_per_route=1,
        )
    )

    assert result.report.suggestions
    assert all(suggestion.reason for suggestion in result.report.suggestions)
    assert all(
        suggestion.supporting_evidence.review_ids for suggestion in result.report.suggestions
    )


def test_product_analysis_service_generates_questions_before_retrieval() -> None:
    service = ProductAnalysisService()

    result = service.analyze(
        ProductAnalysisRequest(
            product_id="backpack_010",
            category_slug="backpack",
            max_reviews=4,
            use_llm=False,
            top_k_per_route=1,
            questions_per_aspect=2,
        )
    )

    assert result.questions
    assert all(question.question for question in result.questions)
    assert all(question.expected_evidence_routes for question in result.questions)
    question_ids = {question.question_id for question in result.questions}
    assert all(retrieval.source_question_id in question_ids for retrieval in result.retrievals)