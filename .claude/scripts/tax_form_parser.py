#!/usr/bin/env python3
"""
Dedicated IRS tax form parser for the finance vault.
Reads Form 1065 and Schedule K-1 line items directly from converted markdown,
then writes real claims into concept pages — bypassing the generic heuristic extractor.

Usage:
    uv run python tax_form_parser.py <path/to/doc.md> --vault-dir <vault>
    uv run python tax_form_parser.py --all --vault-dir <vault>   # parse all k1-YourCompany docs
"""

import re
import sys
import argparse
from pathlib import Path
from datetime import date

# Boot-shim: must run BEFORE any framework imports (config, runtime, etc.)
from personas import apply_persona_override

apply_persona_override()

FINANCE_VAULT = Path(r"C:\Users\YourUser\finance-vault")
CONCEPTS_DIR = FINANCE_VAULT / "concepts"

# ---------------------------------------------------------------------------
# Form 1065 line item patterns
# ---------------------------------------------------------------------------
FORM_1065_PATTERNS = [
    ("gross_receipts",    r"1\s*[abc][^0-9]*([\d,]+)\.",                "Gross receipts/sales (Form 1065 Line 1c)"),
    ("gross_profit",      r"(?:Gross profit)[^0-9]{0,40}3\s+([\d,]+)\.", "Gross profit (Line 3)"),
    ("total_income",      r"(?:Total income)[^0-9]{0,60}8\s+([\d,]+)\.", "Total income (Line 8)"),
    ("repairs",           r"11\s+([\d,]+)\.",                            "Repairs & maintenance (Line 11)"),
    ("rent",              r"13\s+([\d,]+)\.",                            "Rent expense (Line 13)"),
    ("other_deductions",  r"21\s+([\d,]+)\.",                            "Other deductions (Line 21)"),
    ("total_deductions",  r"22\s+([\d,]+)\.",                            "Total deductions (Line 22)"),
    ("ordinary_income",   r"23\s+([\d,]+)\.",                            "Ordinary business income (Line 23)"),
]

# ---------------------------------------------------------------------------
# Schedule K-1 box patterns
# ---------------------------------------------------------------------------
K1_BOX_PATTERNS = [
    ("box1_income",   r"(?:Ordinary business income)[^0-9\-]{0,30}(-?[\d,]+)\.",  "Box 1: Ordinary business income (loss)"),
    ("box14a",        r"A\s+([\d,]+)\.",                                           "Box 14A: Net earnings from self-employment"),
    ("box14c",        r"C\s+([\d,]+)\.",                                           "Box 14C: Gross farming/fishing income (SE)"),
    ("profit_pct",    r"Profit\s+([\d.]+)\s*%",                                    "Partner profit share %"),
    ("loss_pct",      r"Loss\s+([\d.]+)\s*%",                                      "Partner loss share %"),
    ("capital_pct",   r"Capital\s+([\d.]+)\s*%",                                   "Partner capital share %"),
]

# ---------------------------------------------------------------------------
# Entity extraction patterns
# ---------------------------------------------------------------------------
ENTITY_PATTERNS = {
    "partnership_name": r"(Road Shield LLC)",
    "ein":              r"(\d{2}-\d{7})",
    "address":          r"(500 S Rancho Santa Fe Rd[^\n]+)",
    "city_state":       r"(San Marcos, CA \d+)",
    "date_started":     r"(\d{2}/\d{2}/\d{4})",
    "partner_name_oscar": r"(the operator\s+Rosas)",
    "partner_name_owner": r"(owner\s+[A-Z])",
    "tax_year":         r"calendar year (\d{4})",
    "num_partners":     r"Number of Schedules K-1[^0-9]+(\d+)",
    "accounting_method": r"Cash",
}


def extract_amount(text: str, patterns: list) -> dict:
    """Extract amounts from form text using pattern list."""
    results = {}
    for key, pattern, label in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            raw = m.group(1).replace(",", "").strip()
            try:
                val = float(raw)
                results[key] = {"value": val, "label": label, "raw": m.group(1)}
            except ValueError:
                pass
    return results


