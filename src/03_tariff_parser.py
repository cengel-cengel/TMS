"""
03_tariff_parser.py
===================
Parses customer-individual tariff/rate documents (Konditionsblätter) and
constructs a tariff model per customer. Used to calculate the EXPECTED
(Soll) price for each shipment.

Supports:
  - Excel rate tables (Staffeln nach KG / LDM / Stellplätze)
  - PDF tariff documents
  - Manual tariff entry via JSON

Usage:
    python src/03_tariff_parser.py --input data/herma/tarife/ --output output/
    python src/03_tariff_parser.py --input data/fischerwerke/tarife/ --output output/
"""

import pandas as pd
import numpy as np
import pdfplumber
import re
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


# ─── Tariff data model ─────────────────────────────────────────────────────────

@dataclass
class GewichtsStaffel:
    """Weight-based freight rate step (per KG range)."""
    von_kg: float
    bis_kg: float
    preis_eur: float        # absolute price for this range, OR
    preis_je_kg: float = 0  # price per kg within range

@dataclass
class LdmStaffel:
    """LDM-based freight rate."""
    von_ldm: float
    bis_ldm: float
    preis_eur: float        # absolute or per-LDM price
    preis_je_ldm: float = 0

@dataclass
class StellplatzTarif:
    """Pallet/Stellplatz-based rate."""
    preis_je_stellplatz: float
    mindeststellplaetze: float = 0

@dataclass
class ZuschlaegeModell:
    """Surcharge model for a customer."""
    diesel_prozent: float = 0.0    # % on Grundfracht
    maut_prozent: float = 0.0      # % on Grundfracht
    maut_je_km: float = 0.0        # € per km alternative
    insel_pauschal: float = 0.0    # € flat for island/difficult zones
    express_aufschlag: float = 0.0 # % or €
    sonstige_prozent: float = 0.0

@dataclass
class KundeTarif:
    """Complete tariff model for one customer."""
    kundennummer: str
    kundenname: str
    gueltig_ab: str
    gueltig_bis: str = "9999-12-31"
    waehrung: str = "EUR"
    mindestfracht: float = 0.0
    abrechnungsbasis: str = "kg"  # 'kg', 'ldm', 'stellplaetze', 'misch'
    gewichts_staffeln: list = field(default_factory=list)
    ldm_staffeln: list = field(default_factory=list)
    stellplatz_tarif: Optional[StellplatzTarif] = None
    zuschlaege: ZuschlaegeModell = field(default_factory=ZuschlaegeModell)
    zonen: dict = field(default_factory=dict)  # PLZ-zone → zone_factor
    notizen: str = ""
    quell_datei: str = ""


# ─── Tariff calculation ────────────────────────────────────────────────────────

def berechne_grundfracht(tarif: KundeTarif, gewicht_kg: float, ldm: float,
                          stellplaetze: float) -> float:
    """
    Calculate base freight (Grundfracht) for a shipment based on customer tariff.
    Uses the appropriate billing basis (KG / LDM / Stellplätze / mix).
    """
    grundfracht = 0.0

    if tarif.abrechnungsbasis in ("kg", "misch") and tarif.gewichts_staffeln and gewicht_kg > 0:
        for staffel in sorted(tarif.gewichts_staffeln, key=lambda s: s.von_kg):
            if gewicht_kg >= staffel.von_kg and gewicht_kg < staffel.bis_kg:
                if staffel.preis_eur > 0:
                    grundfracht = staffel.preis_eur
                elif staffel.preis_je_kg > 0:
                    grundfracht = gewicht_kg * staffel.preis_je_kg
                break

    if tarif.abrechnungsbasis in ("ldm", "misch") and tarif.ldm_staffeln and ldm > 0:
        ldm_preis = 0.0
        for staffel in sorted(tarif.ldm_staffeln, key=lambda s: s.von_ldm):
            if ldm >= staffel.von_ldm and ldm < staffel.bis_ldm:
                if staffel.preis_eur > 0:
                    ldm_preis = staffel.preis_eur
                elif staffel.preis_je_ldm > 0:
                    ldm_preis = ldm * staffel.preis_je_ldm
                break
        # For mixed billing: take the higher of KG or LDM price
        grundfracht = max(grundfracht, ldm_preis)

    if tarif.abrechnungsbasis in ("stellplaetze",) and tarif.stellplatz_tarif and stellplaetze > 0:
        st = tarif.stellplatz_tarif
        grundfracht = max(stellplaetze, st.mindeststellplaetze) * st.preis_je_stellplatz

    return max(grundfracht, tarif.mindestfracht)


