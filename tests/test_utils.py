from utils import safe_pdf_filename


def test_safe_pdf_filename_basic():
    assert safe_pdf_filename("John Doe") == "John_Doe.pdf"


def test_safe_pdf_filename_strips_weird_chars():
    assert safe_pdf_filename("  A/B:C*D?  ") == "ABCD.pdf"


def test_safe_pdf_filename_empty_fallback():
    assert safe_pdf_filename("") == "member.pdf"
    assert safe_pdf_filename("   ") == "member.pdf"

