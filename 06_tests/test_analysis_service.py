from pathlib import Path

import orjson
import pytest

from decathlon_voc_analyzer.schemas.analysis import (
    AnalysisCheckpointPayload,
    AspectAggregate,
    EvidenceGapItem,
    ImprovementSuggestion,
    InsightItem,
    ProductAnalysisReport,
    ProductAnalysisRequest,
    QuestionIntent,
    ReplayContinuationSummary,
    RetrievedEvidence,
    RetrievalQualityMetrics,
    RetrievalRuntimeProfile,
    RetrievalQuestion,
    RetrievalRecord,
    SupportingEvidence,
)
from decathlon_voc_analyzer.schemas.review import ReviewAspect, ReviewExtractionResponse
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

    assert result.schema_version == "1.1.0"
    assert result.analysis_mode == "heuristic"
    assert result.report.product_id == "backpack_010"
    assert len(result.questions) >= 1
    assert len(result.retrievals) >= 1
    assert result.retrievals[0].source_question_id
    assert result.retrievals[0].source_question
    assert len(result.aggregates) >= 1
    assert len(result.report.supporting_aspects) >= 1
    assert result.report.supporting_reviews


def test_product_analysis_service_emits_evidence_nodes_and_claim_attributions() -> None:
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

    assert result.report.evidence_nodes
    assert result.report.claim_attributions

    node_ids = {node.evidence_node_id for node in result.report.evidence_nodes}
    assert any(node.source_type == "review" for node in result.report.evidence_nodes)
    assert any(node.source_type in {"product_text", "product_image"} for node in result.report.evidence_nodes)
    assert any(attribution.claim_source == "suggestion" for attribution in result.report.claim_attributions)
    assert all(attribution.claim_id for attribution in result.report.claim_attributions)
    assert all(attribution.support_status in {"supported", "partial", "unsupported"} for attribution in result.report.claim_attributions)
    assert all(support_id in node_ids for attribution in result.report.claim_attributions for support_id in attribution.support_ids)


def test_product_analysis_service_can_reuse_persisted_extraction_artifact(monkeypatch) -> None:
    service = ProductAnalysisService()
    extraction = ReviewExtractionResponse(
        product_id="backpack_010",
        category_slug="backpack",
        extraction_mode="llm",
        preprocessed_reviews=[],
        aspects=[],
        skipped_review_ids=[],
        warnings=[],
        artifact_path="/tmp/backpack_010.json",
    )

    monkeypatch.setattr(
        service.review_service,
        "load_persisted_result",
        lambda product_id, category_slug: extraction,
    )

    def _fail_extract(*args, **kwargs):
        raise AssertionError("extract should not be called when reuse_extraction_artifact=True")

    monkeypatch.setattr(service.review_service, "extract", _fail_extract)

    resolved = service._resolve_extraction(
        ProductAnalysisRequest(
            product_id="backpack_010",
            category_slug="backpack",
            use_llm=True,
            reuse_extraction_artifact=True,
        )
    )

    assert resolved is extraction


def test_analysis_checkpoint_roundtrip_requires_exact_signature(tmp_path) -> None:
    service = ProductAnalysisService()
    service.settings.reports_output_dir = tmp_path
    extraction = ReviewExtractionResponse(
        product_id="backpack_010",
        category_slug="backpack",
        extraction_mode="llm",
        preprocessed_reviews=[],
        aspects=[],
        skipped_review_ids=[],
        warnings=[],
        artifact_path="/tmp/backpack_010.json",
    )
    request = ProductAnalysisRequest(
        product_id="backpack_010",
        category_slug="backpack",
        max_reviews=25,
        use_llm=True,
        questions_per_aspect=2,
        top_k_per_route=2,
        reuse_analysis_checkpoint=True,
    )
    retrieval_runtime = RetrievalRuntimeProfile(
        text_embedding_backend="api",
        text_embedding_model="text-embedding-v4",
        image_embedding_backend="clip",
        image_embedding_model="openai/clip-vit-base-patch32",
        reranker_backend="api",
        reranker_model="gte-rerank-v2",
        multimodal_reranker_backend="qwen_vl",
        multimodal_reranker_model="qwen-vl-max-latest",
        native_multimodal_enabled=True,
        summary="demo",
    )
    question_intent = QuestionIntent(
        intent_id="intent_1",
        source_review_id="review_1",
        source_aspect="value_price",
        source_aspect_id="aspect_1",
        intent_type="explicit_support",
        rationale="demo",
        expected_evidence_routes=["text"],
    )
    question = RetrievalQuestion(
        question_id="q1",
        source_review_id="review_1",
        source_aspect="value_price",
        source_aspect_id="aspect_1",
        question="demo question",
        rationale="demo",
        expected_evidence_routes=["text"],
        confidence=0.7,
    )
    retrieval = RetrievalRecord(
        retrieval_id="r1",
        product_id="backpack_010",
        query="demo question",
        source_review_id="review_1",
        source_aspect="value_price",
        source_question_id="q1",
        source_question="demo question",
        source_evidence_span="demo",
        expected_evidence_routes=["text"],
        retrieved=[],
    )
    metric = RetrievalQualityMetrics(
        retrieval_id="r1",
        source_aspect="value_price",
        top_k_count=1,
        route_coverage=1.0,
        answer_coverage=1.0,
        answer_status="supported",
        evidence_coverage=1.0,
        score_drift=0.0,
        text_coverage=True,
        image_coverage=False,
        conflict_risk=0.0,
        retrieval_quality_label="good",
        failure_reason="none",
        corrective_action="keep_current",
    )

    checkpoint_path = service._persist_analysis_checkpoint(
        request=request,
        extraction=extraction,
        question_intents=[question_intent],
        questions=[question],
        question_mode="llm",
        question_warnings=["qwarn"],
        retrievals=[retrieval],
        retrieval_quality=[metric],
        corrective_warnings=["rwarn"],
        retrieval_runtime=retrieval_runtime,
    )

    assert Path(checkpoint_path).exists()

    loaded = service._load_analysis_checkpoint(request=request, extraction=extraction)

    assert loaded.question_mode == "llm"
    assert loaded.question_warnings == ["qwarn"]
    assert loaded.corrective_warnings == ["rwarn"]
    assert loaded.questions[0].question_id == "q1"
    assert loaded.retrieval_quality[0].retrieval_id == "r1"


