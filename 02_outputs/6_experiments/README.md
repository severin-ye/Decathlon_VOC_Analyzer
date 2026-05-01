# 6_experiments

实验矩阵运行结果统一放在这里。

- `current/`：默认实验矩阵输出目录，包含 `experiment_log.jsonl`、`experiment_summary.json` 和 `_progress/` dashboard。
- `test_*`：临时快速测试输出，可在确认无用后清理。

浏览器端仍通过 `/experiment_results/...` 访问当前实验输出；`04_scripts/experiment_ui/serve_ui.py` 会把该 URL 映射到 `current/`。
