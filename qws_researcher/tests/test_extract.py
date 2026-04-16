"""Unit tests for PDF text extraction."""
from __future__ import annotations

from unittest.mock import patch

from qws_researcher.extract import MAX_TEXT_CHARS, extract_equations, extract_text

_PAGE_SEP = "\n------\n"


def test_extract_text_basic(tmp_path):
    fake_pdf = tmp_path / "test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake content")

    page_texts = [
        "Page Header\nThis is the introduction.\nPage 1\n",
        "Page Header\nMain content here.\nPage 2\n",
        "Page Header\nMore content.\nPage 3\n",
    ]

    with patch("pymupdf4llm.to_markdown", return_value="\n".join(page_texts)):
        result = extract_text(str(fake_pdf))

    assert "introduction" in result.lower()
    assert "Main content" in result


def test_extract_text_strips_repeated_headers(tmp_path):
    fake_pdf = tmp_path / "test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")

    repeated_header = "Journal of Finance Vol 42"
    page_texts = [
        f"{repeated_header}\nPage content one.\nFooter Text",
        f"{repeated_header}\nPage content two.\nFooter Text",
        f"{repeated_header}\nPage content three.\nFooter Text",
    ]

    with patch("pymupdf4llm.to_markdown", return_value=_PAGE_SEP.join(page_texts)):
        result = extract_text(str(fake_pdf))

    assert repeated_header not in result
    assert "Page content one" in result


def test_extract_text_truncates_references(tmp_path):
    fake_pdf = tmp_path / "test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")

    main_body = "Main body content.\n" * 50
    references_section = "\nReferences\n[1] Smith et al. 2020...\n[2] Jones 2019..."

    # Put references in last 30% — need enough content
    long_body = "A" * 1000
    long_refs = "\nReferences\n" + "B" * 100

    page_texts = [""] * 5
    page_texts[0] = long_body
    page_texts[-1] = long_refs

    with patch("pymupdf4llm.to_markdown", return_value="\n".join(page_texts)):
        result = extract_text(str(fake_pdf))

    assert "BBBB" not in result


def test_extract_text_caps_at_50k_chars(tmp_path):
    fake_pdf = tmp_path / "test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")

    huge_page = "x " * 30000  # ~60k chars
    page_texts = [huge_page]

    with patch("pymupdf4llm.to_markdown", return_value="\n".join(page_texts)):
        result = extract_text(str(fake_pdf))

    assert len(result) <= MAX_TEXT_CHARS


def test_extract_text_returns_empty_on_unreadable_file(tmp_path):
    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_bytes(b"not a pdf")

    with patch("pymupdf4llm.to_markdown", side_effect=Exception("Invalid PDF")):
        result = extract_text(str(bad_pdf))

    assert result == ""


def test_extract_equations_finds_inline_math():
    text = "The model is $\\sigma^2_t = \\alpha + \\beta r^2_{t-1}$ which is standard."
    equations = extract_equations(text)
    assert any("sigma" in eq or "alpha" in eq for eq in equations)


def test_extract_equations_finds_display_math():
    text = "We derive:\n$$r_t = \\mu + \\sigma_t \\epsilon_t$$\nwhere epsilon is iid."
    equations = extract_equations(text)
    assert len(equations) >= 1
    assert any("mu" in eq or "epsilon" in eq for eq in equations)


def test_extract_equations_deduplicates():
    text = "$x = y$ and again $x = y$ appears twice."
    equations = extract_equations(text)
    assert equations.count("x = y") <= 1


def test_extract_equations_returns_empty_for_plain_text():
    text = "This paper studies stock markets. We find that volatility is high."
    equations = extract_equations(text)
    # Should not pick up normal sentences
    assert all("=" not in eq or len(eq) < 5 for eq in equations)
