import importlib.util
from pathlib import Path
from types import SimpleNamespace


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