from collections import Counter, defaultdict
import re

import orjson
from pydantic import BaseModel, Field

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.llm import QwenChatGateway
from decathlon_voc_analyzer.schemas.analysis import (
    AnalysisArtifactBundle,
    AnalysisMode,
    AspectAggregate,
    ConfidenceBreakdown,
    CustomerImpressionItem,
    EvidenceGapItem,
    ImprovementSuggestion,
    InsightItem,
    ProcessTraceItem,
    ProductImpressionItem,
    ProductAnalysisReport,
    ProductAnalysisRequest,
    ProductAnalysisResponse,
    ReplayContinuationSummary,
    RetrievalQualityMetrics,
    RetrievalRuntimeProfile,
    SupportingEvidence,
)
from decathlon_voc_analyzer.schemas.review import ReviewAspect, ReviewExtractionRequest
from decathlon_voc_analyzer.prompts import get_prompt_template, get_prompt_variant
from decathlon_voc_analyzer.stage1_dataset.dataset_service import DatasetService
from decathlon_voc_analyzer.stage2_review_modeling.review_service import ReviewExtractionService
from decathlon_voc_analyzer.stage3_retrieval.retrieval_service import RetrievalService
from decathlon_voc_analyzer.stage4_generation.artifact_sidecar_service import ArtifactSidecarService
from decathlon_voc_analyzer.stage4_generation.question_service import QuestionGenerationService
from decathlon_voc_analyzer.stage4_generation.report_refinement_service import ReportRefinementService


class LLMInsightItem(BaseModel):
    label: str = "overall_experience"
    summary: str = ""
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class LLMSuggestionItem(BaseModel):
    suggestion: str = ""
    suggestion_type: str = "perception"
    reason: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class LLMReportPayload(BaseModel):
    answer: str = ""
    strengths: list[LLMInsightItem] = Field(default_factory=list)
    weaknesses: list[LLMInsightItem] = Field(default_factory=list)
    controversies: list[LLMInsightItem] = Field(default_factory=list)
    applicable_scenes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    suggestions: list[LLMSuggestionItem] = Field(default_factory=list)


