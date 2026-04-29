import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "04_scripts" / "clear_generated_outputs.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("clear_generated_outputs", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_collect_cleanup_targets_excludes_readme(tmp_path) -> None:
    module = _load_module()
    outputs_dir = tmp_path / "02_outputs"
    outputs_dir.mkdir()
    (outputs_dir / "README.md").write_text("keep", encoding="utf-8")
    (outputs_dir / "1_normalized").mkdir()
    (outputs_dir / "custom_namespace").mkdir()
    (outputs_dir / "local_evidence_index.json").write_text("{}", encoding="utf-8")

    targets = module.collect_cleanup_targets(outputs_dir)

    assert [target.name for target in targets] == ["1_normalized", "custom_namespace", "local_evidence_index.json"]


def test_remove_targets_deletes_files_and_directories(tmp_path) -> None:
    module = _load_module()
    outputs_dir = tmp_path / "02_outputs"
    outputs_dir.mkdir()
    directory_target = outputs_dir / "6_html"
    directory_target.mkdir()
    file_target = outputs_dir / "local_evidence_index.json"
    file_target.write_text("{}", encoding="utf-8")

    module.remove_targets([directory_target, file_target])

    assert not directory_target.exists()
    assert not file_target.exists()


def test_recreate_output_skeleton_creates_expected_directories(tmp_path) -> None:
    module = _load_module()
    base_dir = tmp_path / "02_outputs"
    expected_dirs = [
        base_dir / "1_normalized",
        base_dir / "2_aspects",
        base_dir / "3_indexes",
        base_dir / "4_reports",
        base_dir / "5_feedback",
        base_dir / "5_replay",
        base_dir / "6_html",
        base_dir / "7_manifests",
        base_dir / "8_evaluations",
        base_dir / "CN",
    ]

    module.recreate_output_skeleton(expected_dirs)

    assert all(path.exists() and path.is_dir() for path in expected_dirs)


def test_prompt_for_output_conflict_resolution_accepts_kill_choice() -> None:
    module = _load_module()
    printed: list[str] = []

    action = module._prompt_for_output_conflict_resolution(
        Path("/tmp/02_outputs"),
        [module.OccupyingProcess(pid=4321, user="severin", elapsed="00:12", command="python 04_scripts/run_workflow.py")],
        input_func=lambda _prompt: "1",
        print_func=printed.append,
    )

    assert action == "terminate"
    assert any("PID 4321" in line for line in printed)
    assert any("关闭上述进程" in line for line in printed)


def test_main_blocks_noninteractive_cleanup_when_outputs_are_in_use(monkeypatch, tmp_path) -> None:
    module = _load_module()
    removed: list[list[Path]] = []
    monkeypatch.setattr(module, "parse_args", lambda: SimpleNamespace(yes=True, dry_run=False, kill_running=False, force=False))
    monkeypatch.setattr(module, "collect_cleanup_targets", lambda outputs_dir=module.OUTPUTS_DIR: [tmp_path / "2_aspects"])
    monkeypatch.setattr(
        module,
        "_find_output_occupants",
        lambda outputs_dir=module.OUTPUTS_DIR: [
            module.OccupyingProcess(pid=4321, user="severin", elapsed="00:12", command="python 04_scripts/run_workflow.py")
        ],
    )
    monkeypatch.setattr(module, "remove_targets", lambda targets, dry_run=False: removed.append(targets))

    exit_code = module.main()

    assert exit_code == 1
    assert removed == []