def berechne_zuschlaege(tarif: KundeTarif, grundfracht: float,
                         km: float = 0) -> dict:
    """Calculate surcharges based on tariff model."""
    z = tarif.zuschlaege
    diesel = grundfracht * z.diesel_prozent / 100
    maut = (grundfracht * z.maut_prozent / 100) if z.maut_prozent > 0 else (km * z.maut_je_km)
    sonstige = grundfracht * z.sonstige_prozent / 100
    return {
        "diesel": round(diesel, 2),
        "maut": round(maut, 2),
        "insel": z.insel_pauschal,
        "sonstige": round(sonstige, 2),
    }


def berechne_soll_preis(tarif: KundeTarif, gewicht_kg: float, ldm: float,
                         stellplaetze: float, km: float = 0,
                         insel: bool = False) -> dict:
    """
    Calculate the expected (Soll) price for a shipment.
    Returns breakdown of Grundfracht + Zuschläge + Gesamt.
    """
    grundfracht = berechne_grundfracht(tarif, gewicht_kg, ldm, stellplaetze)
    zuschlaege = berechne_zuschlaege(tarif, grundfracht, km)
    if insel:
        zuschlaege["insel"] = tarif.zuschlaege.insel_pauschal

    gesamt = round(grundfracht + sum(zuschlaege.values()), 2)

    return {
        "grundfracht": round(grundfracht, 2),
        "diesel": zuschlaege["diesel"],
        "maut": zuschlaege["maut"],
        "insel": zuschlaege["insel"],
        "sonstige": zuschlaege["sonstige"],
        "soll_netto": gesamt,
    }


# ─── Tariff file parsers ───────────────────────────────────────────────────────

def parse_excel_tariff(filepath: Path, kundennummer: str = "", kundenname: str = "") -> KundeTarif:
    """
    Parse an Excel tariff sheet.
    Tries to detect:
     - Weight staffel tables (rows: KG ranges, cols: zones or prices)
     - LDM rate tables
     - Surcharge rows (Diesel, Maut, etc.)
    """
    tarif = KundeTarif(
        kundennummer=kundennummer,
        kundenname=kundenname,
        gueltig_ab="2024-01-01",
        quell_datei=filepath.name
    )

    try:
        xl = pd.ExcelFile(filepath)
        for sheet_name in xl.sheet_names:
            df = pd.read_excel(filepath, sheet_name=sheet_name, dtype=str, header=None)
            text = df.to_string().lower()

            # Detect weight staffel
            if any(kw in text for kw in ["kg", "gewicht", "weight"]):
                staffeln = _extract_kg_staffeln(df)
                if staffeln:
                    tarif.gewichts_staffeln = staffeln
                    tarif.abrechnungsbasis = "kg"
                    print(f"    Detected {len(staffeln)} KG-Staffeln in sheet '{sheet_name}'")

            # Detect LDM rates
            if any(kw in text for kw in ["ldm", "lademeter", "ladem"]):
                ldm_staffeln = _extract_ldm_staffeln(df)
                if ldm_staffeln:
                    tarif.ldm_staffeln = ldm_staffeln
                    tarif.abrechnungsbasis = "ldm" if not tarif.gewichts_staffeln else "misch"
                    print(f"    Detected {len(ldm_staffeln)} LDM-Staffeln in sheet '{sheet_name}'")

            # Detect surcharges
            zuschlaege = _extract_zuschlaege(df)
            if zuschlaege.diesel_prozent > 0 or zuschlaege.maut_prozent > 0:
                tarif.zuschlaege = zuschlaege
                print(f"    Detected surcharges: Diesel={zuschlaege.diesel_prozent}%, Maut={zuschlaege.maut_prozent}%")

            # Detect Mindestfracht
            mindest = _extract_mindestfracht(df)
            if mindest:
                tarif.mindestfracht = mindest
                print(f"    Mindestfracht: {mindest:.2f} €")

    except Exception as e:
        print(f"  [ERROR] Cannot parse Excel tariff {filepath.name}: {e}")

    return tarif


def _extract_kg_staffeln(df: pd.DataFrame) -> list:
    """Extract KG-based weight staffel from a DataFrame."""
    staffeln = []
    for i, row in df.iterrows():
        row_str = " ".join(str(v) for v in row.values if pd.notna(v)).lower()
        # Look for patterns like "0-100 kg: 25.00" or "100 | 500 | 18.50"
        numbers = re.findall(r"\d+[.,]?\d*", row_str)
        if len(numbers) >= 3 and any(kw in row_str for kw in ["kg", "bis", "von", "-"]):
            try:
                nums = [float(n.replace(",", ".")) for n in numbers[:3]]
                if nums[0] < nums[1] < 10000:  # plausible kg range
                    staffeln.append(GewichtsStaffel(
                        von_kg=nums[0], bis_kg=nums[1], preis_eur=nums[2]
                    ))
            except Exception:
                pass
    return staffeln


