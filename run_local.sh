#!/bin/bash
# Run the Streamlit app locally with clear error messages.
set -e
cd "$(dirname "$0")"

echo "Working directory: $(pwd)"

# Prefer venv
if [ -d "venv" ]; then
    echo "Activating venv..."
    source venv/bin/activate
    PY=python
else
    PY=""
    for cmd in python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            PY="$cmd"
            break
        fi
    done
    if [ -z "$PY" ]; then
        echo "Error: python3 or python not found. Install Python 3 and try again."
        exit 1
    fi
    echo "Using: $PY"
fi

# Check Streamlit
if ! $PY -c "import streamlit" 2>/dev/null; then
    echo "Streamlit not installed. Run: $PY -m pip install streamlit"
    exit 1
fi

# Optional deps
$PY -c "import pandas" 2>/dev/null || { echo "Warning: pandas not installed. Run: $PY -m pip install -r requirements.txt"; }
$PY -c "import openpyxl" 2>/dev/null || echo "Note: openpyxl not installed (needed for Excel). Run: pip install openpyxl"

echo ""
echo "Starting app at http://localhost:8501"
echo "Press Ctrl+C to stop."
echo ""
exec $PY -m streamlit run ui.py --server.headless true