def test_analysis_checkpoint_rejects_mismatched_request_signature(tmp_path) -> None:
    service = ProductAnalysisService()
    service.settings.reports_output_dir = tmp_path
    extraction = ReviewExtractionResponse(
        product_id="backpack_010",
        category_slug="backpack",
        extraction_mode="llm",
        preprocessed_reviews=[],
        aspects=[],
        skipped_review_ids=[],
        warnings=[],
        artifact_path="/tmp/backpack_010.json",
    )
    base_request = ProductAnalysisRequest(
        product_id="backpack_010",
        category_slug="backpack",
        max_reviews=25,
        use_llm=True,
        questions_per_aspect=2,
        top_k_per_route=2,
        reuse_analysis_checkpoint=True,
    )
    service._persist_analysis_checkpoint(
        request=base_request,
        extraction=extraction,
        question_intents=[],
        questions=[],
        question_mode="llm",
        question_warnings=[],
        retrievals=[],
        retrieval_quality=[],
        corrective_warnings=[],
        retrieval_runtime=RetrievalRuntimeProfile(
            text_embedding_backend="api",
            text_embedding_model="text-embedding-v4",
            image_embedding_backend="clip",
            image_embedding_model="openai/clip-vit-base-patch32",
            reranker_backend="api",
            reranker_model="gte-rerank-v2",
            multimodal_reranker_backend="qwen_vl",
            multimodal_reranker_model="qwen-vl-max-latest",
            native_multimodal_enabled=True,
            summary="demo",
        ),
    )

    mismatched_request = base_request.model_copy(update={"top_k_per_route": 3})

    with pytest.raises(ValueError, match="checkpoint 与当前运行参数或运行时配置不一致"):
        service._load_analysis_checkpoint(request=mismatched_request, extraction=extraction)


def test_resolve_question_retrieval_state_reuses_checkpoint_without_recomputing(monkeypatch) -> None:
    service = ProductAnalysisService()
    extraction = ReviewExtractionResponse(
        product_id="backpack_010",
        category_slug="backpack",
        extraction_mode="llm",
        preprocessed_reviews=[],
        aspects=[],
        skipped_review_ids=[],
        warnings=[],
        artifact_path="/tmp/backpack_010.json",
    )
    checkpoint = AnalysisCheckpointPayload(
        product_id="backpack_010",
        category_slug="backpack",
        signature=service._build_analysis_checkpoint_signature(
            request=ProductAnalysisRequest(
                product_id="backpack_010",
                category_slug="backpack",
                max_reviews=25,
                use_llm=True,
                questions_per_aspect=2,
                top_k_per_route=2,
                reuse_analysis_checkpoint=True,
            ),
            extraction=extraction,
        ),
        question_mode="llm",
        question_warnings=["qwarn"],
        corrective_warnings=["rwarn"],
        question_intents=[],
        questions=[],
        retrievals=[],
        retrieval_quality=[],
        retrieval_runtime=RetrievalRuntimeProfile(
            text_embedding_backend="api",
            text_embedding_model="text-embedding-v4",
            image_embedding_backend="clip",
            image_embedding_model="openai/clip-vit-base-patch32",
            reranker_backend="api",
            reranker_model="gte-rerank-v2",
            multimodal_reranker_backend="qwen_vl",
            multimodal_reranker_model="qwen-vl-max-latest",
            native_multimodal_enabled=True,
            summary="demo",
        ),
    )
    request = ProductAnalysisRequest(
        product_id="backpack_010",
        category_slug="backpack",
        max_reviews=25,
        use_llm=True,
        questions_per_aspect=2,
        top_k_per_route=2,
        reuse_analysis_checkpoint=True,
    )

    monkeypatch.setattr(service, "_load_analysis_checkpoint", lambda request, extraction: checkpoint)

    def _fail(*args, **kwargs):
        raise AssertionError("expensive recomputation should be skipped when checkpoint is reused")

    monkeypatch.setattr(service.question_service, "generate_questions", _fail)
    monkeypatch.setattr(service.retrieval_service, "retrieve_for_package", _fail)

    resolved = service._resolve_question_retrieval_state(
        request=request,
        package=None,
        extraction=extraction,
    )

    assert resolved[2] == ["qwarn"]
    assert resolved[6] == ["rwarn"]
    assert resolved[7].summary == "demo"