def _extract_ldm_staffeln(df: pd.DataFrame) -> list:
    """Extract LDM-based rate staffel."""
    staffeln = []
    for i, row in df.iterrows():
        row_str = " ".join(str(v) for v in row.values if pd.notna(v)).lower()
        if any(kw in row_str for kw in ["ldm", "lademeter", "0,", "0."]):
            numbers = re.findall(r"\d+[.,]?\d*", row_str)
            if len(numbers) >= 3:
                try:
                    nums = [float(n.replace(",", ".")) for n in numbers[:3]]
                    if nums[0] < nums[1] <= 13.6:  # max truck LDM
                        staffeln.append(LdmStaffel(
                            von_ldm=nums[0], bis_ldm=nums[1], preis_eur=nums[2]
                        ))
                except Exception:
                    pass
    return staffeln


def _extract_zuschlaege(df: pd.DataFrame) -> ZuschlaegeModell:
    """Extract surcharge percentages from tariff sheet."""
    z = ZuschlaegeModell()
    for i, row in df.iterrows():
        row_str = " ".join(str(v) for v in row.values if pd.notna(v)).lower()
        numbers = re.findall(r"\d+[.,]?\d*", row_str)
        if not numbers:
            continue
        try:
            val = float(numbers[0].replace(",", "."))
            if any(kw in row_str for kw in ["diesel", "kraftstoff", "fuel", "ksz"]):
                z.diesel_prozent = val
            elif any(kw in row_str for kw in ["maut", "toll"]):
                z.maut_prozent = val
            elif any(kw in row_str for kw in ["insel", "island"]):
                z.insel_pauschal = val
        except Exception:
            pass
    return z


def _extract_mindestfracht(df: pd.DataFrame) -> Optional[float]:
    """Extract Mindestfracht (minimum freight charge)."""
    for i, row in df.iterrows():
        row_str = " ".join(str(v) for v in row.values if pd.notna(v)).lower()
        if any(kw in row_str for kw in ["mindest", "minimum", "mindestfracht"]):
            numbers = re.findall(r"\d+[.,]?\d*", row_str)
            if numbers:
                try:
                    return float(numbers[0].replace(",", "."))
                except Exception:
                    pass
    return None


