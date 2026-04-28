from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import orjson


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _safe_weighted_mean(values: list[float], weights: list[float]) -> float:
    if not values or not weights:
        return 0.0
    total_weight = sum(weights)
    if total_weight <= 0:
        return 0.0
    return sum(value * weight for value, weight in zip(values, weights)) / total_weight


def _load_json(path: Path) -> dict:
    return orjson.loads(path.read_bytes())


def _supporting_evidence_count(item: dict) -> int:
    evidence = item.get("supporting_evidence") or {}
    return sum(
        len(evidence.get(key) or [])
        for key in ("review_ids", "product_text_block_ids", "product_image_ids")
    )


def _counter_rate(counter: Counter[str], key: str, total: int) -> float:
    if total <= 0:
        return 0.0
    return float(counter.get(key, 0)) / float(total)


def _build_claim_attribution_metrics(report: dict) -> dict[str, object]:
    attributions = [
        item
        for item in (report.get("claim_attributions") or [])
        if isinstance(item, dict) and str(item.get("claim_source") or "") != "evidence_gap"
    ]
    claim_total = len(attributions)
    support_status_counter = Counter(str(item.get("support_status") or "unknown") for item in attributions)
    support_type_counter = Counter(str(item.get("support_type") or "unknown") for item in attributions)

    cited_claims = [item for item in attributions if item.get("support_ids")]
    grounded_product_claims = [
        item
        for item in cited_claims
        if str(item.get("support_status") or "") in {"supported", "partial"}
        and str(item.get("support_type") or "") in {"product_text", "image", "mixed"}
    ]
    route_mode_counter: Counter[str] = Counter()
    route_claim_count = 0
    for item in attributions:
        routes = {
            str(route)
            for route in (item.get("route_sources") or [])
            if str(route) in {"text", "image"}
        }
        if not routes:
            continue
        route_claim_count += 1
        if routes == {"text"}:
            route_mode_counter["text"] += 1
        elif routes == {"image"}:
            route_mode_counter["image"] += 1
        else:
            route_mode_counter["mixed"] += 1

    return {
        "claim_count": claim_total,
        "supported_claim_count": int(support_status_counter.get("supported", 0)),
        "partial_claim_count": int(support_status_counter.get("partial", 0)),
        "unsupported_claim_count": int(support_status_counter.get("unsupported", 0)),
        "contradicted_claim_count": int(support_status_counter.get("contradicted", 0)),
        "claim_support_rate": _counter_rate(support_status_counter, "supported", claim_total),
        "claim_grounded_rate": (
            float(support_status_counter.get("supported", 0) + support_status_counter.get("partial", 0)) / float(claim_total)
            if claim_total > 0
            else 0.0
        ),
        "citation_precision": (len(grounded_product_claims) / len(cited_claims)) if cited_claims else 0.0,
        "citation_contradiction_rate": _counter_rate(support_status_counter, "contradicted", claim_total),
        "modality_hit_rate": route_claim_count / claim_total if claim_total else 0.0,
        "route_contribution": {
            "text": _counter_rate(route_mode_counter, "text", route_claim_count),
            "image": _counter_rate(route_mode_counter, "image", route_claim_count),
            "mixed": _counter_rate(route_mode_counter, "mixed", route_claim_count),
        },
        "support_status_counts": dict(support_status_counter),
        "support_type_counts": dict(support_type_counter),
        "route_contribution_counts": dict(route_mode_counter),
    }


