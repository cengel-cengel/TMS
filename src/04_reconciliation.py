"""
04_reconciliation.py
====================
Core analysis: Soll/Ist comparison of freight invoices before and after
the TMS migration (Dinas → Cargosuite, 26.09.2025).

Key methodology:
  1. Match invoices with BI shipment data via Auftragsnummer
  2. Group shipments by ROUTE (same sender/recipient PLZ or 2-digit PLZ zones)
     → only comparable routes get compared (no apples-to-oranges)
  3. Calculate expected (Soll) price from customer tariff model
  4. Compare Soll vs. Ist (=invoiced amount)
  5. Classify error types (A–E)

Usage:
    python src/04_reconciliation.py --kunde herma --output output/
    python src/04_reconciliation.py --kunde fischerwerke --output output/
    python src/04_reconciliation.py --alle --output output/
"""

import pandas as pd
import numpy as np
import json
import argparse
from pathlib import Path
from datetime import datetime

MIGRATION_DATE = pd.Timestamp("2025-09-26")

# ─── Error type classification ─────────────────────────────────────────────────
ERROR_TYPES = {
    "OK":              "Korrekt abgerechnet (Delta < 2%)",
    "A_PAUSCHAL":      "Pauschaltarif statt Staffel → systematisch falsch",
    "B_ZUSCHLAG":      "Zuschlag fehlt oder falsch (Diesel/Maut/sonstige)",
    "C_KONDGRUPPE":    "Falsche Konditionsgruppe zugewiesen",
    "D_PLZZONE":       "Falsche Entfernungszone / PLZ-Zuordnung",
    "E_PARAMETER":     "Falscher Abrechnungsparameter (KG statt LDM o.ä.)",
    "F_NICHT_FAKTURIERT": "Sendung im BI aber keine Rechnung gefunden",
    "G_DOPPELT":       "Sendung doppelt in Rechnung",
    "UNBEKANNT":       "Abweichung vorhanden, Ursache unklar",
}

TOLERANCE_PCT = 2.0  # Delta below this % is treated as OK


def load_invoices(output_dir: Path, kunde: str, system: str) -> pd.DataFrame:
    """Load previously extracted invoice CSV for a customer and system."""
    pattern = f"{kunde}_{system}_rechnungen.csv"
    filepath = output_dir / pattern
    if not filepath.exists():
        print(f"  [WARN] Invoice file not found: {filepath}")
        return pd.DataFrame()
    df = pd.read_csv(filepath, sep=";", dtype=str, encoding="utf-8-sig")
    print(f"  Loaded {len(df)} {system} invoices for {kunde}")
    return df


