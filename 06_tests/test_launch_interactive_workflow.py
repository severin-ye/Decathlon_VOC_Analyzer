import importlib.util
import json
import os
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


def test_prompt_categories_supports_multi_select() -> None:
    module = _load_module()

    selected = module.prompt_categories(
        ["backpack", "shoes", "sunglasses"],
        input_func=lambda _prompt: "1,3",
        print_func=lambda *_args, **_kwargs: None,
    )

    assert selected == ["backpack", "sunglasses"]


def test_write_batch_dashboard_creates_three_level_pages(tmp_path: Path) -> None:
    module = _load_module()
    module.HTML_ROOT = tmp_path
    module.LAUNCHER_DIR = tmp_path / "_launcher"
    module.LAUNCHER_ASSET_DIR = tmp_path / "_launcher_assets"

    state = module.LauncherRunState(
        dashboard_url="http://localhost:8765/_launcher/",
        categories=[
            module.CategoryRunState(
                category="backpack",
                review_limit=25,
                status="running",
                current_product_id="backpack_002",
                detail="正在执行 backpack_002",
                products=[
                    module.BatchProductState(index=1, product_id="backpack_001", review_limit=25, status="completed", detail="执行完成"),
                    module.BatchProductState(index=2, product_id="backpack_002", review_limit=25, status="running", detail="正在执行"),
                ],
            )
        ],
        started_at_epoch=1_700_000_000.0,
        status="running",
        current_category="backpack",
        current_product_id="backpack_002",
        note="正在执行 backpack / backpack_002",
    )

    module.write_batch_dashboard(state)

    session_payload = json.loads((module.LAUNCHER_DIR / "session.state.json").read_text(encoding="utf-8"))
    overview_html = (module.LAUNCHER_DIR / "index.html").read_text(encoding="utf-8")
    category_html = (module.LAUNCHER_DIR / "backpack_interactive_batch.html").read_text(encoding="utf-8")

    assert session_payload["categories"][0]["category"] == "backpack"
    assert session_payload["categories"][0]["products"][1]["productId"] == "backpack_002"
    assert session_payload["categories"][0]["products"][1]["productPageUrl"] == "/_progress/backpack/backpack_002_live_progress.html"
    assert "/_launcher/session.state.json" in overview_html
    assert "data-category=\"backpack\"" in category_html


def test_build_vscode_simple_browser_uri_targets_internal_browser() -> None:
    module = _load_module()

    uri = module._build_vscode_simple_browser_uri("http://localhost:8765/_launcher/")

    assert uri.startswith("command:simpleBrowser.show?")
    assert "localhost%3A8765" in uri
    assert "%5B%22http%3A%2F%2Flocalhost%3A8765%2F_launcher%2F%22%5D" in uri