def detect_form_type(text: str) -> str:
    if "Form  1065" in text or "U.S. Return of Partnership Income" in text:
        return "form_1065"
    if "Schedule" in text and "K-1" in text and "Partner" in text:
        return "schedule_k1"
    return "unknown"


def detect_partner_name(text: str) -> str:
    for name in ["the operator Rosas", "owner"]:
        if name.lower() in text.lower():
            return name
    return "Partner"


def read_concept(slug: str) -> tuple[Path, str]:
    """Read an existing concept page or return empty string."""
    path = CONCEPTS_DIR / f"{slug}.md"
    if path.exists():
        return path, path.read_text(encoding="utf-8")
    return path, ""


def section_exists(content: str, source_stem: str) -> bool:
    """Check if a From [[source]] section already exists."""
    return f"## From [[{source_stem}]]" in content


def append_claims_section(content: str, source_stem: str, claims: list[str]) -> str:
    """Append a new From [[source]] section to a concept page."""
    today = date.today().isoformat()
    section = f"\n## From [[{source_stem}]] ({today})\n\n"
    section += "\n".join(f"- {c}" for c in claims)
    section += "\n"

    if content.strip():
        return content.rstrip() + "\n" + section
    return content + section


def replace_claims_section(content: str, source_stem: str, claims: list[str]) -> str:
    """Replace an existing From [[source]] section with updated claims."""
    today = date.today().isoformat()
    new_section = f"## From [[{source_stem}]] ({today})\n\n"
    new_section += "\n".join(f"- {c}" for c in claims)
    new_section += "\n"

    pattern = rf"## From \[\[{re.escape(source_stem)}\]\][^\n]*\n.*?(?=\n## |\Z)"
    replaced = re.sub(pattern, new_section, content, flags=re.DOTALL)
    if replaced == content:
        return append_claims_section(content, source_stem, claims)
    return replaced


def write_claims_to_concept(slug: str, source_stem: str, claims: list[str], summary: str = "") -> bool:
    """Write or update claims in a concept page."""
    path, content = read_concept(slug)

    if not content:
        # Create minimal concept page
        today = date.today().isoformat()
        content = f"""---
aliases: ["{slug.replace('-', ' ').title()}"]
tags: [concept, auto-compiled, taxconcept]
status: current
date: {today}
summary: "{summary or slug}"
compiled_from:
  - "[[{source_stem}]]"
---

# {slug.replace('-', ' ').title()}

"""

    if section_exists(content, source_stem):
        content = replace_claims_section(content, source_stem, claims)
    else:
        content = append_claims_section(content, source_stem, claims)

    path.write_text(content, encoding="utf-8")
    return True