def test_product_analysis_service_applies_claim_revisions_to_report_items() -> None:
    service = ProductAnalysisService()
    report = ProductAnalysisReport(
        product_id="p1",
        answer="placeholder",
        strengths=[
            InsightItem(
                label="comfort",
                summary="Comfort is positively mentioned by a user review.",
                confidence=0.8,
                supporting_evidence=SupportingEvidence(review_ids=["review_1"]),
            )
        ],
        weaknesses=[],
        controversies=[],
        suggestions=[
            ImprovementSuggestion(
                suggestion="Add quantified ergonomic validation claims.",
                suggestion_type="perception",
                reason=["No product-page ergonomic evidence was retrieved."],
                confidence=0.8,
                supporting_evidence=SupportingEvidence(review_ids=["review_1"]),
            )
        ],
        supporting_product_evidence=SupportingEvidence(),
        confidence=0.8,
    )

    revised = service._attach_claim_attribution(
        report,
        aspects=[
            ReviewAspect(
                aspect_id="a1",
                review_id="review_1",
                product_id="p1",
                aspect="comfort",
                sentiment="positive",
                opinion="comfortable",
                evidence_span="comfortable to wear",
                usage_scene="",
                confidence=0.9,
                extraction_mode="llm",
            )
        ],
        retrievals=[],
    )

    assert revised.strengths[0].summary.startswith("Current evidence only partially supports this claim:")
    assert revised.suggestions[0].suggestion.startswith("Current evidence only partially supports this claim:")


def test_product_analysis_service_accepts_strong_visual_support_below_previous_threshold() -> None:
    service = ProductAnalysisService()

    support = service._support_for_aspect(
        "lens tinting",
        [
            RetrievalRecord(
                retrieval_id="r1",
                product_id="p1",
                query="Do product images clearly show the lens tint when viewed straight-on and under neutral lighting, without glare or reflection obscuring the tint?",
                source_review_id="review_1",
                source_aspect="lens tinting",
                source_question_id="q1",
                source_question="Do product images clearly show the lens tint when viewed straight-on and under neutral lighting, without glare or reflection obscuring the tint?",
                source_evidence_span="Visual confirmation of tint appearance is necessary.",
                expected_evidence_routes=["image"],
                retrieved=[
                    RetrievedEvidence(
                        product_id="p1",
                        route="image",
                        image_id="image_1",
                        region_id="image_1_region_front",
                        region_label="front_lens",
                        image_path="images/img1.png",
                        content_preview="Front-facing tinted lens view under neutral lighting.",
                        embedding_score=0.3,
                        rerank_score=0.85,
                    )
                ],
            )
        ],
    )

    assert support.product_image_ids == ["image_1"]


def test_product_analysis_service_hydrates_report_support_before_claim_attribution() -> None:
    service = ProductAnalysisService()
    report = ProductAnalysisReport(
        product_id="p1",
        answer="placeholder",
        strengths=[
            InsightItem(
                label="lens tinting perception",
                summary="Positive feedback on lens tinting perception comes from user reviews, but no direct product-page text or reliable image evidence was retrieved.",
                confidence=0.8,
                supporting_evidence=SupportingEvidence(review_ids=["review_1"]),
            )
        ],
        weaknesses=[],
        controversies=[],
        evidence_gaps=[],
        suggestions=[],
        supporting_product_evidence=SupportingEvidence(),
        confidence=0.8,
    )

    updated = service._attach_claim_attribution(
        report,
        aspects=[
            ReviewAspect(
                aspect_id="a1",
                review_id="review_1",
                product_id="p1",
                aspect="lens tinting",
                sentiment="positive",
                opinion="excellent tinting",
                evidence_span="excellent tinting",
                usage_scene="",
                confidence=0.9,
                extraction_mode="llm",
            )
        ],
        retrievals=[
            RetrievalRecord(
                retrieval_id="r1",
                product_id="p1",
                query="Do product images clearly show the lens tint when viewed straight-on and under neutral lighting, without glare or reflection obscuring the tint?",
                source_review_id="review_1",
                source_aspect="lens tinting",
                source_question_id="q1",
                source_question="Do product images clearly show the lens tint when viewed straight-on and under neutral lighting, without glare or reflection obscuring the tint?",
                source_evidence_span="Visual confirmation of tint appearance is necessary.",
                expected_evidence_routes=["image"],
                retrieved=[
                    RetrievedEvidence(
                        product_id="p1",
                        route="image",
                        image_id="image_1",
                        region_id="image_1_region_front",
                        region_label="front_lens",
                        image_path="images/img1.png",
                        content_preview="Front-facing tinted lens view under neutral lighting.",
                        embedding_score=0.3,
                        rerank_score=0.85,
                    )
                ],
            )
        ],
    )

    assert updated.strengths[0].supporting_evidence.product_image_ids == ["image_1"]
    assert any(node.evidence_node_id == "image_1_region_front_visual" for node in updated.evidence_nodes)
    lens_tinting_attribution = next(
        attribution
        for attribution in updated.claim_attributions
        if attribution.claim_id == "strength:lens_tinting_issue:0"
    )
    assert lens_tinting_attribution.support_ids == ["review_1_chunk_00", "image_1_region_front_visual"]
    assert lens_tinting_attribution.route_sources == ["image"]
    assert lens_tinting_attribution.support_type == "mixed"


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


def test_product_analysis_service_keeps_all_aggregates_in_impressions_and_supporting_aspects() -> None:
    service = ProductAnalysisService()
    aggregates = [
        AspectAggregate(
            aspect=f"aspect_{index}",
            frequency=1,
            positive_ratio=1.0,
            negative_ratio=0.0,
            neutral_ratio=0.0,
            mixed_ratio=0.0,
            scenes={},
            representative_review_ids=[f"review_{index}"],
        )
        for index in range(6)
    ]

    impressions = service._build_product_impressions(aggregates)

    assert len(impressions) == 6
    assert service._build_supporting_aspects(aggregates)[-1] == "aspect_5"
    assert service._build_supporting_reviews(aggregates)[-1] == "review_5"


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
    assert all(item.evidence_level in {"review_only", "partial_product_support", "product_supported"} for item in result.report.strengths + result.report.weaknesses + result.report.controversies)
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
    assert result.report.supporting_review_evidence.review_ids
    assert not result.report.supporting_product_evidence.review_ids


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


