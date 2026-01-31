#!/usr/bin/env python3
"""List available fonts on the system"""

import os
from pathlib import Path

def find_fonts():
    """Find available TrueType fonts"""
    font_paths = [
        "/System/Library/Fonts",
        "/System/Library/Fonts/Supplemental",
        "/Library/Fonts",
        os.path.expanduser("~/Library/Fonts"),
    ]
    
    fonts = []
    for font_dir in font_paths:
        if os.path.exists(font_dir):
            for file in os.listdir(font_dir):
                if file.endswith(('.ttf', '.otf', '.ttc')):
                    full_path = os.path.join(font_dir, file)
                    fonts.append(full_path)
    
    return sorted(fonts)

if __name__ == '__main__':
    print("Available fonts on your system:\n")
    fonts = find_fonts()
    for i, font in enumerate(fonts, 1):
        print(f"{i}. {os.path.basename(font)}")
        print(f"   Path: {font}\n")
    
    print(f"\nTotal: {len(fonts)} fonts found")