def parse_form_1065(text: str, source_stem: str) -> dict:
    """Parse Form 1065 and write claims to concept pages."""
    amounts = extract_amount(text, FORM_1065_PATTERNS)
    updates = {}

    # Extract entity metadata
    ein_m = re.search(r"(\d{2}-\d{7})", text)
    ein = ein_m.group(1) if ein_m else "unknown"

    addr_m = re.search(r"(500 S Rancho Santa Fe Rd[^\n,]+)", text)
    addr = addr_m.group(1).strip() if addr_m else ""

    year_m = re.search(r"calendar year (\d{4})", text, re.IGNORECASE)
    tax_year = year_m.group(1) if year_m else "2024"

    partners_m = re.search(r"Number of Schedules K-1[^0-9]+(\d+)", text)
    num_partners = int(partners_m.group(1)) if partners_m else 2

    per_partner = None
    if "ordinary_income" in amounts:
        per_partner = amounts["ordinary_income"]["value"] / num_partners

    # --- ROAD-SHIELD-LLC concept page ---
    claims = [
        f"**Entity:** Road Shield LLC, EIN {ein}",
        f"**Business:** Auto Insurance Brokerage (Freeway Insurance franchise)",
        f"**Address:** {addr}, San Marcos, CA 92078" if addr else "**Address:** San Marcos, CA",
        f"**Date started:** March 16, 2023",
        f"**Partners:** {num_partners} (50/50 split)",
        f"**Accounting method:** Cash basis",
        f"**Tax year:** {tax_year}",
    ]
    if "ordinary_income" in amounts:
        claims.append(f"**{tax_year} ordinary business income:** ${amounts['ordinary_income']['value']:,.0f}")
    if "gross_receipts" in amounts:
        claims.append(f"**{tax_year} gross receipts:** ${amounts['gross_receipts']['value']:,.0f}")
    write_claims_to_concept("ROAD-SHIELD-LLC", source_stem, claims,
                            "Road Shield LLC — Freeway Insurance franchise, 50/50 partnership")
    updates["ROAD-SHIELD-LLC"] = len(claims)

    # --- ORDINARY-BUSINESS-INCOME concept page ---
    if "ordinary_income" in amounts:
        oi = amounts["ordinary_income"]["value"]
        claims = [
            f"**Road Shield LLC {tax_year} ordinary business income:** ${oi:,.0f} (Form 1065 Line 23)",
            f"**Per partner (50%):** ${per_partner:,.0f}" if per_partner else "",
            f"**Calculation:** Total income ${amounts['total_income']['value']:,.0f} - Total deductions ${amounts['total_deductions']['value']:,.0f} = ${oi:,.0f}" if "total_income" in amounts and "total_deductions" in amounts else "",
            f"**Flows to:** Each partner's personal Form 1040 via Schedule E (K-1 Box 1)",
            f"**SE tax applies:** Yes — partnership income is subject to self-employment tax (15.3% on net earnings)",
        ]
        claims = [c for c in claims if c]
        write_claims_to_concept("ORDINARY-BUSINESS-INCOME", source_stem, claims,
                                "Partnership ordinary business income — Road Shield LLC 2024")
        updates["ORDINARY-BUSINESS-INCOME"] = len(claims)

    # --- GROSS-RECEIPTS-OR-SALES concept page ---
    if "gross_receipts" in amounts:
        gr = amounts["gross_receipts"]["value"]
        claims = [
            f"**Road Shield LLC {tax_year} gross receipts:** ${gr:,.0f}",
            f"**No cost of goods sold** — insurance brokerage, pure service business",
            f"**Gross profit = Gross receipts** (${gr:,.0f})",
        ]
        write_claims_to_concept("GROSS-RECEIPTS-OR-SALES", source_stem, claims,
                                "Road Shield LLC gross receipts — 2024 Form 1065")
        updates["GROSS-RECEIPTS-OR-SALES"] = len(claims)

    # --- RETAIL-OFFICE-SPACE concept page ---
    if "rent" in amounts:
        rent = amounts["rent"]["value"]
        claims = [
            f"**{tax_year} rent expense (Line 13):** ${rent:,.0f}",
            f"**Location:** 500 S Rancho Santa Fe Rd, Suite 102, San Marcos, CA 92078",
            f"**Fully deductible** as ordinary business expense — retail Freeway Insurance franchise location",
            f"**Note:** This is separate from home office deductions for each partner",
        ]
        write_claims_to_concept("RETAIL-OFFICE-SPACE", source_stem, claims,
                                "Freeway Insurance retail office — Road Shield LLC")
        updates["RETAIL-OFFICE-SPACE"] = len(claims)

    # --- GUARANTEED-PAYMENTS concept page ---
    if "ordinary_income" in amounts:
        claims = [
            f"**{tax_year} guaranteed payments to partners:** $0 (Line 10 — none taken)",
            f"**Note:** Partners took distributions, not guaranteed payments",
            f"**Tax implication:** Guaranteed payments would be ordinary income + SE tax. Distributions are not.",
            f"**2025 S-Corp context:** Must replace with W-2 reasonable salary of $32K-$38K",
        ]
        write_claims_to_concept("GUARANTEED-PAYMENTS", source_stem, claims,
                                "Partner compensation — Road Shield LLC 2024")
        updates["GUARANTEED-PAYMENTS"] = len(claims)

    # --- SELF-EMPLOYMENT concept page ---
    if "ordinary_income" in amounts and per_partner:
        se_tax_net = per_partner * 0.9235  # SE tax is on 92.35% of net earnings
        se_tax_amount = se_tax_net * 0.153  # 15.3% SE tax rate
        se_deduction = se_tax_amount * 0.5  # 50% of SE tax is deductible
        claims = [
            f"**{tax_year} net SE earnings per partner:** ${per_partner:,.0f} (Box 14A on K-1)",
            f"**SE tax base (92.35%):** ${se_tax_net:,.0f}",
            f"**SE tax owed (15.3%):** ~${se_tax_amount:,.0f} per partner",
            f"**SE tax deduction (50% of SE tax):** ~${se_deduction:,.0f} — deductible on Form 1040",
            f"**2025 S-Corp benefit:** Only W-2 salary (~$35K) subject to payroll tax, not distributions",
            f"**Estimated 2025 savings vs partnership:** ~${(per_partner - 35000) * 0.153 * 0.9235:,.0f} per partner in SE tax",
        ]
        write_claims_to_concept("SELF-EMPLOYMENT", source_stem, claims,
                                "Self-employment tax — Road Shield LLC partners 2024")
        updates["SELF-EMPLOYMENT"] = len(claims)

    # --- SECTION-199A / QBI concept page ---
    if "ordinary_income" in amounts and per_partner:
        qbi_deduction = per_partner * 0.20  # 20% QBI deduction (simplified)
        claims = [
            f"**{tax_year} QBI per partner:** ${per_partner:,.0f} (50% of partnership ordinary income)",
            f"**Potential QBI deduction (20%):** ~${qbi_deduction:,.0f} per partner",
            f"**Form:** Deducted on Form 1040 as Section 199A deduction",
            f"**Eligibility:** Insurance brokers qualify as QBI — NOT a specified service trade or business (SSTB)",
            f"**W-2 wage limitation:** May apply if income exceeds thresholds (~$197K single / $394K married 2024)",
        ]
        write_claims_to_concept("QBI", source_stem, claims, "Qualified Business Income — Road Shield LLC")
        write_claims_to_concept("SECTION-199A", source_stem, claims, "Section 199A QBI deduction — Road Shield LLC")
        updates["QBI"] = len(claims)
        updates["SECTION-199A"] = len(claims)

    # --- Other Deductions statement (Line 21 attached schedule) ---
    other_ded = _parse_other_deductions_statement(text, tax_year, source_stem, updates)
    updates.update(other_ded)

    return amounts, updates


