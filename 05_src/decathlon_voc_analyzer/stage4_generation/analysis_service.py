import json
from collections import Counter, defaultdict

import orjson
from openai import OpenAI

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.analysis import (
    AnalysisMode,
    AspectAggregate,
    ImprovementSuggestion,
    InsightItem,
    ProductAnalysisReport,
    ProductAnalysisRequest,
    ProductAnalysisResponse,
    SupportingEvidence,
)
from decathlon_voc_analyzer.schemas.review import ReviewAspect, ReviewExtractionRequest
from decathlon_voc_analyzer.prompts import build_report_generation_user_prompt, get_prompt
from decathlon_voc_analyzer.stage1_dataset.dataset_service import DatasetService
from decathlon_voc_analyzer.stage2_review_modeling.review_service import ReviewExtractionService
from decathlon_voc_analyzer.stage3_retrieval.retrieval_service import RetrievalService
from decathlon_voc_analyzer.stage4_generation.question_service import QuestionGenerationService


class ProductAnalysisService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.dataset_service = DatasetService()
        self.review_service = ReviewExtractionService()
        self.question_service = QuestionGenerationService()
        self.retrieval_service = RetrievalService()

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
                persist_artifact=False,
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
        aggregates = self._aggregate_aspects(extraction.aspects)
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

        artifact_path: str | None = None
        if request.persist_artifact:
            artifact_path = self._persist_report(package.product_id, package.category_slug, extraction, questions, retrievals, aggregates, report, warnings)

        return ProductAnalysisResponse(
            analysis_mode=analysis_mode,
            extraction=extraction,
            questions=questions,
            retrievals=retrievals,
            aggregates=aggregates,
            report=report,
            artifact_path=artifact_path,
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
                    scenes=dict(scenes),
                    representative_review_ids=list(dict.fromkeys(item.review_id for item in items[:3])),
                )
            )
        return sorted(aggregates, key=lambda item: item.frequency, reverse=True)

    def _build_report_with_llm(
        self,
        product_id: str,
        category_slug: str | None,
        aggregates: list[AspectAggregate],
        retrievals: list,
    ) -> ProductAnalysisReport:
        client = OpenAI(api_key=self.settings.qwen_plus_api_key, base_url=self.settings.qwen_base_url)
        payload = {
            "product_id": product_id,
            "category_slug": category_slug,
            "aggregates": [aggregate.model_dump(mode="json") for aggregate in aggregates],
            "retrievals": [retrieval.model_dump(mode="json") for retrieval in retrievals[:10]],
        }
        response = client.chat.completions.create(
            model=self.settings.qwen_plus_model,
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": get_prompt("report_generation_system")},
                {"role": "user", "content": build_report_generation_user_prompt(payload)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        return self._hydrate_report_from_llm(product_id, category_slug, aggregates, retrievals, parsed)

    def _hydrate_report_from_llm(self, product_id: str, category_slug: str | None, aggregates: list[AspectAggregate], retrievals: list, payload: dict) -> ProductAnalysisReport:
        fallback = self._build_report_heuristic(product_id, category_slug, aggregates, retrievals)
        strengths = self._hydrate_insights(payload.get("strengths"), fallback.strengths)
        weaknesses = self._hydrate_insights(payload.get("weaknesses"), fallback.weaknesses)
        controversies = self._hydrate_insights(payload.get("controversies"), fallback.controversies)
        suggestions = self._hydrate_suggestions(payload.get("suggestions"), fallback.suggestions)
        return ProductAnalysisReport(
            product_id=product_id,
            category_slug=category_slug,
            answer=str(payload.get("answer") or fallback.answer),
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
                strengths.append(
                    InsightItem(
                        label=aggregate.aspect,
                        summary=f"用户对 {aggregate.aspect} 的反馈以正向为主，出现 {aggregate.frequency} 次。",
                        confidence=self._aggregate_confidence(aggregate),
                        supporting_evidence=evidence,
                    )
                )
            elif aggregate.negative_ratio >= 0.4:
                weaknesses.append(
                    InsightItem(
                        label=aggregate.aspect,
                        summary=f"用户对 {aggregate.aspect} 存在明显负向反馈，出现 {aggregate.frequency} 次。",
                        confidence=self._aggregate_confidence(aggregate),
                        supporting_evidence=evidence,
                    )
                )
            else:
                controversies.append(
                    InsightItem(
                        label=aggregate.aspect,
                        summary=f"{aggregate.aspect} 的意见分布较分散，存在一定争议。",
                        confidence=self._aggregate_confidence(aggregate),
                        supporting_evidence=evidence,
                    )
                )

        if not strengths and aggregates:
            aggregate = aggregates[0]
            strengths.append(
                InsightItem(
                    label=aggregate.aspect,
                    summary=f"{aggregate.aspect} 是当前评论中最常见的体验主题。",
                    confidence=self._aggregate_confidence(aggregate),
                    supporting_evidence=self._support_for_aspect(aggregate.aspect, retrievals),
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
        return SupportingEvidence(
            review_ids=list(dict.fromkeys(record.source_review_id for record in matching))[:3],
            product_text_block_ids=list(dict.fromkeys(
                evidence.text_block_id
                for record in matching
                for evidence in record.retrieved
                if evidence.text_block_id
            ))[:3],
            product_image_ids=list(dict.fromkeys(
                evidence.image_id
                for record in matching
                for evidence in record.retrieved
                if evidence.image_id
            ))[:3],
        )

    def _build_answer(self, strengths: list[InsightItem], weaknesses: list[InsightItem], controversies: list[InsightItem]) -> str:
        strength_label = strengths[0].label if strengths else "核心体验"
        weakness_label = weaknesses[0].label if weaknesses else None
        controversy_label = controversies[0].label if controversies else None
        parts = [f"该商品当前评论主要集中在 {strength_label} 相关体验。"]
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
            suggestions.append(
                ImprovementSuggestion(
                    suggestion=f"优先优化 {item.label} 相关设计或表达，并在商品页中强化对应说明。",
                    suggestion_type=suggestion_type,
                    reason=reasons,
                    confidence=min(0.88, item.confidence),
                    supporting_evidence=item.supporting_evidence,
                )
            )
        for item in controversies[:1]:
            suggestions.append(
                ImprovementSuggestion(
                    suggestion=f"针对 {item.label} 增加更明确的适用场景说明，降低用户预期偏差。",
                    suggestion_type="perception",
                    reason=[item.summary],
                    confidence=min(0.8, item.confidence),
                    supporting_evidence=item.supporting_evidence,
                )
            )
        if not suggestions:
            fallback = weaknesses[0] if weaknesses else controversies[0] if controversies else strengths[0] if strengths else None
            if fallback is not None:
                suggestions.append(
                    ImprovementSuggestion(
                        suggestion=f"围绕 {fallback.label} 补充更具体的商品说明和使用场景示例，减少用户理解偏差。",
                        suggestion_type="perception",
                        reason=[fallback.summary],
                        confidence=min(0.76, fallback.confidence),
                        supporting_evidence=fallback.supporting_evidence,
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

    def _hydrate_insights(self, raw_items: object, fallback_items: list[InsightItem]) -> list[InsightItem]:
        if not isinstance(raw_items, list) or not raw_items:
            return fallback_items
        hydrated: list[InsightItem] = []
        fallback_lookup = {item.label: item.supporting_evidence for item in fallback_items}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "overall_experience")
            hydrated.append(
                InsightItem(
                    label=label,
                    summary=str(item.get("summary") or ""),
                    confidence=self._clamp_confidence(item.get("confidence"), 0.7),
                    supporting_evidence=fallback_lookup.get(label, fallback_items[0].supporting_evidence if fallback_items else SupportingEvidence()),
                )
            )
        return hydrated or fallback_items

    def _hydrate_suggestions(self, raw_items: object, fallback_items: list[ImprovementSuggestion]) -> list[ImprovementSuggestion]:
        if not isinstance(raw_items, list) or not raw_items:
            return fallback_items
        fallback_support = fallback_items[0].supporting_evidence if fallback_items else SupportingEvidence()
        hydrated: list[ImprovementSuggestion] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            suggestion_type = str(item.get("suggestion_type") or "perception")
            if suggestion_type not in {"structural", "perception"}:
                suggestion_type = "perception"
            reason = item.get("reason") if isinstance(item.get("reason"), list) else [str(item.get("reason") or "")]
            hydrated.append(
                ImprovementSuggestion(
                    suggestion=str(item.get("suggestion") or ""),
                    suggestion_type=suggestion_type,
                    reason=[str(entry) for entry in reason if entry],
                    confidence=self._clamp_confidence(item.get("confidence"), 0.7),
                    supporting_evidence=fallback_support,
                )
            )
        return hydrated or fallback_items

    def _persist_report(self, product_id: str, category_slug: str | None, extraction, questions, retrievals, aggregates, report, warnings: list[str]) -> str:
        target_dir = self.settings.reports_output_dir / (category_slug or "adhoc")
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"{product_id}_analysis.json"
        payload = {
            "extraction": extraction.model_dump(mode="json"),
            "questions": [item.model_dump(mode="json") for item in questions],
            "retrievals": [item.model_dump(mode="json") for item in retrievals],
            "aggregates": [item.model_dump(mode="json") for item in aggregates],
            "report": report.model_dump(mode="json"),
            "warnings": warnings,
        }
        output_path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
        return str(output_path)

    def _clamp_confidence(self, value: object, default: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, numeric))