#!/bin/bash
#
# Runs the Synology duplicate-folder analysis inside an isolated virtualenv.
# Intended to be invoked by the Synology Task Scheduler.
#
# Configure the paths below (or override them via environment variables) to
# match your NAS. The tool itself has no third-party runtime dependencies, so
# the virtualenv exists purely to isolate the Python interpreter.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv}"
LOG_FILE="${LOG_FILE:-$SCRIPT_DIR/analyzer.log}"

# --- Configure these for your NAS ---------------------------------------
# CSV_PATH may be a single report file or a directory (newest *.csv is used).
CSV_PATH="${CSV_PATH:-/volume1/path/to/duplicate_report}"
# HTML_PATH is optional; leave empty to skip HTML injection.
HTML_PATH="${HTML_PATH:-}"
# Minimum reclaimable space (bytes) for a folder group to be reported.
MIN_SIZE="${MIN_SIZE:-50000000}"
# ------------------------------------------------------------------------

# Create the virtual environment on first run.
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

ARGS=(--csv "$CSV_PATH" --log "$LOG_FILE" --min-size "$MIN_SIZE")
if [ -n "$HTML_PATH" ]; then
    ARGS+=(--html "$HTML_PATH")
fi

"$VENV_DIR/bin/python" "$SCRIPT_DIR/src/main.py" "${ARGS[@]}" >> "$LOG_FILE" 2>&1
