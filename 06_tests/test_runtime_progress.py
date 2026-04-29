import json
from time import monotonic, time
from pathlib import Path

from decathlon_voc_analyzer.runtime_progress import WorkflowProgressReporter


def test_progress_reporter_shows_eta_for_overall_and_active_step() -> None:
    reporter = WorkflowProgressReporter(
        [("analyze", "生成分析", [("extract", "抽取评论")])],
        enabled=False,
    )

    reporter.start_count_step("analyze", "extract", total=10, detail="测试步骤")
    reporter.advance_step("analyze", "extract", amount=5)
    reporter.started_at = monotonic() - 10.0
    reporter._module_lookup["analyze"].started_at = monotonic() - 10.0
    step = reporter._step_lookup["analyze:extract"]
    step.started_at = monotonic() - 10.0

    header = reporter._render_header().plain
    current_bar = reporter._current_step_bar().plain
    overall_meta = reporter._overall_meta_text()
    module_meta = reporter._module_progress_text(reporter._module_lookup["analyze"]).plain

    assert "ETA" in header
    assert "Finish ~" in header
    assert "Stage Finish ~" in header
    assert "Step Finish ~" in header
    assert "ETA" in current_bar
    assert "~" in current_bar
    assert overall_meta is not None
    assert "ETA" in overall_meta
    assert "~" in module_meta


def test_progress_reporter_writes_live_dashboard_html(tmp_path: Path) -> None:
    dashboard_path = tmp_path / "live_progress.html"
    reporter = WorkflowProgressReporter(
        [("analyze", "生成分析", [("extract", "抽取评论")])],
        enabled=False,
        dashboard_path=dashboard_path,
        dashboard_title="demo-progress",
    )

    reporter.note("dashboard smoke test")
    reporter.start_count_step("analyze", "extract", total=10, detail="测试步骤")
    reporter.advance_step("analyze", "extract", amount=3)
    reporter.started_at = monotonic() - 12.0
    reporter._module_lookup["analyze"].started_at = monotonic() - 12.0
    reporter._step_lookup["analyze:extract"].started_at = monotonic() - 12.0
    reporter.refresh()

    payload = dashboard_path.read_text(encoding="utf-8")

    assert "demo-progress" in payload
    assert "dashboard smoke test" in payload
    assert "Active Stage" in payload
    assert "技术快照" in payload
    assert "Auto refresh every 2s" in payload


def test_progress_reporter_dashboard_shows_completed_banner(tmp_path: Path) -> None:
    dashboard_path = tmp_path / "live_progress.html"
    reporter = WorkflowProgressReporter(
        [("analyze", "生成分析", [("extract", "抽取评论")])],
        enabled=False,
        dashboard_path=dashboard_path,
    )

    reporter.start_count_step("analyze", "extract", total=1, detail="完成测试")
    reporter.complete_step("analyze", "extract", detail="完成测试")
    reporter.complete_module("analyze", detail="分析完成")
    reporter.refresh()

    payload = dashboard_path.read_text(encoding="utf-8")

    assert "已完成所有流程" in payload
    assert "本页面会停留在最终完成状态" in payload


def test_progress_reporter_persists_stage_timestamps(tmp_path: Path) -> None:
    dashboard_path = tmp_path / "live_progress.html"
    reporter = WorkflowProgressReporter(
        [("analyze", "生成分析", [("extract", "抽取评论")])],
        enabled=False,
        dashboard_path=dashboard_path,
    )

    reporter.start_count_step("analyze", "extract", total=10, detail="测试步骤")
    reporter.advance_step("analyze", "extract", amount=4)
    reporter.refresh()

    state_path = dashboard_path.with_suffix(".state.json")
    payload = json.loads(state_path.read_text(encoding="utf-8"))

    assert payload["workflow"]["started_at"] is not None
    assert payload["modules"][0]["started_at"] is not None
    assert payload["modules"][0]["steps"][0]["started_at"] is not None
    assert payload["modules"][0]["steps"][0]["completed_at"] is None


def test_progress_reporter_restores_elapsed_from_persisted_timestamps(tmp_path: Path) -> None:
    dashboard_path = tmp_path / "live_progress.html"
    state_path = dashboard_path.with_suffix(".state.json")
    previous_start = time() - 120.0
    state_path.write_text(
        json.dumps(
            {
                "workflow": {
                    "started_at_epoch": previous_start,
                    "note": "resume",
                    "active_module_key": "analyze",
                    "active_step_key": "extract",
                },
                "modules": [
                    {
                        "key": "analyze",
                        "status": "in_progress",
                        "detail": "生成分析",
                        "started_at_epoch": previous_start,
                        "completed_at_epoch": None,
                        "steps": [
                            {
                                "key": "extract",
                                "status": "in_progress",
                                "completed": 6.0,
                                "total": 10.0,
                                "detail": "恢复中",
                                "started_at_epoch": previous_start,
                                "completed_at_epoch": None,
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    reporter = WorkflowProgressReporter(
        [("analyze", "生成分析", [("extract", "抽取评论")])],
        enabled=False,
        dashboard_path=dashboard_path,
        restore_state=True,
    )

    payload = reporter._dashboard_payload()

    assert payload["workflowStartedAt"] is not None
    assert payload["elapsed"] != "0.0s"
    assert payload["modules"][0]["startedAt"] is not None
    assert payload["modules"][0]["steps"][0]["startedAt"] is not None