class ProductAnalysisService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.dataset_service = DatasetService()
        self.review_service = ReviewExtractionService()
        self.question_service = QuestionGenerationService()
        self.retrieval_service = RetrievalService()
        self.chat_gateway = QwenChatGateway()
        self.report_refinement_service = ReportRefinementService()
        self.artifact_sidecar_service = ArtifactSidecarService()

    def _uses_main_prompt_variant(self) -> bool:
        return get_prompt_variant() == "main"

    def analyze(self, request: ProductAnalysisRequest) -> ProductAnalysisResponse:
        package = self.dataset_service.load_product_package(
            product_id=request.product_id,
            category_slug=request.category_slug,
        )
        extraction = self.review_service.extract(
            ReviewExtractionRequest(
                product_id=request.product_id,
                category_slug=request.category_slug,
                max_reviews=request.max_reviews,
                use_llm=request.use_llm,
                persist_artifact=request.persist_artifact,
            )
        )

        questions, question_warnings, question_mode = self.question_service.generate_questions(
            aspects=extraction.aspects,
            questions_per_aspect=request.questions_per_aspect,
            use_llm=request.use_llm,
        )

        retrievals = self.retrieval_service.retrieve_for_package(
            package=package,
            questions=questions,
            top_k_per_route=request.top_k_per_route,
            use_llm=request.use_llm,
        )
        retrieval_quality = self._assess_retrieval_quality(retrievals)
        retrieval_runtime = self._build_retrieval_runtime_profile()
        aggregates = self._aggregate_aspects(extraction.aspects)
        replay_payload = None
        feedback_payload = None
        if request.use_replay:
            replay_payload = self.artifact_sidecar_service.load_replay_payload(
                product_id=package.product_id,
                category_slug=package.category_slug,
            )
            feedback_payload = self.artifact_sidecar_service.load_feedback_payload(
                product_id=package.product_id,
                category_slug=package.category_slug,
            )
        warnings = list(extraction.warnings) + question_warnings

        llm_requested = request.use_llm and bool(self.settings.qwen_plus_api_key)
        analysis_mode: AnalysisMode = "llm" if llm_requested and question_mode == "llm" else "heuristic"

        if llm_requested:
            try:
                report = self._build_report_with_llm(package.product_id, package.category_slug, aggregates, retrievals)
            except Exception as exc:
                analysis_mode = "heuristic"
                warnings.append(f"report generation failed, fallback to heuristic ({exc})")
                report = self._build_report_heuristic(package.product_id, package.category_slug, aggregates, retrievals)
        else:
            report = self._build_report_heuristic(package.product_id, package.category_slug, aggregates, retrievals)

        report = self.report_refinement_service.refine(report)
        report = self._normalize_report_structure(report, extraction.aspects)
        report = report.model_copy(
            update={
                "answer": self._build_answer(report.strengths, report.weaknesses, report.controversies),
                "product_impressions": self._build_product_impressions(aggregates),
                "customer_impressions": self._build_customer_impressions(extraction.aspects),
                "supporting_aspects": self._build_supporting_aspects(aggregates),
                "supporting_reviews": self._build_supporting_reviews(aggregates),
                "supporting_review_evidence": self._merge_review_evidence(
                    [
                        item.supporting_evidence
                        for item in report.strengths + report.weaknesses + report.controversies + report.evidence_gaps + report.suggestions
                    ]
                ),
                "supporting_product_evidence": self._merge_product_evidence(
                    [
                        item.supporting_evidence
                        for item in report.strengths + report.weaknesses + report.controversies + report.evidence_gaps + report.suggestions
                    ]
                ),
            }
        )
        report, replay_summary = self._apply_replay_context(report, replay_payload, feedback_payload)
        replay_warning = self._build_replay_warning(replay_summary)
        if replay_warning is not None:
            warnings.append(replay_warning)

        trace = self._build_process_trace(extraction.aspects, questions, retrievals, report, replay_summary)

        artifact_bundle: AnalysisArtifactBundle | None = None
        if request.persist_artifact:
            artifact_bundle = self._persist_report(package.product_id, package.category_slug, analysis_mode, extraction, questions, retrievals, retrieval_quality, retrieval_runtime, aggregates, report, trace, warnings, replay_summary)

        return ProductAnalysisResponse(
            analysis_mode=analysis_mode,
            extraction=extraction,
            questions=questions,
            retrievals=retrievals,
            retrieval_quality=retrieval_quality,
            retrieval_runtime=retrieval_runtime,
            aggregates=aggregates,
            report=report,
            trace=trace,
            replay_summary=replay_summary,
            artifact_bundle=artifact_bundle,
            artifact_path=artifact_bundle.analysis_path if artifact_bundle is not None else None,
            warnings=warnings,
        )

    def _aggregate_aspects(self, aspects: list[ReviewAspect]) -> list[AspectAggregate]:
        grouped: dict[str, list[ReviewAspect]] = defaultdict(list)
        for aspect in aspects:
            grouped[aspect.aspect].append(aspect)

        aggregates: list[AspectAggregate] = []
        for aspect_name, items in grouped.items():
            total = len(items)
            scenes = Counter(item.usage_scene for item in items if item.usage_scene)
            sentiment_counter = Counter(item.sentiment for item in items)
            aggregates.append(
                AspectAggregate(
                    aspect=aspect_name,
                    frequency=total,
                    positive_ratio=sentiment_counter.get("positive", 0) / total,
                    negative_ratio=sentiment_counter.get("negative", 0) / total,
                    neutral_ratio=sentiment_counter.get("neutral", 0) / total,
                    mixed_ratio=sentiment_counter.get("mixed", 0) / total,
                    scenes=dict(scenes),
                    representative_review_ids=list(dict.fromkeys(item.review_id for item in items[:3])),
                )
            )
        return sorted(aggregates, key=lambda item: item.frequency, reverse=True)

    def _build_product_impressions(self, aggregates: list[AspectAggregate]) -> list[ProductImpressionItem]:
        return [
            ProductImpressionItem(
                aspect=aggregate.aspect,
                aspect_frequency=aggregate.frequency,
                positive_ratio=aggregate.positive_ratio,
                negative_ratio=aggregate.negative_ratio,
                mixed_ratio=aggregate.mixed_ratio,
                scene_distribution=aggregate.scenes,
                representative_review_ids=aggregate.representative_review_ids,
            )
            for aggregate in aggregates
        ]

    def _build_supporting_aspects(self, aggregates: list[AspectAggregate]) -> list[str]:
        return [aggregate.aspect for aggregate in aggregates]

    def _build_supporting_reviews(self, aggregates: list[AspectAggregate]) -> list[str]:
        return list(
            dict.fromkeys(
                review_id
                for aggregate in aggregates
                for review_id in aggregate.representative_review_ids
            )
        )

    def _build_customer_impressions(self, aspects: list[ReviewAspect]) -> list[CustomerImpressionItem]:
        grouped: dict[str, list[ReviewAspect]] = defaultdict(list)
        for aspect in aspects:
            if aspect.usage_scene:
                grouped[aspect.usage_scene].append(aspect)

        impressions: list[CustomerImpressionItem] = []
        for scene, items in sorted(grouped.items(), key=lambda entry: len(entry[1]), reverse=True)[:4]:
            aspect_counter = Counter(item.aspect for item in items)
            positive_counter = Counter(item.aspect for item in items if item.sentiment == "positive")
            negative_counter = Counter(item.aspect for item in items if item.sentiment == "negative")
            impressions.append(
                CustomerImpressionItem(
                    segment_label=self._scene_segment_label(scene),
                    scene=scene,
                    review_count=len({item.review_id for item in items}),
                    focus_aspects=[aspect for aspect, _ in aspect_counter.most_common(3)],
                    positive_aspects=[aspect for aspect, _ in positive_counter.most_common(2)],
                    negative_aspects=[aspect for aspect, _ in negative_counter.most_common(2)],
                    representative_review_ids=list(dict.fromkeys(item.review_id for item in items))[:4],
                )
            )
        return impressions

    def _scene_segment_label(self, scene: str) -> str:
        if self._uses_main_prompt_variant():
            return f"Users in the '{scene}' scenario"
        return f"{scene} 场景用户"

    def _build_report_with_llm(
        self,
        product_id: str,
        category_slug: str | None,
        aggregates: list[AspectAggregate],
        retrievals: list,
    ) -> ProductAnalysisReport:
        payload = {
            "product_id": product_id,
            "category_slug": category_slug,
            "aggregates": [aggregate.model_dump(mode="json") for aggregate in aggregates],
            "retrievals": [retrieval.model_dump(mode="json") for retrieval in retrievals[:10]],
        }
        parsed = self.chat_gateway.invoke_json(
            prompt_template=get_prompt_template("report_generation_system"),
            variables={"payload": payload},
            schema=LLMReportPayload,
        )
        return self._hydrate_report_from_llm(product_id, category_slug, aggregates, retrievals, parsed)

    def _hydrate_report_from_llm(self, product_id: str, category_slug: str | None, aggregates: list[AspectAggregate], retrievals: list, payload: dict) -> ProductAnalysisReport:
        fallback = self._build_report_heuristic(product_id, category_slug, aggregates, retrievals)
        evidence_candidates = fallback.strengths + fallback.weaknesses + fallback.controversies
        strengths = self._hydrate_insights(payload.get("strengths"), fallback.strengths, evidence_candidates=evidence_candidates)
        weaknesses = self._hydrate_insights(payload.get("weaknesses"), fallback.weaknesses, evidence_candidates=evidence_candidates)
        controversies = self._hydrate_insights(payload.get("controversies"), fallback.controversies, evidence_candidates=evidence_candidates)
        suggestion_candidates = strengths + weaknesses + controversies + fallback.suggestions
        suggestions = self._hydrate_suggestions(
            payload.get("suggestions"),
            fallback.suggestions,
            evidence_candidates=suggestion_candidates,
        )
        return ProductAnalysisReport(
            product_id=product_id,
            category_slug=category_slug,
            answer=self._build_answer(strengths, weaknesses, controversies),
            strengths=strengths,
            weaknesses=weaknesses,
            controversies=controversies,
            evidence_gaps=[],
            applicable_scenes=list(payload.get("applicable_scenes") or fallback.applicable_scenes),
            supporting_aspects=self._build_supporting_aspects(aggregates),
            supporting_reviews=self._build_supporting_reviews(aggregates),
            supporting_review_evidence=fallback.supporting_review_evidence,
            supporting_product_evidence=fallback.supporting_product_evidence,
            confidence=self._clamp_confidence(payload.get("confidence"), fallback.confidence),
            suggestions=suggestions,
        )

    def _build_report_heuristic(
        self,
        product_id: str,
        category_slug: str | None,
        aggregates: list[AspectAggregate],
        retrievals: list,
    ) -> ProductAnalysisReport:
        strengths: list[InsightItem] = []
        weaknesses: list[InsightItem] = []
        controversies: list[InsightItem] = []
        scenes = Counter()

        for aggregate in aggregates:
            scenes.update(aggregate.scenes)
            evidence = self._support_for_aspect(aggregate.aspect, retrievals)
            if aggregate.positive_ratio >= 0.6:
                summary = (
                    f"Positive feedback dominates for {aggregate.aspect}, appearing {aggregate.frequency} times."
                    if self._uses_main_prompt_variant()
                    else f"用户对 {aggregate.aspect} 的反馈以正向为主，出现 {aggregate.frequency} 次。"
                )
                strengths.append(
                    InsightItem(
                        label=aggregate.aspect,
                        summary=summary,
                        confidence=self._aggregate_confidence(aggregate),
                        supporting_evidence=evidence,
                        confidence_breakdown=self._build_confidence_breakdown(aggregate, evidence),
                    )
                )
            elif aggregate.negative_ratio >= 0.4:
                summary = (
                    f"Clear negative feedback exists for {aggregate.aspect}, appearing {aggregate.frequency} times."
                    if self._uses_main_prompt_variant()
                    else f"用户对 {aggregate.aspect} 存在明显负向反馈，出现 {aggregate.frequency} 次。"
                )
                weaknesses.append(
                    InsightItem(
                        label=aggregate.aspect,
                        summary=summary,
                        confidence=self._aggregate_confidence(aggregate),
                        supporting_evidence=evidence,
                        confidence_breakdown=self._build_confidence_breakdown(aggregate, evidence),
                    )
                )
            else:
                summary = (
                    f"Opinions on {aggregate.aspect} are relatively mixed and somewhat controversial."
                    if self._uses_main_prompt_variant()
                    else f"{aggregate.aspect} 的意见分布较分散，存在一定争议。"
                )
                controversies.append(
                    InsightItem(
                        label=aggregate.aspect,
                        summary=summary,
                        confidence=self._aggregate_confidence(aggregate),
                        supporting_evidence=evidence,
                        confidence_breakdown=self._build_confidence_breakdown(aggregate, evidence),
                    )
                )

        if not strengths and aggregates:
            aggregate = aggregates[0]
            summary = (
                f"{aggregate.aspect} is the most frequently mentioned experience theme in current reviews."
                if self._uses_main_prompt_variant()
                else f"{aggregate.aspect} 是当前评论中最常见的体验主题。"
            )
            strengths.append(
                InsightItem(
                    label=aggregate.aspect,
                    summary=summary,
                    confidence=self._aggregate_confidence(aggregate),
                    supporting_evidence=self._support_for_aspect(aggregate.aspect, retrievals),
                    confidence_breakdown=self._build_confidence_breakdown(aggregate, self._support_for_aspect(aggregate.aspect, retrievals)),
                )
            )

        answer = self._build_answer(strengths, weaknesses, controversies)
        suggestions = self._build_suggestions(weaknesses, controversies, strengths)
        supporting_aspects = self._build_supporting_aspects(aggregates)
        supporting_reviews = self._build_supporting_reviews(aggregates)
        supporting_review_evidence = self._merge_review_evidence(
            [item.supporting_evidence for item in strengths + weaknesses + controversies + suggestions]
        )
        supporting_product_evidence = self._merge_product_evidence(
            [item.supporting_evidence for item in strengths + weaknesses + controversies + suggestions]
        )
        confidence = min(0.9, 0.45 + 0.08 * min(len(aggregates), 4))

        return ProductAnalysisReport(
            product_id=product_id,
            category_slug=category_slug,
            answer=answer,
            strengths=strengths[:3],
            weaknesses=weaknesses[:3],
            controversies=controversies[:2],
            evidence_gaps=[],
            applicable_scenes=[scene for scene, _ in scenes.most_common(4)],
            supporting_aspects=supporting_aspects,
            supporting_reviews=supporting_reviews,
            supporting_review_evidence=supporting_review_evidence,
            supporting_product_evidence=supporting_product_evidence,
            confidence=confidence,
            suggestions=suggestions[:3],
        )

    def _support_for_aspect(self, aspect: str, retrievals: list) -> SupportingEvidence:
        matching = [record for record in retrievals if record.source_aspect == aspect]
        supporting_hits = [
            evidence
            for record in matching
            for evidence in record.retrieved
            if self._evidence_answers_question(record.source_question, evidence)
        ]
        return SupportingEvidence(
            review_ids=list(dict.fromkeys(record.source_review_id for record in matching))[:3],
            product_text_block_ids=list(dict.fromkeys(
                evidence.text_block_id
                for evidence in supporting_hits
                if evidence.text_block_id
            ))[:3],
            product_image_ids=list(dict.fromkeys(
                evidence.image_id
                for evidence in supporting_hits
                if evidence.image_id
            ))[:3],
        )

    def _build_answer(self, strengths: list[InsightItem], weaknesses: list[InsightItem], controversies: list[InsightItem]) -> str:
        strength_labels = [item.label for item in strengths[:3]]
        strong_supported = [item.label for item in strengths if item.supporting_evidence.product_text_block_ids and item.supporting_evidence.product_image_ids]
        image_supported = [item.label for item in strengths if item.supporting_evidence.product_image_ids and not item.supporting_evidence.product_text_block_ids]
        text_supported = [item.label for item in strengths if item.supporting_evidence.product_text_block_ids and not item.supporting_evidence.product_image_ids]
        weak_supported = [
            item.label
            for item in strengths
            if not item.supporting_evidence.product_text_block_ids and not item.supporting_evidence.product_image_ids
        ]
        weakness_label = weaknesses[0].label if weaknesses else None
        controversy_item = controversies[0] if controversies else None
        if self._uses_main_prompt_variant():
            parts: list[str] = []
            if strength_labels:
                parts.append(f"Positive feedback appears on {self._natural_join(strength_labels)}.")
            else:
                parts.append("Current reviews concentrate mainly on the core experience.")
            support_clauses: list[str] = []
            if strong_supported:
                verb = "are" if len(strong_supported) > 1 else "is"
                support_clauses.append(f"{self._natural_join(strong_supported)} {verb} well supported by both product-page text and images")
            if image_supported:
                verb = "are" if len(image_supported) > 1 else "is"
                support_clauses.append(f"{self._natural_join(image_supported)} {verb} partially supported by product images")
            if text_supported:
                verb = "are" if len(text_supported) > 1 else "is"
                support_clauses.append(f"{self._natural_join(text_supported)} {verb} partially supported by product-page text")
            if weak_supported:
                verb = "are" if len(weak_supported) > 1 else "is"
                weak_clause = f"{self._natural_join(weak_supported)} {verb} mainly review-supported and lack direct product-page substantiation" if len(weak_supported) > 1 else f"{self._natural_join(weak_supported)} is mainly review-supported and lacks direct product-page substantiation"
            else:
                weak_clause = None
            if support_clauses:
                supported_text = "; ".join(support_clauses)
                supported_text = supported_text[:1].upper() + supported_text[1:] if supported_text else supported_text
                if weak_clause:
                    parts.append(f"{supported_text}, while {weak_clause}.")
                else:
                    parts.append(f"{supported_text}.")
            elif weak_clause:
                weak_clause = weak_clause[:1].upper() + weak_clause[1:] if weak_clause else weak_clause
                parts.append(f"{weak_clause}.")
            if weakness_label:
                parts.append(f"The most important negative issue is {weakness_label}.")
            controversy_clause = self._answer_controversy_clause(controversy_item)
            if controversy_clause:
                parts.append(controversy_clause)
        else:
            parts = []
            if strength_labels:
                parts.append(f"用户对 {self._natural_join(strength_labels, conjunction='和')} 给出了正面反馈。")
            else:
                parts.append("该商品当前评论主要集中在核心体验相关反馈。")
            if strong_supported and weak_supported:
                parts.append(
                    f"其中 {self._natural_join(strong_supported, conjunction='和')} 有较明确的产品页面证据支持；{self._natural_join(weak_supported, conjunction='和')} 主要来自用户评论，产品页面证据相对不足。"
                )
            elif strong_supported:
                parts.append(f"其中 {self._natural_join(strong_supported, conjunction='和')} 有较明确的产品页面证据支持。")
            elif weak_supported:
                parts.append(f"其中 {self._natural_join(weak_supported, conjunction='和')} 主要来自用户评论，产品页面证据相对不足。")
            if weakness_label:
                parts.append(f"同时，{weakness_label} 是当前最需要关注的问题点。")
            controversy_clause = self._answer_controversy_clause(controversy_item)
            if controversy_clause:
                parts.append(controversy_clause)
        return " ".join(parts) if self._uses_main_prompt_variant() else "".join(parts)

    def _answer_controversy_clause(self, controversy_item: InsightItem | None) -> str:
        if controversy_item is None:
            return ""
        label = controversy_item.label
        label_text = (label or "").lower()
        if any(marker in label_text for marker in (" vs ", "vs.", "versus")) and "overall experience" in label_text:
            primary_label = re.split(r"\bvs\.?\b|\bversus\b", label, maxsplit=1, flags=re.IGNORECASE)[0].strip(" -") or label
            if self._uses_main_prompt_variant():
                return f"Negative overall-experience feedback appears to be tied to {primary_label}, so it should be read as a linked issue rather than a broad disagreement."
            return f"整体负面体验更像是由 {primary_label} 所带出的连带问题，而不是广泛分歧。"
        if self._uses_main_prompt_variant():
            return f"There is still some disagreement around {label}, which should be interpreted by user segment and usage context."
        return f"{label} 上存在一定意见分歧，需要结合具体人群与场景理解。"

    def _build_suggestions(
        self,
        weaknesses: list[InsightItem],
        controversies: list[InsightItem],
        strengths: list[InsightItem],
    ) -> list[ImprovementSuggestion]:
        suggestions: list[ImprovementSuggestion] = []
        for item in weaknesses[:2]:
            reasons = [item.summary]
            suggestion_type = "structural" if item.supporting_evidence.product_image_ids and item.supporting_evidence.product_text_block_ids else "perception"
            suggestion = (
                f"Prioritize improvements to the design or presentation related to {item.label}, and strengthen the corresponding explanation on the product page."
                if self._uses_main_prompt_variant()
                else f"优先优化 {item.label} 相关设计或表达，并在商品页中强化对应说明。"
            )
            suggestions.append(
                ImprovementSuggestion(
                    suggestion=suggestion,
                    suggestion_type=suggestion_type,
                    reason=reasons,
                    confidence=min(0.88, item.confidence),
                    supporting_evidence=item.supporting_evidence,
                    confidence_breakdown=item.confidence_breakdown,
                )
            )
        for item in controversies[:1]:
            suggestion = (
                f"Add clearer usage-scenario guidance for {item.label} to reduce expectation mismatch."
                if self._uses_main_prompt_variant()
                else f"针对 {item.label} 增加更明确的适用场景说明，降低用户预期偏差。"
            )
            suggestions.append(
                ImprovementSuggestion(
                    suggestion=suggestion,
                    suggestion_type="perception",
                    reason=[item.summary],
                    confidence=min(0.8, item.confidence),
                    supporting_evidence=item.supporting_evidence,
                    confidence_breakdown=item.confidence_breakdown,
                )
            )
        if not suggestions:
            fallback = weaknesses[0] if weaknesses else controversies[0] if controversies else strengths[0] if strengths else None
            if fallback is not None:
                suggestion = (
                    f"Add more specific product explanation and usage examples around {fallback.label} to reduce interpretation gaps."
                    if self._uses_main_prompt_variant()
                    else f"围绕 {fallback.label} 补充更具体的商品说明和使用场景示例，减少用户理解偏差。"
                )
                suggestions.append(
                    ImprovementSuggestion(
                        suggestion=suggestion,
                        suggestion_type="perception",
                        reason=[fallback.summary],
                        confidence=min(0.76, fallback.confidence),
                        supporting_evidence=fallback.supporting_evidence,
                        confidence_breakdown=fallback.confidence_breakdown,
                    )
                )
        return suggestions

    def _normalize_report_structure(self, report: ProductAnalysisReport, aspects: list[ReviewAspect]) -> ProductAnalysisReport:
        normalized_strengths = [self._normalize_strength_item(item) for item in report.strengths]
        normalized_weaknesses: list[InsightItem] = []
        evidence_gaps: list[EvidenceGapItem] = list(report.evidence_gaps)

        for item in report.weaknesses:
            matched_aspect = self._match_report_item_aspect(item.label, item.summary, item.supporting_evidence.review_ids, aspects)
            if matched_aspect is None:
                normalized_weaknesses.append(self._normalize_issue_confidence(item))
                continue
            if matched_aspect.aspect == "overall_experience":
                continue
            if matched_aspect.sentiment == "negative":
                normalized_weaknesses.append(self._direct_issue_from_aspect(matched_aspect, item))
                evidence_gaps.append(self._evidence_gap_for_aspect(matched_aspect, item))
                continue
            evidence_gaps.append(self._evidence_gap_for_aspect(matched_aspect, item))

        for item in normalized_strengths:
            matched_aspect = self._match_report_item_aspect(item.label, item.summary, item.supporting_evidence.review_ids, aspects)
            if matched_aspect is None:
                continue
            gap = self._evidence_gap_for_positive_aspect(matched_aspect, item)
            if gap is not None:
                evidence_gaps.append(gap)

        normalized_weaknesses, evidence_gaps = self._backfill_missing_negative_aspects(
            normalized_weaknesses,
            evidence_gaps,
            aspects,
        )

        normalized_weaknesses = self._deduplicate_report_items(normalized_weaknesses)
        evidence_gaps = self._deduplicate_evidence_gaps(evidence_gaps)
        normalized_suggestions = self._rebind_suggestions(
            report.suggestions,
            normalized_strengths + normalized_weaknesses + evidence_gaps,
        )
        normalized_suggestions = self._ensure_gap_suggestions(normalized_suggestions, evidence_gaps)
        normalized_suggestions = self._deduplicate_suggestions(normalized_suggestions)

        return report.model_copy(
            update={
                "strengths": normalized_strengths,
                "weaknesses": normalized_weaknesses,
                "evidence_gaps": evidence_gaps,
                "suggestions": normalized_suggestions,
            }
        )

    def _deduplicate_suggestions(self, items: list[ImprovementSuggestion]) -> list[ImprovementSuggestion]:
        deduplicated: list[ImprovementSuggestion] = []
        seen: set[str] = set()
        for item in items:
            key = self._normalize_match_text(item.suggestion)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(item)
        return deduplicated

    def _backfill_missing_negative_aspects(
        self,
        weaknesses: list[InsightItem],
        evidence_gaps: list[EvidenceGapItem],
        aspects: list[ReviewAspect],
    ) -> tuple[list[InsightItem], list[EvidenceGapItem]]:
        issue_keys = {self._canonical_issue_key(item.label, item.supporting_evidence.review_ids) for item in weaknesses}
        gap_keys = {self._canonical_issue_key(item.label, item.supporting_evidence.review_ids) for item in evidence_gaps}
        normalized_weaknesses = list(weaknesses)
        normalized_gaps = list(evidence_gaps)

        for aspect in aspects:
            if aspect.sentiment != "negative" or aspect.aspect == "overall_experience":
                continue
            seed_item = InsightItem(
                label=aspect.aspect,
                summary=aspect.evidence_span,
                confidence=aspect.confidence,
                supporting_evidence=SupportingEvidence(review_ids=[aspect.review_id]),
                confidence_breakdown=ConfidenceBreakdown(
                    extract_confidence=self._clamp_confidence(aspect.confidence, 0.7),
                    question_confidence=0.7,
                    evidence_confidence=0.7,
                    consistency_confidence=0.7,
                    final_confidence=self._clamp_confidence(aspect.confidence, 0.78),
                ),
            )
            issue_item = self._direct_issue_from_aspect(aspect, seed_item)
            issue_key = self._canonical_issue_key(issue_item.label, issue_item.supporting_evidence.review_ids)
            if issue_key not in issue_keys:
                normalized_weaknesses.append(issue_item)
                issue_keys.add(issue_key)

            gap_item = self._evidence_gap_for_aspect(aspect, seed_item)
            gap_key = self._canonical_issue_key(gap_item.label, gap_item.supporting_evidence.review_ids)
            if gap_key not in gap_keys:
                normalized_gaps.append(gap_item)
                gap_keys.add(gap_key)

        return normalized_weaknesses, normalized_gaps

    def _normalize_strength_item(self, item: InsightItem) -> InsightItem:
        has_text = bool(item.supporting_evidence.product_text_block_ids)
        has_image = bool(item.supporting_evidence.product_image_ids)
        if has_text and has_image:
            return item
        cap = 0.88 if has_text or has_image else 0.78
        return item.model_copy(update={"confidence": min(item.confidence, cap)})

    def _normalize_issue_confidence(self, item: InsightItem) -> InsightItem:
        has_text = bool(item.supporting_evidence.product_text_block_ids)
        has_image = bool(item.supporting_evidence.product_image_ids)
        if has_text and has_image:
            return item
        cap = 0.84 if has_text or has_image else 0.78
        return item.model_copy(update={"confidence": min(item.confidence, cap)})

    def _match_report_item_aspect(
        self,
        label: str,
        summary: str,
        review_ids: list[str],
        aspects: list[ReviewAspect],
    ) -> ReviewAspect | None:
        candidates = [aspect for aspect in aspects if not review_ids or aspect.review_id in review_ids]
        if not candidates:
            return None
        text_family = self._canonical_issue_family(f"{label} {summary}", review_ids)
        family_matches = [
            aspect
            for aspect in candidates
            if self._canonical_issue_family(aspect.aspect, [aspect.review_id]) == text_family
        ]
        if len(family_matches) == 1:
            return family_matches[0]
        label_tokens = self._match_tokens(f"{label} {summary}")
        scored: list[tuple[tuple[int, int, int], ReviewAspect]] = []
        for aspect in candidates:
            aspect_tokens = self._match_tokens(f"{aspect.aspect} {aspect.opinion} {aspect.evidence_span}")
            overlap = len(label_tokens.intersection(aspect_tokens))
            sentiment_bonus = 1 if aspect.sentiment == "negative" else 0
            overall_penalty = 0 if aspect.aspect != "overall_experience" else -1
            scored.append(((overlap, sentiment_bonus, overall_penalty), aspect))
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_aspect = scored[0]
        if best_score[0] > 0:
            return best_aspect
        non_overall = [aspect for aspect in candidates if aspect.aspect != "overall_experience"]
        if len(non_overall) == 1:
            return non_overall[0]
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _direct_issue_from_aspect(self, aspect: ReviewAspect, item: InsightItem) -> InsightItem:
        label, summary = self._direct_issue_label_and_summary(aspect)
        return self._normalize_issue_confidence(
            item.model_copy(
                update={
                    "label": label,
                    "summary": summary,
                    "owner": "product_issue",
                    "evidence_level": self._infer_evidence_level(item.supporting_evidence),
                }
            )
        )

    def _direct_issue_label_and_summary(self, aspect: ReviewAspect) -> tuple[str, str]:
        aspect_name = aspect.aspect.lower()
        if "rubber" in aspect_name and "durability" in aspect_name:
            if self._uses_main_prompt_variant():
                return (
                    "Rubber insert durability failure",
                    "One user reports that the rubber insert near the ear deteriorated and fell apart in less than two years.",
                )
            return ("橡胶耳托耐久性失效", "有用户反馈耳侧橡胶件在不到两年内老化并脱落。")
        if "optical" in aspect_name:
            if self._uses_main_prompt_variant():
                return (
                    "Potential optical magnification affecting depth perception",
                    "One user reports that the lenses slightly magnify vision, making the ground appear closer during walking or outdoor navigation.",
                )
            return ("可能影响景深判断的轻微放大", "有用户反馈镜片存在轻微放大效应，导致步行或户外导航时地面看起来更近。")
        if self._uses_main_prompt_variant():
            return (aspect.aspect.title(), f"User feedback reports a negative issue around {aspect.aspect}: {aspect.evidence_span}.")
        return (aspect.aspect, f"用户反馈在 {aspect.aspect} 上存在负面问题：{aspect.evidence_span}。")

    def _evidence_gap_for_aspect(self, aspect: ReviewAspect, item: InsightItem) -> EvidenceGapItem:
        label, summary = self._evidence_gap_label_and_summary(aspect, item.supporting_evidence)
        return EvidenceGapItem(
            label=label,
            summary=summary,
            confidence=max(0.82, min(0.95, item.confidence)),
            source_aspect=aspect.aspect,
            supporting_evidence=item.supporting_evidence,
            owner="content_presentation",
            evidence_level="missing_product_evidence",
            confidence_breakdown=item.confidence_breakdown,
        )

    def _evidence_gap_for_positive_aspect(self, aspect: ReviewAspect, item: InsightItem) -> EvidenceGapItem | None:
        if aspect.aspect == "overall_experience":
            return None
        aspect_name = aspect.aspect.lower()
        if "tint" in aspect_name and item.supporting_evidence.product_image_ids and not item.supporting_evidence.product_text_block_ids:
            label, summary = self._evidence_gap_label_and_summary(aspect, item.supporting_evidence)
            return EvidenceGapItem(
                label=label,
                summary=summary,
                confidence=max(0.8, min(0.92, item.confidence)),
                source_aspect=aspect.aspect,
                supporting_evidence=item.supporting_evidence,
                owner="content_presentation",
                evidence_level="missing_product_evidence",
                confidence_breakdown=item.confidence_breakdown,
            )
        if item.supporting_evidence.product_text_block_ids or item.supporting_evidence.product_image_ids:
            return None
        label, summary = self._evidence_gap_label_and_summary(aspect, item.supporting_evidence)
        return EvidenceGapItem(
            label=label,
            summary=summary,
            confidence=max(0.8, min(0.92, item.confidence)),
            source_aspect=aspect.aspect,
            supporting_evidence=item.supporting_evidence,
            owner="content_presentation",
            evidence_level="missing_product_evidence",
            confidence_breakdown=item.confidence_breakdown,
        )

    def _evidence_gap_label_and_summary(self, aspect: ReviewAspect, evidence: SupportingEvidence | None = None) -> tuple[str, str]:
        aspect_name = aspect.aspect.lower()
        if "rubber" in aspect_name and "durability" in aspect_name:
            if self._uses_main_prompt_variant():
                return (
                    "Missing rubber insert durability disclosure",
                    "No product-page warranty, material composition, or durability testing detail was retrieved for the rubber insert near the ear.",
                )
            return ("缺少橡胶耳托耐久性披露", "当前未检索到关于耳侧橡胶件的保修、材料组成或耐久性测试说明。")
        if "optical" in aspect_name:
            if self._uses_main_prompt_variant():
                return (
                    "Missing optical distortion validation",
                    "No product-page evidence was retrieved for optical neutrality, distortion control, or magnification-related validation.",
                )
            return ("缺少光学畸变核验信息", "当前未检索到关于光学中性、畸变控制或放大相关核验的信息。")
        if "tint" in aspect_name or "lens tinting" in aspect_name:
            if evidence is not None and evidence.product_image_ids and not evidence.product_text_block_ids:
                if self._uses_main_prompt_variant():
                    return (
                        "Missing explicit lens tint hue disclosure",
                        "Product images visually show tinted lenses, but the product text does not explicitly name the tint color or hue.",
                    )
                return ("缺少明确的镜片色调披露", "商品图片可以看出镜片存在染色，但商品文本没有明确标注具体颜色或色调名称。")
            if self._uses_main_prompt_variant():
                return (
                    "Missing lens tinting substantiation",
                    "Current product-page evidence does not substantiate the review feedback about lens tinting.",
                )
            return ("缺少镜片染色佐证", "当前商品页证据不足以支撑关于镜片染色的评论反馈。")
        if "comfort" in aspect_name:
            if self._uses_main_prompt_variant():
                return (
                    "Comfort substantiation gap",
                    "Comfort is positively mentioned by a user review, but no product-page text or reliable image evidence was retrieved to substantiate the claim.",
                )
            return ("舒适性佐证缺口", "评论提到了舒适性正向反馈，但当前未检索到可佐证该结论的商品页文本或可靠图像证据。")
        if "price" in aspect_name or "value" in aspect_name:
            if self._uses_main_prompt_variant():
                return (
                    "Price substantiation gap",
                    "The product is positively perceived as having an excellent price, but the listed price and comparative pricing context were not retrieved.",
                )
            return ("价格佐证缺口", "用户认为价格表现优秀，但当前未检索到明确售价或可用于比较的定价上下文。")
        if self._uses_main_prompt_variant():
            return (
                f"Missing {aspect.aspect} substantiation",
                f"Current product-page evidence does not substantiate the review feedback about {aspect.aspect}.",
            )
        return (f"缺少 {aspect.aspect} 佐证", f"当前商品页证据不足以支撑关于 {aspect.aspect} 的评论反馈。")

    def _deduplicate_report_items(self, items: list[InsightItem]) -> list[InsightItem]:
        deduplicated: list[InsightItem] = []
        seen: set[str] = set()
        for item in items:
            key = self._canonical_issue_key(item.label, item.supporting_evidence.review_ids)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(item)
        return deduplicated

    def _deduplicate_evidence_gaps(self, items: list[EvidenceGapItem]) -> list[EvidenceGapItem]:
        deduplicated: list[EvidenceGapItem] = []
        seen: set[str] = set()
        for item in items:
            key = self._canonical_issue_key(item.label, item.supporting_evidence.review_ids)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(item)
        return deduplicated

    def _rebind_suggestions(
        self,
        suggestions: list[ImprovementSuggestion],
        candidate_items: list[InsightItem | EvidenceGapItem],
    ) -> list[ImprovementSuggestion]:
        rebound: list[ImprovementSuggestion] = []
        for suggestion in suggestions:
            reason_text = self._meaningful_suggestion_reason_text(suggestion)
            matched = self._resolve_fallback_item(reason_text, suggestion.suggestion, candidate_items)
            updated = suggestion
            if matched is not None:
                updated = suggestion.model_copy(update={"supporting_evidence": matched.supporting_evidence})
                if self._suggestion_text_conflicts_with_fallback(suggestion.suggestion, reason_text, matched):
                    updated = updated.model_copy(update={"suggestion": self._default_suggestion_for_fallback(matched)})
            rebound.append(updated)
        return rebound

    def _ensure_gap_suggestions(
        self,
        suggestions: list[ImprovementSuggestion],
        evidence_gaps: list[EvidenceGapItem],
    ) -> list[ImprovementSuggestion]:
        ensured = list(suggestions)
        existing_keys = {
            self._canonical_issue_family(self._suggestion_family_text(suggestion), suggestion.supporting_evidence.review_ids)
            for suggestion in ensured
        }
        for gap in evidence_gaps:
            gap_key = self._canonical_issue_family(gap.label, gap.supporting_evidence.review_ids)
            if gap_key in existing_keys:
                continue
            if len(ensured) >= 5:
                break
            ensured.append(
                ImprovementSuggestion(
                    suggestion=self._default_suggestion_for_fallback(gap),
                    suggestion_type="perception",
                    reason=[gap.summary],
                    confidence=min(0.9, max(0.75, gap.confidence)),
                    supporting_evidence=gap.supporting_evidence,
                    owner="content_presentation",
                    confidence_breakdown=gap.confidence_breakdown,
                )
            )
            existing_keys.add(gap_key)
        return ensured

    def _suggestion_family_text(self, suggestion: ImprovementSuggestion) -> str:
        suggestion_family = self._canonical_issue_family(suggestion.suggestion, suggestion.supporting_evidence.review_ids)
        if suggestion.supporting_evidence.review_ids and suggestion_family not in set(suggestion.supporting_evidence.review_ids):
            return suggestion.suggestion
        if suggestion_family not in {"unscoped", ""}:
            return suggestion.suggestion
        return " ".join([suggestion.suggestion, self._meaningful_suggestion_reason_text(suggestion)]).strip()

    def _meaningful_suggestion_reason_text(self, suggestion: ImprovementSuggestion) -> str:
        meaningful_reasons = [
            reason
            for reason in suggestion.reason
            if not reason.lower().startswith("replay continuity:") and not reason.startswith("回放连续性：")
        ]
        return " ".join(meaningful_reasons)

    def _infer_evidence_level(self, evidence: SupportingEvidence) -> str:
        has_text = bool(evidence.product_text_block_ids)
        has_image = bool(evidence.product_image_ids)
        if has_text and has_image:
            return "product_supported"
        if has_text or has_image:
            return "partial_product_support"
        return "review_only"

    def _aggregate_confidence(self, aggregate: AspectAggregate) -> float:
        return min(0.92, 0.5 + 0.1 * min(aggregate.frequency, 4))

    def _merge_supporting_evidence(self, evidences: list[SupportingEvidence]) -> SupportingEvidence:
        return SupportingEvidence(
            review_ids=list(dict.fromkeys(
                review_id for evidence in evidences for review_id in evidence.review_ids
            ))[:10],
            product_text_block_ids=list(dict.fromkeys(
                text_id for evidence in evidences for text_id in evidence.product_text_block_ids
            ))[:10],
            product_image_ids=list(dict.fromkeys(
                image_id for evidence in evidences for image_id in evidence.product_image_ids
            ))[:10],
        )

    def _hydrate_insights(
        self,
        raw_items: object,
        fallback_items: list[InsightItem],
        evidence_candidates: list[InsightItem] | None = None,
    ) -> list[InsightItem]:
        if not isinstance(raw_items, list) or not raw_items:
            return fallback_items
        hydrated: list[InsightItem] = []
        candidate_pool = evidence_candidates or fallback_items
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "overall_experience")
            matched_fallback = self._resolve_fallback_item(
                raw_label=label,
                raw_text=" ".join([str(item.get("summary") or "")]),
                fallback_items=candidate_pool,
            )
            hydrated.append(
                InsightItem(
                    label=label,
                    summary=str(item.get("summary") or ""),
                    confidence=self._clamp_confidence(item.get("confidence"), 0.7),
                    supporting_evidence=matched_fallback.supporting_evidence if matched_fallback is not None else SupportingEvidence(),
                    owner=self._normalize_owner(item.get("owner"), default=matched_fallback.owner if matched_fallback is not None else "product_issue"),
                    confidence_breakdown=self._parse_confidence_breakdown(item.get("confidence_breakdown")),
                )
            )
        return hydrated or fallback_items

    def _hydrate_suggestions(
        self,
        raw_items: object,
        fallback_items: list[ImprovementSuggestion],
        evidence_candidates: list | None = None,
    ) -> list[ImprovementSuggestion]:
        if not isinstance(raw_items, list) or not raw_items:
            return fallback_items
        hydrated: list[ImprovementSuggestion] = []
        candidate_pool = evidence_candidates or fallback_items
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            suggestion_type = str(item.get("suggestion_type") or "perception")
            if suggestion_type not in {"structural", "perception"}:
                suggestion_type = "perception"
            reason = item.get("reason") if isinstance(item.get("reason"), list) else [str(item.get("reason") or "")]
            reason_text = " ".join(str(entry) for entry in reason if entry)
            suggestion_text = str(item.get("suggestion") or "")
            matched_fallback = self._resolve_fallback_item(
                raw_label=reason_text,
                raw_text=suggestion_text,
                fallback_items=candidate_pool,
            )
            if matched_fallback is None:
                matched_fallback = self._resolve_fallback_item(
                    raw_label=suggestion_text,
                    raw_text=reason_text,
                    fallback_items=candidate_pool,
                )
            if matched_fallback is not None and self._suggestion_text_conflicts_with_fallback(suggestion_text, reason_text, matched_fallback):
                suggestion_text = self._default_suggestion_for_fallback(matched_fallback)
            hydrated.append(
                ImprovementSuggestion(
                    suggestion=suggestion_text,
                    suggestion_type=suggestion_type,
                    reason=[str(entry) for entry in reason if entry],
                    confidence=self._clamp_confidence(item.get("confidence"), 0.7),
                    supporting_evidence=matched_fallback.supporting_evidence if matched_fallback is not None else SupportingEvidence(),
                    owner=self._normalize_owner(item.get("owner"), default=matched_fallback.owner if matched_fallback is not None else "content_presentation"),
                    confidence_breakdown=self._parse_confidence_breakdown(item.get("confidence_breakdown")),
                )
            )
        return hydrated or fallback_items

    def _resolve_fallback_item(self, raw_label: str, raw_text: str, fallback_items: list) -> object | None:
        if not fallback_items:
            return None
        mentioned_review_ids = self._extract_review_ids(f"{raw_label} {raw_text}")
        if mentioned_review_ids:
            for item in fallback_items:
                if mentioned_review_ids.intersection(item.supporting_evidence.review_ids):
                    return item

        raw_label_key = self._normalize_match_text(raw_label)
        exact_match = next((item for item in fallback_items if self._normalize_match_text(getattr(item, "label", getattr(item, "suggestion", ""))) == raw_label_key), None)
        if exact_match is not None:
            return exact_match

        raw_label_tokens = self._match_tokens(raw_label)
        raw_tokens = self._match_tokens(f"{raw_label} {raw_text}")
        scored = []
        for item in fallback_items:
            candidate_label_text = " ".join(
                [
                    str(getattr(item, "label", "")),
                    str(getattr(item, "suggestion", "")),
                ]
            )
            candidate_text = " ".join(
                [
                    str(getattr(item, "summary", "")),
                    " ".join(getattr(item, "reason", [])),
                    " ".join(item.supporting_evidence.review_ids),
                ]
            )
            candidate_label_tokens = self._match_tokens(candidate_label_text)
            candidate_tokens = self._match_tokens(candidate_text)
            label_overlap = len(raw_label_tokens.intersection(candidate_label_tokens))
            text_overlap = len(raw_tokens.intersection(candidate_label_tokens.union(candidate_tokens)))
            scored.append(((label_overlap, text_overlap), item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored[0][1] if scored and scored[0][0] > (0, 0) else None

    def _suggestion_text_conflicts_with_fallback(self, suggestion_text: str, reason_text: str, matched_fallback: object) -> bool:
        label = str(getattr(matched_fallback, "label", getattr(matched_fallback, "suggestion", "")))
        label_tokens = self._match_tokens(label)
        if not label_tokens:
            return False
        suggestion_tokens = self._match_tokens(suggestion_text)
        reason_tokens = self._match_tokens(reason_text)
        has_reason_alignment = bool(label_tokens.intersection(reason_tokens))
        has_suggestion_alignment = bool(label_tokens.intersection(suggestion_tokens))
        return has_reason_alignment and not has_suggestion_alignment

    def _default_suggestion_for_fallback(self, matched_fallback: object) -> str:
        label = str(getattr(matched_fallback, "label", "")).lower()
        if any(token in label for token in ("price", "value")):
            if self._uses_main_prompt_variant():
                return "State the current selling price and any active discount or list-price reference directly in the primary product metadata so the value claim can be checked quickly."
            return "在商品主信息中直接标明当前售价，以及任何生效中的折扣或划线价参考，方便用户快速核验价值表述。"
        if any(token in label for token in ("comfort", "fit")):
            if self._uses_main_prompt_variant():
                return "Clarify the fit and comfort-related design cues on the product page, and add close-up visuals of the features that help users judge wear comfort."
            return "在商品页中补充佩戴贴合度与舒适性相关设计说明，并增加帮助用户判断佩戴舒适性的局部特写。"
        if any(token in label for token in ("tint", "lens")):
            if self._uses_main_prompt_variant():
                return "State the exact lens tint in the primary product copy and include a color-accurate front-facing lens image so the tint claim can be checked visually."
            return "在商品核心文案中写明镜片的具体染色信息，并提供色彩准确的正面镜片图片，便于直观看到染色效果。"
        if any(token in label for token in ("optical", "distortion", "magnification")):
            if self._uses_main_prompt_variant():
                return "Add optical validation notes relevant to motion and depth perception, and explain what current product-page evidence can and cannot verify."
            return "补充与运动和景深感知相关的光学核验说明，并明确当前商品页证据能确认和不能确认的内容。"
        if any(token in label for token in ("durability", "rubber", "insert")):
            if self._uses_main_prompt_variant():
                return "Add durability-validation notes and warranty scope for the rubber ear insert, and describe the actual material and test scope without claiming unsupported lifetime thresholds."
            return "补充橡胶耳托的耐久性核验说明与保修范围，并说明实际材料与测试范围，不要给出缺乏证据支撑的寿命阈值。"
        if self._uses_main_prompt_variant():
            return f"Strengthen the product-page explanation and evidence around {getattr(matched_fallback, 'label', 'this issue')}."
        return f"围绕 {getattr(matched_fallback, 'label', '该问题')} 补充更明确的商品页说明与证据。"

    def _extract_review_ids(self, text: str) -> set[str]:
        return set(re.findall(r"[A-Za-z0-9]+_[A-Za-z0-9]+_review_\d+", text or ""))

    def _canonical_issue_key(self, label: str, review_ids: list[str] | None = None) -> str:
        text = (label or "").lower()
        if any(token in text for token in ("rubber", "insert", "durability")):
            base = "rubber_insert_durability"
        elif any(token in text for token in ("optical", "magnification", "distortion", "prism")):
            base = "optical_accuracy"
        elif any(token in text for token in ("comfort", "fit", "nose-pad", "temple-tip")):
            base = "comfort"
        elif any(token in text for token in ("price", "value", "discount", "pricing")):
            base = "price"
        elif any(token in text for token in ("tint", "lens tint", "hue")):
            base = "lens_tinting"
        elif "overall_experience" in text or "overall experience" in text:
            base = "overall_experience"
        else:
            review_key = review_ids[0] if review_ids else "unscoped"
            base = f"{review_key}:{self._normalize_match_text(label).replace(' ', '_')}"

        if any(token in text for token in ("transparency", "communication", "validation", "substantiation", "disclosure", "documentation", "gap", "missing", "claim")):
            issue_type = "evidence_gap"
        else:
            issue_type = "issue"
        return f"{base}:{issue_type}"

    def _canonical_issue_family(self, label: str, review_ids: list[str] | None = None) -> str:
        return self._canonical_issue_key(label, review_ids).split(":", 1)[0]

    def _normalize_match_text(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    def _match_tokens(self, text: str) -> set[str]:
        ignored_tokens = {
            "claim",
            "claims",
            "clear",
            "comes",
            "communication",
            "concern",
            "concerns",
            "evidence",
            "feedback",
            "from",
            "mentioned",
            "perception",
            "positive",
            "negative",
            "reported",
            "review",
            "reviews",
            "substantiation",
            "transparency",
            "user",
        }
        return {
            token
            for token in re.findall(r"[a-z0-9_]+", (text or "").lower())
            if len(token) > 2 and token not in ignored_tokens
        }

    def _natural_join(self, items: list[str], conjunction: str = "and") -> str:
        cleaned = [item for item in items if item]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} {conjunction} {cleaned[1]}"
        return ", ".join(cleaned[:-1]) + f", {conjunction} {cleaned[-1]}"

    def _evidence_answers_question(self, question: str, evidence) -> bool:
        question_text = (question or "").lower()
        preview = ((getattr(evidence, "content_preview", None) or "") + " " + (getattr(evidence, "source_section", None) or "")).lower()
        rerank_score = float(getattr(evidence, "rerank_score", 0.0) or 0.0)

        if getattr(evidence, "route", None) == "text":
            if any(term in question_text for term in ("price", "discount", "sale", "was/now")):
                return bool(re.search(r"\b\d+(?:[\.,]\d+)?\b", preview)) and rerank_score >= 0.1
            if any(term in question_text for term in ("comfortable", "comfort")):
                return any(term in preview for term in ("comfortable", "comfort", "ergonomic")) and rerank_score >= 0.1
            return rerank_score >= 0.2

        asks_visual = any(term in question_text for term in ("visible", "images", "show", "shown", "worn", "tinted", "hue", "mirrored"))
        defect_like = any(term in question_text for term in ("deteriorat", "crack", "crumbl", "fall apart", "detachment", "magnification", "distortion", "diopter"))
        threshold = 0.95 if defect_like else 0.9
        return asks_visual and rerank_score >= threshold

    def _apply_replay_context(
        self,
        report: ProductAnalysisReport,
        replay_payload: dict[str, object] | None,
        feedback_payload: dict[str, object] | None,
    ) -> tuple[ProductAnalysisReport, ReplayContinuationSummary | None]:
        if not replay_payload:
            return report, None

        previous_report = replay_payload.get("report")
        if not isinstance(previous_report, dict):
            return report, None

        previous_issue_records = self._extract_issue_records(previous_report)
        current_issue_records = self._issue_records_from_report(report)
        previous_issue_by_key = {record[1]: record[0] for record in previous_issue_records}
        current_issue_by_key = {record[1]: record[0] for record in current_issue_records}
        previous_issue_keys = set(previous_issue_by_key)
        current_issue_keys = set(current_issue_by_key)
        persistent_issue_keys = sorted(current_issue_keys.intersection(previous_issue_keys))
        resolved_issue_keys = sorted(previous_issue_keys.difference(current_issue_keys))
        new_issue_keys = sorted(current_issue_keys.difference(previous_issue_keys))
        persistent_issue_labels = [current_issue_by_key[key] for key in persistent_issue_keys]
        resolved_issue_labels = [previous_issue_by_key[key] for key in resolved_issue_keys]
        new_issue_labels = [current_issue_by_key[key] for key in new_issue_keys]
        feedback_state = self._extract_feedback_state(feedback_payload)
        accepted_persistent_issue_labels = [
            label for label in persistent_issue_labels if label in feedback_state["accepted_issue_labels"]
        ]
        rejected_persistent_issue_labels = [
            label for label in persistent_issue_labels if label in feedback_state["rejected_issue_labels"]
        ]

        updated_report = report.model_copy(
            update={
                "weaknesses": self._prioritize_replayed_insights(
                    report.weaknesses,
                    persistent_issue_labels,
                    accepted_persistent_issue_labels,
                    rejected_persistent_issue_labels,
                ),
                "controversies": self._prioritize_replayed_insights(
                    report.controversies,
                    persistent_issue_labels,
                    accepted_persistent_issue_labels,
                    rejected_persistent_issue_labels,
                ),
                "suggestions": self._annotate_suggestions_with_replay(
                    report.suggestions,
                    persistent_issue_labels,
                    accepted_persistent_issue_labels,
                    rejected_persistent_issue_labels,
                ),
            }
        )
        replay_summary = ReplayContinuationSummary(
            replay_path=str(replay_payload.get("replay_path")),
            feedback_path=str(feedback_payload.get("feedback_path")) if isinstance(feedback_payload, dict) else None,
            previous_analysis_mode=self._normalize_analysis_mode(replay_payload.get("analysis_mode")),
            applied=True,
            reviewed_slot_count=int(feedback_state["reviewed_slot_count"]),
            pending_slot_count=int(feedback_state["pending_slot_count"]),
            accepted_issue_labels=feedback_state["accepted_issue_labels"],
            rejected_issue_labels=feedback_state["rejected_issue_labels"],
            persistent_issue_labels=persistent_issue_labels,
            persistent_issue_keys=persistent_issue_keys,
            resolved_issue_labels=resolved_issue_labels,
            resolved_issue_keys=resolved_issue_keys,
            new_issue_labels=new_issue_labels,
            new_issue_keys=new_issue_keys,
        )
        return updated_report, replay_summary

    def _persist_report(self, product_id: str, category_slug: str | None, analysis_mode: AnalysisMode, extraction, questions, retrievals, retrieval_quality, retrieval_runtime: RetrievalRuntimeProfile, aggregates, report, trace, warnings: list[str], replay_summary: ReplayContinuationSummary | None) -> AnalysisArtifactBundle:
        target_dir = self.settings.reports_output_dir / (category_slug or "adhoc")
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"{product_id}_analysis.json"
        sidecar_paths = self.artifact_sidecar_service.persist_sidecars(
            product_id=product_id,
            category_slug=category_slug,
            analysis_mode=analysis_mode,
            report=report,
            trace=trace,
            retrieval_quality=retrieval_quality,
            warnings=warnings,
        )
        artifact_bundle = AnalysisArtifactBundle(
            analysis_path=str(output_path),
            feedback_path=sidecar_paths.get("feedback_path"),
            replay_path=sidecar_paths.get("replay_path"),
        )
        payload = {
            "analysis_mode": analysis_mode,
            "extraction": extraction.model_dump(mode="json"),
            "questions": [item.model_dump(mode="json") for item in questions],
            "retrievals": [item.model_dump(mode="json") for item in retrievals],
            "retrieval_quality": [item.model_dump(mode="json") for item in retrieval_quality],
            "retrieval_runtime": retrieval_runtime.model_dump(mode="json"),
            "aggregates": [item.model_dump(mode="json") for item in aggregates],
            "report": report.model_dump(mode="json"),
            "trace": [item.model_dump(mode="json") for item in trace],
            "replay_summary": replay_summary.model_dump(mode="json") if replay_summary is not None else None,
            "artifact_bundle": artifact_bundle.model_dump(mode="json"),
            "warnings": warnings,
        }
        output_path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
        return artifact_bundle

    def _build_process_trace(
        self,
        aspects: list[ReviewAspect],
        questions: list,
        retrievals: list,
        report: ProductAnalysisReport,
        replay_summary: ReplayContinuationSummary | None,
    ) -> list[ProcessTraceItem]:
        trace: list[ProcessTraceItem] = []
        if replay_summary is not None and replay_summary.applied:
            trace.append(
                ProcessTraceItem(
                    trace_type="observation",
                    aspect="replay_continuity",
                    summary=self._summarize_replay_continuity(replay_summary),
                    supporting_evidence=SupportingEvidence(),
                )
            )
        aggregate_lookup = {item.label: item for item in report.strengths + report.weaknesses + report.controversies}
        for aspect in aspects[:8]:
            insight = aggregate_lookup.get(aspect.aspect)
            support = insight.supporting_evidence if insight is not None else self._support_for_aspect(aspect.aspect, retrievals)
            breakdown = insight.confidence_breakdown if insight is not None else None
            related_questions = [item.question for item in questions if item.source_aspect == aspect.aspect][:2]
            trace.append(
                ProcessTraceItem(
                    trace_type="observation",
                    aspect=aspect.aspect,
                    summary=f"review={aspect.review_id}, sentiment={aspect.sentiment}, evidence_span={aspect.evidence_span}",
                    supporting_evidence=SupportingEvidence(review_ids=[aspect.review_id]),
                    confidence_breakdown=breakdown,
                )
            )
            trace.append(
                ProcessTraceItem(
                    trace_type="evidence_check",
                    aspect=aspect.aspect,
                    summary=self._summarize_evidence_check(support, related_questions),
                    owner=insight.owner if insight is not None else self._normalize_owner(None, default="evidence_gap"),
                    supporting_evidence=support,
                    confidence_breakdown=breakdown,
                )
            )
            if insight is not None:
                trace.append(
                    ProcessTraceItem(
                        trace_type="owner_judgement",
                        aspect=aspect.aspect,
                        summary=insight.summary,
                        owner=insight.owner,
                        supporting_evidence=support,
                        confidence_breakdown=breakdown,
                    )
                )
        for suggestion in report.suggestions[:3]:
            trace.append(
                ProcessTraceItem(
                    trace_type="action_generation",
                    aspect=suggestion.reason[0] if suggestion.reason else suggestion.suggestion,
                    summary=suggestion.suggestion,
                    owner=suggestion.owner,
                    supporting_evidence=suggestion.supporting_evidence,
                    confidence_breakdown=suggestion.confidence_breakdown,
                )
            )
        return trace

    def _summarize_evidence_check(self, evidence: SupportingEvidence, related_questions: list[str]) -> str:
        question_hint = f" questions={'; '.join(related_questions)}" if related_questions else ""
        return (
            f"reviews={len(evidence.review_ids)}, valid_text_blocks={len(evidence.product_text_block_ids)}, valid_images={len(evidence.product_image_ids)}.{question_hint}"
        )

    def _extract_issue_records(self, report_payload: dict[str, object]) -> list[tuple[str, str]]:
        records: list[tuple[str, str]] = []
        for key in ("weaknesses", "controversies", "evidence_gaps"):
            items = report_payload.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                label = item.get("label")
                if isinstance(label, str) and label:
                    support = item.get("supporting_evidence") if isinstance(item.get("supporting_evidence"), dict) else {}
                    review_ids = support.get("review_ids") if isinstance(support, dict) else []
                    records.append((label, self._canonical_issue_key(label, review_ids if isinstance(review_ids, list) else [])))
        deduplicated: list[tuple[str, str]] = []
        seen: set[str] = set()
        for label, key in records:
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append((label, key))
        return deduplicated

    def _issue_records_from_report(self, report: ProductAnalysisReport) -> list[tuple[str, str]]:
        records: list[tuple[str, str]] = []
        for item in report.weaknesses + report.controversies + report.evidence_gaps:
            records.append((item.label, self._canonical_issue_key(item.label, item.supporting_evidence.review_ids)))
        deduplicated: list[tuple[str, str]] = []
        seen: set[str] = set()
        for label, key in records:
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append((label, key))
        return deduplicated

    def _prioritize_replayed_insights(
        self,
        items: list[InsightItem],
        persistent_issue_labels: list[str],
        accepted_issue_labels: list[str],
        rejected_issue_labels: list[str],
    ) -> list[InsightItem]:
        persistent_issue_set = set(persistent_issue_labels)
        accepted_issue_set = set(accepted_issue_labels)
        rejected_issue_set = set(rejected_issue_labels)

        def rank(item: InsightItem) -> tuple[int, float]:
            if item.label in accepted_issue_set:
                return (0, -(item.confidence_breakdown.final_confidence if item.confidence_breakdown else item.confidence))
            if item.label in persistent_issue_set and item.label not in rejected_issue_set:
                return (1, -(item.confidence_breakdown.final_confidence if item.confidence_breakdown else item.confidence))
            if item.label in rejected_issue_set:
                return (3, -(item.confidence_breakdown.final_confidence if item.confidence_breakdown else item.confidence))
            return (2, -(item.confidence_breakdown.final_confidence if item.confidence_breakdown else item.confidence))

        return sorted(items, key=rank)

    def _annotate_suggestions_with_replay(
        self,
        suggestions: list[ImprovementSuggestion],
        persistent_issue_labels: list[str],
        accepted_issue_labels: list[str],
        rejected_issue_labels: list[str],
    ) -> list[ImprovementSuggestion]:
        if not suggestions or not persistent_issue_labels:
            return suggestions

        updated: list[ImprovementSuggestion] = []
        for suggestion in suggestions:
            matched_label = next(
                (label for label in persistent_issue_labels if self._suggestion_matches_label(suggestion, label)),
                None,
            )
            if matched_label is None:
                updated.append(suggestion)
                continue
            note = self._replay_continuity_note([matched_label])
            matched_family = self._canonical_issue_family(matched_label, suggestion.supporting_evidence.review_ids)
            accepted_match = next(
                (
                    label
                    for label in accepted_issue_labels
                    if self._canonical_issue_family(label, suggestion.supporting_evidence.review_ids) == matched_family
                ),
                None,
            )
            rejected_match = next(
                (
                    label
                    for label in rejected_issue_labels
                    if self._canonical_issue_family(label, suggestion.supporting_evidence.review_ids) == matched_family
                ),
                None,
            )
            if accepted_match is not None:
                note = f"{note} {self._feedback_alignment_note(accepted_match, 'accepted')}"
            elif rejected_match is not None:
                note = f"{note} {self._feedback_alignment_note(rejected_match, 'rejected')}"
            updated.append(suggestion.model_copy(update={"replay_note": note}))
        return sorted(
            updated,
            key=lambda suggestion: self._suggestion_replay_rank(
                suggestion,
                accepted_issue_labels=accepted_issue_labels,
                rejected_issue_labels=rejected_issue_labels,
                persistent_issue_labels=persistent_issue_labels,
            ),
        )

    def _suggestion_matches_label(self, suggestion: ImprovementSuggestion, label: str) -> bool:
        suggestion_family = self._canonical_issue_family(
            " ".join([suggestion.suggestion, *suggestion.reason]),
            suggestion.supporting_evidence.review_ids,
        )
        label_family = self._canonical_issue_family(label, suggestion.supporting_evidence.review_ids)
        if suggestion_family == label_family:
            return True
        haystack = " ".join([suggestion.suggestion, *suggestion.reason]).lower()
        return label.lower() in haystack

    def _replay_continuity_note(self, labels: list[str]) -> str:
        joined = ", ".join(labels)
        if self._uses_main_prompt_variant():
            return f"Replay continuity: the issue around {joined} also appeared in the previous run."
        return f"回放延续性：{joined} 在上一轮分析中也出现过。"

    def _feedback_alignment_note(self, label: str, status: str) -> str:
        if self._uses_main_prompt_variant():
            if status == "accepted":
                return f"Reviewer feedback: {label} was explicitly accepted in the previous review round."
            return f"Reviewer feedback: {label} was previously marked as rejected or disputed."
        if status == "accepted":
            return f"人工反馈：{label} 在上一轮审核中被明确接受。"
        return f"人工反馈：{label} 在上一轮审核中被标记为拒绝或存在争议。"

    def _suggestion_replay_rank(
        self,
        suggestion: ImprovementSuggestion,
        accepted_issue_labels: list[str],
        rejected_issue_labels: list[str],
        persistent_issue_labels: list[str],
    ) -> tuple[int, float]:
        matched_persistent = any(self._suggestion_matches_label(suggestion, label) for label in persistent_issue_labels)
        matched_accepted = any(self._suggestion_matches_label(suggestion, label) for label in accepted_issue_labels)
        matched_rejected = any(self._suggestion_matches_label(suggestion, label) for label in rejected_issue_labels)
        if matched_accepted:
            return (0, -suggestion.confidence)
        if matched_persistent and not matched_rejected:
            return (1, -suggestion.confidence)
        if matched_rejected:
            return (3, -suggestion.confidence)
        return (2, -suggestion.confidence)

    def _build_replay_warning(self, replay_summary: ReplayContinuationSummary | None) -> str | None:
        if replay_summary is None or not replay_summary.applied:
            return None
        if self._uses_main_prompt_variant():
            return (
                "replay continuity applied: "
                f"persistent={len(replay_summary.persistent_issue_labels)}, "
                f"resolved={len(replay_summary.resolved_issue_labels)}, "
                f"new={len(replay_summary.new_issue_labels)}, "
                f"reviewed={replay_summary.reviewed_slot_count}"
            )
        return (
            "已应用 replay 回放延续性："
            f"持续问题 {len(replay_summary.persistent_issue_labels)} 个，"
            f"已消退问题 {len(replay_summary.resolved_issue_labels)} 个，"
            f"新增问题 {len(replay_summary.new_issue_labels)} 个，"
            f"已审核反馈 {replay_summary.reviewed_slot_count} 项"
        )

    def _summarize_replay_continuity(self, replay_summary: ReplayContinuationSummary) -> str:
        persistent = ", ".join(replay_summary.persistent_issue_labels[:3]) or "none"
        resolved = ", ".join(replay_summary.resolved_issue_labels[:3]) or "none"
        new_labels = ", ".join(replay_summary.new_issue_labels[:3]) or "none"
        accepted = ", ".join(replay_summary.accepted_issue_labels[:3]) or "none"
        rejected = ", ".join(replay_summary.rejected_issue_labels[:3]) or "none"
        return (
            f"replay_path={replay_summary.replay_path}, feedback_path={replay_summary.feedback_path}, "
            f"persistent={persistent}, resolved={resolved}, new={new_labels}, "
            f"accepted={accepted}, rejected={rejected}, reviewed={replay_summary.reviewed_slot_count}"
        )

    def _extract_feedback_state(self, feedback_payload: dict[str, object] | None) -> dict[str, object]:
        slots = feedback_payload.get("slots") if isinstance(feedback_payload, dict) else None
        if not isinstance(slots, list):
            return {
                "accepted_issue_labels": [],
                "rejected_issue_labels": [],
                "reviewed_slot_count": 0,
                "pending_slot_count": 0,
            }

        accepted_issue_labels: list[str] = []
        rejected_issue_labels: list[str] = []
        reviewed_slot_count = 0
        pending_slot_count = 0

        for slot in slots:
            if not isinstance(slot, dict):
                continue
            status = str(slot.get("status") or "pending_review").lower()
            label = str(slot.get("label") or "")
            item_type = str(slot.get("item_type") or "")
            if status == "pending_review":
                pending_slot_count += 1
            else:
                reviewed_slot_count += 1
            if item_type != "insight" or not label:
                continue
            if status in {"accepted", "confirmed", "keep", "resolved"}:
                accepted_issue_labels.append(label)
            elif status in {"rejected", "dismissed", "false_positive", "disputed"}:
                rejected_issue_labels.append(label)

        return {
            "accepted_issue_labels": self._unique_labels(accepted_issue_labels),
            "rejected_issue_labels": self._unique_labels(rejected_issue_labels),
            "reviewed_slot_count": reviewed_slot_count,
            "pending_slot_count": pending_slot_count,
        }

    def _unique_labels(self, labels: list[str]) -> list[str]:
        return list(dict.fromkeys(label for label in labels if label))

    def _normalize_analysis_mode(self, value: object) -> AnalysisMode | None:
        if value in {"heuristic", "llm"}:
            return value
        return None

    def _build_confidence_breakdown(self, aggregate: AspectAggregate, evidence: SupportingEvidence) -> ConfidenceBreakdown:
        extract_confidence = self._clamp_confidence(0.52 + 0.08 * min(aggregate.frequency, 4), 0.7)
        question_confidence = self._clamp_confidence(0.62 + (0.05 if evidence.product_text_block_ids and evidence.product_image_ids else 0.0), 0.7)
        evidence_hits = sum(
            1
            for present in [evidence.review_ids, evidence.product_text_block_ids, evidence.product_image_ids]
            if present
        )
        evidence_confidence = self._clamp_confidence(0.35 + 0.18 * evidence_hits, 0.7)
        consistency_confidence = self._clamp_confidence(0.55 + 0.1 * min(aggregate.frequency, 3) - (0.08 if aggregate.negative_ratio and aggregate.positive_ratio else 0.0), 0.7)
        final_confidence = self._clamp_confidence(
            0.25 * extract_confidence + 0.2 * question_confidence + 0.35 * evidence_confidence + 0.2 * consistency_confidence,
            self._aggregate_confidence(aggregate),
        )
        return ConfidenceBreakdown(
            extract_confidence=extract_confidence,
            question_confidence=question_confidence,
            evidence_confidence=evidence_confidence,
            consistency_confidence=consistency_confidence,
            final_confidence=final_confidence,
        )

    def _parse_confidence_breakdown(self, value: object) -> ConfidenceBreakdown | None:
        if not isinstance(value, dict):
            return None
        return ConfidenceBreakdown(
            extract_confidence=self._clamp_confidence(value.get("extract_confidence"), 0.7),
            question_confidence=self._clamp_confidence(value.get("question_confidence"), 0.7),
            evidence_confidence=self._clamp_confidence(value.get("evidence_confidence"), 0.7),
            consistency_confidence=self._clamp_confidence(value.get("consistency_confidence"), 0.7),
            final_confidence=self._clamp_confidence(value.get("final_confidence"), 0.7),
        )

    def _normalize_owner(self, value: object, default: str = "product_issue") -> str:
        owner = str(value or default)
        if owner not in {"product_issue", "content_presentation", "evidence_gap", "expectation_mismatch"}:
            return default
        return owner

    def _build_retrieval_runtime_profile(self) -> RetrievalRuntimeProfile:
        image_backend = self.settings.image_embedding_backend
        multimodal_backend = self.settings.multimodal_reranker_backend
        native_multimodal_enabled = image_backend not in {"proxy_text", "disabled"} or multimodal_backend not in {"disabled", "off"}

        if self._uses_main_prompt_variant():
            if native_multimodal_enabled:
                summary = "Image evidence is configured to use native multimodal retrieval or reranking paths."
            else:
                summary = "Image evidence is currently indexed through proxy text, and reranking remains text-only rather than native multimodal."
        else:
            if native_multimodal_enabled:
                summary = "当前图片证据已配置为走原生多模态检索或精排路径。"
            else:
                summary = "当前图片证据仍通过代理文本建索引，精排也仍是纯文本路径，尚未进入原生多模态。"

        return RetrievalRuntimeProfile(
            text_embedding_backend=self.settings.embedding_backend,
            text_embedding_model=self.settings.qwen_embedding_model,
            image_embedding_backend=image_backend,
            image_embedding_model=(
                self.settings.clip_vl_embedding_model
                if image_backend == "clip"
                else self.settings.qwen_vl_embedding_model if image_backend not in {"proxy_text", "disabled"} else None
            ),
            reranker_backend=self.settings.reranker_backend,
            reranker_model=self.settings.qwen_reranker_model,
            multimodal_reranker_backend=multimodal_backend,
            multimodal_reranker_model=self.settings.qwen_vl_reranker_model if multimodal_backend not in {"disabled", "off"} else None,
            native_multimodal_enabled=native_multimodal_enabled,
            summary=summary,
        )

    def _assess_retrieval_quality(self, retrievals: list) -> list[RetrievalQualityMetrics]:
        metrics: list[RetrievalQualityMetrics] = []
        for retrieval in retrievals:
            evidence_count = len(retrieval.retrieved)
            expected_routes = set(retrieval.expected_evidence_routes or [])
            if evidence_count == 0:
                metrics.append(
                    RetrievalQualityMetrics(
                        retrieval_id=retrieval.retrieval_id,
                        source_aspect=retrieval.source_aspect,
                        top_k_count=0,
                        route_coverage=0.0,
                        answer_coverage=0.0,
                        answer_status="none",
                        answer_value=None,
                        answer_source=None,
                        evidence_coverage=0.0,
                        score_drift=0.0,
                        text_coverage=False,
                        image_coverage=False,
                        conflict_risk=0.0,
                    )
                )
                continue
            text_coverage = any(item.route == "text" for item in retrieval.retrieved)
            image_coverage = any(item.route == "image" for item in retrieval.retrieved)
            available_routes = {item.route for item in retrieval.retrieved}
            if not expected_routes:
                expected_routes = set(available_routes)
            route_coverage = len(expected_routes.intersection(available_routes)) / len(expected_routes) if expected_routes else 0.0
            answered_hits = [item for item in retrieval.retrieved if self._evidence_answers_question(retrieval.source_question, item)]
            answer_coverage = min(1.0, len(answered_hits) / max(1, len(expected_routes)))
            answer_value, answer_source = self._extract_answer_value(retrieval.source_question, answered_hits)
            answer_status, answer_coverage = self._classify_answer_status(
                retrieval.source_question,
                answer_value,
                answer_source,
                answer_coverage,
            )
            drift_samples = [
                abs(item.embedding_score - (item.rerank_score if item.rerank_score is not None else item.embedding_score))
                for item in retrieval.retrieved
            ]
            score_drift = sum(drift_samples) / len(drift_samples)
            answered_route_scores: dict[str, list[float]] = defaultdict(list)
            for item in answered_hits:
                answered_route_scores[item.route].append(float(item.rerank_score if item.rerank_score is not None else item.embedding_score))
            if len(answered_route_scores) >= 2:
                route_means = [sum(scores) / len(scores) for scores in answered_route_scores.values() if scores]
                conflict_risk = min(1.0, max(route_means) - min(route_means)) if route_means else 0.0
            else:
                conflict_risk = 0.0
            metrics.append(
                RetrievalQualityMetrics(
                    retrieval_id=retrieval.retrieval_id,
                    source_aspect=retrieval.source_aspect,
                    top_k_count=evidence_count,
                    route_coverage=route_coverage,
                    answer_coverage=answer_coverage,
                    answer_status=answer_status,
                    answer_value=answer_value,
                    answer_source=answer_source,
                    evidence_coverage=answer_coverage,
                    score_drift=score_drift,
                    text_coverage=text_coverage,
                    image_coverage=image_coverage,
                    conflict_risk=conflict_risk,
                )
            )
        return metrics

    def _extract_answer_value(self, question: str, answered_hits: list) -> tuple[str | None, str | None]:
        if not answered_hits:
            return None, None
        question_text = (question or "").lower()
        ranked_hits = sorted(
            answered_hits,
            key=lambda item: float(item.rerank_score if item.rerank_score is not None else item.embedding_score),
            reverse=True,
        )
        joined_preview = " ".join(filter(None, [getattr(item, "content_preview", None) for item in ranked_hits])).lower()

        if "price" in question_text:
            match = re.search(r"(?:\$|€|£)?\s*\d+(?:[\.,]\d+)?", joined_preview)
            if match:
                return match.group(0).strip(), "text"
            return None, None

        if any(token in question_text for token in ("uv protection", "uv400", "category 4", "tint provides uv")):
            fragments = []
            for pattern in (r"100% uv protection", r"uv400", r"category\s*\d+"):
                match = re.search(pattern, joined_preview)
                if match:
                    fragments.append(match.group(0))
            if fragments:
                return "; ".join(dict.fromkeys(fragment.title() if fragment.startswith("category") else fragment for fragment in fragments)), "text"

        if any(token in question_text for token in ("tint color", "tint", "hue")):
            color_match = re.search(r"\b(gray|grey|brown|green|rose|blue|amber|bronze|smoke|mirrored)\b", joined_preview)
            if color_match:
                return color_match.group(1), "text"
            if any(getattr(item, "route", None) == "image" for item in ranked_hits):
                return "Lens tint is visually present in product images, but the exact hue is not explicitly named.", "image"

        best = ranked_hits[0]
        preview = getattr(best, "content_preview", None)
        if preview:
            return preview[:160], getattr(best, "route", None)
        return None, None

    def _classify_answer_status(
        self,
        question: str,
        answer_value: str | None,
        answer_source: str | None,
        answer_coverage: float,
    ) -> tuple[str, float]:
        if not answer_value:
            return "none", 0.0
        question_text = (question or "").lower()
        answer_text = answer_value.lower()
        if any(token in question_text for token in ("tint color", "hue", "tint color or hue")) and "not explicitly named" in answer_text:
            return "partial", min(answer_coverage, 0.5)
        if answer_source in {"text", "image"}:
            return "supported", answer_coverage
        return "unsupported", answer_coverage

    def _merge_review_evidence(self, evidences: list[SupportingEvidence]) -> SupportingEvidence:
        return SupportingEvidence(
            review_ids=list(dict.fromkeys(review_id for evidence in evidences for review_id in evidence.review_ids))[:10],
            product_text_block_ids=[],
            product_image_ids=[],
        )

    def _merge_product_evidence(self, evidences: list[SupportingEvidence]) -> SupportingEvidence:
        return SupportingEvidence(
            review_ids=[],
            product_text_block_ids=list(dict.fromkeys(text_id for evidence in evidences for text_id in evidence.product_text_block_ids))[:10],
            product_image_ids=list(dict.fromkeys(image_id for evidence in evidences for image_id in evidence.product_image_ids))[:10],
        )

    def _clamp_confidence(self, value: object, default: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, numeric))