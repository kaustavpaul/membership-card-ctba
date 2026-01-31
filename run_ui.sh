#!/bin/bash
# Launch the Streamlit UI

cd "$(dirname "$0")"

if [ -d "venv" ]; then
    source venv/bin/activate
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

streamlit run ui.py
