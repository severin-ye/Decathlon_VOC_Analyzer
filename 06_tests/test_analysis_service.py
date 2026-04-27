from pathlib import Path

import orjson
import pytest

from decathlon_voc_analyzer.schemas.analysis import (
    ImprovementSuggestion,
    InsightItem,
    ProductAnalysisRequest,
    RetrievedEvidence,
    RetrievalRecord,
    SupportingEvidence,
)
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
    assert result.report.supporting_reviews


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


def test_product_analysis_service_derives_impression_models() -> None:
    service = ProductAnalysisService()

    result = service.analyze(
        ProductAnalysisRequest(
            product_id="backpack_010",
            category_slug="backpack",
            max_reviews=8,
            use_llm=False,
            top_k_per_route=1,
        )
    )

    assert result.report.product_impressions
    assert result.report.product_impressions[0].aspect_frequency >= 1
    assert result.report.product_impressions[0].representative_review_ids
    if result.report.applicable_scenes:
        assert result.report.customer_impressions
        assert result.report.customer_impressions[0].scene
        assert result.report.customer_impressions[0].focus_aspects


def test_product_analysis_service_normalizes_prompt_variant_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMPT_VARIANT", "en")
    service = ProductAnalysisService()

    assert service._scene_segment_label("commute") == "Users in the 'commute' scenario"


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
    assert all(0.0 <= metric.route_coverage <= 1.0 for metric in result.retrieval_quality)
    assert all(0.0 <= metric.answer_coverage <= 1.0 for metric in result.retrieval_quality)
    assert all(0.0 <= metric.score_drift <= 1.0 for metric in result.retrieval_quality)


def test_product_analysis_service_hydrates_llm_insights_by_review_reference() -> None:
    service = ProductAnalysisService()
    fallback_items = [
        InsightItem(
            label="rubber insert durability",
            summary="fallback 1",
            confidence=0.9,
            supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0021"]),
        ),
        InsightItem(
            label="optical accuracy",
            summary="fallback 2",
            confidence=0.9,
            supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0064"]),
        ),
    ]

    hydrated = service._hydrate_insights(
        [
            {
                "label": "Optical accuracy degrades spatial perception during navigation",
                "summary": "A review (sunglasses_010_review_0064) reports impaired visual function during navigation.",
                "confidence": 0.8,
            }
        ],
        fallback_items,
    )

    assert hydrated[0].supporting_evidence.review_ids == ["sunglasses_010_review_0064"]


def test_product_analysis_service_hydrates_cross_section_controversy_evidence() -> None:
    service = ProductAnalysisService()
    controversy_fallback = [
        InsightItem(
            label="rubber insert durability controversy",
            summary="fallback controversy",
            confidence=0.8,
            supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0021"]),
        )
    ]
    evidence_candidates = controversy_fallback + [
        InsightItem(
            label="optical accuracy",
            summary="walking or navigating terrain issue",
            confidence=0.8,
            supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0064"]),
        )
    ]

    hydrated = service._hydrate_insights(
        [
            {
                "label": "Optical accuracy",
                "summary": "A review (sunglasses_010_review_0064) reports optical inaccuracy specifically when walking or navigating terrain.",
                "confidence": 0.8,
            }
        ],
        controversy_fallback,
        evidence_candidates=evidence_candidates,
    )

    assert hydrated[0].supporting_evidence.review_ids == ["sunglasses_010_review_0064"]


def test_product_analysis_service_hydrates_suggestions_by_text_similarity() -> None:
    service = ProductAnalysisService()
    fallback_items = [
        ImprovementSuggestion(
            suggestion="Publish durability specifications for rubber inserts.",
            suggestion_type="perception",
            reason=["rubber insert failure under long-term wear"],
            confidence=0.8,
            supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0021"]),
        ),
        ImprovementSuggestion(
            suggestion="Add optical performance claims and test summaries.",
            suggestion_type="perception",
            reason=["optical accuracy issue while navigating terrain"],
            confidence=0.8,
            supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0064"]),
        ),
    ]

    hydrated = service._hydrate_suggestions(
        [
            {
                "suggestion": "Add optical performance claims and validate with third-party tests.",
                "suggestion_type": "perception",
                "reason": ["Optical accuracy is negatively reported in a functional scene while navigating terrain."],
                "confidence": 0.8,
            }
        ],
        fallback_items,
    )

    assert hydrated[0].supporting_evidence.review_ids == ["sunglasses_010_review_0064"]