def test_product_analysis_service_hydrates_report_suggestions_from_hydrated_insights() -> None:
    service = ProductAnalysisService()
    aggregates = [
        AspectAggregate(
            aspect="price",
            frequency=1,
            positive_ratio=1.0,
            negative_ratio=0.0,
            neutral_ratio=0.0,
            mixed_ratio=0.0,
            scenes={},
            representative_review_ids=["sunglasses_010_review_0064"],
        )
    ]
    retrievals = [
        RetrievalRecord(
            retrieval_id="r1",
            product_id="sunglasses_010",
            query="What is the listed price of the product on the product page?",
            source_review_id="sunglasses_010_review_0064",
            source_aspect="price",
            source_question_id="q1",
            source_question="What is the listed price of the product on the product page?",
            source_evidence_span="Price feedback",
            expected_evidence_routes=["text"],
            retrieved=[],
        )
    ]

    report = service._hydrate_report_from_llm(
        "sunglasses_010",
        "sunglasses",
        aggregates,
        retrievals,
        {
            "strengths": [
                {
                    "label": "price",
                    "summary": "Price is praised in sunglasses_010_review_0064.",
                    "confidence": 0.8,
                }
            ],
            "weaknesses": [],
            "controversies": [],
            "suggestions": [
                {
                    "suggestion": "Surface the exact listed price and any active promotions in primary product metadata.",
                    "suggestion_type": "perception",
                    "reason": ["No numeric price or discount indicators were retrieved despite a positive price sentiment."],
                    "confidence": 0.8,
                }
            ],
            "applicable_scenes": [],
            "confidence": 0.8,
        },
    )

    assert report.suggestions[0].supporting_evidence.review_ids == ["sunglasses_010_review_0064"]


def test_product_analysis_service_prefers_reason_alignment_for_suggestion_hydration() -> None:
    service = ProductAnalysisService()
    evidence_candidates = [
        InsightItem(
            label="comfort",
            summary="comfort concern from sunglasses_010_review_0064",
            confidence=0.8,
            supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0064"]),
        )
    ]

    hydrated = service._hydrate_suggestions(
        [
            {
                "suggestion": "Add durability-validation notes and warranty scope for the rubber ear insert.",
                "suggestion_type": "perception",
                "reason": ["Comfort is positive but the product page does not explain fit or ergonomic cues."],
                "confidence": 0.8,
            }
        ],
        [],
        evidence_candidates=evidence_candidates,
    )

    assert hydrated[0].supporting_evidence.review_ids == ["sunglasses_010_review_0064"]
    assert "comfort" in hydrated[0].suggestion.lower()


def test_product_analysis_service_rebind_suggestions_downgrades_unsupported_claims() -> None:
    service = ProductAnalysisService()
    suggestions = [
        ImprovementSuggestion(
            suggestion="Validate lens quality against ANSI Z80.3 prism-deviation thresholds before publishing claims.",
            suggestion_type="perception",
            reason=["No product-page claims or test data regarding optical clarity were retrieved."],
            confidence=0.85,
            supporting_evidence=SupportingEvidence(review_ids=["review_1"]),
        )
    ]
    candidate_items = [
        EvidenceGapItem(
            label="Missing optical distortion validation",
            summary="No product-page evidence was retrieved for optical neutrality, distortion control, or magnification-related validation.",
            confidence=0.9,
            supporting_evidence=SupportingEvidence(review_ids=["review_1"]),
        )
    ]

    rebound = service._rebind_suggestions(suggestions, candidate_items)

    assert "ansi" not in rebound[0].suggestion.lower()
    assert "optical validation" in rebound[0].suggestion.lower()
    assert rebound[0].supporting_evidence.review_ids == ["review_1"]


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
    assert price_metric.answer_status == "none"
    assert price_metric.conflict_risk == 0.0
    assert price_metric.answer_value is None


def test_product_analysis_service_extracts_answer_value_for_supported_tint_question() -> None:
    service = ProductAnalysisService()

    retrievals = [
        RetrievalRecord(
            retrieval_id="r1",
            product_id="demo_product",
            query="What specific tint color or hue is used in the lenses?",
            source_review_id="review_1",
            source_aspect="lens tinting",
            source_question_id="q1",
            source_question="What specific tint color or hue is used in the lenses?",
            source_evidence_span="Need actual tint clue.",
            expected_evidence_routes=["text", "image"],
            retrieved=[
                RetrievedEvidence(
                    product_id="demo_product",
                    route="text",
                    text_block_id="model_description",
                    source_section="model_description",
                    content_preview="100% UV protection and Category 4 lenses fully block intense sunlight and glare.",
                    embedding_score=0.58,
                    rerank_score=0.18,
                ),
                RetrievedEvidence(
                    product_id="demo_product",
                    route="image",
                    image_id="img1",
                    image_path="images/img1.png",
                    content_preview="Lens appears visibly tinted in the front-facing image.",
                    embedding_score=0.29,
                    rerank_score=0.97,
                ),
            ],
        )
    ]

    tint_metric = service._assess_retrieval_quality(retrievals)[0]

    assert tint_metric.answer_coverage == 0.5
    assert tint_metric.answer_status == "partial"
    assert tint_metric.answer_value is not None
    assert tint_metric.answer_source == "image"


