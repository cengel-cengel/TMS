"""
02_bi_loader.py
===============
Loads and normalizes the BI raw report (12 months of shipment data).
Creates a cleaned master dataset with pre/post migration split and
PLZ-based route grouping for comparable transport analysis.

Usage:
    python src/02_bi_loader.py --input data/bi_report/ --output output/
"""

import pandas as pd
import numpy as np
import os
import argparse
from pathlib import Path
from datetime import datetime

MIGRATION_DATE = pd.Timestamp("2025-09-26")

# ─── Known column name mappings (Dinas BI export vs Cargosuite BI export) ──────
# Maps possible column names to canonical names
COLUMN_ALIASES = {
    # Shipment identifier
    "auftragsnummer":    ["auftragsnummer", "sendungsnummer", "auftrag_nr", "sendung_nr",
                          "order_no", "shipment_no", "frachtbriefnr", "frachtbrief_nr",
                          "auftrags_nr", "sendungs_nr", "belegnummer", "beleg_nr"],
    # Date fields
    "ladedatum":         ["ladedatum", "ladedate", "abladedatum", "versanddatum",
                          "shipping_date", "dispatch_date", "datum", "date",
                          "auftragsdatum", "pickup_date"],
    "lieferdatum":       ["lieferdatum", "delivery_date", "zustelldatum"],
    # Customer
    "kundennummer":      ["kundennummer", "kunden_nr", "customer_no", "auftraggeber_nr",
                          "debitor", "debitor_nr", "debitorennummer"],
    "kundenname":        ["kundenname", "kunde", "customer_name", "auftraggeber",
                          "auftraggeber_name", "firma", "company"],
    # Sender
    "absender_name":     ["absender", "absender_name", "sender", "shipper", "versender"],
    "absender_plz":      ["absender_plz", "absender_postleitzahl", "sender_plz",
                          "plz_absender", "von_plz", "from_plz", "abs_plz"],
    "absender_ort":      ["absender_ort", "sender_ort", "von_ort", "abs_ort"],
    "absender_land":     ["absender_land", "sender_land", "von_land", "abs_land"],
    # Recipient
    "empfaenger_name":   ["empfaenger", "empfaenger_name", "receiver", "consignee",
                          "empf_name", "ziel_name"],
    "empfaenger_plz":    ["empfaenger_plz", "empfaenger_postleitzahl", "receiver_plz",
                          "plz_empfaenger", "nach_plz", "to_plz", "empf_plz", "ziel_plz"],
    "empfaenger_ort":    ["empfaenger_ort", "receiver_ort", "nach_ort", "empf_ort", "ziel"],
    "empfaenger_land":   ["empfaenger_land", "receiver_land", "nach_land"],
    # Shipment parameters
    "gewicht_kg":        ["gewicht_kg", "gewicht", "weight_kg", "weight", "kg",
                          "gesamtgewicht", "brutto_gewicht", "bruttogewicht"],
    "lademeter":         ["lademeter", "ldm", "loading_metres", "lm", "ladem",
                          "lademass", "ladelaenge"],
    "stellplaetze":      ["stellplaetze", "paletten", "pallets", "stpl", "stl",
                          "stellplatz", "europaletten"],
    "packstücke":        ["packstücke", "packstucke", "colli", "col", "pieces",
                          "anzahl_packstücke", "anzahl_colli", "stueckzahl"],
    "laenge_cm":         ["laenge_cm", "laenge", "length_cm", "länge_cm"],
    "breite_cm":         ["breite_cm", "breite", "width_cm"],
    "hoehe_cm":          ["hoehe_cm", "hoehe", "height_cm", "höhe_cm"],
    # Billing
    "frachtkosten_netto": ["frachtkosten_netto", "frachtkosten", "fracht_netto",
                           "netto_fracht", "freight_net", "freight_cost",
                           "abrechnungsbetrag", "rechnungsbetrag_netto", "nettobetrag"],
    "frachtkosten_brutto": ["frachtkosten_brutto", "brutto_fracht", "freight_gross",
                            "rechnungsbetrag_brutto", "bruttobetrag"],
    # Service / product
    "produkt":           ["produkt", "service_code", "product", "leistungsart",
                          "versandart", "transport_art", "service"],
    "system_quelle":     ["system_quelle", "system", "source_system", "quelle", "tms"],
}


