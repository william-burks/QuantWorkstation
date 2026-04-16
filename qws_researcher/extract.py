from __future__ import annotations

import re
from collections import Counter

MAX_TEXT_CHARS = 50_000


def extract_text(pdf_path: str) -> str:
    """
    Extract clean text from a PDF file using pymupdf4llm (markdown output).
    - Strips repeated header/footer lines
    - Truncates at References section (only searched in last 30% of doc)
    - Normalizes whitespace
    - Caps at 50,000 characters
    """
    try:
        import pymupdf4llm  # noqa: PLC0415
        raw = pymupdf4llm.to_markdown(pdf_path)
    except Exception:
        return ""

    if not raw:
        return ""

    # Split into page-like chunks by markdown horizontal rules (pymupdf4llm uses ------)
    pages_text = re.split(r"\n-{6,}\n", raw)
    if not pages_text:
        return ""

    # Identify repeated header/footer lines (appear on >= 3 pages)
    line_page_count: Counter[str] = Counter()
    for page_text in pages_text:
        lines = page_text.splitlines()
        if not lines:
            continue
        candidates = set(lines[:3] + lines[-3:])
        for line in candidates:
            stripped = line.strip()
            if stripped and len(stripped) < 200:
                line_page_count[stripped] += 1

    repeated_lines = {line for line, count in line_page_count.items() if count >= 3}

    cleaned_pages = []
    for page_text in pages_text:
        lines = page_text.splitlines()
        kept = [ln for ln in lines if ln.strip() not in repeated_lines]
        cleaned_pages.append("\n".join(kept))

    full_text = "\n\n".join(cleaned_pages)

    # Truncate at References section (search only last 30%)
    cutoff = int(len(full_text) * 0.70)
    refs_tail = full_text[cutoff:]
    refs_match = re.search(r"\n\s*#{0,3}\s*References?\s*\n", refs_tail, re.IGNORECASE)
    if refs_match:
        full_text = full_text[:cutoff + refs_match.start()]

    # Normalize excessive blank lines
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)
    full_text = full_text.strip()

    return full_text[:MAX_TEXT_CHARS]


_MAX_EQ_CHARS = 500

# Named math environments (starred variants included)
_ENV_PATTERN = re.compile(
    r"\\begin\{(equation|align|gather|multline|eqnarray|flalign|alignat)\*?\}"
    r"(.*?)"
    r"\\end\{\1\*?\}",
    re.DOTALL,
)


def _clean_latex_eq(s: str) -> str:
    # Strip LaTeX inline comments: % not preceded by backslash
    s = re.sub(r"(?<!\\)%.*", "", s)
    # Strip metadata commands
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"\\nonumber\b", "", s)
    # Normalize whitespace
    s = re.sub(r"[ \t]+", " ", s)   # collapse horizontal whitespace (preserve newlines)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_equations_from_latex(tex: str) -> list[str]:
    """
    Extract equations from raw LaTeX source.

    Priority order:
    1. Named environments: equation, align, gather, multline, eqnarray (+ starred)
    2. Display math: $$...$$ and \\[...\\]
    3. Inline math: $...$ (4–200 chars, skips trivial one-symbol fragments)

    Returns deduplicated list capped at _MAX_EQ_CHARS per equation.
    """
    equations: list[str] = []

    # Named environments
    for m in _ENV_PATTERN.finditer(tex):
        content = _clean_latex_eq(m.group(2))
        if content:
            equations.append(content)

    # Display math: $$...$$ and \[...\]
    for m in re.finditer(r"\$\$(.+?)\$\$", tex, re.DOTALL):
        content = _clean_latex_eq(m.group(1))
        if content:
            equations.append(content)

    for m in re.finditer(r"\\\[(.+?)\\\]", tex, re.DOTALL):
        content = _clean_latex_eq(m.group(1))
        if content:
            equations.append(content)

    # Inline math: $...$
    for m in re.finditer(r"\$([^$\n]{4,200})\$", tex):
        content = _clean_latex_eq(m.group(1))
        if content:
            equations.append(content)

    # Deduplicate, cap length
    seen: set[str] = set()
    result = []
    for eq in equations:
        if eq not in seen and len(eq) <= _MAX_EQ_CHARS:
            seen.add(eq)
            result.append(eq)

    return result


def extract_equations(text: str) -> list[str]:
    """
    Extract LaTeX-like equation strings from text using heuristics.
    Returns deduplicated list.
    """
    equations: list[str] = []

    # Inline and display math: $...$ and $$...$$
    display_math = re.findall(r"\$\$(.+?)\$\$", text, re.DOTALL)
    equations.extend(eq.strip() for eq in display_math if eq.strip())

    inline_math = re.findall(r"\$([^$\n]{3,100})\$", text)
    equations.extend(eq.strip() for eq in inline_math if eq.strip())

    # Lines containing = with mathematical symbols
    math_symbols = re.compile(r"[∑∏∫∂∇α-ωΑ-Ω×÷±≤≥≠∞√~^]|\\[a-z]+\{")
    for line in text.splitlines():
        line = line.strip()
        if "=" in line and math_symbols.search(line) and 5 < len(line) < 300:
            equations.append(line)

    # Deduplicate preserving order
    seen: set[str] = set()
    result = []
    for eq in equations:
        if eq not in seen:
            seen.add(eq)
            result.append(eq)

    return result
