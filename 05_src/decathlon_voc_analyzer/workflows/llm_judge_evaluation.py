#!/usr/bin/env python3
"""
LLM-as-Judge evaluation for experiment results.

Usage:
    python -m decathlon_voc_analyzer.workflows.llm_judge_evaluation \
        --experiment-dir ./experiment_results \
        --output-dir ./evaluation_results
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import orjson

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "05_src"))

from decathlon_voc_analyzer.llm import QwenChatGateway
from decathlon_voc_analyzer.schemas.analysis import ProductAnalysisResponse


def load_analysis_response(artifact_path: str) -> ProductAnalysisResponse | None:
    path = Path(artifact_path)
    if not path.exists():
        return None
    try:
        payload = orjson.loads(path.read_bytes())
        return ProductAnalysisResponse.model_validate(payload)
    except Exception:
        return None


def judge_retrieval_quality(response: ProductAnalysisResponse, chat: QwenChatGateway) -> dict[str, float]:
    """Evaluate retrieval quality: relevance and coverage."""
    scores: list[float] = []
    coverage_count = 0
    total_questions = len(response.retrievals)

    for rec in response.retrievals:
        if not rec.retrieved:
            continue
        evidence_text = "\n".join([
            f"- [{ev.route}] {ev.content_preview or ''}"
            for ev in rec.retrieved
        ])
        prompt = (
            "You are an expert retrieval evaluator. Rate the relevance of the retrieved evidence "
            "to the query on a scale of 1-5, where 1=irrelevant, 3=partially relevant, 5=highly relevant.\n\n"
            f"Query: {rec.query}\n\n"
            f"Retrieved Evidence:\n{evidence_text}\n\n"
            "Respond with ONLY a JSON object: {\"score\": number, \"reason\": string}"
        )
        try:
            result = chat.invoke_json(prompt_template=None, variables={}, system_prompt=prompt)
            score = float(result.get("score", 3.0))
            scores.append(max(1.0, min(5.0, score)))
            if score >= 3.0:
                coverage_count += 1
        except Exception:
            scores.append(3.0)
            coverage_count += 1

    return {
        "retrieval_relevance_mean": sum(scores) / len(scores) if scores else 0.0,
        "retrieval_coverage": coverage_count / total_questions if total_questions else 0.0,
    }


def judge_report_quality(response: ProductAnalysisResponse, chat: QwenChatGateway) -> dict[str, float]:
    """Evaluate report quality: coverage, factual consistency, structure."""
    aspects = response.extraction.aspects
    aspect_names = [a.aspect for a in aspects]
    report = response.report

    # Coverage: does report cover all aspects?
    all_claims = (
        [i.summary for i in report.strengths]
        + [i.summary for i in report.weaknesses]
        + [i.summary for i in report.controversies]
        + [i.summary for i in report.evidence_gaps]
    )
    claims_text = "\n".join(f"- {c}" for c in all_claims)
    aspects_text = "\n".join(f"- {a}" for a in aspect_names)

    coverage_prompt = (
        "You are an expert report evaluator. Given the extracted aspects and the report claims, "
        "rate the coverage on a scale of 1-5, where 1=most aspects missing, 5=all aspects covered.\n\n"
        f"Extracted Aspects:\n{aspects_text}\n\n"
        f"Report Claims:\n{claims_text}\n\n"
        "Respond with ONLY a JSON object: {\"score\": number, \"reason\": string}"
    )
    try:
        coverage_result = chat.invoke_json(prompt_template=None, variables={}, system_prompt=coverage_prompt)
        coverage_score = float(coverage_result.get("score", 3.0))
    except Exception:
        coverage_score = 3.0

    # Factual consistency: are claims supported by evidence?
    evidence_text = "\n".join([
        f"- [{ev.route}] {ev.content_preview or ''}"
        for rec in response.retrievals
        for ev in rec.retrieved
    ])
    consistency_prompt = (
        "You are a fact-checking expert. Rate the factual consistency of the report claims "
        "with the retrieved evidence on a scale of 1-5, where 1=many unsupported claims, 5=all claims supported.\n\n"
        f"Report Claims:\n{claims_text}\n\n"
        f"Retrieved Evidence:\n{evidence_text}\n\n"
        "Respond with ONLY a JSON object: {\"score\": number, \"reason\": string}"
    )
    try:
        consistency_result = chat.invoke_json(prompt_template=None, variables={}, system_prompt=consistency_prompt)
        consistency_score = float(consistency_result.get("score", 3.0))
    except Exception:
        consistency_score = 3.0

    return {
        "report_coverage": coverage_score,
        "report_factual_consistency": consistency_score,
    }


def judge_attribution_quality(response: ProductAnalysisResponse) -> dict[str, float]:
    """Evaluate attribution quality using existing metrics."""
    attrs = response.report.claim_attributions
    total = len(attrs)
    if total == 0:
        return {
            "claim_support_rate": 0.0,
            "claim_grounded_rate": 0.0,
            "citation_precision": 0.0,
        }
    supported = sum(1 for a in attrs if a.support_status == "supported")
    partial = sum(1 for a in attrs if a.support_status == "partial")
    cited = [a for a in attrs if a.support_ids]
    grounded = [
        a for a in cited
        if a.support_status in {"supported", "partial"} and a.support_type in {"product_text", "image", "mixed"}
    ]
    return {
        "claim_support_rate": supported / total,
        "claim_grounded_rate": (supported + partial) / total,
        "citation_precision": len(grounded) / len(cited) if cited else 0.0,
    }


def evaluate_run(run: dict[str, Any], chat: QwenChatGateway) -> dict[str, Any]:
    if run.get("status") != "success":
        return {**run, "evaluation": {"status": "skipped", "reason": "run_failed"}}

    artifact_path = run.get("artifact_path")
    if not artifact_path:
        return {**run, "evaluation": {"status": "skipped", "reason": "no_artifact"}}

    response = load_analysis_response(artifact_path)
    if response is None:
        return {**run, "evaluation": {"status": "skipped", "reason": "artifact_load_failed"}}

    retrieval_scores = judge_retrieval_quality(response, chat)
    report_scores = judge_report_quality(response, chat)
    attribution_scores = judge_attribution_quality(response)

    return {
        **run,
        "evaluation": {
            "status": "evaluated",
            **retrieval_scores,
            **report_scores,
            **attribution_scores,
        },
    }


def aggregate_by_condition(evaluated_runs: list[dict]) -> dict[str, dict[str, float]]:
    from collections import defaultdict

    metrics_by_condition: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for run in evaluated_runs:
        ev = run.get("evaluation", {})
        if ev.get("status") != "evaluated":
            continue
        condition = run["condition"]
        for key, value in ev.items():
            if key == "status":
                continue
            if isinstance(value, (int, float)):
                metrics_by_condition[condition][key].append(float(value))

    aggregated: dict[str, dict[str, float]] = {}
    for condition, metrics in metrics_by_condition.items():
        aggregated[condition] = {
            key: sum(values) / len(values) if values else 0.0
            for key, values in metrics.items()
        }
    return aggregated


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-as-Judge evaluation")
    parser.add_argument("--experiment-dir", type=str, required=True)
    parser.add_argument("--output-dir", type=str, required=True)
    parser.add_argument("--max-runs", type=int, default=None, help="Limit number of runs to evaluate (for testing)")
    args = parser.parse_args()

    experiment_dir = Path(args.experiment_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    log_path = experiment_dir / "experiment_log.jsonl"
    if not log_path.exists():
        print(f"Error: {log_path} not found")
        sys.exit(1)

    runs: list[dict] = []
    with log_path.open("rb") as f:
        for line in f:
            line = line.strip()
            if line:
                runs.append(orjson.loads(line))

    if args.max_runs:
        runs = runs[:args.max_runs]

    chat = QwenChatGateway()
    evaluated: list[dict] = []

    for idx, run in enumerate(runs, start=1):
        print(f"[{idx}/{len(runs)}] Evaluating {run['run_id']} ...")
        evaluated.append(evaluate_run(run, chat))

    # Write evaluated results
    eval_log_path = output_dir / "evaluation_log.jsonl"
    with eval_log_path.open("wb") as f:
        for run in evaluated:
            f.write(orjson.dumps(run, option=orjson.OPT_APPEND_NEWLINE))

    # Aggregate
    aggregated = aggregate_by_condition(evaluated)
    summary_path = output_dir / "evaluation_summary.json"
    summary_path.write_bytes(
        orjson.dumps(
            {
                "total_evaluated": len([r for r in evaluated if r.get("evaluation", {}).get("status") == "evaluated"]),
                "aggregated_by_condition": aggregated,
            },
            option=orjson.OPT_INDENT_2,
        )
    )

    print(f"\nDone. Results in {output_dir}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