def detect_separator(filepath: Path) -> str:
    """Detect CSV separator by reading first line."""
    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
        first_line = f.readline()
    counts = {sep: first_line.count(sep) for sep in [";", ",", "\t", "|"]}
    return max(counts, key=counts.get)


def load_file(filepath: Path) -> pd.DataFrame:
    """Load CSV or Excel file into DataFrame."""
    suffix = filepath.suffix.lower()
    print(f"  Loading {filepath.name}...")

    if suffix in (".xlsx", ".xls"):
        # Try all sheets, use the one with most rows
        xl = pd.ExcelFile(filepath)
        dfs = {}
        for sheet in xl.sheet_names:
            try:
                df = pd.read_excel(filepath, sheet_name=sheet, dtype=str)
                if len(df) > 10:
                    dfs[sheet] = df
                    print(f"    Sheet '{sheet}': {len(df)} rows × {len(df.columns)} cols")
            except Exception as e:
                print(f"    [WARN] Sheet '{sheet}': {e}")
        if not dfs:
            return pd.DataFrame()
        # Return the largest sheet (most data rows)
        best_sheet = max(dfs, key=lambda s: len(dfs[s]))
        print(f"    → Using sheet: '{best_sheet}'")
        return dfs[best_sheet]

    elif suffix == ".csv":
        sep = detect_separator(filepath)
        for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
            try:
                df = pd.read_csv(filepath, sep=sep, dtype=str, encoding=enc,
                                 low_memory=False)
                print(f"    Loaded with sep='{sep}', enc={enc}: {len(df)} rows × {len(df.columns)} cols")
                return df
            except Exception:
                continue
        print(f"    [ERROR] Could not read {filepath.name}")
        return pd.DataFrame()
    else:
        print(f"    [SKIP] Unknown format: {suffix}")
        return pd.DataFrame()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map raw column names to canonical names using COLUMN_ALIASES."""
    # Normalize existing column names for comparison
    col_lower = {col: col.lower().strip().replace(" ", "_").replace("ä", "a")
                             .replace("ö", "o").replace("ü", "u").replace("ß", "ss")
                 for col in df.columns}

    rename_map = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for col_orig, col_norm in col_lower.items():
            if col_norm in [a.lower() for a in aliases] and col_orig not in rename_map:
                rename_map[col_orig] = canonical
                break

    df = df.rename(columns=rename_map)

    print(f"  Column mapping: {len(rename_map)} columns renamed")
    unmapped = [c for c in df.columns if c not in COLUMN_ALIASES.keys()
                and c not in rename_map.values()]
    if unmapped:
        print(f"  Unmapped columns ({len(unmapped)}): {unmapped[:10]}")

    return df


def clean_numeric(series: pd.Series) -> pd.Series:
    """Convert German-formatted numbers to float."""
    if series.dtype != object:
        return pd.to_numeric(series, errors="coerce")
    s = series.astype(str).str.strip()
    # Handle German format: 1.234,56 → 1234.56
    mask_german = s.str.contains(r"\d\.\d{3},\d", regex=True, na=False)
    s[mask_german] = s[mask_german].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    # Handle simple comma decimal: 12,5 → 12.5
    mask_comma = s.str.contains(r",", na=False) & ~mask_german
    s[mask_comma] = s[mask_comma].str.replace(",", ".", regex=False)
    # Remove currency symbols and spaces
    s = s.str.replace(r"[€$£\s]", "", regex=True)
    return pd.to_numeric(s, errors="coerce")


def clean_dates(series: pd.Series) -> pd.Series:
    """Parse date columns to datetime."""
    return pd.to_datetime(series, dayfirst=True, errors="coerce")


def clean_plz(series: pd.Series) -> pd.Series:
    """Normalize PLZ: extract 5-digit German PLZ."""
    return series.astype(str).str.extract(r"(\d{5})", expand=False)


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived analysis columns."""
    # Migration period flag
    if "ladedatum" in df.columns:
        df["migration_periode"] = np.where(
            df["ladedatum"] < MIGRATION_DATE, "pre", "post"
        )
        df["monat"] = df["ladedatum"].dt.to_period("M").astype(str)
        df["quartal"] = df["ladedatum"].dt.to_period("Q").astype(str)

    # Route grouping (2-digit PLZ prefix)
    if "absender_plz" in df.columns:
        df["absender_plz2"] = df["absender_plz"].astype(str).str[:2]
    if "empfaenger_plz" in df.columns:
        df["empfaenger_plz2"] = df["empfaenger_plz"].astype(str).str[:2]

    # Route key for matching
    if "absender_plz" in df.columns and "empfaenger_plz" in df.columns:
        df["route_exakt"] = df["absender_plz"].astype(str) + "→" + df["empfaenger_plz"].astype(str)
        df["route_zone"] = df["absender_plz2"].astype(str) + "→" + df["empfaenger_plz2"].astype(str)

    # Preis je Einheit
    if "frachtkosten_netto" in df.columns:
        if "gewicht_kg" in df.columns:
            df["preis_je_kg"] = df["frachtkosten_netto"] / df["gewicht_kg"].replace(0, np.nan)
        if "lademeter" in df.columns:
            df["preis_je_ldm"] = df["frachtkosten_netto"] / df["lademeter"].replace(0, np.nan)
        if "stellplaetze" in df.columns:
            df["preis_je_stellplatz"] = df["frachtkosten_netto"] / df["stellplaetze"].replace(0, np.nan)

    # Volumengewicht (L×B×H in cm → kg at 333 kg/m³ for LTL or 250 kg/m³)
    if all(c in df.columns for c in ["laenge_cm", "breite_cm", "hoehe_cm"]):
        df["volumen_m3"] = (df["laenge_cm"] * df["breite_cm"] * df["hoehe_cm"]) / 1_000_000
        df["volumengewicht_kg"] = df["volumen_m3"] * 333  # 333 kg/m³ standard

    return df