def test_prompt_run_mode_returns_resume_checkpoint_choice() -> None:
    module = _load_module()
    printed: list[str] = []

    candidate = module.ResumeCandidate(
        dashboard_path=Path("/tmp/index.html"),
        payload={
            "categories": [
                {
                    "category": "shoes",
                    "products": [{"productId": "shoes_001", "status": "failed"}],
                }
            ],
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
    assert any("正常跑" in line for line in printed)


def test_prompt_run_mode_defaults_to_resume_when_enter_is_pressed() -> None:
    module = _load_module()

    candidate = module.ResumeCandidate(
        dashboard_path=Path("/tmp/index.html"),
        payload={
            "categories": [
                {
                    "category": "shoes",
                    "products": [{"productId": "shoes_001", "status": "failed"}],
                }
            ],
        },
    )

    module._resume_mode_has_aspects = lambda payload: True
    module._resume_mode_has_analysis_checkpoint = lambda payload: False

    result = module.prompt_run_mode(
        candidate,
        input_func=lambda _prompt: "",
        print_func=lambda *_args, **_kwargs: None,
    )

    assert result == module.RUN_MODE_RESUME_ASPECTS


def test_run_mode_args_include_resume_flags() -> None:
    module = _load_module()

    assert module._run_mode_args(module.RUN_MODE_NORMAL) == []
    assert module._run_mode_args(module.RUN_MODE_RESUME_ASPECTS) == ["--skip-normalize", "--skip-index", "--resume-from-aspects"]
    assert module._run_mode_args(module.RUN_MODE_RESUME_ANALYSIS_CHECKPOINT) == ["--skip-normalize", "--skip-index", "--resume-from-analysis-checkpoint"]


def test_available_run_mode_options_hide_missing_analysis_checkpoint() -> None:
    module = _load_module()
    candidate = module.ResumeCandidate(
        dashboard_path=Path("/tmp/index.html"),
        payload={"categories": [{"category": "shoes", "products": [{"productId": "shoes_001", "status": "failed"}]}]},
    )

    module._resume_mode_has_aspects = lambda payload: True
    module._resume_mode_has_analysis_checkpoint = lambda payload: False

    options = module.available_run_mode_options(candidate)

    assert [option.code for option in options] == [module.RUN_MODE_NORMAL, module.RUN_MODE_RESUME_ASPECTS]


def test_available_run_mode_options_prioritize_resume_modes() -> None:
    module = _load_module()
    candidate = module.ResumeCandidate(
        dashboard_path=Path("/tmp/index.html"),
        payload={"categories": [{"category": "shoes", "products": [{"productId": "shoes_001", "status": "failed"}]}]},
    )

    module._resume_mode_has_aspects = lambda payload: True
    module._resume_mode_has_analysis_checkpoint = lambda payload: True

    options = module.available_run_mode_options(candidate)

    assert [option.code for option in options] == [
        module.RUN_MODE_NORMAL,
        module.RUN_MODE_RESUME_ASPECTS,
        module.RUN_MODE_RESUME_ANALYSIS_CHECKPOINT,
    ]


def test_unavailable_resume_mode_messages_report_missing_checkpoint() -> None:
    module = _load_module()
    module._resume_mode_has_aspects = lambda payload: True
    module._resume_mode_has_analysis_checkpoint = lambda payload: False

    messages = module.unavailable_resume_mode_messages({"categories": [{"category": "shoes", "products": [{"productId": "shoes_001", "status": "failed"}]}]})

    assert messages == ["“从 analysis checkpoint 续跑”不可用：缺少 analysis checkpoint。"]


def test_find_latest_resumable_batch_prefers_recent_session_state(tmp_path: Path) -> None:
    module = _load_module()
    launcher_dir = tmp_path / "_launcher"
    launcher_dir.mkdir()
    older = launcher_dir / "bags_interactive_batch.state.json"
    newer = launcher_dir / "session.state.json"
    older.write_text(json.dumps({"category": "bags", "status": "failed", "products": [{"productId": "bags_001", "status": "failed"}]}), encoding="utf-8")
    newer.write_text(
        json.dumps(
            {
                "status": "running",
                "categories": [
                    {
                        "category": "shoes",
                        "reviewLimit": 10,
                        "products": [{"productId": "shoes_001", "status": "running"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_700_000_100, 1_700_000_100))

    candidate = module.find_latest_resumable_batch(launcher_dir)

    assert candidate is not None
    assert candidate.payload["categories"][0]["category"] == "shoes"


def test_prompt_continue_previous_batch_accepts_yes() -> None:
    module = _load_module()
    printed: list[str] = []

    result = module.prompt_continue_previous_batch(
        {
            "categories": [
                {
                    "category": "shoes",
                    "reviewLimit": 10,
                    "products": [{"productId": "shoes_001", "status": "failed"}],
                }
            ]
        },
        module.RUN_MODE_RESUME_ASPECTS,
        input_func=lambda _prompt: "y",
        print_func=printed.append,
    )

    assert result is True
    assert any("未完成商品: shoes / shoes_001" in line for line in printed)


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


def test_restore_batch_state_supports_multi_category_payload() -> None:
    module = _load_module()

    state = module.restore_batch_state(
        {
            "status": "failed",
            "runMode": "resume_aspects",
            "startedAt": "2026-04-30T00:26:44",
            "currentCategory": "shoes",
            "currentProductId": "shoes_002",
            "categories": [
                {
                    "category": "shoes",
                    "reviewLimit": 10,
                    "status": "failed",
                    "products": [
                        {"index": 1, "productId": "shoes_001", "reviewLimit": 10, "status": "completed", "startedAt": "2026-04-30T00:26:44", "completedAt": "2026-04-30T00:30:44", "detail": "执行完成", "exitCode": 0},
                        {"index": 2, "productId": "shoes_002", "reviewLimit": 10, "status": "failed", "startedAt": "2026-04-30T00:31:44", "completedAt": None, "detail": "执行失败", "exitCode": 1},
                    ],
                },
                {
                    "category": "sunglasses",
                    "reviewLimit": 10,
                    "status": "pending",
                    "products": [{"index": 1, "productId": "sunglasses_001", "reviewLimit": 10, "status": "pending"}],
                },
            ],
        }
    )

    assert len(state.categories) == 2
    assert state.categories[0].category == "shoes"
    assert state.categories[0].products[0].status == "completed"
    assert state.categories[1].products[0].product_id == "sunglasses_001"
    assert state.run_mode == module.RUN_MODE_RESUME_ASPECTS