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


def test_product_analysis_service_emits_trace_and_owner_metadata() -> None:
    service = ProductAnalysisService()

    result = service.analyze(
        ProductAnalysisRequest(
            product_id="backpack_010",
            category_slug="backpack",
            max_reviews=4,
            use_llm=False,
            top_k_per_route=1,
        )
    )

    assert result.trace
    assert any(item.trace_type == "observation" for item in result.trace)
    assert any(item.trace_type == "action_generation" for item in result.trace)
    allowed_owners = {"product_issue", "content_presentation", "evidence_gap", "expectation_mismatch"}
    assert all(item.owner in allowed_owners for item in result.report.strengths + result.report.weaknesses + result.report.controversies)
    assert all(item.confidence_breakdown is not None for item in result.report.strengths + result.report.weaknesses + result.report.controversies)
    assert all(item.confidence_breakdown.final_confidence >= 0.0 for item in result.report.strengths + result.report.weaknesses + result.report.controversies)
    assert result.retrieval_quality
    assert result.retrieval_runtime.image_embedding_backend == "proxy_text"
    assert result.retrieval_runtime.native_multimodal_enabled is False
    assert "proxy text" in result.retrieval_runtime.summary.lower() or "代理文本" in result.retrieval_runtime.summary
    assert result.artifact_bundle is None
    assert all(metric.top_k_count >= 1 for metric in result.retrieval_quality)
    assert all(0.0 <= metric.evidence_coverage <= 1.0 for metric in result.retrieval_quality)
    assert all(0.0 <= metric.score_drift <= 1.0 for metric in result.retrieval_quality)


def test_product_analysis_service_returns_artifact_bundle_when_persisted() -> None:
    service = ProductAnalysisService()

    result = service.analyze(
        ProductAnalysisRequest(
            product_id="backpack_010",
            category_slug="backpack",
            max_reviews=4,
            use_llm=False,
            top_k_per_route=1,
            persist_artifact=True,
        )
    )

    assert result.artifact_bundle is not None
    assert result.artifact_bundle.analysis_path == result.artifact_path
    assert result.artifact_bundle.feedback_path is not None
    assert result.artifact_bundle.replay_path is not None


def test_product_analysis_service_can_apply_replay_continuity() -> None:
    service = ProductAnalysisService()

    service.analyze(
        ProductAnalysisRequest(
            product_id="backpack_010",
            category_slug="backpack",
            max_reviews=4,
            use_llm=False,
            top_k_per_route=1,
            persist_artifact=True,
            use_replay=False,
        )
    )

    replayed = service.analyze(
        ProductAnalysisRequest(
            product_id="backpack_010",
            category_slug="backpack",
            max_reviews=4,
            use_llm=False,
            top_k_per_route=1,
            persist_artifact=True,
            use_replay=True,
        )
    )

    assert replayed.replay_summary is not None
    assert replayed.replay_summary.applied is True
    assert replayed.replay_summary.replay_path.endswith("backpack_010_replay.json")
    assert any(item.aspect == "replay_continuity" for item in replayed.trace)
    assert any("replay" in warning.lower() or "回放" in warning for warning in replayed.warnings)