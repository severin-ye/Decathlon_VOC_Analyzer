#!/usr/bin/env python3
"""
Experiment matrix runner for ablation and control experiments.

Usage:
    python -m decathlon_voc_analyzer.workflows.experiment_runner \
        --categories backpack shoes sunglasses \
        --products-per-category 5 \
        --max-reviews 25 \
        --output-dir ./experiment_results
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import orjson

# Add project root to path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "05_src"))

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.analysis import (
    ExperimentConfig,
    ProductAnalysisRequest,
)
from decathlon_voc_analyzer.stage4_generation.analysis_service import ProductAnalysisService


def discover_products(category: str, dataset_root: Path) -> list[str]:
    category_dir = dataset_root / category
    if not category_dir.exists():
        return []
    return sorted([d.name for d in category_dir.iterdir() if d.is_dir()])


EXPERIMENT_CONDITIONS: list[tuple[str, ExperimentConfig]] = [
    ("full_system", ExperimentConfig()),
    ("ablation_no_qp", ExperimentConfig(ablation_no_question_planning=True)),
    ("ablation_no_image", ExperimentConfig(ablation_no_image_route=True)),
    ("ablation_no_rerank", ExperimentConfig(ablation_no_reranking=True)),
    ("ablation_no_attribution", ExperimentConfig(ablation_no_claim_attribution=True)),
    ("control_lewis2020", ExperimentConfig(control_method="lewis2020")),
    ("control_jarvis", ExperimentConfig(control_method="jarvis")),
    ("control_vericite", ExperimentConfig(control_method="vericite")),
]


def run_experiment_matrix(
    categories: list[str],
    products_per_category: int,
    max_reviews: int,
    output_dir: Path,
    seed: int = 42,
) -> None:
    settings = get_settings()
    dataset_root = settings.dataset_root
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine product selection
    selected_products: dict[str, list[str]] = {}
    for category in categories:
        all_products = discover_products(category, dataset_root)
        if not all_products:
            print(f"Warning: no products found for category {category}")
            continue
        rng = random.Random(seed)
        shuffled = all_products.copy()
        rng.shuffle(shuffled)
        selected = shuffled[:products_per_category]
        selected_products[category] = selected
        print(f"Category {category}: selected {len(selected)} / {len(all_products)} products")

    service = ProductAnalysisService()
    results_log: list[dict] = []

    for category, products in selected_products.items():
        for product_id in products:
            for condition_name, exp_config in EXPERIMENT_CONDITIONS:
                run_id = f"{category}__{product_id}__{condition_name}"
                print(f"\n[RUN] {run_id}")
                try:
                    request = ProductAnalysisRequest(
                        product_id=product_id,
                        category_slug=category,
                        max_reviews=max_reviews,
                        use_llm=True,
                        persist_artifact=True,
                        use_replay=False,
                        reuse_extraction_artifact=False,
                        reuse_analysis_checkpoint=False,
                        top_k_per_route=2,
                        questions_per_aspect=2,
                        experiment_config=exp_config,
                    )
                    response = service.analyze(request)
                    result_summary = {
                        "run_id": run_id,
                        "category": category,
                        "product_id": product_id,
                        "condition": condition_name,
                        "status": "success",
                        "analysis_mode": response.analysis_mode,
                        "aspect_count": len(response.extraction.aspects),
                        "question_count": len(response.questions),
                        "retrieval_count": len(response.retrievals),
                        "claim_count": len(response.report.claim_attributions),
                        "supported_claims": sum(
                            1 for c in response.report.claim_attributions if c.support_status == "supported"
                        ),
                        "artifact_path": response.artifact_path,
                    }
                except Exception as exc:
                    print(f"[ERROR] {run_id}: {exc}")
                    result_summary = {
                        "run_id": run_id,
                        "category": category,
                        "product_id": product_id,
                        "condition": condition_name,
                        "status": "error",
                        "error": str(exc),
                    }
                results_log.append(result_summary)
                # Flush log after each run
                log_path = output_dir / "experiment_log.jsonl"
                with log_path.open("ab") as f:
                    f.write(orjson.dumps(result_summary, option=orjson.OPT_APPEND_NEWLINE))

    # Write summary
    summary_path = output_dir / "experiment_summary.json"
    summary_path.write_bytes(
        orjson.dumps(
            {
                "categories": categories,
                "products_per_category": products_per_category,
                "max_reviews": max_reviews,
                "conditions": [name for name, _ in EXPERIMENT_CONDITIONS],
                "total_runs": len(results_log),
                "successful_runs": sum(1 for r in results_log if r["status"] == "success"),
                "failed_runs": sum(1 for r in results_log if r["status"] == "error"),
                "runs": results_log,
            },
            option=orjson.OPT_INDENT_2,
        )
    )
    print(f"\nDone. Summary written to {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run experiment matrix")
    parser.add_argument("--categories", nargs="+", default=["backpack", "shoes", "sunglasses"])
    parser.add_argument("--products-per-category", type=int, default=5)
    parser.add_argument("--max-reviews", type=int, default=25)
    parser.add_argument("--output-dir", type=str, default=str(ROOT / "experiment_results"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    run_experiment_matrix(
        categories=args.categories,
        products_per_category=args.products_per_category,
        max_reviews=args.max_reviews,
        output_dir=Path(args.output_dir),
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
