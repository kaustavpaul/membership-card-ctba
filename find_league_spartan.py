#!/usr/bin/env python3
"""Helper script to find League Spartan font"""

import os
from pathlib import Path

def find_league_spartan():
    """Find League Spartan font files"""
    search_paths = [
        os.path.expanduser("~/Library/Fonts"),
        "/Library/Fonts",
        "/System/Library/Fonts",
        "/System/Library/Fonts/Supplemental",
        os.path.expanduser("~/Downloads"),
    ]
    
    found_fonts = []
    for search_path in search_paths:
        if os.path.exists(search_path):
            for root, dirs, files in os.walk(search_path):
                for file in files:
                    if 'league' in file.lower() and 'spartan' in file.lower():
                        full_path = os.path.join(root, file)
                        found_fonts.append(full_path)
    
    return found_fonts

if __name__ == '__main__':
    print("Searching for League Spartan font...\n")
    fonts = find_league_spartan()
    
    if fonts:
        print(f"Found {len(fonts)} League Spartan font file(s):\n")
        for font in fonts:
            print(f"  ✓ {font}")
    else:
        print("❌ League Spartan font not found in standard locations.")
        print("\nIf you downloaded it, please:")
        print("1. Double-click the font file to install it, OR")
        print("2. Copy it to ~/Library/Fonts/ directory")
        print("\nThe app will search for it automatically once installed.")
