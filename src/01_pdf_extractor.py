"""
01_pdf_extractor.py
===================
Extracts structured billing data from Dinas (old TMS) and Cargosuite (new TMS) PDF invoices.
Migration date: 26.09.2025

Usage:
    python src/01_pdf_extractor.py --system dinas --input data/herma/rechnungen_dinas/ --output output/
    python src/01_pdf_extractor.py --system cargosuite --input data/herma/rechnungen_cargosuite/ --output output/
    python src/01_pdf_extractor.py --test  # Parse first 3 PDFs found and show extracted fields
"""

import pdfplumber
import pandas as pd
import re
import os
import json
import argparse
from pathlib import Path
from datetime import datetime


# ─── Regex patterns for Dinas invoices ─────────────────────────────────────────
DINAS_PATTERNS = {
    "rechnungsnummer":  r"Rechnungs(?:nummer|nr\.?)[:\s]+([A-Z0-9\-\/]+)",
    "rechnungsdatum":   r"Rechnungsdatum[:\s]+(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
    "auftragsnummer":   r"(?:Auftrags(?:nummer|nr\.?)|Sendungs(?:nummer|nr\.?))[:\s]+([A-Z0-9\-\/]+)",
    "kundennummer":     r"Kunden(?:nummer|nr\.?)[:\s]+([0-9]+)",
    "kundenname":       r"(?:Kunde|Auftraggeber)[:\s]+(.+?)(?:\n|Kunden)",
    "absender_plz":     r"Absender.*?(\d{5})\s+\w+",
    "empfaenger_plz":   r"Empf[äa]nger.*?(\d{5})\s+\w+",
    "gewicht_kg":       r"(?:Gewicht|Gesamtgewicht)[:\s]+([\d.,]+)\s*[kK][gG]",
    "lademeter":        r"(?:Lademeter|LDM|Ladem\.)[:\s]+([\d.,]+)",
    "stellplaetze":     r"(?:Stellpl[äa]tze|Paletten|STL)[:\s]+([\d.,]+)",
    "packstücke":       r"(?:Packst[üu]cke|Colli|COL)[:\s]+([\d.,]+)",
    "grundfracht":      r"Grundfracht[:\s]+([\d.,]+)",
    "diesel_zuschlag":  r"(?:Dieselzuschlag|Kraftstoffzuschlag|KSZ)[:\s]+([\d.,]+)",
    "maut_zuschlag":    r"(?:Mautzuschlag|Maut)[:\s]+([\d.,]+)",
    "sonstige_zuschl":  r"(?:Sonstige Zuschläge|Nebenkosten)[:\s]+([\d.,]+)",
    "netto_betrag":     r"Netto(?:betrag)?[:\s]+([\d.,]+)",
    "mwst_betrag":      r"(?:MwSt\.|Mehrwertsteuer)[:\s]+([\d.,]+)",
    "brutto_betrag":    r"(?:Brutto(?:betrag)?|Gesamtbetrag)[:\s]+([\d.,]+)",
}

# ─── Regex patterns for Cargosuite invoices ────────────────────────────────────
# Cargosuite (Anaxco) has a different layout — patterns will be refined once first
# PDFs are inspected. Initial patterns cover likely field names.
CARGOSUITE_PATTERNS = {
    "rechnungsnummer":  r"(?:Invoice No\.|Rechnungs(?:nummer|nr\.?)|Belegnummer)[:\s]+([A-Z0-9\-\/]+)",
    "rechnungsdatum":   r"(?:Invoice Date|Rechnungsdatum|Datum)[:\s]+(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
    "auftragsnummer":   r"(?:Order No\.|Auftrags(?:nummer|nr\.?)|Sendungs(?:nummer|nr\.?)|Frachtbrief)[:\s]+([A-Z0-9\-\/]+)",
    "kundennummer":     r"(?:Customer No\.|Kunden(?:nummer|nr\.?))[:\s]+([0-9]+)",
    "kundenname":       r"(?:Customer|Kunde|Auftraggeber)[:\s]+(.+?)(?:\n|Kunden|Customer)",
    "absender_plz":     r"(?:Shipper|Absender).*?(\d{5})\s+\w+",
    "empfaenger_plz":   r"(?:Consignee|Receiver|Empf[äa]nger).*?(\d{5})\s+\w+",
    "gewicht_kg":       r"(?:Weight|Gewicht|Gesamtgewicht)[:\s]+([\d.,]+)\s*[kK][gG]",
    "lademeter":        r"(?:Loading Metres?|Lademeter|LDM)[:\s]+([\d.,]+)",
    "stellplaetze":     r"(?:Pallets?|Stellpl[äa]tze|Paletten)[:\s]+([\d.,]+)",
    "packstücke":       r"(?:Pieces?|Packst[üu]cke|Colli)[:\s]+([\d.,]+)",
    "grundfracht":      r"(?:Base Freight|Grundfracht|Frachtkosten)[:\s]+([\d.,]+)",
    "diesel_zuschlag":  r"(?:Fuel Surcharge|Dieselzuschlag|Kraftstoffzuschlag)[:\s]+([\d.,]+)",
    "maut_zuschlag":    r"(?:Toll Surcharge|Mautzuschlag|Maut)[:\s]+([\d.,]+)",
    "sonstige_zuschl":  r"(?:Other Charges|Sonstige|Nebenkosten)[:\s]+([\d.,]+)",
    "netto_betrag":     r"(?:Net Amount|Netto(?:betrag)?)[:\s]+([\d.,]+)",
    "mwst_betrag":      r"(?:VAT|MwSt\.|Mehrwertsteuer)[:\s]+([\d.,]+)",
    "brutto_betrag":    r"(?:Total|Gross Amount|Brutto(?:betrag)?|Gesamtbetrag)[:\s]+([\d.,]+)",
}


