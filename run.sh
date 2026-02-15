#!/bin/bash
set -euo pipefail

SESSION="epstein-scraper"
PROJECT_DIR="/root/epstein"

# Kill existing session if present
tmux kill-session -t "$SESSION" 2>/dev/null || true

# Create new tmux session
tmux new-session -d -s "$SESSION" -c "$PROJECT_DIR"

# Top pane: run the scraper
tmux send-keys -t "$SESSION" "cd $PROJECT_DIR && python3 -m epstein_scraper.main 2>&1 | tee logs/scraper_\$(date +%Y%m%d_%H%M%S).log" Enter

# Split horizontally for stats pane
tmux split-window -v -t "$SESSION" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION" "sleep 5 && watch -n 30 'python3 -m epstein_scraper.main --stats'" Enter

# Set pane sizes (70/30 split)
tmux resize-pane -t "$SESSION:0.0" -y 70%

echo "tmux session '$SESSION' created."
echo "Attach with: tmux attach -t $SESSION"
echo "Detach with: Ctrl+B, D"
