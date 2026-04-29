import argparse
from dataclasses import dataclass
import os
import signal
import shutil
import subprocess
import sys
from pathlib import Path
from time import sleep, time


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = ROOT_DIR / "02_outputs"
PROTECTED_OUTPUT_NAMES = {"README.md"}
RECREATE_OUTPUT_DIRS = [
    OUTPUTS_DIR / "1_normalized",
    OUTPUTS_DIR / "2_aspects",
    OUTPUTS_DIR / "3_indexes",
    OUTPUTS_DIR / "4_reports",
    OUTPUTS_DIR / "5_feedback",
    OUTPUTS_DIR / "5_replay",
    OUTPUTS_DIR / "6_html",
    OUTPUTS_DIR / "7_manifests",
    OUTPUTS_DIR / "8_evaluations",
    OUTPUTS_DIR / "CN",
]
WORKFLOW_SCRIPT_MARKERS = (
    "04_scripts/run_workflow.py",
    "04_scripts/launch_interactive_workflow.py",
    "04_scripts/validate_multimodal_runtime.py",
)


@dataclass
class OccupyingProcess:
    pid: int
    user: str = "--"
    elapsed: str = "--"
    command: str = "--"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="一键清除 02_outputs 下的历史运行产物")
    parser.add_argument("--yes", action="store_true", help="跳过确认提示，直接执行清理")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要删除的内容，不实际删除")
    parser.add_argument("--kill-running", action="store_true", help="发现仍在运行的工作流时，先结束相关进程再执行清理")
    parser.add_argument("--force", action="store_true", help="即使检测到输出目录仍被占用，也强制继续清理")
    return parser.parse_args()


def collect_cleanup_targets(outputs_dir: Path = OUTPUTS_DIR) -> list[Path]:
    if not outputs_dir.exists():
        return []
    return sorted(
        [path for path in outputs_dir.iterdir() if path.name not in PROTECTED_OUTPUT_NAMES],
        key=lambda path: path.name,
    )


def recreate_output_skeleton(output_dirs: list[Path] = RECREATE_OUTPUT_DIRS) -> None:
    for directory in output_dirs:
        directory.mkdir(parents=True, exist_ok=True)


def remove_targets(targets: list[Path], dry_run: bool = False) -> None:
    for target in targets:
        print(f"[清理] {'将删除' if dry_run else '删除'}: {target}")
        if dry_run:
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()


def confirm_cleanup(targets: list[Path], input_func=input) -> bool:
    if not targets:
        return True
    print("将清除以下历史运行产物：")
    for target in targets:
        print(f"  - {target}")
    choice = input_func("确认继续吗？输入 yes 执行清理，其它任意输入取消: ").strip().lower()
    return choice == "yes"


def _find_output_occupants(outputs_dir: Path = OUTPUTS_DIR) -> list[OccupyingProcess]:
    process_map: dict[int, OccupyingProcess] = {}
    lsof_path = shutil.which("lsof")
    if outputs_dir.exists() and lsof_path:
        completed = subprocess.run(
            [lsof_path, "-t", "+D", str(outputs_dir)],
            cwd=str(ROOT_DIR),
            check=False,
            capture_output=True,
            text=True,
        )
        for line in completed.stdout.splitlines():
            pid_text = line.strip()
            if not pid_text.isdigit():
                continue
            pid = int(pid_text)
            if pid == os.getpid() or not _process_exists(pid):
                continue
            process_map[pid] = _describe_process(pid)
    for process in _find_repo_workflow_processes():
        process_map[process.pid] = process
    return sorted(process_map.values(), key=lambda process: process.pid)


def _find_repo_workflow_processes() -> list[OccupyingProcess]:
    completed = subprocess.run(
        ["ps", "-eo", "pid=,user=,etime=,command="],
        cwd=str(ROOT_DIR),
        check=False,
        capture_output=True,
        text=True,
    )
    processes: list[OccupyingProcess] = []
    for line in completed.stdout.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 4 or not parts[0].isdigit():
            continue
        pid = int(parts[0])
        if pid == os.getpid():
            continue
        command = parts[3]
        if str(ROOT_DIR) not in command:
            continue
        if not any(marker in command for marker in WORKFLOW_SCRIPT_MARKERS):
            continue
        processes.append(
            OccupyingProcess(
                pid=pid,
                user=parts[1],
                elapsed=parts[2],
                command=command,
            )
        )
    return processes