def load_bi_report(input_dir: Path, output_dir: Path) -> pd.DataFrame:
    """Load all BI report files from input directory."""
    files = (
        list(input_dir.glob("*.csv")) +
        list(input_dir.glob("*.xlsx")) +
        list(input_dir.glob("*.xls")) +
        list(input_dir.glob("**/*.csv")) +
        list(input_dir.glob("**/*.xlsx"))
    )
    files = list(set(files))  # deduplicate

    if not files:
        print(f"[WARN] No files found in {input_dir}")
        return pd.DataFrame()

    print(f"Found {len(files)} file(s) in {input_dir}")
    dfs = []
    for f in sorted(files):
        df = load_file(f)
        if not df.empty:
            df["quell_datei"] = f.name
            dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    df_combined = pd.concat(dfs, ignore_index=True)
    print(f"\n  Combined: {len(df_combined)} rows, {len(df_combined.columns)} columns")

    # Normalize columns
    df_combined = normalize_columns(df_combined)

    # Clean data types
    numeric_cols = ["gewicht_kg", "lademeter", "stellplaetze", "packstücke",
                    "frachtkosten_netto", "frachtkosten_brutto",
                    "laenge_cm", "breite_cm", "hoehe_cm"]
    for col in numeric_cols:
        if col in df_combined.columns:
            df_combined[col] = clean_numeric(df_combined[col])

    date_cols = ["ladedatum", "lieferdatum"]
    for col in date_cols:
        if col in df_combined.columns:
            df_combined[col] = clean_dates(df_combined[col])

    plz_cols = ["absender_plz", "empfaenger_plz"]
    for col in plz_cols:
        if col in df_combined.columns:
            df_combined[col] = clean_plz(df_combined[col])

    # Add derived columns
    df_combined = add_derived_columns(df_combined)

    # Remove duplicates on auftragsnummer if present
    if "auftragsnummer" in df_combined.columns:
        n_before = len(df_combined)
        df_combined = df_combined.drop_duplicates(subset=["auftragsnummer"])
        n_after = len(df_combined)
        if n_before > n_after:
            print(f"  Removed {n_before - n_after} duplicate auftragsnummer entries")

    # Save
    out_file = output_dir / "bi_report_clean.csv"
    df_combined.to_csv(out_file, index=False, sep=";", encoding="utf-8-sig")
    print(f"  → Saved: {out_file}")

    return df_combined


