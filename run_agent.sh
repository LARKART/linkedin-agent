#!/bin/bash
# Wrapper for cron: runs a lane with the project's venv and logs output.
# Usage: run_agent.sh <run|comments> [--lane post|carousel]
set -euo pipefail
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

mkdir -p logs
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
LOG="logs/${STAMP}_$1${2:+_}${3:-}.log"

"$DIR/.venv/bin/python" -m agent.cli "$@" >> "$LOG" 2>&1
echo "exit=$? at $(date)" >> "$LOG"