def _describe_process(pid: int) -> OccupyingProcess:
    completed = subprocess.run(
        ["ps", "-p", str(pid), "-o", "pid=,user=,etime=,command="],
        cwd=str(ROOT_DIR),
        check=False,
        capture_output=True,
        text=True,
    )
    line = completed.stdout.strip()
    if not line:
        return OccupyingProcess(pid=pid)
    parts = line.split(None, 3)
    return OccupyingProcess(
        pid=int(parts[0]) if len(parts) >= 1 and parts[0].isdigit() else pid,
        user=parts[1] if len(parts) >= 2 else "--",
        elapsed=parts[2] if len(parts) >= 3 else "--",
        command=parts[3] if len(parts) >= 4 else "--",
    )


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _print_output_conflict(outputs_dir: Path, occupants: list[OccupyingProcess], print_func=print) -> None:
    print_func(f"[冲突] 输出目录仍被运行中的流程占用: {outputs_dir}")
    for process in occupants:
        print_func(f"  - PID {process.pid} | USER {process.user} | ELAPSED {process.elapsed}")
        print_func(f"    {process.command}")


def _prompt_for_output_conflict_resolution(
    outputs_dir: Path,
    occupants: list[OccupyingProcess],
    input_func=input,
    print_func=print,
) -> str:
    _print_output_conflict(outputs_dir, occupants, print_func=print_func)
    print_func("请选择后续操作：")
    print_func("  1. 关闭上述进程，并继续清理")
    print_func("  2. 强制继续清理（运行中的流程很可能立即失败）")
    print_func("  3. 取消本次清理")
    while True:
        choice = input_func("请输入编号 1 / 2 / 3: ").strip()
        if choice == "1":
            return "terminate"
        if choice == "2":
            return "force"
        if choice == "3":
            return "cancel"
        print_func("输入无效，请输入 1、2 或 3。")


def _terminate_processes(processes: list[OccupyingProcess]) -> None:
    for process in processes:
        try:
            os.kill(process.pid, signal.SIGTERM)
        except OSError:
            continue
    deadline = time() + 3.0
    remaining = {process.pid for process in processes}
    while remaining and time() < deadline:
        remaining = {pid for pid in remaining if _process_exists(pid)}
        if remaining:
            sleep(0.1)
    for pid in sorted(remaining):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            continue
    if processes:
        print("[接管] 已尝试结束占用输出目录的现有进程，继续执行清理。")


def main() -> int:
    args = parse_args()
    targets = collect_cleanup_targets()
    if not targets:
        recreate_output_skeleton()
        print(f"[完成] 未发现需要清理的历史产物，已确认目录骨架存在: {OUTPUTS_DIR}")
        return 0
    occupants = _find_output_occupants()
    if occupants and not args.dry_run:
        if args.kill_running:
            _print_output_conflict(OUTPUTS_DIR, occupants)
            _terminate_processes(occupants)
        elif args.force:
            _print_output_conflict(OUTPUTS_DIR, occupants)
            print("[警告] 将按 --force 强制继续清理，运行中的流程可能立即失败。")
        elif args.yes:
            _print_output_conflict(OUTPUTS_DIR, occupants)
            print("[阻止] 检测到运行中的流程；未执行清理。若要接管，请使用 --kill-running；若确认强制删除，请使用 --force。")
            return 1
        else:
            action = _prompt_for_output_conflict_resolution(OUTPUTS_DIR, occupants)
            if action == "terminate":
                _terminate_processes(occupants)
            elif action == "force":
                print("[警告] 将强制继续清理，运行中的流程可能立即失败。")
            else:
                print("[取消] 已保留运行中的流程，未执行清理。")
                return 130
    if not args.yes and not args.dry_run:
        if not confirm_cleanup(targets):
            print("[取消] 未执行清理。")
            return 130
    remove_targets(targets, dry_run=args.dry_run)
    if args.dry_run:
        print("[预览] dry-run 模式未实际删除文件。")
        return 0
    recreate_output_skeleton()
    print(f"[完成] 已清空历史运行产物，并重建基础目录: {OUTPUTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())