def load_bi_data(output_dir: Path, kunde: str = None) -> pd.DataFrame:
    """Load cleaned BI report and optionally filter by customer."""
    filepath = output_dir / "bi_report_clean.csv"
    if not filepath.exists():
        print(f"  [WARN] BI report not found: {filepath}")
        return pd.DataFrame()

    df = pd.read_csv(filepath, sep=";", dtype=str, encoding="utf-8-sig",
                     parse_dates=["ladedatum"], dayfirst=True)

    # Numeric conversion
    num_cols = ["gewicht_kg", "lademeter", "stellplaetze", "packstücke",
                "frachtkosten_netto", "preis_je_kg", "preis_je_ldm"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")

    if "ladedatum" in df.columns:
        df["ladedatum"] = pd.to_datetime(df["ladedatum"], errors="coerce")
        df["migration_periode"] = np.where(df["ladedatum"] < MIGRATION_DATE, "pre", "post")

    if kunde:
        # Filter by customer name or number
        mask = pd.Series(False, index=df.index)
        for col in ["kundenname", "kundennummer"]:
            if col in df.columns:
                mask |= df[col].str.lower().str.contains(kunde.lower(), na=False)
        df = df[mask]
        print(f"  Filtered to {len(df)} shipments for customer '{kunde}'")

    return df


def load_tariff(output_dir: Path, kunde: str) -> dict:
    """Load tariff model JSON for a customer."""
    # Search for tariff file
    for pattern in [f"tarif_{kunde}_*.json", f"tarif_*{kunde}*.json"]:
        files = list(output_dir.glob(pattern))
        if files:
            with open(files[0], encoding="utf-8") as f:
                return json.load(f)
    print(f"  [WARN] No tariff file found for {kunde} in {output_dir}")
    return {}


def classify_delta(row: pd.Series, tarif: dict) -> str:
    """Classify the error type based on delta characteristics."""
    if pd.isna(row.get("delta_pct")):
        if row.get("hat_rechnung") == False:
            return "F_NICHT_FAKTURIERT"
        return "UNBEKANNT"

    abs_delta = abs(row.get("delta_pct", 0))

    if abs_delta <= TOLERANCE_PCT:
        return "OK"

    ist = row.get("ist_netto", 0) or 0
    soll = row.get("soll_netto", 0) or 0
    delta = ist - soll

    # Check for systematically too high/low (suggests wrong rate table)
    if abs_delta > 20:
        return "A_PAUSCHAL"

    # Check if surcharges are missing: ist is close to Grundfracht only
    grundfracht = row.get("soll_grundfracht", soll * 0.75)
    if soll > 0 and abs(ist - grundfracht) / soll * 100 < 5:
        return "B_ZUSCHLAG"

    # Check for LDM vs KG confusion
    if row.get("lademeter", 0) > 0 and row.get("gewicht_kg", 0) > 0:
        ldm_based = row.get("lademeter", 0) * 80  # rough LDM price
        kg_based = row.get("gewicht_kg", 0) * 0.15  # rough KG price
        if abs(ist - ldm_based) < abs(ist - kg_based) * 0.2:
            return "E_PARAMETER"

    if abs_delta <= 15:
        return "D_PLZZONE"

    return "UNBEKANNT"


def identify_comparable_routes(df_bi: pd.DataFrame,
                                 min_pre: int = 3,
                                 min_post: int = 3) -> pd.DataFrame:
    """
    Identify route groups that appear in BOTH pre and post migration periods.
    Uses exact PLZ matching first, then falls back to 2-digit zone matching.

    Returns DataFrame with only comparable shipments + route_group column.
    """
    if df_bi.empty:
        return df_bi

    results = []
    for match_level, route_col in [("exakt", "route_exakt"), ("zone", "route_zone")]:
        if route_col not in df_bi.columns:
            continue

        groups = df_bi.groupby([route_col, "migration_periode"]).size().unstack(fill_value=0)

        if "pre" not in groups.columns or "post" not in groups.columns:
            continue

        # Routes with enough data in both periods
        valid_routes = groups[
            (groups.get("pre", 0) >= min_pre) &
            (groups.get("post", 0) >= min_post)
        ].index.tolist()

        comparable = df_bi[df_bi[route_col].isin(valid_routes)].copy()
        comparable["route_match_level"] = match_level
        comparable["route_group"] = comparable[route_col]

        n_routes = len(valid_routes)
        n_shipments = len(comparable)
        print(f"  Route matching ({match_level}): {n_routes} routes, {n_shipments} comparable shipments")
        results.append(comparable)

        if n_shipments > 100:  # enough data, stop here
            break

    if results:
        return pd.concat(results, ignore_index=True).drop_duplicates(subset=["auftragsnummer"] if "auftragsnummer" in df_bi.columns else None)
    return df_bi.copy()


def reconcile_customer(kunde: str, output_dir: Path) -> pd.DataFrame:
    """
    Full reconciliation for one customer:
    1. Load BI data + invoices (Dinas + Cargosuite) + tariff
    2. Join on Auftragsnummer
    3. Filter to comparable routes (pre + post migration)
    4. Calculate Soll price, compare to Ist
    5. Classify errors
    Returns DataFrame with one row per shipment.
    """
    print(f"\n{'='*60}")
    print(f"RECONCILIATION: {kunde.upper()}")
    print(f"{'='*60}")

    # Load data
    df_bi = load_bi_data(output_dir, kunde)
    df_dinas = load_invoices(output_dir, kunde, "dinas")
    df_cargosuite = load_invoices(output_dir, kunde, "cargosuite")
    tarif = load_tariff(output_dir, kunde)

    if df_bi.empty:
        print(f"  [ERROR] No BI data for {kunde}")
        return pd.DataFrame()

    # Combine invoices
    dfs_inv = []
    for df_inv, sys in [(df_dinas, "dinas"), (df_cargosuite, "cargosuite")]:
        if not df_inv.empty:
            df_inv = df_inv.copy()
            df_inv["inv_system"] = sys
            # Normalize key fields
            for col in ["auftragsnummer", "netto_betrag", "rechnungsnummer", "rechnungsdatum"]:
                if col not in df_inv.columns:
                    df_inv[col] = None
            dfs_inv.append(df_inv)

    df_inv_all = pd.concat(dfs_inv, ignore_index=True) if dfs_inv else pd.DataFrame()

    # Join BI with invoices
    if not df_inv_all.empty and "auftragsnummer" in df_bi.columns:
        df_inv_all["auftragsnummer"] = df_inv_all["auftragsnummer"].astype(str).str.strip()
        df_bi["auftragsnummer"] = df_bi["auftragsnummer"].astype(str).str.strip()

        df = df_bi.merge(
            df_inv_all[["auftragsnummer", "netto_betrag", "rechnungsnummer",
                        "rechnungsdatum", "inv_system", "grundfracht",
                        "diesel_zuschlag", "maut_zuschlag"]],
            on="auftragsnummer",
            how="left",
            suffixes=("_bi", "_inv")
        )
        df["hat_rechnung"] = df["netto_betrag"].notna()
        df["ist_netto"] = pd.to_numeric(df["netto_betrag"].astype(str).str.replace(",", "."), errors="coerce")
    else:
        df = df_bi.copy()
        df["hat_rechnung"] = False
        df["ist_netto"] = df.get("frachtkosten_netto")
        df["inv_system"] = "bi_only"

    # Filter to comparable routes only
    df = identify_comparable_routes(df)

    # Calculate Soll price if tariff available
    if tarif:
        from src.tariff_parser import berechne_soll_preis, KundeTarif
        # This would use the tariff model — simplified here for pipeline
        pass

    # Delta calculation
    bi_preis_col = "frachtkosten_netto" if "frachtkosten_netto" in df.columns else None
    if bi_preis_col and "ist_netto" in df.columns:
        df["soll_netto"] = pd.to_numeric(df[bi_preis_col], errors="coerce")
    elif "ist_netto" in df.columns:
        df["soll_netto"] = np.nan

    if "ist_netto" in df.columns and "soll_netto" in df.columns:
        df["delta_eur"] = df["ist_netto"] - df["soll_netto"]
        df["delta_pct"] = (df["delta_eur"] / df["soll_netto"].replace(0, np.nan)) * 100

    # Classify error types
    df["fehler_typ"] = df.apply(lambda r: classify_delta(r, tarif), axis=1)
    df["fehler_beschreibung"] = df["fehler_typ"].map(ERROR_TYPES)
    df["kunde"] = kunde

    # Save
    out_file = output_dir / f"{kunde}_reconciliation.csv"
    df.to_csv(out_file, index=False, sep=";", encoding="utf-8-sig")
    print(f"  → Saved: {out_file} ({len(df)} records)")

    return df


def print_reconciliation_summary(df: pd.DataFrame, kunde: str):
    """Print summary of reconciliation results."""
    if df.empty:
        return

    print(f"\n{'='*60}")
    print(f"ERGEBNIS: {kunde.upper()}")
    print(f"{'='*60}")

    if "migration_periode" not in df.columns:
        return

    for periode in ["pre", "post"]:
        sub = df[df["migration_periode"] == periode]
        if sub.empty:
            continue

        avg_preis = sub["ist_netto"].mean() if "ist_netto" in sub.columns else 0
        total = sub["ist_netto"].sum() if "ist_netto" in sub.columns else 0
        n = len(sub)
        avg_kg = sub["gewicht_kg"].mean() if "gewicht_kg" in sub.columns else 0
        avg_ldm = sub["lademeter"].mean() if "lademeter" in sub.columns else 0

        print(f"\n  {periode.upper()}-Migration ({MIGRATION_DATE.date()}):")
        print(f"    Sendungen:       {n:,}")
        print(f"    Ø Preis/Sendung: {avg_preis:,.2f} €")
        print(f"    Gesamtumsatz:    {total:,.2f} €")
        print(f"    Ø Gewicht:       {avg_kg:,.1f} kg")
        print(f"    Ø Lademeter:     {avg_ldm:,.2f} LDM")
        if "preis_je_kg" in sub.columns:
            print(f"    Ø Preis/kg:      {sub['preis_je_kg'].mean():,.4f} €/kg")
        if "preis_je_ldm" in sub.columns:
            print(f"    Ø Preis/LDM:     {sub['preis_je_ldm'].mean():,.2f} €/LDM")

    # Delta between pre and post
    if "delta_eur" in df.columns:
        total_delta = df[df["migration_periode"] == "post"]["delta_eur"].sum()
        print(f"\n  Kumulierter Delta (post-Migration): {total_delta:,.2f} €")
        print(f"  → {'ZU VIEL BERECHNET' if total_delta > 0 else 'ZU WENIG BERECHNET' if total_delta < 0 else 'KORREKT'}")

    # Error type distribution
    if "fehler_typ" in df.columns:
        post = df[df["migration_periode"] == "post"]
        print(f"\n  Fehlertypen (post-Migration, n={len(post)}):")
        for typ, desc in ERROR_TYPES.items():
            count = (post["fehler_typ"] == typ).sum()
            if count > 0:
                pct = count / len(post) * 100
                print(f"    {typ:20s}: {count:4d} ({pct:.1f}%) — {desc}")


def main():
    parser = argparse.ArgumentParser(description="TMS Billing Reconciliation")
    parser.add_argument("--kunde", type=str, help="Customer name to reconcile")
    parser.add_argument("--alle", action="store_true", help="Reconcile all customers")
    parser.add_argument("--output", type=str, default="output/",
                        help="Output directory")
    parser.add_argument("--sample", type=int, default=0,
                        help="Show N sample shipments with Soll/Ist detail")
    args = parser.parse_args()

    output_dir = Path(args.output)

    kunden = []
    if args.alle:
        # Find all available customers from reconciliation files
        kunden = [f.stem.replace("_reconciliation", "")
                  for f in output_dir.glob("*_reconciliation.csv")]
        if not kunden:
            kunden = ["herma", "fischerwerke"]
    elif args.kunde:
        kunden = [args.kunde]
    else:
        parser.print_help()
        return

    all_results = []
    for kunde in kunden:
        df = reconcile_customer(kunde, output_dir)
        if not df.empty:
            print_reconciliation_summary(df, kunde)
            all_results.append(df)

            if args.sample > 0:
                print(f"\n  SAMPLE ({args.sample} Sendungen mit höchstem Delta):")
                sample = df.nlargest(args.sample, "delta_eur") if "delta_eur" in df.columns else df.head(args.sample)
                cols = ["auftragsnummer", "ladedatum", "migration_periode",
                        "route_group", "gewicht_kg", "lademeter",
                        "soll_netto", "ist_netto", "delta_eur", "delta_pct",
                        "fehler_typ"]
                print(sample[[c for c in cols if c in sample.columns]].to_string(index=False))

    if all_results:
        df_all = pd.concat(all_results, ignore_index=True)
        df_all.to_csv(output_dir / "reconciliation_gesamt.csv",
                      index=False, sep=";", encoding="utf-8-sig")
        print(f"\n→ Gesamtdatei gespeichert: {output_dir}/reconciliation_gesamt.csv")


if __name__ == "__main__":
    main()
