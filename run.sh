#!/bin/bash
# Helper script to run the membership card generator

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtual environment if it exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Default data: use safe template committed to repo
DATA_DEFAULT="$SCRIPT_DIR/input/template_members.csv"

BANNER_DEFAULT="$SCRIPT_DIR/input/banner.png"
[ -f "$BANNER_DEFAULT" ] || BANNER_DEFAULT="$SCRIPT_DIR/input/Central Texas Bengali Association Banner.png"

DATA_FILE="${1:-$DATA_DEFAULT}"
BANNER_FILE="${2:-$BANNER_DEFAULT}"
OUTPUT_DIR="${3:-output}"

if [ ! -f "$DATA_FILE" ]; then
    echo "Error: Data file not found: $DATA_FILE"
    echo "Usage: $0 [excel_or_csv] [banner] [output_dir]"
    exit 1
fi
if [ ! -f "$BANNER_FILE" ]; then
    echo "Error: Banner not found: $BANNER_FILE"
    exit 1
fi

python3 app.py "$DATA_FILE" "$BANNER_FILE" -o "$OUTPUT_DIR"
