import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import json


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "04_scripts" / "launch_interactive_workflow.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("launch_interactive_workflow", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_index_selection_supports_ranges_and_commas() -> None:
    module = _load_module()

    assert module.parse_index_selection("2-4,7,9-10", 12) == [2, 3, 4, 7, 9, 10]


def test_parse_index_selection_rejects_out_of_range() -> None:
    module = _load_module()

    try:
        module.parse_index_selection("2-20", 10)
    except ValueError as exc:
        assert "out of range" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_render_batch_dashboard_html_shows_completed_banner() -> None:
    module = _load_module()
    state = module.BatchRunState(
        category="backpack",
        review_limit=25,
        dashboard_url="http://127.0.0.1:8765/_launcher/backpack_interactive_batch.html",
        products=[module.BatchProductState(index=1, product_id="backpack_002", status="completed", detail="执行完成")],
        started_at_epoch=1_700_000_000.0,
        completed_at_epoch=1_700_000_120.0,
        status="completed",
        current_product_id="backpack_002",
        current_product_dashboard_url="http://127.0.0.1:8765/_progress/backpack/backpack_002_live_progress.html",
        note="所有商品都已完成，本页面会停留在最终完成状态。",
    )

    html = module.render_batch_dashboard_html(state)

    assert "已完成所有流程" in html
    assert "本页面会停留在最终完成状态" in html
    assert "Current Product Dashboard" in html
    assert "backpack_002_live_progress.html" in html


def test_build_vscode_simple_browser_uri_targets_internal_browser() -> None:
    module = _load_module()

    uri = module._build_vscode_simple_browser_uri("http://127.0.0.1:8765/_launcher/backpack_interactive_batch.html")

    assert uri.startswith("command:simpleBrowser.show?")
    assert "127.0.0.1%3A8765" in uri
    assert "%5B%22http%3A%2F%2F127.0.0.1%3A8765%2F_launcher%2Fbackpack_interactive_batch.html%22%5D" in uri


def test_prompt_run_mode_returns_resume_checkpoint_choice() -> None:
    module = _load_module()
    printed: list[str] = []

    candidate = module.ResumeCandidate(
        dashboard_path=Path("/tmp/shoes_interactive_batch.html"),
        payload={
            "category": "shoes",
            "products": [{"productId": "shoes_001", "status": "failed"}],
        },
    )

    module._resume_mode_has_aspects = lambda payload: True
    module._resume_mode_has_analysis_checkpoint = lambda payload: True

    result = module.prompt_run_mode(
        candidate,
        input_func=lambda _prompt: "3",
        print_func=printed.append,
    )

    assert result == module.RUN_MODE_RESUME_ANALYSIS_CHECKPOINT
    assert any("从 analysis checkpoint 续跑" in line for line in printed)


def test_run_mode_args_include_resume_flags() -> None:
    module = _load_module()

    assert module._run_mode_args(module.RUN_MODE_NORMAL) == []
    assert module._run_mode_args(module.RUN_MODE_RESUME_ASPECTS) == ["--skip-normalize", "--skip-index", "--resume-from-aspects"]
    assert module._run_mode_args(module.RUN_MODE_RESUME_ANALYSIS_CHECKPOINT) == ["--skip-normalize", "--skip-index", "--resume-from-analysis-checkpoint"]


def test_available_run_mode_options_hide_missing_analysis_checkpoint() -> None:
    module = _load_module()
    candidate = module.ResumeCandidate(
        dashboard_path=Path("/tmp/shoes_interactive_batch.html"),
        payload={"category": "shoes", "products": [{"productId": "shoes_001", "status": "failed"}]},
    )

    module._resume_mode_has_aspects = lambda payload: True
    module._resume_mode_has_analysis_checkpoint = lambda payload: False

    options = module.available_run_mode_options(candidate)

    assert [option.code for option in options] == [module.RUN_MODE_NORMAL, module.RUN_MODE_RESUME_ASPECTS]


def test_unavailable_resume_mode_messages_report_missing_checkpoint() -> None:
    module = _load_module()
    module._resume_mode_has_aspects = lambda payload: True
    module._resume_mode_has_analysis_checkpoint = lambda payload: False

    messages = module.unavailable_resume_mode_messages({"category": "shoes", "products": [{"productId": "shoes_001", "status": "failed"}]})

    assert messages == ["“从 analysis checkpoint 续跑”不可用：缺少 analysis checkpoint。"]


