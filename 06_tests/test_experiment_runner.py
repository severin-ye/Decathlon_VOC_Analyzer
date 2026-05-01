import orjson

from decathlon_voc_analyzer.workflows.experiment_runner import _write_summary


def test_write_summary_counts_skipped_completed_runs_once(tmp_path) -> None:
    summary_path = tmp_path / "experiment_summary.json"
    planned_run_ids = ["backpack__p1__full_system", "backpack__p1__ablation_no_qp"]
    log_entries = [
        {
            "run_id": "backpack__p1__full_system",
            "condition": "full_system",
            "status": "success",
        }
    ]

    _write_summary(
        summary_path,
        categories=["backpack"],
        products_per_category=1,
        max_reviews=25,
        selected_products={"backpack": ["p1"]},
        planned_run_ids=planned_run_ids,
        skipped_run_ids={"backpack__p1__full_system"},
        log_entries=log_entries,
        runner_state="running",
        started_at="2026-01-01T00:00:00+00:00",
    )

    summary = orjson.loads(summary_path.read_bytes())

    assert summary["planned_total_runs"] == 2
    assert summary["completed_runs"] == 1
    assert summary["skipped_runs"] == 1
    assert summary["remaining_runs"] == 1
    assert summary["condition_totals"]["full_system"] == 1
