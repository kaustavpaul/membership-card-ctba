import re


def safe_pdf_filename(name: str) -> str:
    """
    Convert a display name into a safe PDF filename.
    - Uses only letters/numbers/spaces/_/-
    - Collapses whitespace to underscores
    - Falls back to 'member.pdf'
    """
    raw = "" if name is None else str(name)
    safe = re.sub(r"[^A-Za-z0-9 _-]+", "", raw).strip()
    safe = re.sub(r"\s+", "_", safe)
    if not safe:
        safe = "member"
    return f"{safe}.pdf"

