#!/usr/bin/env python3
"""
Finance vault ingest CLI.
One command: PDF/markdown → parsed → placed → entity compiled → linted.

Usage:
    uv run python finance_ingest.py "file.pdf" --category tax-returns/2024
    uv run python finance_ingest.py "folder/" --category bank-statements/personal
    uv run python finance_ingest.py "file.pdf" --category research/irs-publications --dry-run
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from entity_extractor import preserve_raw
from tax_form_postprocess import postprocess_tax_markdown

FINANCE_VAULT = Path(r"C:\Users\YourUser\finance-vault")
SCRIPTS_DIR = Path(__file__).parent

VALID_CATEGORIES = [
    "tax-returns/2024",
    "bank-statements/personal",
    "bank-statements/business",
    "income/k1-YourCompany",
    "income/franchise-revenue",
    "business-expenses/home-office",
    "business-expenses/retail-office",
    "business-expenses/franchise-fees",
    "business-expenses/software",
    "research/irs-publications",
    "research/tax-strategies",
    "research/scorp-playbook",
]


def resolve_target_dir(category: str) -> Path:
    if category.startswith("research/"):
        return FINANCE_VAULT / category
    return FINANCE_VAULT / "documents" / category


def convert_pdf(pdf_path: Path) -> Path:
    """Convert PDF to markdown using pdf_to_markdown.py."""
    script = SCRIPTS_DIR / "pdf_to_markdown.py"
    md_path = pdf_path.with_suffix(".md")
    result = subprocess.run(
        ["uv", "run", "python", str(script), str(pdf_path)],
        cwd=SCRIPTS_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PDF conversion failed:\n{result.stderr}")
    return md_path


def compile_entities(md_path: Path) -> str:
    """Run entity compilation on a markdown file."""
    result = subprocess.run(
        [
            "uv", "run", "python",
            str(SCRIPTS_DIR / "entity_extractor.py"),
            "compile", str(md_path),
            "--vault-dir", str(FINANCE_VAULT),
        ],
        cwd=SCRIPTS_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"warning: {result.stderr[:300]}"
    return result.stdout.strip()


def run_lint():
    """Run vault lint, surface errors only."""
    result = subprocess.run(
        [
            "uv", "run", "python",
            str(SCRIPTS_DIR / "vault_lint.py"),
            "--vault-dir", str(FINANCE_VAULT),
        ],
        cwd=SCRIPTS_DIR,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    error_lines = [l for l in output.splitlines() if "ERROR" in l or "error" in l.lower()]
    if error_lines:
        print("  [!] Lint errors:")
        for line in error_lines[:5]:
            print(f"    {line}")
    else:
        print("  [ok] Lint clean")


def count_concepts() -> int:
    concepts_dir = FINANCE_VAULT / "concepts"
    if not concepts_dir.exists():
        return 0
    return len([f for f in concepts_dir.glob("*.md") if f.name not in ("INDEX.md", "BUILD-LOG.md")])


def ingest_file(source: Path, category: str, dry_run: bool = False):
    """Ingest a single file into the finance vault."""
    target_dir = resolve_target_dir(category)
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n>> {source.name}")

    # Step 1: Preserve raw original — canonical Karpathy raw/ pattern via
    # entity_extractor.preserve_raw (always_date_prefix=True matches the
    # legacy finance_ingest semantics: bank statements reuse names daily).
    if not dry_run:
        raw_dest = preserve_raw(source, FINANCE_VAULT, always_date_prefix=True)
        print(f"  [ok] Raw preserved -> raw/{raw_dest.name}")
    else:
        from datetime import date as _date
        print(f"  [dry-run] raw/{_date.today()}-{source.name}")

    # Step 2: Convert PDF if needed
    if source.suffix.lower() == ".pdf":
        print(f"  Converting PDF...")
        if not dry_run:
            try:
                md_path = convert_pdf(source)
                # Post-process tax forms to add markdown structure + frontmatter
                if any(cat in category for cat in ("tax-return", "income", "k1")):
                    raw = md_path.read_text(encoding="utf-8")
                    processed = postprocess_tax_markdown(raw, source.name)
                    md_path.write_text(processed, encoding="utf-8")
                    print(f"  [ok] Converted + structured -> {md_path.name}")
                else:
                    print(f"  [ok] Converted -> {md_path.name}")
            except RuntimeError as e:
                print(f"  [err] {e}")
                return
        else:
            md_path = source.with_suffix(".md")
            print(f"  [dry-run] Would convert -> {md_path.name}")
    else:
        md_path = source

    # Step 3: Place in vault
    dest = target_dir / md_path.name
    if not dry_run:
        shutil.copy2(md_path, dest)
        print(f"  [ok] Placed -> {dest.relative_to(FINANCE_VAULT)}")
    else:
        print(f"  [dry-run] Would place -> {dest.relative_to(FINANCE_VAULT)}")
        return

    # Step 4: Compile entities
    print(f"  Compiling entities...")
    concepts_before = count_concepts()
    out = compile_entities(dest)
    concepts_after = count_concepts()
    created = concepts_after - concepts_before
    print(f"  [ok] Entity compilation done ({created:+d} concept pages)")
    if out and created == 0:
        # Show first meaningful output line
        for line in out.splitlines():
            if line.strip():
                print(f"    {line.strip()}")
                break

    # Step 5: Lint
    run_lint()


def main():
    parser = argparse.ArgumentParser(
        description="Finance vault ingest — PDF or markdown → concept pages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Valid categories:\n  " + "\n  ".join(VALID_CATEGORIES),
    )
    parser.add_argument("source", help="PDF file or directory of PDFs/markdown files")
    parser.add_argument(
        "--category",
        required=True,
        help="Target category (see list below)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making changes",
    )
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"Error: {source} not found")
        sys.exit(1)

    if args.category not in VALID_CATEGORIES:
        print(f"Warning: '{args.category}' is not a recognized category.")
        print(f"Valid: {', '.join(VALID_CATEGORIES)}")
        print("Continuing anyway...\n")

    if args.dry_run:
        print("DRY RUN — no files will be modified\n")

    if source.is_dir():
        files = list(source.glob("*.pdf")) + list(source.glob("*.md"))
        if not files:
            print(f"No PDF or markdown files found in {source}")
            sys.exit(1)
        print(f"Found {len(files)} file(s) in {source}")
        for f in sorted(files):
            ingest_file(f, args.category, args.dry_run)
    else:
        ingest_file(source, args.category, args.dry_run)

    if not args.dry_run:
        total = count_concepts()
        print(f"\n[ok] Done. Finance vault concept pages: {total}")
        print(f"  Vault: {FINANCE_VAULT}")

        # Regenerate index
        subprocess.run(
            ["uv", "run", "python", str(SCRIPTS_DIR / "entity_extractor.py"),
             "index", "--vault-dir", str(FINANCE_VAULT)],
            cwd=SCRIPTS_DIR,
            capture_output=True,
        )
        print(f"  ✓ Index regenerated")


if __name__ == "__main__":
    main()
