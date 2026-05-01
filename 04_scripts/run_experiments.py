#!/usr/bin/env python3
"""
实验矩阵一键启动器。

用法:
    # 启动实验（后台 tmux）+ 监控 UI
    python 04_scripts/run_experiments.py start

    # 只启动监控 UI
    python 04_scripts/run_experiments.py ui

    # 查看当前状态
    python 04_scripts/run_experiments.py status

    # 停止实验
    python 04_scripts/run_experiments.py stop

    # 启动实验但不启动 UI（仅后台 tmux）
    python 04_scripts/run_experiments.py start --no-ui
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import orjson

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "05_src"
EXPERIMENT_RESULTS_DIR = ROOT_DIR / "experiment_results"
UI_DIR = ROOT_DIR / "04_scripts" / "experiment_ui"
LOG_FILE = ROOT_DIR / "experiment_run.log"
PYTHON = str(ROOT_DIR / ".venv" / "bin" / "python")

EXPERIMENT_CMD = [
    PYTHON,
    "-m",
    "decathlon_voc_analyzer.workflows.experiment_runner",
    "--categories",
    "backpack",
    "shoes",
    "sunglasses",
    "--products-per-category",
    "5",
    "--max-reviews",
    "25",
    "--output-dir",
    str(EXPERIMENT_RESULTS_DIR),
    "--seed",
    "42",
]


def _run_in_tmux(resume: bool = False) -> None:
    """Kill existing session and start a new one."""
    subprocess.run(["tmux", "kill-session", "-t", "experiment"], capture_output=True)
    time.sleep(0.5)
    cmd = (
        f"cd {ROOT_DIR} && "
        f"{PYTHON} -m decathlon_voc_analyzer.workflows.experiment_runner "
        f"--categories backpack shoes sunglasses "
        f"--products-per-category 5 --max-reviews 25 "
        f"--output-dir {EXPERIMENT_RESULTS_DIR} --seed 42 "
        f"{'--resume ' if resume else ''}2>&1 | tee experiment_run.log"
    )
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", "experiment", cmd],
        check=True,
    )
    print("[OK] 实验已在 tmux 会话 'experiment' 中后台启动")
    print("     查看实时输出: tmux attach -t experiment")
    print("     脱离会话: Ctrl+B, 然后按 D")


def _start_ui() -> None:
    """Start the UI server in background."""
    os.chdir(UI_DIR)
    # Check if already running
    result = subprocess.run(
        ["lsof", "-i", ":8080"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        print("[OK] 监控 UI 已在 http://localhost:8080/experiment.html 运行")
        return

    subprocess.Popen(
        [sys.executable, str(UI_DIR / "serve_ui.py")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(UI_DIR),
    )
    time.sleep(1)
    print("[OK] 监控 UI 已启动: http://localhost:8080/experiment.html")


def _status() -> None:
    """Print current experiment status."""
    log_path = EXPERIMENT_RESULTS_DIR / "experiment_log.jsonl"
    completed = 0
    failed = 0
    if log_path.exists():
        with log_path.open("rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = orjson.loads(line)
                    if entry.get("status") == "success":
                        completed += 1
                    elif entry.get("status") == "error":
                        failed += 1
                except Exception:
                    pass

    # Check tmux
    tmux_result = subprocess.run(
        ["tmux", "ls"],
        capture_output=True,
        text=True,
    )
    running = "experiment:" in tmux_result.stdout if tmux_result.returncode == 0 else False

    summary_path = EXPERIMENT_RESULTS_DIR / "experiment_summary.json"
    total = 0
    runner_state = "running" if running else "stopped"
    remaining = None
    if summary_path.exists():
        try:
            summary = orjson.loads(summary_path.read_bytes())
            total = int(summary.get("planned_total_runs") or summary.get("total_runs") or 0)
            completed = int(summary.get("completed_runs") or summary.get("successful_runs") or completed)
            failed = int(summary.get("failed_runs") or failed)
            remaining = summary.get("remaining_runs")
            runner_state = str(summary.get("runner_state") or runner_state)
        except Exception:
            pass
    if total == 0:
        total = completed + failed

    print("=== 实验状态 ===")
    print(f"状态: {'运行中' if running else runner_state}")
    print(f"进度: {completed} / {total} 已完成")
    print(f"失败: {failed}")
    if remaining is not None:
        print(f"剩余: {remaining}")
    print(f"成功率: {(completed / (completed + failed) * 100):.1f}%" if (completed + failed) > 0 else "N/A")
    print(f"日志: {log_path}")
    print(f"摘要: {summary_path}")
    print("监控: http://localhost:8080/experiment.html")


def _stop() -> None:
    """Stop the experiment tmux session."""
    result = subprocess.run(
        ["tmux", "kill-session", "-t", "experiment"],
        capture_output=True,
    )
    if result.returncode == 0:
        print("[OK] 实验已停止")
    else:
        print("[INFO] 实验未在运行")


def main() -> None:
    parser = argparse.ArgumentParser(description="实验矩阵一键启动器")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    start_parser = subparsers.add_parser("start", help="启动实验矩阵 + 监控 UI")
    start_parser.add_argument("--no-ui", action="store_true", help="不启动监控 UI")
    start_parser.add_argument("--resume", action="store_true", help="复用已有成功记录继续实验")

    subparsers.add_parser("ui", help="只启动监控 UI")
    subparsers.add_parser("status", help="查看当前状态")
    subparsers.add_parser("stop", help="停止实验")

    args = parser.parse_args()

    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    if args.command == "start":
        EXPERIMENT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        _run_in_tmux(resume=args.resume)
        if not args.no_ui:
            _start_ui()
            print("\n[INFO] 实验和监控 UI 都已启动")
            print("       打开浏览器访问: http://localhost:8080/experiment.html")
        else:
            print("\n[INFO] 实验已启动（未启动 UI）")
    elif args.command == "ui":
        _start_ui()
    elif args.command == "status":
        _status()
    elif args.command == "stop":
        _stop()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
