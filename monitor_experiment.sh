#!/bin/bash
# Monitor experiment progress

LOG="/home/severin/Codelib/Decathlon_VOC_Analyzer/experiment_results/experiment_log.jsonl"
SUMMARY="/home/severin/Codelib/Decathlon_VOC_Analyzer/experiment_results/experiment_summary.json"

echo "=== Experiment Monitor ==="
echo "Time: $(date)"

# Check if process is running
PID=$(pgrep -f "experiment_runner" | head -1)
if [ -n "$PID" ]; then
    echo "Status: RUNNING (PID: $PID)"
    echo "CPU/Memory:"
    ps -p $PID -o %cpu,%mem,etime | tail -1
else
    echo "Status: NOT RUNNING"
fi

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

# Check if summary exists (means all done)
if [ -f "$SUMMARY" ]; then
    echo ""
    echo "Summary file exists - experiment may be complete!"
fi

echo ""
echo "To attach to tmux session: tmux attach -t experiment"
echo "To detach from tmux: Ctrl+B, then D"