def print_bi_summary(df: pd.DataFrame):
    """Print summary statistics of loaded BI data."""
    print(f"\n{'='*60}")
    print(f"BI-REPORT ZUSAMMENFASSUNG")
    print(f"{'='*60}")
    print(f"Gesamt Datensätze: {len(df):,}")

    if "ladedatum" in df.columns:
        print(f"Zeitraum: {df['ladedatum'].min().date()} bis {df['ladedatum'].max().date()}")

    if "migration_periode" in df.columns:
        pre = (df["migration_periode"] == "pre").sum()
        post = (df["migration_periode"] == "post").sum()
        print(f"\nPre-Migration  (< 26.09.2025): {pre:,} Sendungen")
        print(f"Post-Migration (≥ 26.09.2025): {post:,} Sendungen")

    if "kundennummer" in df.columns or "kundenname" in df.columns:
        key = "kundennummer" if "kundennummer" in df.columns else "kundenname"
        print(f"\nAnzahl Kunden: {df[key].nunique():,}")

    if "frachtkosten_netto" in df.columns:
        total = df["frachtkosten_netto"].sum()
        pre_rev = df[df.get("migration_periode", pd.Series()) == "pre"]["frachtkosten_netto"].sum() if "migration_periode" in df.columns else 0
        post_rev = df[df.get("migration_periode", pd.Series()) == "post"]["frachtkosten_netto"].sum() if "migration_periode" in df.columns else 0
        print(f"\nGesamtumsatz netto: {total:,.2f} €")
        if "migration_periode" in df.columns:
            print(f"  Pre-Migration:    {pre_rev:,.2f} €")
            print(f"  Post-Migration:   {post_rev:,.2f} €")

    # Top 20 customers by revenue
    if "frachtkosten_netto" in df.columns:
        key = "kundenname" if "kundenname" in df.columns else "kundennummer" if "kundennummer" in df.columns else None
        if key:
            top20 = (df.groupby(key)["frachtkosten_netto"]
                     .sum().nlargest(20).reset_index())
            top20.columns = [key, "umsatz_netto"]
            top20["rang"] = range(1, len(top20) + 1)
            print(f"\n--- TOP 20 KUNDEN (nach Nettoumsatz) ---")
            for _, row in top20.iterrows():
                print(f"  #{row['rang']:2d}  {str(row[key])[:40]:40s}  {row['umsatz_netto']:>12,.2f} €")

    print(f"\n--- DATENVOLLSTÄNDIGKEIT ---")
    important_cols = ["auftragsnummer", "ladedatum", "kundennummer", "kundenname",
                      "absender_plz", "empfaenger_plz", "gewicht_kg",
                      "lademeter", "stellplaetze", "frachtkosten_netto"]
    for col in important_cols:
        if col in df.columns:
            pct = df[col].notna().mean() * 100
            status = "✓" if pct > 90 else "⚠" if pct > 50 else "✗"
            print(f"  {status} {col:30s}: {pct:.0f}%")


def main():
    parser = argparse.ArgumentParser(description="TMS BI Report Loader")
    parser.add_argument("--input", type=str, default="data/bi_report/",
                        help="Input directory with BI report files")
    parser.add_argument("--output", type=str, default="output/",
                        help="Output directory for cleaned CSV")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    df = load_bi_report(Path(args.input), output_dir)
    if not df.empty:
        print_bi_summary(df)
    else:
        print("[ERROR] No data loaded — check input directory and file formats")


if __name__ == "__main__":
    main()
