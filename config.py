"""
Central configuration for membership-card.

Keep runtime-safe (no secrets).
"""

# UI
MAX_INDIVIDUAL_DOWNLOADS = 10  # <= this: individual PDF downloads + previews; > this: ZIP download
ZIP_SPOOL_MAX_BYTES = 25 * 1024 * 1024  # spill ZIP to disk after ~25MB

PREVIEW_COLUMNS_DESKTOP = 5
PREVIEW_COLUMNS_MOBILE = 2
PREVIEW_WIDTH_DESKTOP = 170
PREVIEW_WIDTH_MOBILE = 200

# Card rendering
CARD_FONT_SIZE = 24
NAME_TO_MEMBER_GAP_PX = 55
