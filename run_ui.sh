#!/bin/bash
# Launch the Streamlit UI

cd "$(dirname "$0")"

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON="$cmd"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "Error: python3 or python not found in PATH."
    exit 1
fi

if [ -d "venv" ]; then
    source venv/bin/activate
    PYTHON=python
    # Ensure openpyxl is installed (required for Excel)
    if ! python -c "import openpyxl" 2>/dev/null; then
        echo "Installing openpyxl (required for Excel input)..."
        pip install openpyxl
    fi
    # Ensure requests is installed (required for AppSheet API)
    if ! python -c "import requests" 2>/dev/null; then
        echo "Installing requests (required for AppSheet API)..."
        pip install requests
    fi
fi

# Prefer python -m streamlit so it works when streamlit is installed but not on PATH
if $PYTHON -c "import streamlit" 2>/dev/null; then
    exec $PYTHON -m streamlit run ui.py
elif command -v streamlit >/dev/null 2>&1; then
    exec streamlit run ui.py
else
    echo "Streamlit not found. Install with: pip install streamlit"
    exit 1
fi