def test_product_analysis_service_marks_retrieval_quality_as_low_precision_for_unanswered_hits() -> None:
    service = ProductAnalysisService()

    retrievals = [
        RetrievalRecord(
            retrieval_id="r1",
            product_id="demo_product",
            query="What is the listed selling price?",
            source_review_id="review_1",
            source_aspect="price",
            source_question_id="q1",
            source_question="What is the listed selling price?",
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

    metric = service._assess_retrieval_quality(retrievals)[0]

    assert metric.retrieval_quality_label == "bad"
    assert metric.failure_reason == "low_precision"
    assert metric.corrective_action == "filter_noise"


def test_product_analysis_service_marks_missing_expected_route_as_modality_miss() -> None:
    service = ProductAnalysisService()

    retrievals = [
        RetrievalRecord(
            retrieval_id="r1",
            product_id="demo_product",
            query="Does the page include a front-facing image showing lens tint?",
            source_review_id="review_1",
            source_aspect="lens tinting",
            source_question_id="q1",
            source_question="Does the page include a front-facing image showing lens tint?",
            source_evidence_span="Need image evidence.",
            expected_evidence_routes=["text", "image"],
            retrieved=[
                RetrievedEvidence(
                    product_id="demo_product",
                    route="text",
                    text_block_id="model_description",
                    source_section="model_description",
                    content_preview="Category 4 lenses fully block intense sunlight and glare.",
                    embedding_score=0.55,
                    rerank_score=0.24,
                )
            ],
        )
    ]

    metric = service._assess_retrieval_quality(retrievals)[0]

    assert metric.retrieval_quality_label == "mixed"
    assert metric.failure_reason == "modality_miss"
    assert metric.corrective_action == "add_multimodal_route"


def test_product_analysis_service_retries_corrective_retrieval_when_candidate_is_better(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ProductAnalysisService()
    question = RetrievalQuestion(
        question_id="q1",
        source_review_id="review_1",
        source_aspect="price",
        source_aspect_id="a1",
        question="What is the listed selling price?",
        rationale="Need actual price value.",
        expected_evidence_routes=["text"],
        confidence=0.7,
    )
    baseline_retrieval = RetrievalRecord(
        retrieval_id="r1",
        product_id="demo_product",
        query=question.question,
        source_review_id="review_1",
        source_aspect="price",
        source_question_id="q1",
        source_question=question.question,
        source_evidence_span=question.rationale,
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
            )
        ],
    )
    baseline_metric = service._assess_retrieval_quality([baseline_retrieval])[0]

    def fake_retry(*, package, question, top_k_per_route, use_llm):
        assert question.question != "What is the listed selling price?"
        return RetrievalRecord(
            retrieval_id="r2",
            product_id="demo_product",
            query=question.question,
            source_review_id="review_1",
            source_aspect="price",
            source_question_id="q1",
            source_question=question.question,
            source_evidence_span=question.rationale,
            expected_evidence_routes=question.expected_evidence_routes,
            retrieved=[
                RetrievedEvidence(
                    product_id="demo_product",
                    route="text",
                    text_block_id="sale_price",
                    source_section="pricing",
                    content_preview="Current selling price: $49.99.",
                    embedding_score=0.62,
                    rerank_score=0.94,
                )
            ],
        )

    monkeypatch.setattr(service.retrieval_service, "_retrieve_for_question", fake_retry)

    updated_questions, updated_retrievals, updated_quality, warnings = service._apply_corrective_retrievals(
        package=object(),
        questions=[question],
        retrievals=[baseline_retrieval],
        retrieval_quality=[baseline_metric],
        top_k_per_route=2,
        use_llm=False,
    )

    assert updated_questions[0].question != question.question
    assert updated_retrievals[0].retrieval_id == "r2"
    assert updated_quality[0].retrieval_quality_label == "good"
    assert warnings


def test_product_analysis_service_marks_trace_with_valid_evidence_counts() -> None:
    service = ProductAnalysisService()

    summary = service._summarize_evidence_check(
        SupportingEvidence(
            review_ids=["r1"],
            product_text_block_ids=["t1", "t2"],
            product_image_ids=["img1"],
        ),
        ["Question A"],
    )

    assert "valid_text_blocks=2" in summary
    assert "valid_images=1" in summary


def test_report_refinement_service_calibrates_unsupported_summaries_and_filters_relation_controversy() -> None:
    service = ProductAnalysisService()
    report = ProductAnalysisReport(
        product_id="p1",
        answer="placeholder",
        strengths=[
            InsightItem(
                label="comfort",
                summary="Comfort is partially supported by lifestyle imagery.",
                confidence=0.7,
                supporting_evidence=SupportingEvidence(review_ids=["r1"]),
            )
        ],
        weaknesses=[
            InsightItem(
                label="rubber insert durability",
                summary="The issue is corroborated by multiple retrieval queries.",
                confidence=0.7,
                supporting_evidence=SupportingEvidence(review_ids=["r2"]),
            )
        ],
        controversies=[
            InsightItem(
                label="rubber insert durability vs. overall experience",
                summary="This looks like a root-cause link to overall experience rather than a disagreement.",
                confidence=0.7,
                supporting_evidence=SupportingEvidence(review_ids=["r2"]),
            )
        ],
        supporting_product_evidence=SupportingEvidence(),
        confidence=0.7,
        suggestions=[
            ImprovementSuggestion(
                suggestion="Validate lens quality against ANSI Z80.3 prism-deviation thresholds before publishing claims.",
                suggestion_type="perception",
                reason=["Current evidence does not justify that threshold claim."],
                confidence=0.7,
                supporting_evidence=SupportingEvidence(review_ids=["r3"]),
            )
        ],
    )

    refined = service.report_refinement_service.refine(report)

    assert "lifestyle imagery" not in refined.strengths[0].summary.lower()
    assert "corroborated by multiple retrieval queries" not in refined.weaknesses[0].summary.lower()
    assert not refined.controversies
    assert "ansi" not in refined.suggestions[0].suggestion.lower()


def test_report_refinement_service_rewrites_price_and_duration_suggestions() -> None:
    service = ProductAnalysisService()
    report = ProductAnalysisReport(
        product_id="p1",
        answer="placeholder",
        strengths=[],
        weaknesses=[],
        controversies=[],
        supporting_product_evidence=SupportingEvidence(),
        confidence=0.7,
        suggestions=[
            ImprovementSuggestion(
                suggestion="Replace unsupported external-standard references with a simpler explanation.",
                suggestion_type="perception",
                reason=["No pricing context such as MSRP or discount was retrieved for the excellent price claim."],
                confidence=0.7,
                supporting_evidence=SupportingEvidence(review_ids=["r1"]),
            ),
            ImprovementSuggestion(
                suggestion="Add a 2-year warranty claim for the rubber insert.",
                suggestion_type="perception",
                reason=["No warranty terms or durability scope were retrieved for the rubber ear insert."],
                confidence=0.7,
                supporting_evidence=SupportingEvidence(review_ids=["r2"]),
            ),
        ],
    )

    refined = service.report_refinement_service.refine(report)

    assert "selling price" in refined.suggestions[0].suggestion.lower()
    assert "unsupported lifetime thresholds" in refined.suggestions[1].suggestion.lower()


def test_report_refinement_service_sanitizes_optical_external_validation_reason() -> None:
    service = ProductAnalysisService()
    report = ProductAnalysisReport(
        product_id="p1",
        answer="placeholder",
        strengths=[],
        weaknesses=[],
        controversies=[],
        supporting_product_evidence=SupportingEvidence(),
        confidence=0.7,
        suggestions=[
            ImprovementSuggestion(
                suggestion="Include optical performance claim validated for motion and link to third-party test summary if available.",
                suggestion_type="perception",
                reason=["No product-page claims or test data regarding optical clarity, ANSI Z80.3 compliance, or distortion-free field of view were retrieved."],
                confidence=0.7,
                supporting_evidence=SupportingEvidence(review_ids=["r1"]),
            )
        ],
    )

    refined = service.report_refinement_service.refine(report)

    assert "third-party" not in refined.suggestions[0].suggestion.lower()
    assert "ansi" not in " ".join(refined.suggestions[0].reason).lower()


def test_report_refinement_service_sanitizes_tint_over_specificity() -> None:
    service = ProductAnalysisService()
    report = ProductAnalysisReport(
        product_id="p1",
        answer="placeholder",
        strengths=[],
        weaknesses=[],
        controversies=[],
        supporting_product_evidence=SupportingEvidence(),
        confidence=0.7,
        suggestions=[
            ImprovementSuggestion(
                suggestion="State exact lens tint (e.g., 'gray-green') and uniformity ('full-surface uniform tint') in bullet-point specs.",
                suggestion_type="perception",
                reason=["Lens tint color and uniformity are not stated in text, and customers cannot assess color fidelity or contrast suitability for their activity."],
                confidence=0.8,
                supporting_evidence=SupportingEvidence(review_ids=["r1"]),
            )
        ],
    )

    refined = service.report_refinement_service.refine(report)

    assert "gray-green" not in refined.suggestions[0].suggestion.lower()
    assert "uniform tint" not in refined.suggestions[0].suggestion.lower()
    assert "exact lens tint" in refined.suggestions[0].suggestion.lower()
    assert "color fidelity" not in " ".join(refined.suggestions[0].reason).lower()


def test_product_analysis_service_normalizes_issues_gaps_and_suggestion_bindings() -> None:
    service = ProductAnalysisService()
    aspects = [
        ReviewAspect(
            aspect_id="a1",
            review_id="sunglasses_010_review_0021",
            product_id="sunglasses_010",
            aspect="rubber insert durability",
            sentiment="negative",
            opinion="poor durability",
            evidence_span="the rubber insert deteriorates in less than two years and falls apart",
            usage_scene="long-term wear",
            confidence=0.95,
            extraction_mode="llm",
        ),
        ReviewAspect(
            aspect_id="a2",
            review_id="sunglasses_010_review_0064",
            product_id="sunglasses_010",
            aspect="price",
            sentiment="positive",
            opinion="excellent",
            evidence_span="Excellent price",
            usage_scene="",
            confidence=0.95,
            extraction_mode="llm",
        ),
        ReviewAspect(
            aspect_id="a3",
            review_id="sunglasses_010_review_0064",
            product_id="sunglasses_010",
            aspect="comfort",
            sentiment="positive",
            opinion="comfortable",
            evidence_span="comfortable to wear",
            usage_scene="",
            confidence=0.9,
            extraction_mode="llm",
        ),
        ReviewAspect(
            aspect_id="a4",
            review_id="sunglasses_010_review_0064",
            product_id="sunglasses_010",
            aspect="optical accuracy",
            sentiment="negative",
            opinion="slight magnification causing distorted depth perception",
            evidence_span="they slightly magnify vision, so the ground beneath appears closer than it actually is",
            usage_scene="walking/outdoor navigation",
            confidence=0.98,
            extraction_mode="llm",
        ),
        ReviewAspect(
            aspect_id="a5",
            review_id="sunglasses_010_review_0064",
            product_id="sunglasses_010",
            aspect="lens tinting",
            sentiment="positive",
            opinion="excellent",
            evidence_span="excellent tinting",
            usage_scene="",
            confidence=0.95,
            extraction_mode="llm",
        ),
    ]
    report = ProductAnalysisReport(
        product_id="sunglasses_010",
        answer="placeholder",
        strengths=[
            InsightItem(
                label="Price perception",
                summary="Positive feedback on Price perception comes from user reviews.",
                confidence=0.95,
                supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0064"]),
            ),
            InsightItem(
                label="Comfort perception",
                summary="Positive feedback on Comfort perception comes from user reviews.",
                confidence=0.89,
                supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0064"]),
            ),
            InsightItem(
                label="Lens tinting perception",
                summary="Tinting looks good and product images show visible tint.",
                confidence=0.9,
                supporting_evidence=SupportingEvidence(
                    review_ids=["sunglasses_010_review_0064"],
                    product_image_ids=["image_1"],
                ),
            ),
        ],
        weaknesses=[
            InsightItem(
                label="Optical accuracy communication",
                summary="Concerns about Optical accuracy communication are clear in user reviews.",
                confidence=0.96,
                supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0064"]),
            ),
            InsightItem(
                label="ergonomic and fit specification gaps",
                summary="Concerns about ergonomic and fit specification gaps are clear in user reviews.",
                confidence=0.88,
                supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0064"]),
            ),
        ],
        controversies=[],
        supporting_product_evidence=SupportingEvidence(),
        confidence=0.94,
        suggestions=[
            ImprovementSuggestion(
                suggestion="Add product-page optical verification notes and publish the measured distortion or prism-control results before making strong visual-performance claims.",
                suggestion_type="perception",
                reason=["No product-page claims or test data about optical clarity, distortion control, or motion-relevant visual performance were retrieved."],
                confidence=0.91,
                supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0021"]),
            ),
            ImprovementSuggestion(
                suggestion="Include quantified comfort-related specs: list frame weight (g), describe nose-pad material, and add annotated imagery highlighting pressure-distribution features.",
                suggestion_type="perception",
                reason=[
                    "The positive comfort rating lacks supporting evidence in specs or imagery.",
                    "Replay continuity: the issue around Comfort substantiation gap, Missing optical distortion validation also appeared in the previous run.",
                ],
                confidence=0.87,
                supporting_evidence=SupportingEvidence(review_ids=["sunglasses_010_review_0021"]),
            ),
            ImprovementSuggestion(
                suggestion="State the specific lens tint (e.g., 'gray polarized') in both product title/description and on lens close-up images.",
                suggestion_type="perception",
                reason=["Three positive aspects (price, lens tinting, comfort) lack clear product-page support in current copy."],
                confidence=0.86,
                supporting_evidence=SupportingEvidence(
                    review_ids=["sunglasses_010_review_0064"],
                    product_text_block_ids=["text_1"],
                    product_image_ids=["image_1"],
                ),
            ),
        ],
    )

    normalized = service._normalize_report_structure(report, aspects)

    weakness_labels = {item.label for item in normalized.weaknesses}
    gap_labels = {item.label for item in normalized.evidence_gaps}

    assert "Rubber insert durability failure" in weakness_labels
    assert "Potential optical magnification affecting depth perception" in weakness_labels
    assert "ergonomic and fit specification gaps" not in weakness_labels
    assert "Missing rubber insert durability disclosure" in gap_labels
    assert "Missing optical distortion validation" in gap_labels
    assert "Comfort substantiation gap" in gap_labels
    assert "Price substantiation gap" in gap_labels
    assert "Missing explicit lens tint hue disclosure" in gap_labels
    assert any("optical" in suggestion.suggestion.lower() and suggestion.supporting_evidence.review_ids == ["sunglasses_010_review_0064"] for suggestion in normalized.suggestions)
    assert any("comfort" in suggestion.suggestion.lower() and suggestion.supporting_evidence.review_ids == ["sunglasses_010_review_0064"] for suggestion in normalized.suggestions)
    assert any("selling price" in suggestion.suggestion.lower() and suggestion.supporting_evidence.review_ids == ["sunglasses_010_review_0064"] for suggestion in normalized.suggestions)
    assert len(normalized.suggestions) >= 5


def test_product_analysis_service_builds_grammatically_correct_answer_with_partial_support() -> None:
    service = ProductAnalysisService()

    answer = service._build_answer(
        strengths=[
            InsightItem(
                label="perceived value",
                summary="review-supported",
                confidence=0.78,
                supporting_evidence=SupportingEvidence(review_ids=["r1"]),
            ),
            InsightItem(
                label="lens tinting",
                summary="image-supported",
                confidence=0.88,
                supporting_evidence=SupportingEvidence(review_ids=["r2"], product_image_ids=["img1"]),
            ),
            InsightItem(
                label="comfort",
                summary="review-supported",
                confidence=0.78,
                supporting_evidence=SupportingEvidence(review_ids=["r2"]),
            ),
        ],
        weaknesses=[
            InsightItem(
                label="Rubber insert durability failure",
                summary="negative",
                confidence=0.78,
                supporting_evidence=SupportingEvidence(review_ids=["r3"]),
            )
        ],
        controversies=[],
    )

    assert answer.startswith("Positive feedback appears")
    assert "Lens tinting is partially supported by product images" in answer
    assert "perceived value and comfort are mainly review-supported" in answer
    assert "The most important negative issue is Rubber insert durability failure." in answer


def test_product_analysis_service_attaches_replay_note_without_polluting_reason() -> None:
    service = ProductAnalysisService()
    suggestions = [
        ImprovementSuggestion(
            suggestion="Clarify the fit and comfort-related design cues on the product page.",
            suggestion_type="perception",
            reason=["Comfort is positively mentioned by a user review, but no product-page text was retrieved."],
            confidence=0.82,
            supporting_evidence=SupportingEvidence(review_ids=["review_1"]),
        )
    ]

    annotated = service._annotate_suggestions_with_replay(
        suggestions,
        persistent_issue_labels=["Comfort substantiation gap"],
        accepted_issue_labels=[],
        rejected_issue_labels=[],
    )

    assert annotated[0].replay_note is not None
    assert all("Replay continuity:" not in reason for reason in annotated[0].reason)


def test_product_analysis_service_uses_canonical_issue_keys_for_replay_continuity() -> None:
    service = ProductAnalysisService()
    report = ProductAnalysisReport(
        product_id="p1",
        answer="placeholder",
        strengths=[],
        weaknesses=[],
        controversies=[],
        evidence_gaps=[
            EvidenceGapItem(
                label="Missing rubber insert durability disclosure",
                summary="No product-page durability detail was retrieved.",
                confidence=0.9,
                source_aspect="rubber insert durability",
                supporting_evidence=SupportingEvidence(review_ids=["review_1"]),
            )
        ],
        supporting_product_evidence=SupportingEvidence(),
        confidence=0.8,
        suggestions=[],
    )

    replayed_report, replay_summary = service._apply_replay_context(
        report,
        {
            "replay_path": "demo_replay.json",
            "analysis_mode": "llm",
            "report": {
                "weaknesses": [],
                "controversies": [],
                "evidence_gaps": [
                    {
                        "label": "rubber insert durability disclosure gap",
                        "supporting_evidence": {"review_ids": ["review_1"], "product_text_block_ids": [], "product_image_ids": []},
                    }
                ],
            },
        },
        None,
    )

    assert replayed_report.evidence_gaps[0].label == "Missing rubber insert durability disclosure"
    assert replay_summary is not None
    assert replay_summary.persistent_issue_labels == ["Missing rubber insert durability disclosure"]
    assert replay_summary.persistent_issue_keys == ["rubber_insert_durability:evidence_gap"]


def test_product_analysis_service_trace_uses_full_replay_summary_and_all_suggestions() -> None:
    service = ProductAnalysisService()
    aspects = [
        ReviewAspect(
            aspect_id="a1",
            review_id="review_1",
            product_id="p1",
            aspect="overall_experience",
            sentiment="mixed",
            opinion="initially positive but ultimately disappointing",
            evidence_span="The sunglasses are great! However, the rubber insert fell apart.",
            usage_scene=None,
            confidence=0.9,
            extraction_mode="llm",
        ),
        ReviewAspect(
            aspect_id="a2",
            review_id="review_1",
            product_id="p1",
            aspect="rubber insert durability",
            sentiment="negative",
            opinion="poor durability",
            evidence_span="the rubber insert fell apart",
            usage_scene=None,
            confidence=0.9,
            extraction_mode="llm",
        ),
    ]
    report = ProductAnalysisReport(
        product_id="p1",
        answer="placeholder",
        strengths=[],
        weaknesses=[
            InsightItem(
                label="Rubber insert durability failure",
                summary="negative",
                confidence=0.8,
                supporting_evidence=SupportingEvidence(review_ids=["review_1"]),
            )
        ],
        controversies=[],
        suggestions=[
            ImprovementSuggestion(
                suggestion=f"Suggestion {index}",
                suggestion_type="perception",
                reason=[f"Reason {index}"],
                confidence=0.8,
                supporting_evidence=SupportingEvidence(review_ids=["review_1"]),
            )
            for index in range(5)
        ],
        supporting_product_evidence=SupportingEvidence(),
        confidence=0.8,
    ).model_copy(update={"aspect_relations": service._build_aspect_relations(aspects)})
    replay_summary = ReplayContinuationSummary(
        replay_path="demo_replay.json",
        applied=True,
        persistent_issue_labels=[f"persistent_{index}" for index in range(5)],
        resolved_issue_labels=["resolved_1"],
        new_issue_labels=["new_1"],
    )

    trace = service._build_process_trace(aspects, [], [], report, replay_summary)

    replay_trace = next(item for item in trace if item.aspect == "replay_continuity")
    assert "persistent_4" in replay_trace.summary
    action_traces = [item for item in trace if item.trace_type == "action_generation"]
    assert len(action_traces) == 5
    assert all(item.suggestion_id for item in action_traces)
    assert report.aspect_relations
    assert report.aspect_relations[0].source_aspect == "rubber insert durability"
    assert report.aspect_relations[0].target_aspect == "overall_experience"



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
    assert any(
        suggestion.replay_note and ("Reviewer feedback" in suggestion.replay_note or "人工反馈" in suggestion.replay_note)
        for suggestion in replayed.report.suggestions
    )

    preserved_payload = orjson.loads(Path(feedback_path).read_bytes())
    assert preserved_payload["slots"][0]["status"] == "accepted"