# ---------------------------------------------------------------------------
# Other Deductions statement parser (Form 1065 Line 21 attachment)
# ---------------------------------------------------------------------------

_OTHER_DED_PATTERNS = [
    ("accounting",    r"Accounting fees\s+\d+\s+([\d,]+)\.",                   "Accounting fees"),
    ("advertising",   r"Advertising\s+\d+\s+([\d,]+)\.",                       "Advertising"),
    ("amortization",  r"Amortization\s+\d+\s+([\d,]+)\.",                      "Amortization"),
    ("bank_fees",     r"Bank fees\s+\d+\s+([\d,]+)\.",                         "Bank fees"),
    ("cc_fees",       r"Credit card convenience fees\s+\d+\s+([\d,]+)\.",      "Credit card convenience fees"),
    ("insurance",     r"Insurance\s+\d+\s+([\d,]+)\.",                         "Insurance (business)"),
    ("janitorial",    r"Janitorial\s+\d+\s+([\d,]+)\.",                        "Janitorial"),
    ("dues",          r"Professional dues and subscriptions\s+\d+\s+([\d,]+)\.", "Professional dues/subscriptions"),
    ("supplies",      r"Supplies\s+\d+\s+([\d,]+)\.",                          "Supplies"),
    ("telephone",     r"Telephone\s+\d+\s+([\d,]+)\.",                         "Telephone"),
    ("meals",         r"(?:non-entertainment )?meals\s+(?:expense[^0-9]+)?\d+\s+([\d,]+)\.", "Deductible meals (50% limit)"),
    ("utilities",     r"Utilities\s+\d+\s+([\d,]+)\.",                         "Utilities"),
    ("vehicle",       r"Vehicle mileage deduction\s+\d+\s+([\d,]+)\.",         "Vehicle mileage deduction"),
    ("augusta",       r"Home office rental.*?Augusta Rule\s+\d+\s+([\d,]+)\.", "Home office rental — Augusta Rule"),
]


