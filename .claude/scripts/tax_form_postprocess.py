#!/usr/bin/env python3
"""
Post-processor for IRS tax form PDFs converted to markdown.
Adds markdown structure (headings, bold, frontmatter) so entity_extractor.py
can pick up meaningful entities from raw form text.

Detects:
- Schedule headers (Schedule K-1, Schedule B, etc.) -> ## headings
- Form section labels -> ## headings
- Labeled dollar amounts -> **bold label:** $amount
- Key IRS line items -> bold

Usage:
    from tax_form_postprocess import postprocess_tax_markdown
    structured = postprocess_tax_markdown(raw_markdown, source_filename)
"""

import re
from pathlib import Path
from datetime import date


# IRS form section patterns -> markdown headings
SECTION_PATTERNS = [
    (r"^(Schedule\s+[A-Z0-9\-]+(?:\s+\([^)]+\))?)\s*$", r"## \1"),
    (r"^(Form\s+\d+[A-Z]?\s+\(\d{4}\)[^\n]*?)$", r"## \1"),
    (r"^(Part\s+[IVX]+[\s\.:]+[A-Z][^\n]{3,60})$", r"## \1"),
    (r"^(Section\s+\d+[^\n]{0,60})$", r"## \1"),
]

# Key IRS line items to bold (label: amount pattern)
BOLD_LINE_PATTERNS = [
    # Gross receipts / income lines
    r"(Gross receipts or sales)[^\n]*?(\$?[\d,]+\.?\d*)",
    r"(Ordinary business income[^\n]*?)(\$?[\d,]+\.?\d*)",
    r"(Total income[^\n]*?)(\$?[\d,]+\.?\d*)",
    r"(Gross profit[^\n]*?)(\$?[\d,]+\.?\d*)",
    # Deduction lines
    r"(Total deductions[^\n]*?)(\$?[\d,]+\.?\d*)",
    r"(Other deductions[^\n]*?)(\$?[\d,]+\.?\d*)",
    r"(Rent[^\n]{0,30})(\$?[\d,]+\.?\d*)",
    r"(Repairs and maintenance[^\n]*?)(\$?[\d,]+\.?\d*)",
    r"(Salaries and wages[^\n]*?)(\$?[\d,]+\.?\d*)",
    r"(Guaranteed payments[^\n]*?)(\$?[\d,]+\.?\d*)",
    r"(Interest[^\n]{0,30})(\$?[\d,]+\.?\d*)",
    r"(Depreciation[^\n]*?)(\$?[\d,]+\.?\d*)",
    r"(Retirement plans[^\n]*?)(\$?[\d,]+\.?\d*)",
    # K-1 boxes
    r"(Ordinary business income \(loss\)[^\n]*?)(\$?-?[\d,]+\.?\d*)",
    r"(Net rental real estate income[^\n]*?)(\$?-?[\d,]+\.?\d*)",
    r"(Self-employment earnings[^\n]*?)(\$?-?[\d,]+\.?\d*)",
    r"(Partner's share[^\n]{0,40})(\$?[\d,]+\.?\d*)",
    r"(Distributive share[^\n]{0,40})(\$?[\d,]+\.?\d*)",
    # Entity info
    r"(Employer identification number)[^\n]*?(\d{2}-\d{7})",
    r"(EIN)[:\s]+(\d{2}-\d{7})",
]

# Known entity names to extract from tax forms -> create wikilink references
ENTITY_KEYWORDS = [
    "Road Shield LLC",
    "Road Shield",
    "Freeway Insurance",
    "CONFIE",
    "Schedule K-1",
    "Form 1065",
    "Schedule E",
    "Schedule C",
    "Schedule SE",
    "Section 199A",
    "QBI",
    "self-employment",
    "ordinary business income",
    "guaranteed payments",
    "home office",
    "partnership",
    "S corporation",
    "S-Corp",
]


