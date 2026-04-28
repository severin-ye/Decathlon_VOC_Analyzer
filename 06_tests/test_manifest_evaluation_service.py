from pathlib import Path

import orjson
import pytest

from decathlon_voc_analyzer.evaluation import ManifestEvaluationService


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))


def test_manifest_evaluation_service_aggregates_run_metrics(tmp_path: Path) -> None:
    manifests_dir = tmp_path / "manifests" / "backpack"
    artifacts_dir = tmp_path / "artifacts"

    analysis_path = artifacts_dir / "backpack_010_analysis.json"
    feedback_path = artifacts_dir / "backpack_010_feedback_slots.json"
    replay_path = artifacts_dir / "backpack_010_replay.json"
    manifest_path = manifests_dir / "backpack_010_run_manifest.json"

    _write_json(
        analysis_path,
        {
            "extraction": {
                "preprocessed_reviews": [
                    {"review_id": "r1", "is_informative": True},
                    {"review_id": "r2", "is_informative": False},
                ],
                "aspects": [
                    {"aspect_id": "a1", "confidence": 0.8},
                    {"aspect_id": "a2", "confidence": 0.6},
                ],
                "skipped_review_ids": ["r2"],
            },
            "questions": [
                {"question_id": "q1", "confidence": 0.7},
                {"question_id": "q2", "confidence": 0.5},
            ],
            "retrievals": [
                {
                    "retrieval_id": "t1",
                    "retrieved": [
                        {"text_block_id": "tb_rel"},
                        {"image_id": "img_other"},
                    ],
                },
                {
                    "retrieval_id": "t2",
                    "retrieved": [
                        {"text_block_id": "tb_other"},
                        {"image_id": "img_rel"},
                    ],
                },
            ],
            "retrieval_quality": [
                {
                    "retrieval_id": "t1",
                    "source_aspect": "portability_size",
                    "evidence_coverage": 0.8,
                    "score_drift": 0.2,
                    "conflict_risk": 0.1,
                    "text_coverage": True,
                    "image_coverage": False,
                    "retrieval_quality_label": "good",
                    "failure_reason": "none",
                    "corrective_action": "keep_current",
                },
                {
                    "retrieval_id": "t2",
                    "source_aspect": "value_price",
                    "evidence_coverage": 0.4,
                    "score_drift": 0.1,
                    "conflict_risk": 0.3,
                    "text_coverage": True,
                    "image_coverage": True,
                    "retrieval_quality_label": "bad",
                    "failure_reason": "low_precision",
                    "corrective_action": "filter_noise",
                },
            ],
            "report": {
                "strengths": [
                    {
                        "label": "value_price",
                        "confidence": 0.6,
                        "supporting_evidence": {"review_ids": ["r1"], "product_text_block_ids": [], "product_image_ids": []},
                        "confidence_breakdown": {"final_confidence": 0.75},
                    }
                ],
                "weaknesses": [
                    {
                        "label": "portability_size",
                        "confidence": 0.7,
                        "supporting_evidence": {"review_ids": [], "product_text_block_ids": [], "product_image_ids": []},
                        "confidence_breakdown": {"final_confidence": 0.55},
                    }
                ],
                "controversies": [],
                "suggestions": [
                    {
                        "suggestion": "clarify sizing",
                        "confidence": 0.4,
                        "supporting_evidence": {"review_ids": ["r1"], "product_text_block_ids": ["t1"], "product_image_ids": []},
                        "confidence_breakdown": {"final_confidence": 0.65},
                    }
                ],
                "claim_attributions": [
                    {
                        "claim_id": "strength:value_price:0",
                        "claim_source": "strength",
                        "support_status": "supported",
                        "support_type": "product_text",
                        "support_ids": ["t1"],
                        "route_sources": ["text"],
                    },
                    {
                        "claim_id": "weakness:portability_size:0",
                        "claim_source": "weakness",
                        "support_status": "partial",
                        "support_type": "image",
                        "support_ids": ["img_rel"],
                        "route_sources": ["image"],
                    },
                    {
                        "claim_id": "suggestion:clarify_sizing:0",
                        "claim_source": "suggestion",
                        "support_status": "contradicted",
                        "support_type": "review",
                        "support_ids": ["r1"],
                        "route_sources": [],
                    },
                ],
            },
            "replay_summary": {
                "applied": True,
                "persistent_issue_labels": ["portability_size"],
                "resolved_issue_labels": [],
                "new_issue_labels": ["value_price"],
            },
        },
    )
    _write_json(
        feedback_path,
        {
            "slots": [
                {"slot_id": "s1", "item_type": "insight", "status": "pending_review"},
                {"slot_id": "s2", "item_type": "suggestion", "status": "accepted"},
            ]
        },
    )
    _write_json(replay_path, {"product_id": "backpack_010"})
    _write_json(
        manifest_path,
        {
            "category": "backpack",
            "product_id": "backpack_010",
            "prompt_variant": "main",
            "review_sampling": {"profile_name": "problem_first", "requested_reviews": 2},
            "index_result": {"backend": "qdrant"},
            "retrieval_runtime": {"native_multimodal_enabled": True},
            "analysis": {"analysis_mode": "llm", "warnings": []},
            "artifact_bundle": {
                "analysis_path": str(analysis_path),
                "feedback_path": str(feedback_path),
                "replay_path": str(replay_path),
            },
            "evaluation_labels": {
                "retrieval_relevance": [
                    {
                        "retrieval_id": "t1",
                        "relevant_evidence_ids": ["tb_rel"],
                        "graded_relevance": {"tb_rel": 1.0},
                    },
                    {
                        "retrieval_id": "t2",
                        "relevant_evidence_ids": ["img_rel"],
                        "graded_relevance": {"img_rel": 1.0},
                    },
                ]
            },
        },
    )

    report = ManifestEvaluationService().build_report(manifests_dir.parent)

    assert report["run_count"] == 1
    assert report["analysis_mode_counts"]["llm"] == 1
    assert report["native_multimodal_rate"] == 1.0

    run = report["runs"][0]
    assert run["extraction_metrics"]["informative_review_count"] == 1
    assert run["question_metrics"]["question_count"] == 2
    assert run["retrieval_metrics"]["avg_candidates_per_query"] == 2.0
    assert run["retrieval_metrics"]["judged_query_count"] == 2
    assert run["retrieval_metrics"]["evaluator_query_count"] == 2
    assert run["retrieval_metrics"]["quality_label_counts"] == {"good": 1, "bad": 1}
    assert run["retrieval_metrics"]["failure_reason_counts"] == {"none": 1, "low_precision": 1}
    assert run["retrieval_metrics"]["corrective_action_counts"] == {"keep_current": 1, "filter_noise": 1}
    assert run["retrieval_metrics"]["good_query_rate"] == 0.5
    assert run["retrieval_metrics"]["bad_query_rate"] == 0.5
    assert run["retrieval_metrics"]["recall_at_1"] == 0.5
    assert run["retrieval_metrics"]["recall_at_3"] == 1.0
    assert run["retrieval_metrics"]["mrr"] == 0.75
    assert run["retrieval_metrics"]["ndcg_at_3"] == pytest.approx(0.8154648768)
    assert run["generation_metrics"]["citation_coverage_rate"] == 2 / 3
    assert run["generation_metrics"]["claim_support_rate"] == 1 / 3
    assert run["generation_metrics"]["claim_grounded_rate"] == 2 / 3
    assert run["generation_metrics"]["citation_precision"] == 2 / 3
    assert run["generation_metrics"]["citation_contradiction_rate"] == 1 / 3
    assert run["generation_metrics"]["modality_hit_rate"] == 2 / 3
    assert run["generation_metrics"]["route_contribution"] == {"text": 0.5, "image": 0.5, "mixed": 0.0}
    assert run["feedback_metrics"]["reviewed_slot_count"] == 1
    assert run["replay_metrics"]["persistent_issue_count"] == 1
    assert report["aggregate_metrics"]["avg_good_query_rate"] == 0.5
    assert report["aggregate_metrics"]["avg_bad_query_rate"] == 0.5
    assert report["aggregate_metrics"]["avg_recall_at_1"] == 0.5
    assert report["aggregate_metrics"]["avg_mrr"] == 0.75
    assert report["aggregate_metrics"]["avg_claim_support_rate"] == 1 / 3
    assert report["aggregate_metrics"]["avg_claim_grounded_rate"] == 2 / 3
    assert report["aggregate_metrics"]["avg_citation_precision"] == 2 / 3
    assert report["aggregate_metrics"]["avg_citation_contradiction_rate"] == 1 / 3
    assert report["aggregate_metrics"]["avg_modality_hit_rate"] == 2 / 3
    assert report["retrieval_evaluator_summary"]["evaluator_query_count"] == 2
    assert report["retrieval_evaluator_summary"]["quality_label_counts"] == {"good": 1, "bad": 1}
    assert report["retrieval_evaluator_summary"]["failure_reason_counts"] == {"none": 1, "low_precision": 1}
    assert report["retrieval_evaluator_summary"]["corrective_action_counts"] == {"keep_current": 1, "filter_noise": 1}
    assert report["claim_attribution_summary"]["support_status_counts"] == {"supported": 1, "partial": 1, "contradicted": 1}
    assert report["claim_attribution_summary"]["route_contribution_counts"] == {"text": 1, "image": 1}


