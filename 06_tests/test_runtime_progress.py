from time import monotonic

from decathlon_voc_analyzer.runtime_progress import WorkflowProgressReporter


def test_progress_reporter_shows_eta_for_overall_and_active_step() -> None:
    reporter = WorkflowProgressReporter(
        [("analyze", "生成分析", [("extract", "抽取评论")])],
        enabled=False,
    )

    reporter.start_count_step("analyze", "extract", total=10, detail="测试步骤")
    reporter.advance_step("analyze", "extract", amount=5)
    reporter.started_at = monotonic() - 10.0
    step = reporter._step_lookup["analyze:extract"]
    step.started_at = monotonic() - 10.0

    header = reporter._render_header().plain
    current_bar = reporter._current_step_bar().plain
    overall_meta = reporter._overall_meta_text()

    assert "ETA" in header
    assert "Finish ~" in header
    assert "ETA" in current_bar
    assert overall_meta is not None
    assert "ETA" in overall_meta