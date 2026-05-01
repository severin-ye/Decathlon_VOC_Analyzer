#!/bin/bash
# Monitor experiment progress

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
EXPERIMENT_RESULTS_DIR="$ROOT_DIR/02_outputs/6_experiments/current"
RUNTIME_LOG="$ROOT_DIR/02_outputs/runtime_logs/experiment_run.log"
LOG="$EXPERIMENT_RESULTS_DIR/experiment_log.jsonl"
SUMMARY="$EXPERIMENT_RESULTS_DIR/experiment_summary.json"

echo "=== Experiment Monitor ==="
echo "Time: $(date)"

# Check if the experiment runner module is running.
PID=$(pgrep -f "decathlon_voc_analyzer.workflows.experiment_runner" | head -1)
if [ -n "$PID" ]; then
    echo "Status: RUNNING (PID: $PID)"
    echo "CPU/Memory:"
    ps -p $PID -o %cpu,%mem,etime | tail -1
else
    echo "Status: NOT RUNNING"
fi

echo "Runtime log: $RUNTIME_LOG"

# Check progress
if [ -f "$LOG" ]; then
    COMPLETED=$(wc -l < "$LOG")
    echo "Completed runs: $COMPLETED / 120"
    
    # Show last few runs
    echo ""
    echo "Last 3 runs:"
    tail -3 "$LOG" | python3 -m json.tool 2>/dev/null || tail -3 "$LOG"
else
    echo "Completed runs: 0 / 120"
    echo "Log file not created yet (still initializing)"
fi

# Show summary state when available.
if [ -f "$SUMMARY" ]; then
    echo ""
    python3 - "$SUMMARY" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    summary = json.load(f)

print(f"Summary state: {summary.get('runner_state', '--')}")
print(f"Successful runs: {summary.get('successful_runs', summary.get('completed_runs', '--'))}")
print(f"Failed runs: {summary.get('failed_runs', '--')}")
print(f"Remaining runs: {summary.get('remaining_runs', '--')}")
PY
fi

echo ""
echo "To attach to tmux session: tmux attach -t experiment"
echo "To detach from tmux: Ctrl+B, then D"
