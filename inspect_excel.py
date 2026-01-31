#!/usr/bin/env python3
"""Print column names and a few rows from the Excel 'Form Responses 1' sheet."""

from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("Run: pip install pandas openpyxl")
    raise

p = Path(__file__).resolve().parent / "input" / "template_members.csv"
if not p.exists():
    print(f"Not found: {p}")
    exit(1)
df = pd.read_csv(p)
print("Columns:")
for i, c in enumerate(df.columns):
    print(f"  {i} {repr(c)}")
print("\nFirst 2 rows (first 4 cols):")
print(df.iloc[:2, :4].to_string())