def _parse_other_deductions_statement(text: str, tax_year: str, source_stem: str, updates: dict) -> dict:
    """Parse the attached Other Deductions statement and write to concept pages."""
    exp = extract_amount(text, [(k, p, l) for k, p, l in _OTHER_DED_PATTERNS])
    new_updates = {}

    def _dollar(key):
        return f"${exp[key]['value']:,.0f}" if key in exp else "N/A"

    # --- BUSINESS-EXPENSES master summary ---
    if exp:
        claims = [f"**{tax_year} Form 1065 Line 21 Other Deductions (attached statement):**"]
        for key, _, label in _OTHER_DED_PATTERNS:
            if key in exp:
                claims.append(f"  - {label}: ${exp[key]['value']:,.0f}")
        claims.append(f"**Total Other Deductions (Line 21):** ${sum(v['value'] for v in exp.values()):,.0f}")
        write_claims_to_concept("BUSINESS-EXPENSES", source_stem, claims,
                                "Road Shield LLC 2024 business expense breakdown")
        new_updates["BUSINESS-EXPENSES"] = len(claims)

    # --- BOOKKEEPING-EXPENSES (accounting fees) ---
    if "accounting" in exp:
        claims = [
            f"**{tax_year} accounting fees (Form 1065):** ${exp['accounting']['value']:,.0f}",
            f"**Vendor:** CPA / bookkeeping service (Booxkeeping Corp per 2025 bank statements)",
            f"**Fully deductible** as ordinary business expense",
        ]
        write_claims_to_concept("BOOKKEEPING-EXPENSES", source_stem, claims,
                                "Bookkeeping and accounting fees — Road Shield LLC 2024")
        new_updates["BOOKKEEPING-EXPENSES"] = len(claims)

    # --- ADVERTISING-EXPENSES (new concept page) ---
    if "advertising" in exp:
        claims = [
            f"**{tax_year} advertising expense (Form 1065):** ${exp['advertising']['value']:,.0f}",
            f"**Largest single deductible expense category** after rent",
            f"**Likely includes:** Google Ads, digital marketing for insurance lead gen, franchise-required co-op advertising",
            f"**Fully deductible** — IRS Pub 535, ordinary and necessary business expense",
            f"**Note:** Verify breakdown with CPA — franchise may require minimum advertising spend",
        ]
        write_claims_to_concept("ADVERTISING-EXPENSES", source_stem, claims,
                                "Advertising and marketing expense — Road Shield LLC 2024")
        new_updates["ADVERTISING-EXPENSES"] = len(claims)

    # --- COMMUNICATION-EXPENSES (telephone) ---
    if "telephone" in exp:
        claims = [
            f"**{tax_year} telephone expense (Form 1065):** ${exp['telephone']['value']:,.0f}",
            f"**Vendors:** Vonage (business phone), MetTel (per 2025 bank statements)",
            f"**Fully deductible** — business communications",
        ]
        write_claims_to_concept("COMMUNICATION-EXPENSES", source_stem, claims,
                                "Telephone and communication expense — Road Shield LLC 2024")
        new_updates["COMMUNICATION-EXPENSES"] = len(claims)

    # --- UTILITY-EXPENSES ---
    if "utilities" in exp:
        claims = [
            f"**{tax_year} utilities expense (Form 1065):** ${exp['utilities']['value']:,.0f}",
            f"**Vendor:** SDG&E (San Diego Gas & Electric) per 2025 bank statements",
            f"**Location:** Retail office at 500 S Rancho Santa Fe Rd",
            f"**Fully deductible** as ordinary business expense",
        ]
        write_claims_to_concept("UTILITY-EXPENSES", source_stem, claims,
                                "Utility expense — Road Shield LLC 2024")
        new_updates["UTILITY-EXPENSES"] = len(claims)

    # --- VEHICLE-MILEAGE (new concept page) ---
    if "vehicle" in exp:
        miles_2024 = exp['vehicle']['value'] / 0.67  # 2024 IRS standard rate: $0.67/mile
        claims = [
            f"**{tax_year} vehicle mileage deduction (Form 1065):** ${exp['vehicle']['value']:,.0f}",
            f"**Implied business miles (~$0.67/mile, 2024 rate):** ~{miles_2024:,.0f} miles",
            f"**Method:** IRS standard mileage rate (vs. actual expense method)",
            f"**Documentation required:** Mileage log with dates, destinations, business purpose",
            f"**Qualifying trips:** Client visits, office supply runs, regulatory/licensing errands, banking",
        ]
        write_claims_to_concept("VEHICLE-MILEAGE", source_stem, claims,
                                "Vehicle mileage deduction — Road Shield LLC 2024")
        new_updates["VEHICLE-MILEAGE"] = len(claims)

    # --- AUGUSTA-RULE (new concept page — major strategy) ---
    if "augusta" in exp:
        augusta_amt = exp['augusta']['value']
        days = 14  # Augusta Rule max = 14 days, $16,800 / 14 = $1,200/day
        daily_rate = augusta_amt / days
        claims = [
            f"**{tax_year} Augusta Rule deduction (Form 1065 Line 21):** ${augusta_amt:,.0f}",
            f"**Days rented:** {days} days (maximum allowed under IRC §280A(g))",
            f"**Daily rental rate:** ${daily_rate:,.0f}/day per partner meeting",
            f"**IRS rule (§280A(g)):** Rental income from a personal residence rented for 14 or fewer days per year is EXCLUDED from gross income — no tax owed by the recipient",
            f"**Business deduction:** The partnership deducts the full rental payment as an ordinary business expense",
            f"**Net effect:** ${augusta_amt:,.0f} moves from the business (pre-tax) to the partners (tax-free)",
            f"**Documentation required:** Written rental agreement, market rate substantiation, actual meetings held",
            f"**Caution:** IRS scrutiny is high — must have legitimate business meetings, arms-length rate",
        ]
        write_claims_to_concept("AUGUSTA-RULE", source_stem, claims,
                                "Augusta Rule (IRC §280A(g)) — tax-free home office rental strategy")
        new_updates["AUGUSTA-RULE"] = len(claims)

    # --- FRANCHISE-FEES (bank fees + CC fees are not franchise fees, but check supplies/dues) ---
    if "bank_fees" in exp or "cc_fees" in exp:
        total_bank = (exp.get("bank_fees", {}).get("value", 0) +
                      exp.get("cc_fees", {}).get("value", 0))
        claims = [
            f"**{tax_year} bank fees (Form 1065):** ${_dollar('bank_fees')}",
            f"**{tax_year} credit card convenience fees:** ${_dollar('cc_fees')}",
            f"**Total banking/processing fees:** ${total_bank:,.0f}",
            f"**Fully deductible** as ordinary business expenses",
        ]
        write_claims_to_concept("FRANCHISE-FEES", source_stem, claims,
                                "Banking and processing fees — Road Shield LLC 2024")
        new_updates["FRANCHISE-FEES"] = len(claims)

    return new_updates