def parse_pdf_tariff(filepath: Path, kundennummer: str = "", kundenname: str = "") -> KundeTarif:
    """Parse a PDF tariff document."""
    tarif = KundeTarif(
        kundennummer=kundennummer,
        kundenname=kundenname,
        gueltig_ab="2024-01-01",
        quell_datei=filepath.name
    )

    full_text = ""
    try:
        with pdfplumber.open(str(filepath)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    full_text += t + "\n"
    except Exception as e:
        print(f"  [ERROR] Cannot read PDF {filepath.name}: {e}")
        return tarif

    # Extract gueltig_ab
    date_match = re.search(r"(?:g[üu]ltig ab|valid from|ab dem)[:\s]+(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
                           full_text, re.IGNORECASE)
    if date_match:
        tarif.gueltig_ab = date_match.group(1)

    # Extract Diesel
    diesel_match = re.search(r"diesel(?:zuschlag|zuschl\.|)[:\s]+([\d.,]+)\s*%",
                              full_text, re.IGNORECASE)
    if diesel_match:
        tarif.zuschlaege.diesel_prozent = float(diesel_match.group(1).replace(",", "."))

    # Extract Maut
    maut_match = re.search(r"maut(?:zuschlag|zuschl\.|)[:\s]+([\d.,]+)\s*%",
                            full_text, re.IGNORECASE)
    if maut_match:
        tarif.zuschlaege.maut_prozent = float(maut_match.group(1).replace(",", "."))

    # Extract Mindestfracht
    mf_match = re.search(r"mindestfracht[:\s]+([\d.,]+)\s*€?",
                          full_text, re.IGNORECASE)
    if mf_match:
        tarif.mindestfracht = float(mf_match.group(1).replace(",", "."))

    tarif.notizen = full_text[:500]
    return tarif


def load_tariffs(input_dir: Path, kundennummer: str = "",
                 kundenname: str = "") -> list[KundeTarif]:
    """Load all tariff files from a directory."""
    files = (list(input_dir.glob("*.xlsx")) + list(input_dir.glob("*.xls")) +
             list(input_dir.glob("*.pdf")) + list(input_dir.glob("*.json")))

    if not files:
        print(f"  [WARN] No tariff files found in {input_dir}")
        return []

    tarife = []
    print(f"  Found {len(files)} tariff file(s)")

    for f in sorted(files):
        print(f"    Parsing {f.name}...")
        if f.suffix.lower() in (".xlsx", ".xls"):
            t = parse_excel_tariff(f, kundennummer, kundenname)
        elif f.suffix.lower() == ".pdf":
            t = parse_pdf_tariff(f, kundennummer, kundenname)
        elif f.suffix.lower() == ".json":
            with open(f) as jf:
                data = json.load(jf)
            t = KundeTarif(**data)
        else:
            continue
        tarife.append(t)

    return tarife


def save_tariffs(tarife: list[KundeTarif], output_dir: Path, prefix: str = ""):
    """Save tariff models to JSON for reuse in reconciliation."""
    for tarif in tarife:
        name = tarif.kundennummer or tarif.kundenname.replace(" ", "_").lower()
        out_file = output_dir / f"tarif_{prefix}{name}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(asdict(tarif), f, indent=2, ensure_ascii=False)
        print(f"  → Saved: {out_file}")


def print_tariff_summary(tarife: list[KundeTarif]):
    """Print tariff model summary."""
    print(f"\n{'='*60}")
    print(f"TARIF-ZUSAMMENFASSUNG")
    print(f"{'='*60}")
    for t in tarife:
        print(f"\n  Kunde:           {t.kundenname} ({t.kundennummer})")
        print(f"  Gültig ab:       {t.gueltig_ab}")
        print(f"  Basis:           {t.abrechnungsbasis}")
        print(f"  Mindestfracht:   {t.mindestfracht:.2f} €")
        print(f"  KG-Staffeln:     {len(t.gewichts_staffeln)}")
        print(f"  LDM-Staffeln:    {len(t.ldm_staffeln)}")
        print(f"  Diesel:          {t.zuschlaege.diesel_prozent:.1f}%")
        print(f"  Maut:            {t.zuschlaege.maut_prozent:.1f}%")
        if t.gewichts_staffeln:
            print(f"  KG-Staffeln Detail:")
            for s in t.gewichts_staffeln[:5]:
                print(f"    {s.von_kg:>8.0f} – {s.bis_kg:>8.0f} kg: {s.preis_eur:>8.2f} €")


def main():
    parser = argparse.ArgumentParser(description="TMS Tariff Parser")
    parser.add_argument("--input", type=str, required=True,
                        help="Input directory with tariff files")
    parser.add_argument("--output", type=str, default="output/",
                        help="Output directory for tariff JSON")
    parser.add_argument("--kunde", type=str, default="",
                        help="Customer name prefix for output files")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    # Derive customer name from path
    input_dir = Path(args.input)
    kunde_name = args.kunde or input_dir.parts[-2] if len(input_dir.parts) >= 2 else ""

    tarife = load_tariffs(input_dir, kundenname=kunde_name)
    if tarife:
        print_tariff_summary(tarife)
        save_tariffs(tarife, output_dir, prefix=f"{kunde_name}_")
    else:
        print("[WARN] No tariffs loaded — manual entry may be required")
        # Create template
        template = KundeTarif(
            kundennummer="XXXXX",
            kundenname=kunde_name or "Kunde",
            gueltig_ab="2024-01-01",
            mindestfracht=15.0,
            abrechnungsbasis="misch",
            gewichts_staffeln=[
                asdict(GewichtsStaffel(0, 100, 25.00)),
                asdict(GewichtsStaffel(100, 500, 0, 0.18)),
                asdict(GewichtsStaffel(500, 1000, 0, 0.15)),
                asdict(GewichtsStaffel(1000, 5000, 0, 0.12)),
            ],
            ldm_staffeln=[
                asdict(LdmStaffel(0, 1.0, 85.00)),
                asdict(LdmStaffel(1.0, 3.0, 0, 80.00)),
                asdict(LdmStaffel(3.0, 13.6, 0, 75.00)),
            ],
            zuschlaege=asdict(ZuschlaegeModell(diesel_prozent=18.0, maut_prozent=4.5)),
            notizen="VORLAGE - bitte mit echten Konditionsdaten füllen"
        )
        template_file = output_dir / f"tarif_{kunde_name or 'vorlage'}_TEMPLATE.json"
        with open(template_file, "w", encoding="utf-8") as f:
            json.dump(asdict(template), f, indent=2, ensure_ascii=False)
        print(f"  → Template saved: {template_file}")
        print("  → Bitte Tarifdaten manuell eintragen und _TEMPLATE aus dem Dateinamen entfernen")


if __name__ == "__main__":
    main()
