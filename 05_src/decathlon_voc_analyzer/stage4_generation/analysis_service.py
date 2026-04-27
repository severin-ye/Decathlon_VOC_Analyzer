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
        report = report.model_copy(
            update={
                "product_impressions": self._build_product_impressions(aggregates),
                "customer_impressions": self._build_customer_impressions(extraction.aspects),
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
            for aggregate in aggregates[:5]
        ]

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
        suggestions = self._hydrate_suggestions(payload.get("suggestions"), fallback.suggestions, evidence_candidates=fallback.suggestions + evidence_candidates)
        return ProductAnalysisReport(
            product_id=product_id,
            category_slug=category_slug,
            answer=self._build_answer(strengths, weaknesses, controversies),
            strengths=strengths,
            weaknesses=weaknesses,
            controversies=controversies,
            applicable_scenes=list(payload.get("applicable_scenes") or fallback.applicable_scenes),
            supporting_aspects=fallback.supporting_aspects,
            supporting_reviews=fallback.supporting_reviews,
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
        supporting_aspects = [aggregate.aspect for aggregate in aggregates[:5]]
        supporting_reviews = list(dict.fromkeys(
            review_id
            for aggregate in aggregates[:5]
            for review_id in aggregate.representative_review_ids
        ))
        supporting_product_evidence = self._merge_supporting_evidence(
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
            applicable_scenes=[scene for scene, _ in scenes.most_common(4)],
            supporting_aspects=supporting_aspects,
            supporting_reviews=supporting_reviews,
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
        weak_supported = [item.label for item in strengths if item.label not in strong_supported]
        weakness_label = weaknesses[0].label if weaknesses else None
        controversy_label = controversies[0].label if controversies else None
        if self._uses_main_prompt_variant():
            parts: list[str] = []
            if strength_labels:
                parts.append(f"Positive feedback appears on {self._natural_join(strength_labels)}.")
            else:
                parts.append("Current reviews concentrate mainly on the core experience.")
            if strong_supported and weak_supported:
                weak_verb = "are" if len(weak_supported) > 1 else "is"
                parts.append(
                    f"{self._natural_join(strong_supported)} is relatively well supported by product-page evidence, while {self._natural_join(weak_supported)} {weak_verb} mainly supported by user reviews and only weakly supported by product-page evidence."
                )
            elif strong_supported:
                parts.append(f"{self._natural_join(strong_supported)} is relatively well supported by product-page evidence.")
            elif weak_supported:
                parts.append(f"{self._natural_join(weak_supported)} is mainly supported by user reviews and only weakly supported by product-page evidence.")
            if weakness_label:
                parts.append(f"The most important issue to watch is {weakness_label}.")
            if controversy_label:
                parts.append(f"There is still some disagreement around {controversy_label}, which should be interpreted by user segment and usage context.")
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
            if controversy_label:
                parts.append(f"{controversy_label} 上存在一定意见分歧，需要结合具体人群与场景理解。")
        return "".join(parts)

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
            matched_fallback = self._resolve_fallback_item(
                raw_label=str(item.get("suggestion") or ""),
                raw_text=" ".join(str(entry) for entry in reason if entry),
                fallback_items=candidate_pool,
            )
            hydrated.append(
                ImprovementSuggestion(
                    suggestion=str(item.get("suggestion") or ""),
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

        raw_tokens = self._match_tokens(f"{raw_label} {raw_text}")
        scored = []
        for item in fallback_items:
            candidate_text = " ".join(
                [
                    str(getattr(item, "label", "")),
                    str(getattr(item, "summary", "")),
                    str(getattr(item, "suggestion", "")),
                    " ".join(getattr(item, "reason", [])),
                    " ".join(item.supporting_evidence.review_ids),
                ]
            )
            candidate_tokens = self._match_tokens(candidate_text)
            overlap = len(raw_tokens.intersection(candidate_tokens))
            scored.append((overlap, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored[0][1] if scored and scored[0][0] > 0 else fallback_items[0]

    def _extract_review_ids(self, text: str) -> set[str]:
        return set(re.findall(r"[A-Za-z0-9]+_[A-Za-z0-9]+_review_\d+", text or ""))

    def _normalize_match_text(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    def _match_tokens(self, text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9_]+", (text or "").lower()) if len(token) > 2}

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

        previous_issue_labels = self._extract_issue_labels(previous_report)
        current_issue_labels = self._unique_labels([item.label for item in report.weaknesses + report.controversies])
        previous_issue_set = set(previous_issue_labels)
        current_issue_set = set(current_issue_labels)
        persistent_issue_labels = [label for label in current_issue_labels if label in previous_issue_set]
        resolved_issue_labels = [label for label in previous_issue_labels if label not in current_issue_set]
        new_issue_labels = [label for label in current_issue_labels if label not in previous_issue_set]
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
            resolved_issue_labels=resolved_issue_labels,
            new_issue_labels=new_issue_labels,
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
            f"reviews={len(evidence.review_ids)}, text_blocks={len(evidence.product_text_block_ids)}, images={len(evidence.product_image_ids)}.{question_hint}"
        )

    def _extract_issue_labels(self, report_payload: dict[str, object]) -> list[str]:
        labels: list[str] = []
        for key in ("weaknesses", "controversies"):
            items = report_payload.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                label = item.get("label")
                if isinstance(label, str) and label:
                    labels.append(label)
        return self._unique_labels(labels)

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
        matched_labels: set[str] = set()
        for suggestion in suggestions:
            matched_label = next(
                (label for label in persistent_issue_labels if self._suggestion_matches_label(suggestion, label)),
                None,
            )
            if matched_label is None:
                updated.append(suggestion)
                continue
            matched_labels.add(matched_label)
            reasons = list(suggestion.reason)
            notes = [self._replay_continuity_note([matched_label])]
            if matched_label in accepted_issue_labels:
                notes.append(self._feedback_alignment_note(matched_label, "accepted"))
            elif matched_label in rejected_issue_labels:
                notes.append(self._feedback_alignment_note(matched_label, "rejected"))
            for note in notes:
                if note not in reasons:
                    reasons.append(note)
            updated.append(suggestion.model_copy(update={"reason": reasons}))

        unmatched_labels = [label for label in persistent_issue_labels if label not in matched_labels]
        if unmatched_labels and updated:
            note = self._replay_continuity_note(unmatched_labels[:2])
            reasons = list(updated[0].reason)
            if note not in reasons:
                updated[0] = updated[0].model_copy(update={"reason": reasons + [note]})
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
                        evidence_coverage=0.0,
                        score_drift=0.0,
                        text_coverage=False,
                        image_coverage=False,
                        conflict_risk=1.0,
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
            drift_samples = [
                abs(item.embedding_score - (item.rerank_score if item.rerank_score is not None else item.embedding_score))
                for item in retrieval.retrieved
            ]
            score_drift = sum(drift_samples) / len(drift_samples)
            conflict_risk = 1.0 - min(1.0, (0.6 if text_coverage else 0.0) + (0.4 if image_coverage else 0.0))
            metrics.append(
                RetrievalQualityMetrics(
                    retrieval_id=retrieval.retrieval_id,
                    source_aspect=retrieval.source_aspect,
                    top_k_count=evidence_count,
                    route_coverage=route_coverage,
                    answer_coverage=answer_coverage,
                    evidence_coverage=answer_coverage,
                    score_drift=score_drift,
                    text_coverage=text_coverage,
                    image_coverage=image_coverage,
                    conflict_risk=conflict_risk,
                )
            )
        return metrics

    def _clamp_confidence(self, value: object, default: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, numeric))