def detect_form_type(text: str) -> str:
    """Detect the IRS form type from text."""
    text_lower = text.lower()
    if "schedule k-1" in text_lower and "1065" in text:
        return "Schedule K-1 (Form 1065)"
    if "form 1065" in text_lower:
        return "Form 1065 Partnership Return"
    if "schedule k-1" in text_lower and "1120" in text:
        return "Schedule K-1 (Form 1120-S)"
    if "form 1040" in text_lower:
        return "Form 1040 Individual Return"
    if "form 1120" in text_lower:
        return "Form 1120-S S-Corp Return"
    return "Tax Document"


def extract_entity_name(text: str) -> str:
    """Try to extract the entity/taxpayer name from form text."""
    patterns = [
        r"Name of partnership\s+([A-Za-z][A-Za-z\s]+LLC|[A-Za-z][A-Za-z\s]+Inc|[A-Za-z][A-Za-z\s]+Corp)",
        r"(Road Shield LLC)",
        r"Partner's name.*?\n([A-Z][A-Za-z\s,]+)\n",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def extract_tax_year(text: str) -> str:
    """Extract tax year from form text."""
    m = re.search(r"calendar year (\d{4})", text, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"For tax year (\d{4})", text, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"\b(202[0-9])\b", text)
    if m:
        return m.group(1)
    return ""


def add_section_headings(text: str) -> str:
    """Convert IRS schedule/section labels to markdown headings."""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        converted = False
        for pattern, replacement in SECTION_PATTERNS:
            if re.match(pattern, stripped, re.IGNORECASE):
                result.append(re.sub(pattern, replacement, stripped, flags=re.IGNORECASE))
                converted = True
                break
        if not converted:
            result.append(line)
    return "\n".join(result)


def bold_key_figures(text: str) -> str:
    """Bold important labeled dollar amounts."""
    for pattern in BOLD_LINE_PATTERNS:
        def replacer(m):
            return f"**{m.group(1).strip()}:** {m.group(2).strip()}"
        text = re.sub(pattern, replacer, text, flags=re.IGNORECASE)
    return text


def build_frontmatter(text: str, source_filename: str) -> str:
    """Build YAML frontmatter with detected metadata and entity references."""
    form_type = detect_form_type(text)
    entity_name = extract_entity_name(text)
    tax_year = extract_tax_year(text)

    # Build related list from detected entity keywords
    found_entities = []
    for kw in ENTITY_KEYWORDS:
        if kw.lower() in text.lower():
            slug = kw.upper().replace(" ", "-").replace("(", "").replace(")", "")
            found_entities.append(f'  - "[[{slug}]]"')

    related_block = "\n".join(found_entities) if found_entities else '  - "[[]]"'

    tags = ["document", "tax"]
    if "k-1" in form_type.lower():
        tags.append("income")
        tags.append("partnership")
    if "1065" in form_type:
        tags.append("partnership")
    if "1040" in form_type:
        tags.append("income")

    summary = f"{form_type}"
    if entity_name:
        summary += f" — {entity_name}"
    if tax_year:
        summary += f" ({tax_year})"

    fm = f"""---
tags: [{", ".join(tags)}]
status: reference
date: {date.today()}
tax_year: "{tax_year}"
form_type: "{form_type}"
entity: "{entity_name}"
related:
{related_block}
summary: "{summary}"
---

"""
    return fm


def postprocess_tax_markdown(raw_markdown: str, source_filename: str = "") -> str:
    """Full post-processing pipeline: frontmatter + headings + bold figures."""
    # Strip existing title line (# filename)
    lines = raw_markdown.split("\n")
    title_line = lines[0] if lines and lines[0].startswith("# ") else ""
    body = "\n".join(lines[1:]) if title_line else raw_markdown

    # Apply transformations
    body = add_section_headings(body)
    body = bold_key_figures(body)

    # Build frontmatter
    fm = build_frontmatter(raw_markdown, source_filename)

    # Reconstruct: frontmatter + original title + body
    return fm + title_line + "\n" + body


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: tax_form_postprocess.py <converted.md>")
        sys.exit(1)
    path = Path(sys.argv[1])
    raw = path.read_text(encoding="utf-8")
    processed = postprocess_tax_markdown(raw, path.name)
    path.write_text(processed, encoding="utf-8")
    print(f"[ok] Post-processed: {path.name}")