def parse_schedule_k1(text: str, source_stem: str, partner_name: str) -> dict:
    """Parse a Schedule K-1 and write partner-specific claims."""
    amounts = extract_amount(text, K1_BOX_PATTERNS)
    updates = {}
    tax_year = "2024"

    year_m = re.search(r"calendar year (\d{4})", text, re.IGNORECASE)
    if year_m:
        tax_year = year_m.group(1)

    if not amounts:
        return amounts, updates

    # --- SCHEDULE-K-1 concept page ---
    claims = [
        f"**{tax_year} K-1 for {partner_name}** (Road Shield LLC, 50% partner)",
    ]
    if "box1_income" in amounts:
        claims.append(f"**Box 1 — Ordinary business income:** ${amounts['box1_income']['value']:,.0f}")
    if "box14a" in amounts:
        claims.append(f"**Box 14A — Net SE earnings:** ${amounts['box14a']['value']:,.0f}")
    if "profit_pct" in amounts:
        claims.append(f"**Profit/Loss/Capital share:** {amounts['profit_pct']['value']:.1f}% each")
    claims.append(f"**Flows to:** Personal Form 1040 Schedule E (passive income) + Schedule SE (SE tax)")
    write_claims_to_concept("SCHEDULE-K-1", source_stem, claims,
                            f"Schedule K-1 — Road Shield LLC {tax_year}")
    updates["SCHEDULE-K-1"] = len(claims)

    # --- PARTNERSHIP concept page ---
    if "box1_income" in amounts:
        claims = [
            f"**{tax_year} partnership structure:** 50/50, Road Shield LLC (Form 1065)",
            f"**{partner_name}'s share of ordinary income:** ${amounts['box1_income']['value']:,.0f}",
            f"**Reported on:** Schedule E of personal Form 1040",
            f"**2025 change:** S-Corp election — partnership return (1065) replaced by Form 1120-S",
        ]
        write_claims_to_concept("PARTNERSHIP", source_stem, claims,
                                "Road Shield LLC partnership structure 2024")
        updates["PARTNERSHIP"] = len(claims)

    return amounts, updates