def test_find_latest_resumable_batch_prefers_recent_state_file(tmp_path: Path) -> None:
    module = _load_module()
    launcher_dir = tmp_path / "_launcher"
    launcher_dir.mkdir()
    older = launcher_dir / "bags_interactive_batch.state.json"
    newer = launcher_dir / "shoes_interactive_batch.state.json"
    older.write_text(json.dumps({"category": "bags", "status": "failed", "products": [{"productId": "bags_001", "status": "failed"}]}), encoding="utf-8")
    newer.write_text(json.dumps({"category": "shoes", "status": "running", "reviewLimit": 10, "products": [{"productId": "shoes_001", "status": "running"}]}), encoding="utf-8")
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_700_000_100, 1_700_000_100))

    candidate = module.find_latest_resumable_batch(launcher_dir)

    assert candidate is not None
    assert candidate.payload["category"] == "shoes"


def test_prompt_continue_previous_batch_accepts_yes() -> None:
    module = _load_module()
    printed: list[str] = []

    result = module.prompt_continue_previous_batch(
        {
            "category": "shoes",
            "reviewLimit": 10,
            "products": [{"productId": "shoes_001", "status": "failed"}],
        },
        module.RUN_MODE_RESUME_ASPECTS,
        input_func=lambda _prompt: "y",
        print_func=printed.append,
    )

    assert result is True
    assert any("未完成商品: shoes_001" in line for line in printed)


def test_prompt_for_qdrant_conflict_resolution_accepts_takeover_choice() -> None:
    module = _load_module()
    printed: list[str] = []

    action = module._prompt_for_qdrant_conflict_resolution(
        Path("/tmp/qdrant_store"),
        [module.OccupyingProcess(pid=1234, user="severin", elapsed="00:10", command="python old_run.py")],
        input_func=lambda _prompt: "1",
        print_func=printed.append,
    )

    assert action == "terminate"
    assert any("PID 1234" in line for line in printed)
    assert any("关闭上述进程" in line for line in printed)


def test_run_product_workflow_stops_when_user_cancels(monkeypatch) -> None:
    module = _load_module()
    subprocess_calls: list[list[str]] = []

    monkeypatch.setattr(module, "_ensure_shared_qdrant_access", lambda: False)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, cwd, check: subprocess_calls.append(command) or SimpleNamespace(returncode=0),
    )

    exit_code = module.run_product_workflow(category="backpack", product_id="backpack_001", max_reviews=10)

    assert exit_code == 130
    assert subprocess_calls == []


def test_run_product_workflow_passes_resume_aspects_flags(monkeypatch) -> None:
    module = _load_module()
    subprocess_calls: list[list[str]] = []

    monkeypatch.setattr(module, "_ensure_shared_qdrant_access", lambda: True)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, cwd, check: subprocess_calls.append(command) or SimpleNamespace(returncode=0),
    )

    exit_code = module.run_product_workflow(
        category="backpack",
        product_id="backpack_001",
        max_reviews=10,
        run_mode=module.RUN_MODE_RESUME_ASPECTS,
    )

    assert exit_code == 0
    assert subprocess_calls
    assert "--resume-from-aspects" in subprocess_calls[0]
    assert "--skip-normalize" in subprocess_calls[0]
    assert "--skip-index" in subprocess_calls[0]


def test_restore_batch_state_preserves_completed_products() -> None:
    module = _load_module()

    state = module.restore_batch_state(
        {
            "category": "shoes",
            "reviewLimit": 10,
            "status": "failed",
            "startedAt": "2026-04-30T00:26:44",
            "products": [
                {"index": 1, "productId": "shoes_001", "status": "completed", "startedAt": "2026-04-30T00:26:44", "completedAt": "2026-04-30T00:30:44", "detail": "执行完成", "exitCode": 0},
                {"index": 2, "productId": "shoes_002", "status": "failed", "startedAt": "2026-04-30T00:31:44", "completedAt": None, "detail": "执行失败", "exitCode": 1},
            ],
        }
    )

    assert state.category == "shoes"
    assert state.review_limit == 10
    assert len(state.products) == 2
    assert state.products[0].status == "completed"
    assert state.products[1].status == "failed"