"""
Etappe 5k Nachverdichtung — SikaATM re-validation against Dinas PDFs.

For each SikaATM parquet row (erka_kundennr 18894 / 18748):
  1. Detect groupage PDFs (contain 'zusammengefasst') — DLV Anlage 1 does not apply
  2. Re-extract shipment weight from PDF text (gewicht_kg is NaN for all rows)
  3. Run SikaATMDeCalculator (18894) or SikaATMChCalculator (18748)
  4. Compare soll vs fracht; classify result
  5. Write data/reports/sika_atm_revalidation.md

Match threshold: ±2%
95% threshold applies to direct (non-groupage) rows only.

Usage:
    python src/sika_atm_revalidation.py
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import fitz  # PyMuPDF
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from tms.tariff.calculators.sika_atm import SikaATMChCalculator, SikaATMDeCalculator

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PARQUET   = Path("data/parsed/dinas_pdfs.parquet")
REPORT    = Path("data/reports/sika_atm_revalidation.md")
MATCH_PCT = 2.0   # ≤2% deviation → match

ERKA_18894 = "18894"   # Sika Automotive Deutschland GmbH → SikaATMDeCalculator
ERKA_18748 = "18748"   # Sika Automotive AG (CH)          → SikaATMChCalculator

_ch_calc = SikaATMChCalculator()
_de_calc = SikaATMDeCalculator()

# ---------------------------------------------------------------------------
# PDF groupage detection
# ---------------------------------------------------------------------------

def _is_groupage_pdf(pdf_path: str) -> bool:
    """True if invoice contains 'zusammengefasst' (Sammelladung/groupage)."""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            if "zusammengefasst" in page.get_text().lower():
                return True
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# PDF weight extraction
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(
    r'\b(\d+)\)\s+\d{2}\.\d{2}\.\d{2}\s*\n\s*\((\d+)\)',
)
_WEIGHT_BEFORE_FRACHT_RE = re.compile(
    r'(\d[\d.]*)\s*kg\s*\n\s*(?:FRACHT|FREIGHT)',
    re.IGNORECASE,
)
_WEIGHT_RE = re.compile(r'\b(\d+)\s*kg\b')


def _parse_int_weight(raw: str) -> int:
    return int(raw.replace(".", "").replace(",", ""))


def _extract_weights_from_pdf(pdf_path: str) -> dict[int, int]:
    """Return {sendungsnummer: weight_kg} for all sections in PDF."""
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return {}

    full_text = ""
    for page in doc:
        full_text += page.get_text()

    matches = list(_SECTION_RE.finditer(full_text))
    if not matches:
        return {}

    result: dict[int, int] = {}
    for idx, m in enumerate(matches):
        sendnr = int(m.group(2))
        start  = m.start()
        end    = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        section_text = full_text[start:end]

        wm = _WEIGHT_BEFORE_FRACHT_RE.search(section_text)
        if wm:
            result[sendnr] = _parse_int_weight(wm.group(1))
            continue

        wm = _WEIGHT_RE.search(section_text)
        if wm:
            result[sendnr] = _parse_int_weight(wm.group(1))

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> None:
    df = pd.read_parquet(PARQUET)
    sika = df[df["erka_kundennr"].isin([ERKA_18894, ERKA_18748])].copy()

    sika["leistung_date"] = pd.to_datetime(sika["leistung_date"])
    sika = sika[sika["leistung_date"] <= pd.Timestamp("2025-09-26")]
    sika = sika[sika["fracht"] > 0]
    sika = sika[sika["fracht_currency"] == "EUR"]

    print(f"Rows after filtering: {len(sika)}")

    # Pre-scan all unique PDFs for groupage flag and weights
    print("Scanning PDFs...")
    groupage_set: set[str] = set()
    weight_cache: dict[str, dict[int, int]] = {}
    for pdf_path, grp in sika.groupby("pdf_path"):
        is_groupage = _is_groupage_pdf(pdf_path)
        if is_groupage:
            groupage_set.add(pdf_path)
        weight_cache[pdf_path] = _extract_weights_from_pdf(pdf_path)
    print(f"  Groupage PDFs: {len(groupage_set)}")

    # Per-row evaluation
    rows: list[dict] = []
    for _, row in sika.iterrows():
        erka      = str(row["erka_kundennr"])
        sendnr    = int(row["sendungsnummer"]) if pd.notna(row["sendungsnummer"]) else None
        pdf_path  = row["pdf_path"]
        empf_plz  = str(row["empf_plz"]).strip() if pd.notna(row["empf_plz"]) else ""
        empf_land = str(row["empf_land"]).strip() if pd.notna(row["empf_land"]) else ""
        fracht    = float(row["fracht"])
        is_groupage = pdf_path in groupage_set

        weight_kg = weight_cache.get(pdf_path, {}).get(sendnr) if sendnr else None

        result_row: dict = {
            "erka":       erka,
            "sendnr":     sendnr,
            "pdf_path":   pdf_path,
            "empf_plz":   empf_plz,
            "empf_land":  empf_land,
            "weight_kg":  weight_kg,
            "fracht_ist": fracht,
            "soll":       None,
            "dev_pct":    None,
            "class":      None,
            "is_groupage": is_groupage,
            "error":      None,
        }

        if is_groupage:
            result_row["class"] = "groupage"
            rows.append(result_row)
            continue

        if weight_kg is None:
            result_row["class"] = "no_weight"
            rows.append(result_row)
            continue

        calc = _de_calc if erka == ERKA_18894 else _ch_calc

        try:
            r = calc.calculate(empf_plz, empf_land, tonnage_kg=float(weight_kg))
            soll = float(r.basispreis)
            dev_pct = (soll - fracht) / fracht * 100.0
            result_row["soll"]    = soll
            result_row["dev_pct"] = dev_pct
            result_row["class"]   = "match" if abs(dev_pct) <= MATCH_PCT else "deviation"
        except LookupError as e:
            result_row["class"] = "lookup_error"
            result_row["error"] = str(e)[:120]
        except ValueError as e:
            result_row["class"] = "value_error"
            result_row["error"] = str(e)[:120]
        except Exception as e:
            result_row["class"] = "error"
            result_row["error"] = str(e)[:120]

        rows.append(result_row)

    results = pd.DataFrame(rows)
    direct  = results[~results["is_groupage"]]

    # -----------------------------------------------------------------------
    # Summary stats per erka (direct rows only for match %)
    # -----------------------------------------------------------------------
    def _stats(all_sub: pd.DataFrame, direct_sub: pd.DataFrame, label: str) -> dict:
        n_total    = len(all_sub)
        n_groupage = (all_sub["class"] == "groupage").sum()
        n_direct   = len(direct_sub)
        n_match    = (direct_sub["class"] == "match").sum()
        n_dev      = (direct_sub["class"] == "deviation").sum()
        n_no_wt    = (direct_sub["class"] == "no_weight").sum()
        n_lu       = (direct_sub["class"] == "lookup_error").sum()
        n_not_nom  = direct_sub[
            (direct_sub["class"] == "lookup_error") &
            (direct_sub["empf_land"].isin(["DE", "CH"]))
        ].shape[0]
        denom = n_match + n_dev + (n_lu - n_not_nom)
        match_pct = (n_match / denom * 100) if denom > 0 else 0.0
        return {
            "label": label, "n_total": n_total, "n_groupage": n_groupage,
            "n_direct": n_direct, "match": n_match, "deviation": n_dev,
            "no_weight": n_no_wt, "lookup_error": n_lu, "not_nominated": n_not_nom,
            "match_pct": match_pct,
        }

    s_de = _stats(
        results[results["erka"] == ERKA_18894],
        direct[direct["erka"] == ERKA_18894],
        "18894 (De)",
    )
    s_ch = _stats(
        results[results["erka"] == ERKA_18748],
        direct[direct["erka"] == ERKA_18748],
        "18748 (CH)",
    )

    # Top 10 deviations in direct rows
    deviations = direct[direct["class"] == "deviation"].copy()
    deviations["abs_dev"] = deviations["dev_pct"].abs()
    top10 = deviations.nlargest(10, "abs_dev")

    # -----------------------------------------------------------------------
    # Markdown report
    # -----------------------------------------------------------------------
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    lines += [
        "# SikaATM Re-Validation Report",
        "",
        f"Generated: {date.today()}  ",
        f"Total rows evaluated: {len(results)}  ",
        f"Match threshold: ±{MATCH_PCT}%  ",
        "Note: DLV Anlage 1 rates apply to direct (Einzelsendung) shipments only.",
        "      Groupage (Sammelladung) invoices are classified separately.",
        "",
        "## Summary Table (Direct Shipments Only)",
        "",
        "| ERKA | N total | Groupage | N direct | Match | Deviation | No Weight | LookupErr | Not Nominated | Match % (direct excl. not-nom) |",
        "|------|---------|----------|----------|-------|-----------|-----------|-----------|---------------|-------------------------------|",
    ]
    for s in [s_de, s_ch]:
        lines.append(
            f"| {s['label']} | {s['n_total']} | {s['n_groupage']} | {s['n_direct']} "
            f"| {s['match']} | {s['deviation']} | {s['no_weight']} "
            f"| {s['lookup_error']} | {s['not_nominated']} | {s['match_pct']:.1f}% |"
        )

    lines += ["", "## Classification Details (Direct Only)", ""]

    for label, sub in [
        ("ERKA 18894 (SikaATMDeCalculator)", direct[direct["erka"] == ERKA_18894]),
        ("ERKA 18748 (SikaATMChCalculator)", direct[direct["erka"] == ERKA_18748]),
    ]:
        lines.append(f"### {label}")
        lines.append("")
        cls_vc = sub["class"].value_counts()
        for cls, cnt in cls_vc.items():
            pct = cnt / len(sub) * 100 if len(sub) > 0 else 0
            lines.append(f"- **{cls}**: {cnt} ({pct:.1f}%)")
        lines.append("")

        dev_sub = sub[sub["class"] == "deviation"]
        if len(dev_sub) > 0:
            lines.append("  Deviations by empf_land:")
            for land, cnt in dev_sub["empf_land"].value_counts().items():
                avg_dev = dev_sub[dev_sub["empf_land"] == land]["dev_pct"].mean()
                lines.append(f"  - {land}: {cnt} rows, avg dev={avg_dev:+.1f}%")
            lines.append("")

        lu_sub = sub[sub["class"] == "lookup_error"]
        if len(lu_sub) > 0:
            lines.append("  LookupError sample (up to 5):")
            for _, r in lu_sub.head(5).iterrows():
                lines.append(f"  - PLZ={r['empf_plz']} land={r['empf_land']} → {r['error']}")
            lines.append("")

    lines += ["## Top 10 Absolute Deviations (Direct Only)", ""]
    if len(top10) > 0:
        lines.append("| Sendnr | ERKA | Land | PLZ | weight_kg | fracht_ist | soll | dev_pct% |")
        lines.append("|--------|------|------|-----|-----------|------------|------|---------|")
        for _, r in top10.iterrows():
            lines.append(
                f"| {r['sendnr']} | {r['erka']} | {r['empf_land']} | {r['empf_plz']} "
                f"| {r['weight_kg']:.0f} | {r['fracht_ist']:.2f} "
                f"| {r['soll']:.2f} | {r['dev_pct']:+.1f}% |"
            )
    else:
        lines.append("_No deviations found in direct shipments._")

    lines += ["", "## Known Gaps", ""]
    lines += [
        f"- **Groupage**: {(results['class']=='groupage').sum()} rows from Sammelladung invoices "
        f"(identified by 'zusammengefasst' in PDF). DLV Anlage 1 does not apply; separate rate structure.",
        "- **no_weight**: PDF weight extraction failed (section pattern not matched).",
        "- **not_nominated**: DE/CH destination — ERKA not nominated per DLV; expected LookupError.",
        "- **real_lookup**: Zone not found in tariff sheet (PLZ prefix not configured).",
        "",
    ]

    # Histogram of deviations for direct rows
    matched_devs = direct[direct["class"].isin(["match", "deviation"])]["dev_pct"].dropna()
    if len(matched_devs) > 0:
        import numpy as np
        lines += ["## Deviation Histogram (Direct Only)", ""]
        bins = [-100, -20, -10, -5, -2, 0, 2, 5, 10, 20, 100]
        labels_hist = ["≤-20%", "-20..-10%", "-10..-5%", "-5..-2%", "-2..0%",
                       "0..+2%", "+2..+5%", "+5..+10%", "+10..+20%", ">+20%"]
        counts, _ = np.histogram(matched_devs, bins=bins)
        lines.append("| Bucket | Count |")
        lines.append("|--------|-------|")
        for lbl, cnt in zip(labels_hist, counts):
            lines.append(f"| {lbl} | {cnt} |")
        lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written to {REPORT}")

    # -----------------------------------------------------------------------
    # Console summary
    # -----------------------------------------------------------------------
    print()
    print("=" * 70)
    print("SUMMARY — SikaATM Nachverdichtung (post summary before commit)")
    print("=" * 70)
    hdr = f"{'ERKA':<12} {'Total':>6} {'Grpge':>6} {'Direct':>7} {'Match':>6} {'Dev':>5} {'LU':>4} {'NotNom':>7} {'Match%':>7}"
    print(hdr)
    print("-" * 70)
    for s in [s_de, s_ch]:
        print(
            f"{s['label']:<12} {s['n_total']:>6} {s['n_groupage']:>6} {s['n_direct']:>7} "
            f"{s['match']:>6} {s['deviation']:>5} {s['lookup_error']:>4} "
            f"{s['not_nominated']:>7} {s['match_pct']:>6.1f}%"
        )
    print()
    print("Top 10 absolute deviations (direct only):")
    if len(top10) > 0:
        for _, r in top10.iterrows():
            print(
                f"  sendnr={r['sendnr']} erka={r['erka']} {r['empf_land']}/{r['empf_plz']} "
                f"wt={r['weight_kg']:.0f}kg ist={r['fracht_ist']:.2f} "
                f"soll={r['soll']:.2f} dev={r['dev_pct']:+.1f}%"
            )
    else:
        print("  (none)")
    print()

    total_groupage = (results["class"] == "groupage").sum()
    total_no_wt = (results["class"] == "no_weight").sum()
    total_not_nom = sum(s["not_nominated"] for s in [s_de, s_ch])
    print("Known gaps:")
    print(f"  groupage (Sammelladung, DLV N/A):  {total_groupage}")
    print(f"  no_weight (extraction failed):      {total_no_wt}")
    print(f"  not_nominated (DE/CH dest):         {total_not_nom}")
    print()

    ok_de = s_de["match_pct"] >= 95.0
    ok_ch = s_ch["match_pct"] >= 95.0
    print(
        f"Threshold ≥95% (direct excl. not-nom): "
        f"18894={'PASS' if ok_de else 'FAIL'}, "
        f"18748={'PASS' if ok_ch else 'FAIL'}"
    )


if __name__ == "__main__":
    run()