def test_manifest_evaluation_service_marks_missing_sidecars(tmp_path: Path) -> None:
    manifests_dir = tmp_path / "manifests"
    analysis_path = tmp_path / "analysis.json"
    manifest_path = manifests_dir / "sample_run_manifest.json"

    _write_json(
        analysis_path,
        {
            "extraction": {"preprocessed_reviews": [], "aspects": [], "skipped_review_ids": []},
            "questions": [],
            "retrievals": [],
            "retrieval_quality": [],
            "report": {"strengths": [], "weaknesses": [], "controversies": [], "suggestions": []},
        },
    )
    _write_json(
        manifest_path,
        {
            "category": "backpack",
            "product_id": "backpack_010",
            "prompt_variant": "main",
            "review_sampling": {"profile_name": "problem_first", "requested_reviews": 0},
            "index_result": {"backend": "local"},
            "retrieval_runtime": {"native_multimodal_enabled": False},
            "analysis": {"analysis_mode": "heuristic", "warnings": []},
            "artifact_bundle": {"analysis_path": str(analysis_path), "feedback_path": None, "replay_path": None},
        },
    )

    run = ManifestEvaluationService().build_report(manifests_dir)["runs"][0]

    assert "missing_feedback_sidecar" in run["warnings"]
    assert "missing_replay_sidecar" in run["warnings"]
    assert run["retrieval_metrics"]["judged_query_count"] == 0
    assert run["retrieval_metrics"]["evaluator_query_count"] == 0
    assert run["retrieval_metrics"]["mrr"] == 0.0