def test_product_analysis_service_hydrates_suggestions_from_related_insights() -> None:
    service = ProductAnalysisService()
    evidence_candidates = [
        ImprovementSuggestion(
            suggestion="Add optical performance claims and test summaries.",
            suggestion_type="perception",
            reason=["optical accuracy issue while navigating terrain"],
            confidence=0.8,
            supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0064"]),
        ),
        InsightItem(
            label="price",
            summary="excellent price sentiment from sunglasses_010_review_0064",
            confidence=0.8,
            supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0064"]),
        ),
    ]

    hydrated = service._hydrate_suggestions(
        [
            {
                "suggestion": "Surface the exact listed price and any active promotions in primary product metadata.",
                "suggestion_type": "perception",
                "reason": ["No numeric price or discount indicators were retrieved despite a positive price sentiment."],
                "confidence": 0.8,
            }
        ],
        [],
        evidence_candidates=evidence_candidates,
    )

    assert hydrated[0].supporting_evidence.review_ids == ["sunglasses_010_review_0064"]


def test_product_analysis_service_tracks_mixed_ratio_in_aggregates() -> None:
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

    assert all(0.0 <= aggregate.mixed_ratio <= 1.0 for aggregate in result.aggregates)


def test_product_analysis_service_uses_conservative_answer_coverage_for_unanswered_hits() -> None:
    service = ProductAnalysisService()

    retrievals = [
        RetrievalRecord(
            retrieval_id="r1",
            product_id="demo_product",
            query="What is the listed price of the product on the product page?",
            source_review_id="review_1",
            source_aspect="price",
            source_question_id="q1",
            source_question="What is the listed price of the product on the product page?",
            source_evidence_span="Need actual price value.",
            expected_evidence_routes=["text"],
            retrieved=[
                RetrievedEvidence(
                    product_id="demo_product",
                    route="text",
                    text_block_id="product_name",
                    source_section="product_name",
                    content_preview="MH580 Sports Polarized Sunglasses",
                    embedding_score=0.31,
                    rerank_score=0.07,
                ),
                RetrievedEvidence(
                    product_id="demo_product",
                    route="text",
                    text_block_id="category",
                    source_section="category",
                    content_preview="All Sports > Running > Accessories > Sunglasses",
                    embedding_score=0.32,
                    rerank_score=0.06,
                ),
            ],
        )
    ]

    price_metric = service._assess_retrieval_quality(retrievals)[0]
    assert price_metric.route_coverage >= 0.5
    assert price_metric.answer_coverage == 0.0


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


def test_product_analysis_service_can_apply_feedback_aware_replay() -> None:
    service = ProductAnalysisService()

    first = service.analyze(
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

    assert first.artifact_bundle is not None
    feedback_path = first.artifact_bundle.feedback_path
    assert feedback_path is not None

    payload = orjson.loads(Path(feedback_path).read_bytes())
    payload["slots"][0]["status"] = "accepted"
    payload["slots"][0]["reviewer_note"] = "confirmed in manual review"
    Path(feedback_path).write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))

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
    assert replayed.replay_summary.reviewed_slot_count >= 1
    assert replayed.replay_summary.feedback_path is not None
    assert replayed.replay_summary.accepted_issue_labels
    assert any("Reviewer feedback" in reason or "人工反馈" in reason for suggestion in replayed.report.suggestions for reason in suggestion.reason)

    preserved_payload = orjson.loads(Path(feedback_path).read_bytes())
    assert preserved_payload["slots"][0]["status"] == "accepted"