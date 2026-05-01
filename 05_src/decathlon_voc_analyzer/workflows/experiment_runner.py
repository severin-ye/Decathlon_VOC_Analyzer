#!/usr/bin/env python3
"""
Experiment matrix runner for ablation and control experiments.

Usage:
    python -m decathlon_voc_analyzer.workflows.experiment_runner \
        --categories backpack shoes sunglasses \
        --products-per-category 5 \
        --max-reviews 25 \
        --output-dir ./02_outputs/6_experiments/current
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import random
import sys
import time
from pathlib import Path

import orjson

# Add project root to path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "05_src"))
DEFAULT_EXPERIMENT_OUTPUT_DIR = ROOT / "02_outputs" / "6_experiments" / "current"

from decathlon_voc_analyzer.app.core.config import get_settings  # noqa: E402
from decathlon_voc_analyzer.runtime_progress import (  # noqa: E402
    WorkflowProgressReporter,
    use_workflow_progress,
)
from decathlon_voc_analyzer.schemas.analysis import (  # noqa: E402
    ExperimentConfig,
    ProductAnalysisRequest,
)
from decathlon_voc_analyzer.stage4_generation.analysis_service import ProductAnalysisService  # noqa: E402


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

EXPERIMENT_PROGRESS_PLAN = [
    (
        "index",
        "构建索引",
        [
            ("load_packages", "加载商品包"),
            ("embed_text", "生成文本向量"),
            ("embed_image", "生成图像向量"),
            ("persist", "保存索引快照"),
        ],
    ),
    (
        "analyze",
        "生成分析",
        [
            ("extract", "抽取评论"),
            ("questions", "规划和生成问题"),
            ("retrieve", "检索证据"),
            ("quality", "评估检索质量"),
            ("report", "生成报告"),
            ("attribution", "归因和修订"),
            ("persist", "写入分析产物"),
        ],
    ),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _progress_dashboard_path(output_dir: Path, category: str, product_id: str, condition: str) -> Path:
    return output_dir / "_progress" / category / product_id / f"{condition}.html"


def _progress_dashboard_url(output_dir: Path, dashboard_path: Path) -> str | None:
    try:
        relative_path = dashboard_path.resolve().relative_to(output_dir.resolve()).as_posix()
    except ValueError:
        return None
    return f"/experiment_results/{relative_path}"


def _read_log_entries(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    entries: list[dict] = []
    with log_path.open("rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = orjson.loads(line)
            except Exception:
                continue
            if isinstance(entry, dict):
                entries.append(entry)
    return entries


def _latest_entries_by_run_id(entries: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for entry in entries:
        run_id = entry.get("run_id")
        if run_id:
            latest[str(run_id)] = entry
    return latest


def _write_summary(
    summary_path: Path,
    *,
    categories: list[str],
    products_per_category: int,
    max_reviews: int,
    selected_products: dict[str, list[str]],
    planned_run_ids: list[str],
    skipped_run_ids: set[str],
    log_entries: list[dict],
    runner_state: str,
    started_at: str,
    current_run_id: str | None = None,
    finished_at: str | None = None,
) -> None:
    latest = _latest_entries_by_run_id(log_entries)
    planned_set = set(planned_run_ids)
    planned_latest = {run_id: entry for run_id, entry in latest.items() if run_id in planned_set}
    completed_runs = sum(1 for entry in planned_latest.values() if entry.get("status") == "success")
    failed_runs = sum(1 for entry in planned_latest.values() if entry.get("status") == "error")
    skipped_runs = len(skipped_run_ids)
    remaining_runs = max(len(planned_run_ids) - completed_runs - failed_runs, 0)
    condition_totals = {
        condition_name: sum(1 for run_id in planned_run_ids if run_id.endswith(f"__{condition_name}"))
        for condition_name, _ in EXPERIMENT_CONDITIONS
    }
    summary_path.write_bytes(
        orjson.dumps(
            {
                "categories": categories,
                "selected_products": selected_products,
                "products_per_category": products_per_category,
                "max_reviews": max_reviews,
                "conditions": [name for name, _ in EXPERIMENT_CONDITIONS],
                "condition_totals": condition_totals,
                "planned_total_runs": len(planned_run_ids),
                "total_runs": len(planned_run_ids),
                "completed_runs": completed_runs,
                "successful_runs": completed_runs,
                "failed_runs": failed_runs,
                "skipped_runs": skipped_runs,
                "remaining_runs": remaining_runs,
                "runner_state": runner_state,
                "current_run_id": current_run_id,
                "started_at": started_at,
                "updated_at": _now_iso(),
                "finished_at": finished_at,
                "runs": [planned_latest[run_id] for run_id in planned_run_ids if run_id in planned_latest],
            },
            option=orjson.OPT_INDENT_2,
        )
    )


def run_experiment_matrix(
    categories: list[str],
    products_per_category: int,
    max_reviews: int,
    output_dir: Path,
    seed: int = 42,
    resume: bool = False,
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
    log_path = output_dir / "experiment_log.jsonl"
    summary_path = output_dir / "experiment_summary.json"
    started_at = _now_iso()
    planned_runs = [
        (category, product_id, condition_name, exp_config)
        for category, products in selected_products.items()
        for product_id in products
        for condition_name, exp_config in EXPERIMENT_CONDITIONS
    ]
    planned_run_ids = [
        f"{category}__{product_id}__{condition_name}"
        for category, product_id, condition_name, _ in planned_runs
    ]

    if not resume and log_path.exists():
        log_path.write_bytes(b"")

    existing_entries = _read_log_entries(log_path) if resume else []
    latest_existing = _latest_entries_by_run_id(existing_entries)
    completed_run_ids = {
        run_id
        for run_id, entry in latest_existing.items()
        if entry.get("status") == "success" and run_id in set(planned_run_ids)
    }
    skipped_run_ids: set[str] = set()
    log_entries = list(existing_entries)

    if resume:
        print(f"\n[RESUME] Found {len(completed_run_ids)} completed runs. Skipping successes only.")

    _write_summary(
        summary_path,
        categories=categories,
        products_per_category=products_per_category,
        max_reviews=max_reviews,
        selected_products=selected_products,
        planned_run_ids=planned_run_ids,
        skipped_run_ids=skipped_run_ids,
        log_entries=log_entries,
        runner_state="running",
        started_at=started_at,
    )

    for category, product_id, condition_name, exp_config in planned_runs:
        run_id = f"{category}__{product_id}__{condition_name}"
        if resume and run_id in completed_run_ids:
            print(f"\n[SKIP] {run_id} (already completed)")
            skipped_run_ids.add(run_id)
            _write_summary(
                summary_path,
                categories=categories,
                products_per_category=products_per_category,
                max_reviews=max_reviews,
                selected_products=selected_products,
                planned_run_ids=planned_run_ids,
                skipped_run_ids=skipped_run_ids,
                log_entries=log_entries,
                runner_state="running",
                started_at=started_at,
                current_run_id=run_id,
            )
            continue

        print(f"\n[RUN] {run_id}")
        run_started_at = _now_iso()
        run_start_time = time.monotonic()
        progress_dashboard_path = _progress_dashboard_path(
            output_dir,
            category,
            product_id,
            condition_name,
        )
        progress_dashboard_url = _progress_dashboard_url(output_dir, progress_dashboard_path)
        progress = WorkflowProgressReporter(
            EXPERIMENT_PROGRESS_PLAN,
            dashboard_path=progress_dashboard_path,
            dashboard_title=f"{category}/{product_id}/{condition_name} Experiment Progress",
            terminal_mode="events",
        )
        _write_summary(
            summary_path,
            categories=categories,
            products_per_category=products_per_category,
            max_reviews=max_reviews,
            selected_products=selected_products,
            planned_run_ids=planned_run_ids,
            skipped_run_ids=skipped_run_ids,
            log_entries=log_entries,
            runner_state="running",
            started_at=started_at,
            current_run_id=run_id,
        )
        try:
            reuse_extraction = True
            reuse_checkpoint = (
                exp_config.ablation_no_claim_attribution
                and not exp_config.ablation_no_question_planning
                and not exp_config.ablation_no_image_route
                and not exp_config.ablation_no_reranking
            )
            request = ProductAnalysisRequest(
                product_id=product_id,
                category_slug=category,
                max_reviews=max_reviews,
                use_llm=True,
                persist_artifact=True,
                use_replay=False,
                reuse_extraction_artifact=reuse_extraction,
                reuse_analysis_checkpoint=reuse_checkpoint,
                top_k_per_route=2,
                questions_per_aspect=2,
                experiment_config=exp_config,
            )
            with progress:
                with use_workflow_progress(progress):
                    progress.note(f"实验运行已启动：{run_id}")
                    response = service.analyze(request)
                    index_module = next((module for module in progress.modules if module.key == "index"), None)
                    if index_module is not None and index_module.status == "pending":
                        progress.skip_module("index", detail="本 run 未触发索引构建")
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
                "progress_dashboard_url": progress_dashboard_url,
            }
        except Exception as exc:
            progress.fail_workflow(detail=f"实验运行失败: {exc}")
            print(f"[ERROR] {run_id}: {exc}")
            result_summary = {
                "run_id": run_id,
                "category": category,
                "product_id": product_id,
                "condition": condition_name,
                "status": "error",
                "error": str(exc),
                "progress_dashboard_url": progress_dashboard_url,
            }

        run_finished_at = _now_iso()
        result_summary.update(
            {
                "started_at": run_started_at,
                "finished_at": run_finished_at,
                "timestamp": run_finished_at,
                "duration_seconds": round(time.monotonic() - run_start_time, 3),
            }
        )
        log_entries.append(result_summary)
        with log_path.open("ab") as f:
            f.write(orjson.dumps(result_summary, option=orjson.OPT_APPEND_NEWLINE))
        _write_summary(
            summary_path,
            categories=categories,
            products_per_category=products_per_category,
            max_reviews=max_reviews,
            selected_products=selected_products,
            planned_run_ids=planned_run_ids,
            skipped_run_ids=skipped_run_ids,
            log_entries=log_entries,
            runner_state="running",
            started_at=started_at,
            current_run_id=run_id,
        )

    final_entries = _read_log_entries(log_path)
    _write_summary(
        summary_path,
        categories=categories,
        products_per_category=products_per_category,
        max_reviews=max_reviews,
        selected_products=selected_products,
        planned_run_ids=planned_run_ids,
        skipped_run_ids=skipped_run_ids,
        log_entries=final_entries,
        runner_state="completed",
        started_at=started_at,
        finished_at=_now_iso(),
    )
    print(f"\nDone. Summary written to {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run experiment matrix")
    parser.add_argument("--categories", nargs="+", default=["backpack", "shoes", "sunglasses"])
    parser.add_argument("--products-per-category", type=int, default=5)
    parser.add_argument("--max-reviews", type=int, default=25)
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_EXPERIMENT_OUTPUT_DIR))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", action="store_true", help="Skip already successful runs in existing log")
    args = parser.parse_args()

    run_experiment_matrix(
        categories=args.categories,
        products_per_category=args.products_per_category,
        max_reviews=args.max_reviews,
        output_dir=Path(args.output_dir),
        seed=args.seed,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
