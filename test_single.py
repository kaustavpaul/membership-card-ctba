#!/usr/bin/env python3
"""Test script to generate a single card for testing."""

import tempfile
from pathlib import Path

from app import MembershipCardGenerator

# Test with a single member
csv_content = """Name,Member_ID
Kaustav Paul,CTBA2026KPkaustavmyselfGMA"""

# Create temp CSV (secure temp file; ignore user-provided names)
with tempfile.NamedTemporaryFile(mode="w", prefix="test_member_", suffix=".csv", delete=False) as tmp:
    tmp.write(csv_content)
    temp_csv = tmp.name

# Prefer banner.png, fallback to project banner
script_dir = Path(__file__).resolve().parent
banner_path = script_dir / "input" / "banner.png"
if not banner_path.exists():
    banner_path = script_dir / "input" / "Central Texas Bengali Association Banner.png"
output_dir = "output"

if banner_path.exists():
    generator = MembershipCardGenerator(temp_csv, str(banner_path), output_dir)
    generator.generate_all_cards()
    print(f"\n✓ Test successful! Check '{output_dir}' directory for the generated card.")
else:
    print("✗ No banner found (banner.png or Central Texas Bengali Association Banner.png)")