def _evidence_identifier(item: dict) -> str | None:
    for key in ("region_id", "text_block_id", "image_id", "evidence_id"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _first_relevant_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> int | None:
    for index, evidence_id in enumerate(retrieved_ids, start=1):
        if evidence_id in relevant_ids:
            return index
    return None


def _recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    hits = sum(1 for evidence_id in retrieved_ids[:k] if evidence_id in relevant_ids)
    return hits / len(relevant_ids)


def _dcg_at_k(retrieved_ids: list[str], graded_relevance: dict[str, float], k: int) -> float:
    score = 0.0
    for index, evidence_id in enumerate(retrieved_ids[:k], start=1):
        gain = float(graded_relevance.get(evidence_id, 0.0))
        if gain <= 0.0:
            continue
        score += gain / (1.0 if index == 1 else _log2(index + 1))
    return score


def _ideal_dcg_at_k(graded_relevance: dict[str, float], k: int) -> float:
    ordered_gains = sorted((float(value) for value in graded_relevance.values() if float(value) > 0.0), reverse=True)
    score = 0.0
    for index, gain in enumerate(ordered_gains[:k], start=1):
        score += gain / (1.0 if index == 1 else _log2(index + 1))
    return score


def _log2(value: int) -> float:
    from math import log2

    return log2(value)


@dataclass(frozen=True)
class EvaluationInputBundle:
    manifest_path: Path
    manifest_payload: dict
    analysis_payload: dict | None
    feedback_payload: dict | None
    replay_payload: dict | None


class ManifestEvaluationService:
    def _extract_retrieval_labels(self, bundle: EvaluationInputBundle) -> dict[str, dict[str, object]]:
        manifest_labels = ((bundle.manifest_payload.get("evaluation_labels") or {}).get("retrieval_relevance") or [])
        analysis_labels = (bundle.analysis_payload or {}).get("retrieval_labels") or []
        raw_labels = manifest_labels or analysis_labels
        labels_by_key: dict[str, dict[str, object]] = {}

        for item in raw_labels:
            if not isinstance(item, dict):
                continue
            key = str(item.get("retrieval_id") or item.get("question_id") or item.get("source_question_id") or "")
            if not key:
                continue
            relevant_evidence_ids = [
                str(evidence_id)
                for evidence_id in (item.get("relevant_evidence_ids") or [])
                if isinstance(evidence_id, str) and evidence_id
            ]
            graded_relevance_payload = item.get("graded_relevance") or item.get("relevance_by_evidence_id") or {}
            graded_relevance: dict[str, float] = {}
            if isinstance(graded_relevance_payload, dict):
                for evidence_id, relevance in graded_relevance_payload.items():
                    if not isinstance(evidence_id, str) or not evidence_id:
                        continue
                    graded_relevance[evidence_id] = float(relevance)
            if not graded_relevance:
                graded_relevance = {evidence_id: 1.0 for evidence_id in relevant_evidence_ids}
            elif relevant_evidence_ids:
                for evidence_id in relevant_evidence_ids:
                    graded_relevance.setdefault(evidence_id, 1.0)
            else:
                relevant_evidence_ids = [evidence_id for evidence_id, relevance in graded_relevance.items() if relevance > 0.0]

            labels_by_key[key] = {
                "relevant_evidence_ids": relevant_evidence_ids,
                "graded_relevance": graded_relevance,
            }
        return labels_by_key

    def _build_formal_retrieval_metrics(self, retrievals: list[dict], labels_by_key: dict[str, dict[str, object]]) -> dict[str, object]:
        if not retrievals:
            return {
                "judged_query_count": 0,
                "label_coverage_rate": 0.0,
                "recall_at_1": 0.0,
                "recall_at_3": 0.0,
                "recall_at_5": 0.0,
                "mrr": 0.0,
                "ndcg_at_3": 0.0,
                "ndcg_at_5": 0.0,
            }

        recall_at_1: list[float] = []
        recall_at_3: list[float] = []
        recall_at_5: list[float] = []
        reciprocal_ranks: list[float] = []
        ndcg_at_3: list[float] = []
        ndcg_at_5: list[float] = []
        judged_query_count = 0

        for retrieval in retrievals:
            if not isinstance(retrieval, dict):
                continue
            key = str(retrieval.get("retrieval_id") or retrieval.get("source_question_id") or "")
            label = labels_by_key.get(key)
            if label is None:
                continue
            relevant_ids = {
                str(evidence_id)
                for evidence_id in (label.get("relevant_evidence_ids") or [])
                if isinstance(evidence_id, str) and evidence_id
            }
            graded_relevance = {
                str(evidence_id): float(relevance)
                for evidence_id, relevance in (label.get("graded_relevance") or {}).items()
                if isinstance(evidence_id, str) and evidence_id
            }
            if not relevant_ids and not graded_relevance:
                continue
            if not graded_relevance:
                graded_relevance = {evidence_id: 1.0 for evidence_id in relevant_ids}
            if not relevant_ids:
                relevant_ids = {evidence_id for evidence_id, relevance in graded_relevance.items() if relevance > 0.0}

            retrieved_ids = [
                evidence_id
                for evidence_id in (_evidence_identifier(item) for item in (retrieval.get("retrieved") or []))
                if evidence_id is not None
            ]
            judged_query_count += 1
            recall_at_1.append(_recall_at_k(retrieved_ids, relevant_ids, 1))
            recall_at_3.append(_recall_at_k(retrieved_ids, relevant_ids, 3))
            recall_at_5.append(_recall_at_k(retrieved_ids, relevant_ids, 5))

            first_rank = _first_relevant_rank(retrieved_ids, relevant_ids)
            reciprocal_ranks.append(0.0 if first_rank is None else 1.0 / first_rank)

            ideal_at_3 = _ideal_dcg_at_k(graded_relevance, 3)
            ideal_at_5 = _ideal_dcg_at_k(graded_relevance, 5)
            ndcg_at_3.append(0.0 if ideal_at_3 <= 0.0 else _dcg_at_k(retrieved_ids, graded_relevance, 3) / ideal_at_3)
            ndcg_at_5.append(0.0 if ideal_at_5 <= 0.0 else _dcg_at_k(retrieved_ids, graded_relevance, 5) / ideal_at_5)

        return {
            "judged_query_count": judged_query_count,
            "label_coverage_rate": judged_query_count / len(retrievals) if retrievals else 0.0,
            "recall_at_1": _safe_mean(recall_at_1),
            "recall_at_3": _safe_mean(recall_at_3),
            "recall_at_5": _safe_mean(recall_at_5),
            "mrr": _safe_mean(reciprocal_ranks),
            "ndcg_at_3": _safe_mean(ndcg_at_3),
            "ndcg_at_5": _safe_mean(ndcg_at_5),
        }

    def discover_manifest_paths(self, manifest_root: Path) -> list[Path]:
        if manifest_root.is_file():
            return [manifest_root]
        if not manifest_root.exists():
            return []
        return sorted(path for path in manifest_root.rglob("*_run_manifest.json") if path.is_file())

    def load_bundle(self, manifest_path: Path) -> EvaluationInputBundle:
        manifest_payload = _load_json(manifest_path)
        artifact_bundle = manifest_payload.get("artifact_bundle") or {}

        analysis_path = artifact_bundle.get("analysis_path") or manifest_payload.get("analysis", {}).get("artifact_path")
        feedback_path = artifact_bundle.get("feedback_path")
        replay_path = artifact_bundle.get("replay_path")

        analysis_payload = _load_json(Path(analysis_path)) if analysis_path and Path(analysis_path).exists() else None
        feedback_payload = _load_json(Path(feedback_path)) if feedback_path and Path(feedback_path).exists() else None
        replay_payload = _load_json(Path(replay_path)) if replay_path and Path(replay_path).exists() else None

        return EvaluationInputBundle(
            manifest_path=manifest_path,
            manifest_payload=manifest_payload,
            analysis_payload=analysis_payload,
            feedback_payload=feedback_payload,
            replay_payload=replay_payload,
        )

    def evaluate_bundle(self, bundle: EvaluationInputBundle) -> dict[str, object]:
        manifest = bundle.manifest_payload
        analysis = bundle.analysis_payload or {}
        extraction = analysis.get("extraction") or {}
        preprocessed_reviews = extraction.get("preprocessed_reviews") or []
        aspects = extraction.get("aspects") or []
        questions = analysis.get("questions") or []
        retrievals = analysis.get("retrievals") or []
        retrieval_quality = analysis.get("retrieval_quality") or []
        report = analysis.get("report") or {}
        replay_summary = analysis.get("replay_summary") or {}

        informative_reviews = [item for item in preprocessed_reviews if item.get("is_informative")]
        aspect_confidences = [float(item.get("confidence", 0.0)) for item in aspects]
        question_confidences = [float(item.get("confidence", 0.0)) for item in questions]
        retrieval_lengths = [len(item.get("retrieved") or []) for item in retrievals]
        evidence_coverage = [float(item.get("evidence_coverage", 0.0)) for item in retrieval_quality]
        score_drift = [float(item.get("score_drift", 0.0)) for item in retrieval_quality]
        conflict_risk = [float(item.get("conflict_risk", 0.0)) for item in retrieval_quality]
        evaluator_items = [
            item
            for item in retrieval_quality
            if isinstance(item, dict)
            and any(
                key in item
                for key in ("retrieval_quality_label", "failure_reason", "corrective_action")
            )
        ]
        evaluator_query_count = len(evaluator_items)
        quality_label_counter = Counter(
            str(item.get("retrieval_quality_label") or "unknown") for item in evaluator_items
        )
        failure_reason_counter = Counter(
            str(item.get("failure_reason") or "unknown") for item in evaluator_items
        )
        corrective_action_counter = Counter(
            str(item.get("corrective_action") or "unknown") for item in evaluator_items
        )
        retrieval_labels = self._extract_retrieval_labels(bundle)
        formal_retrieval_metrics = self._build_formal_retrieval_metrics(retrievals, retrieval_labels)

        insights = []
        for key in ("strengths", "weaknesses", "controversies", "suggestions"):
            insights.extend(report.get(key) or [])

        supported_items = [item for item in insights if _supporting_evidence_count(item) > 0]
        final_confidences = [
            float((item.get("confidence_breakdown") or {}).get("final_confidence", item.get("confidence", 0.0)))
            for item in insights
        ]
        claim_metrics = _build_claim_attribution_metrics(report)

        feedback_slots = (bundle.feedback_payload or {}).get("slots") or []
        feedback_status_counter = Counter(str(item.get("status") or "pending_review") for item in feedback_slots)
        feedback_type_counter = Counter(str(item.get("item_type") or "unknown") for item in feedback_slots)

        warnings = list(manifest.get("analysis", {}).get("warnings") or [])
        if bundle.analysis_payload is None:
            warnings.append("missing_analysis_artifact")
        if bundle.feedback_payload is None:
            warnings.append("missing_feedback_sidecar")
        if bundle.replay_payload is None:
            warnings.append("missing_replay_sidecar")

        return {
            "manifest_path": str(bundle.manifest_path),
            "category": manifest.get("category"),
            "product_id": manifest.get("product_id"),
            "analysis_mode": manifest.get("analysis", {}).get("analysis_mode"),
            "retrieval_backend": (manifest.get("index_result") or {}).get("backend"),
            "native_multimodal_enabled": bool((manifest.get("retrieval_runtime") or {}).get("native_multimodal_enabled")),
            "prompt_variant": manifest.get("prompt_variant"),
            "review_sampling_profile": (manifest.get("review_sampling") or {}).get("profile_name"),
            "warnings": warnings,
            "extraction_metrics": {
                "requested_reviews": int((manifest.get("review_sampling") or {}).get("requested_reviews") or 0),
                "preprocessed_review_count": len(preprocessed_reviews),
                "informative_review_count": len(informative_reviews),
                "aspect_count": len(aspects),
                "avg_aspects_per_informative_review": (
                    len(aspects) / len(informative_reviews) if informative_reviews else 0.0
                ),
                "avg_extract_confidence": _safe_mean(aspect_confidences),
                "skipped_review_count": len(extraction.get("skipped_review_ids") or []),
            },
            "question_metrics": {
                "question_count": len(questions),
                "avg_question_confidence": _safe_mean(question_confidences),
                "avg_questions_per_aspect": len(questions) / len(aspects) if aspects else 0.0,
            },
            "retrieval_metrics": {
                "retrieval_record_count": len(retrievals),
                "judged_query_count": int(formal_retrieval_metrics["judged_query_count"]),
                "label_coverage_rate": float(formal_retrieval_metrics["label_coverage_rate"]),
                "evaluator_query_count": evaluator_query_count,
                "evaluator_coverage_rate": evaluator_query_count / len(retrieval_quality) if retrieval_quality else 0.0,
                "avg_candidates_per_query": _safe_mean([float(item) for item in retrieval_lengths]),
                "avg_evidence_coverage": _safe_mean(evidence_coverage),
                "avg_score_drift": _safe_mean(score_drift),
                "avg_conflict_risk": _safe_mean(conflict_risk),
                "text_coverage_rate": _safe_mean([1.0 if item.get("text_coverage") else 0.0 for item in retrieval_quality]),
                "image_coverage_rate": _safe_mean([1.0 if item.get("image_coverage") else 0.0 for item in retrieval_quality]),
                "quality_label_counts": dict(quality_label_counter),
                "failure_reason_counts": dict(failure_reason_counter),
                "corrective_action_counts": dict(corrective_action_counter),
                "good_query_rate": _counter_rate(quality_label_counter, "good", evaluator_query_count),
                "mixed_query_rate": _counter_rate(quality_label_counter, "mixed", evaluator_query_count),
                "bad_query_rate": _counter_rate(quality_label_counter, "bad", evaluator_query_count),
                "recall_at_1": float(formal_retrieval_metrics["recall_at_1"]),
                "recall_at_3": float(formal_retrieval_metrics["recall_at_3"]),
                "recall_at_5": float(formal_retrieval_metrics["recall_at_5"]),
                "mrr": float(formal_retrieval_metrics["mrr"]),
                "ndcg_at_3": float(formal_retrieval_metrics["ndcg_at_3"]),
                "ndcg_at_5": float(formal_retrieval_metrics["ndcg_at_5"]),
            },
            "generation_metrics": {
                "strength_count": len(report.get("strengths") or []),
                "weakness_count": len(report.get("weaknesses") or []),
                "controversy_count": len(report.get("controversies") or []),
                "suggestion_count": len(report.get("suggestions") or []),
                "citation_coverage_rate": len(supported_items) / len(insights) if insights else 0.0,
                "claim_count": int(claim_metrics["claim_count"]),
                "supported_claim_count": int(claim_metrics["supported_claim_count"]),
                "partial_claim_count": int(claim_metrics["partial_claim_count"]),
                "unsupported_claim_count": int(claim_metrics["unsupported_claim_count"]),
                "contradicted_claim_count": int(claim_metrics["contradicted_claim_count"]),
                "claim_support_rate": float(claim_metrics["claim_support_rate"]),
                "claim_grounded_rate": float(claim_metrics["claim_grounded_rate"]),
                "citation_precision": float(claim_metrics["citation_precision"]),
                "citation_contradiction_rate": float(claim_metrics["citation_contradiction_rate"]),
                "modality_hit_rate": float(claim_metrics["modality_hit_rate"]),
                "route_contribution": dict(claim_metrics["route_contribution"]),
                "support_status_counts": dict(claim_metrics["support_status_counts"]),
                "support_type_counts": dict(claim_metrics["support_type_counts"]),
                "route_contribution_counts": dict(claim_metrics["route_contribution_counts"]),
                "avg_final_confidence": _safe_mean(final_confidences),
            },
            "feedback_metrics": {
                "slot_count": len(feedback_slots),
                "status_counts": dict(feedback_status_counter),
                "item_type_counts": dict(feedback_type_counter),
                "reviewed_slot_count": sum(count for status, count in feedback_status_counter.items() if status != "pending_review"),
            },
            "replay_metrics": {
                "applied": bool(replay_summary.get("applied")),
                "persistent_issue_count": len(replay_summary.get("persistent_issue_labels") or []),
                "resolved_issue_count": len(replay_summary.get("resolved_issue_labels") or []),
                "new_issue_count": len(replay_summary.get("new_issue_labels") or []),
            },
        }

    def build_report(self, manifest_root: Path) -> dict[str, object]:
        manifest_paths = self.discover_manifest_paths(manifest_root)
        runs = [self.evaluate_bundle(self.load_bundle(path)) for path in manifest_paths]

        analysis_mode_counter = Counter(str(run.get("analysis_mode") or "unknown") for run in runs)
        category_counter = Counter(str(run.get("category") or "unknown") for run in runs)
        profile_counter = Counter(str(run.get("review_sampling_profile") or "unknown") for run in runs)

        extraction_means = [run["extraction_metrics"] for run in runs]
        question_means = [run["question_metrics"] for run in runs]
        retrieval_means = [run["retrieval_metrics"] for run in runs]
        generation_means = [run["generation_metrics"] for run in runs]
        retrieval_metric_weights = [float(item.get("judged_query_count", 0.0)) for item in retrieval_means]
        evaluator_metric_weights = [float(item.get("evaluator_query_count", 0.0)) for item in retrieval_means]
        quality_label_counter: Counter[str] = Counter()
        failure_reason_counter: Counter[str] = Counter()
        corrective_action_counter: Counter[str] = Counter()
        support_status_counter: Counter[str] = Counter()
        support_type_counter: Counter[str] = Counter()
        route_contribution_counter: Counter[str] = Counter()

        for item in retrieval_means:
            quality_label_counter.update(
                {
                    str(key): int(value)
                    for key, value in (item.get("quality_label_counts") or {}).items()
                }
            )
            failure_reason_counter.update(
                {
                    str(key): int(value)
                    for key, value in (item.get("failure_reason_counts") or {}).items()
                }
            )
            corrective_action_counter.update(
                {
                    str(key): int(value)
                    for key, value in (item.get("corrective_action_counts") or {}).items()
                }
            )
        for item in generation_means:
            support_status_counter.update(
                {
                    str(key): int(value)
                    for key, value in (item.get("support_status_counts") or {}).items()
                }
            )
            support_type_counter.update(
                {
                    str(key): int(value)
                    for key, value in (item.get("support_type_counts") or {}).items()
                }
            )
            route_contribution_counter.update(
                {
                    str(key): int(value)
                    for key, value in (item.get("route_contribution_counts") or {}).items()
                }
            )

        return {
            "manifest_root": str(manifest_root),
            "run_count": len(runs),
            "analysis_mode_counts": dict(analysis_mode_counter),
            "category_counts": dict(category_counter),
            "sampling_profile_counts": dict(profile_counter),
            "native_multimodal_rate": _safe_mean(
                [1.0 if run.get("native_multimodal_enabled") else 0.0 for run in runs]
            ),
            "aggregate_metrics": {
                "avg_aspects_per_informative_review": _safe_mean(
                    [float(item.get("avg_aspects_per_informative_review", 0.0)) for item in extraction_means]
                ),
                "avg_extract_confidence": _safe_mean(
                    [float(item.get("avg_extract_confidence", 0.0)) for item in extraction_means]
                ),
                "avg_question_confidence": _safe_mean(
                    [float(item.get("avg_question_confidence", 0.0)) for item in question_means]
                ),
                "avg_questions_per_aspect": _safe_mean(
                    [float(item.get("avg_questions_per_aspect", 0.0)) for item in question_means]
                ),
                "avg_candidates_per_query": _safe_mean(
                    [float(item.get("avg_candidates_per_query", 0.0)) for item in retrieval_means]
                ),
                "avg_label_coverage_rate": _safe_mean(
                    [float(item.get("label_coverage_rate", 0.0)) for item in retrieval_means]
                ),
                "avg_evaluator_coverage_rate": _safe_mean(
                    [float(item.get("evaluator_coverage_rate", 0.0)) for item in retrieval_means]
                ),
                "avg_evidence_coverage": _safe_mean(
                    [float(item.get("avg_evidence_coverage", 0.0)) for item in retrieval_means]
                ),
                "avg_conflict_risk": _safe_mean(
                    [float(item.get("avg_conflict_risk", 0.0)) for item in retrieval_means]
                ),
                "avg_good_query_rate": _safe_weighted_mean(
                    [float(item.get("good_query_rate", 0.0)) for item in retrieval_means],
                    evaluator_metric_weights,
                ),
                "avg_mixed_query_rate": _safe_weighted_mean(
                    [float(item.get("mixed_query_rate", 0.0)) for item in retrieval_means],
                    evaluator_metric_weights,
                ),
                "avg_bad_query_rate": _safe_weighted_mean(
                    [float(item.get("bad_query_rate", 0.0)) for item in retrieval_means],
                    evaluator_metric_weights,
                ),
                "avg_recall_at_1": _safe_weighted_mean(
                    [float(item.get("recall_at_1", 0.0)) for item in retrieval_means],
                    retrieval_metric_weights,
                ),
                "avg_recall_at_3": _safe_weighted_mean(
                    [float(item.get("recall_at_3", 0.0)) for item in retrieval_means],
                    retrieval_metric_weights,
                ),
                "avg_recall_at_5": _safe_weighted_mean(
                    [float(item.get("recall_at_5", 0.0)) for item in retrieval_means],
                    retrieval_metric_weights,
                ),
                "avg_mrr": _safe_weighted_mean(
                    [float(item.get("mrr", 0.0)) for item in retrieval_means],
                    retrieval_metric_weights,
                ),
                "avg_ndcg_at_3": _safe_weighted_mean(
                    [float(item.get("ndcg_at_3", 0.0)) for item in retrieval_means],
                    retrieval_metric_weights,
                ),
                "avg_ndcg_at_5": _safe_weighted_mean(
                    [float(item.get("ndcg_at_5", 0.0)) for item in retrieval_means],
                    retrieval_metric_weights,
                ),
                "avg_citation_coverage_rate": _safe_mean(
                    [float(item.get("citation_coverage_rate", 0.0)) for item in generation_means]
                ),
                "avg_claim_support_rate": _safe_mean(
                    [float(item.get("claim_support_rate", 0.0)) for item in generation_means]
                ),
                "avg_claim_grounded_rate": _safe_mean(
                    [float(item.get("claim_grounded_rate", 0.0)) for item in generation_means]
                ),
                "avg_citation_precision": _safe_mean(
                    [float(item.get("citation_precision", 0.0)) for item in generation_means]
                ),
                "avg_citation_contradiction_rate": _safe_mean(
                    [float(item.get("citation_contradiction_rate", 0.0)) for item in generation_means]
                ),
                "avg_modality_hit_rate": _safe_mean(
                    [float(item.get("modality_hit_rate", 0.0)) for item in generation_means]
                ),
                "avg_text_route_contribution": _safe_mean(
                    [float((item.get("route_contribution") or {}).get("text", 0.0)) for item in generation_means]
                ),
                "avg_image_route_contribution": _safe_mean(
                    [float((item.get("route_contribution") or {}).get("image", 0.0)) for item in generation_means]
                ),
                "avg_mixed_route_contribution": _safe_mean(
                    [float((item.get("route_contribution") or {}).get("mixed", 0.0)) for item in generation_means]
                ),
                "avg_final_confidence": _safe_mean(
                    [float(item.get("avg_final_confidence", 0.0)) for item in generation_means]
                ),
            },
            "retrieval_evaluator_summary": {
                "evaluator_query_count": int(sum(evaluator_metric_weights)),
                "quality_label_counts": dict(quality_label_counter),
                "failure_reason_counts": dict(failure_reason_counter),
                "corrective_action_counts": dict(corrective_action_counter),
            },
            "claim_attribution_summary": {
                "support_status_counts": dict(support_status_counter),
                "support_type_counts": dict(support_type_counter),
                "route_contribution_counts": dict(route_contribution_counter),
            },
            "runs": runs,
        }