def parse_document(doc_path: Path, vault_dir: Path) -> None:
    """Main entry point — detect form type and parse."""
    global FINANCE_VAULT, CONCEPTS_DIR
    FINANCE_VAULT = vault_dir
    CONCEPTS_DIR = vault_dir / "concepts"
    CONCEPTS_DIR.mkdir(exist_ok=True)

    text = doc_path.read_text(encoding="utf-8")
    source_stem = doc_path.stem
    form_type = detect_form_type(text)

    print(f"\n>> Parsing: {doc_path.name} ({form_type})")

    if form_type == "form_1065":
        amounts, updates = parse_form_1065(text, source_stem)
        print(f"   Extracted {len(amounts)} line items")
        for concept, count in updates.items():
            print(f"   [ok] {concept}.md — {count} claims written")

    elif form_type == "schedule_k1":
        partner = detect_partner_name(text)
        amounts, updates = parse_schedule_k1(text, source_stem, partner)
        print(f"   Extracted {len(amounts)} box values (partner: {partner})")
        for concept, count in updates.items():
            print(f"   [ok] {concept}.md — {count} claims written")

    else:
        print(f"   [!] Unknown form type — skipping")
        return

    print(f"   Total concept pages updated: {len(updates)}")


def main():
    parser = argparse.ArgumentParser(description="IRS tax form parser for finance vault")
    parser.add_argument("doc", nargs="?", help="Path to converted markdown file")
    parser.add_argument("--all", action="store_true", help="Parse all docs in k1-YourCompany folder")
    parser.add_argument("--vault-dir", default=str(FINANCE_VAULT), help="Finance vault path")
    args = parser.parse_args()

    vault_dir = Path(args.vault_dir)

    if args.all:
        k1_dir = vault_dir / "documents" / "income" / "k1-YourCompany"
        docs = list(k1_dir.glob("*.md"))
        if not docs:
            print(f"No markdown files found in {k1_dir}")
            sys.exit(1)
        for doc in sorted(docs):
            parse_document(doc, vault_dir)
    elif args.doc:
        parse_document(Path(args.doc), vault_dir)
    else:
        parser.print_help()
        sys.exit(1)

    print(f"\n[ok] Done. Concept pages: {len(list((vault_dir / 'concepts').glob('*.md')))}")


if __name__ == "__main__":
    main()