def parse_german_number(s: str) -> float:
    """Convert German number format (1.234,56) to float."""
    if not s:
        return None
    s = s.strip().replace(" ", "")
    # Handle German format: 1.234,56 → 1234.56
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(s: str) -> str:
    """Normalize date to ISO format YYYY-MM-DD."""
    if not s:
        return None
    for fmt in ["%d.%m.%Y", "%d.%m.%y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s.strip()


def extract_from_text(text: str, patterns: dict) -> dict:
    """Apply all regex patterns to extracted text, return field dict."""
    result = {}
    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        result[field] = match.group(1).strip() if match else None

    # Normalize numeric fields
    numeric_fields = [
        "gewicht_kg", "lademeter", "stellplaetze", "packstücke",
        "grundfracht", "diesel_zuschlag", "maut_zuschlag",
        "sonstige_zuschl", "netto_betrag", "mwst_betrag", "brutto_betrag"
    ]
    for f in numeric_fields:
        if result.get(f):
            result[f] = parse_german_number(result[f])

    # Normalize date
    if result.get("rechnungsdatum"):
        result["rechnungsdatum"] = parse_date(result["rechnungsdatum"])

    return result


def extract_tables_from_pdf(pdf_path: Path) -> list[dict]:
    """
    Extract invoice line items from PDF tables (for detailed position breakdown).
    Returns list of position dicts.
    """
    positions = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    # Try to identify header row
                    header = [str(c).lower().strip() if c else "" for c in table[0]]
                    for row in table[1:]:
                        if not row or all(c is None for c in row):
                            continue
                        pos = {}
                        for i, cell in enumerate(row):
                            if i < len(header) and header[i]:
                                pos[header[i]] = str(cell).strip() if cell else None
                        if any(v for v in pos.values()):
                            positions.append(pos)
    except Exception as e:
        print(f"  [WARN] Table extraction failed for {pdf_path.name}: {e}")
    return positions


def parse_pdf(pdf_path: Path, system: str, verbose: bool = False) -> dict:
    """
    Parse a single invoice PDF and return structured dict.
    system: 'dinas' or 'cargosuite'
    """
    patterns = DINAS_PATTERNS if system == "dinas" else CARGOSUITE_PATTERNS
    full_text = ""

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if page_text:
                    full_text += page_text + "\n"
    except Exception as e:
        print(f"  [ERROR] Cannot open {pdf_path.name}: {e}")
        return {"datei": pdf_path.name, "fehler": str(e), "system": system}

    if verbose:
        print(f"\n{'='*60}")
        print(f"FILE: {pdf_path.name}")
        print(f"{'='*60}")
        print(full_text[:3000])
        print("...")

    result = extract_from_text(full_text, patterns)
    result["datei"] = pdf_path.name
    result["system"] = system
    result["migration_periode"] = (
        "post" if result.get("rechnungsdatum", "") >= "2025-09-26"
        else "pre"
        if result.get("rechnungsdatum")
        else "unbekannt"
    )
    result["raw_text_len"] = len(full_text)
    result["volltext_snippet"] = full_text[:500].replace("\n", " ")

    # Also try to extract line item tables
    result["positionen"] = extract_tables_from_pdf(pdf_path)

    return result


def process_directory(input_dir: Path, system: str, output_dir: Path, verbose: bool = False) -> pd.DataFrame:
    """Process all PDFs in a directory and return DataFrame."""
    pdf_files = list(input_dir.glob("**/*.pdf")) + list(input_dir.glob("**/*.PDF"))

    if not pdf_files:
        print(f"[WARN] No PDFs found in {input_dir}")
        return pd.DataFrame()

    print(f"Found {len(pdf_files)} PDFs in {input_dir}")
    records = []

    for i, pdf_path in enumerate(sorted(pdf_files)):
        print(f"  [{i+1:3d}/{len(pdf_files)}] {pdf_path.name}", end=" ")
        record = parse_pdf(pdf_path, system, verbose=verbose)
        records.append(record)

        # Show match quality indicator
        key_fields = ["rechnungsnummer", "auftragsnummer", "netto_betrag", "rechnungsdatum"]
        found = sum(1 for f in key_fields if record.get(f))
        print(f"→ {found}/{len(key_fields)} Pflichtfelder gefunden", end="")
        if record.get("auftragsnummer"):
            print(f" | AuftrNr: {record['auftragsnummer']}", end="")
        if record.get("netto_betrag"):
            print(f" | Netto: {record['netto_betrag']:.2f}€", end="")
        print()

    df = pd.DataFrame(records)

    # Save positions separately
    all_positions = []
    for r in records:
        positions = r.pop("positionen", [])
        for pos in positions:
            pos["datei"] = r.get("datei")
            pos["auftragsnummer"] = r.get("auftragsnummer")
            all_positions.append(pos)

    # Save main data
    kunde = input_dir.parts[-2] if len(input_dir.parts) >= 2 else "unbekannt"
    out_file = output_dir / f"{kunde}_{system}_rechnungen.csv"
    df.to_csv(out_file, index=False, sep=";", encoding="utf-8-sig")
    print(f"  → Saved: {out_file} ({len(df)} records)")

    if all_positions:
        pos_file = output_dir / f"{kunde}_{system}_positionen.csv"
        pd.DataFrame(all_positions).to_csv(pos_file, index=False, sep=";", encoding="utf-8-sig")
        print(f"  → Saved: {pos_file} ({len(all_positions)} line items)")

    return df


def print_summary(df: pd.DataFrame, system: str):
    """Print extraction quality summary."""
    if df.empty:
        return
    print(f"\n{'='*60}")
    print(f"EXTRAKTIONS-ZUSAMMENFASSUNG: {system.upper()}")
    print(f"{'='*60}")
    print(f"Gesamt PDFs: {len(df)}")

    key_fields = ["rechnungsnummer", "auftragsnummer", "rechnungsdatum",
                  "netto_betrag", "gewicht_kg", "lademeter", "stellplaetze",
                  "absender_plz", "empfaenger_plz"]

    for field in key_fields:
        if field in df.columns:
            not_null = df[field].notna().sum()
            pct = not_null / len(df) * 100
            status = "✓" if pct > 90 else "⚠" if pct > 50 else "✗"
            print(f"  {status} {field:25s}: {not_null:4d}/{len(df)} ({pct:.0f}%)")

    if "netto_betrag" in df.columns:
        total = df["netto_betrag"].sum()
        print(f"\n  Gesamt Nettoumsatz: {total:,.2f} €")

    if "migration_periode" in df.columns:
        print(f"\n  pre-Migration:  {(df['migration_periode'] == 'pre').sum()} Rechnungen")
        print(f"  post-Migration: {(df['migration_periode'] == 'post').sum()} Rechnungen")


def main():
    parser = argparse.ArgumentParser(description="TMS Invoice PDF Extractor")
    parser.add_argument("--system", choices=["dinas", "cargosuite", "auto"],
                        default="auto", help="Invoice system type")
    parser.add_argument("--input", type=str, help="Input directory with PDFs")
    parser.add_argument("--output", type=str, default="output/",
                        help="Output directory for CSV files")
    parser.add_argument("--test", action="store_true",
                        help="Test mode: parse first 3 PDFs with verbose output")
    parser.add_argument("--verbose", action="store_true",
                        help="Print extracted text for debugging")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    if args.test:
        # Find any PDFs on the system for testing
        test_dirs = [
            Path("data/herma/rechnungen_dinas"),
            Path("data/herma/rechnungen_cargosuite"),
            Path("data/fischerwerke/rechnungen_dinas"),
            Path("data/fischerwerke/rechnungen_cargosuite"),
        ]
        for d in test_dirs:
            pdfs = list(d.glob("*.pdf"))[:3] if d.exists() else []
            if pdfs:
                system = "cargosuite" if "cargosuite" in str(d) else "dinas"
                print(f"\n[TEST] Processing {d} as {system}:")
                for pdf in pdfs:
                    result = parse_pdf(pdf, system, verbose=True)
                    print(json.dumps({k: v for k, v in result.items()
                                      if k not in ("volltext_snippet", "positionen")},
                                     indent=2, ensure_ascii=False))
        return

    if not args.input:
        parser.print_help()
        return

    input_dir = Path(args.input)
    if not input_dir.exists():
        print(f"[ERROR] Input directory not found: {input_dir}")
        return

    # Auto-detect system from path
    system = args.system
    if system == "auto":
        if "cargosuite" in str(input_dir).lower():
            system = "cargosuite"
        elif "dinas" in str(input_dir).lower():
            system = "dinas"
        else:
            print("[WARN] Cannot auto-detect system, defaulting to 'dinas'")
            system = "dinas"

    df = process_directory(input_dir, system, output_dir, verbose=args.verbose)
    print_summary(df, system)


if __name__ == "__main__":
    main()
