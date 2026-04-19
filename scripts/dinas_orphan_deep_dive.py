"""
Etappe 8e Teil 2 — Vertiefte Analyse der größten Dinas-Orphan-Familien.

Klassifiziert jede Dinas-Orphan-Familie als:
  likely_ax_successor_found  – AX hat plausiblen Nachfolger (anderes PLZ, gleiches Land)
  ax_coverage_gap            – Route war kurz vor Cutoff aktiv, kein AX-Nachfolger
  no_ax_successor_plausible  – Route bereits länger vor Cutoff inaktiv oder
                               klar eingestellt
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

PARQUET = Path("output/etappe8_cluster_families.parquet")
OUT_MD  = Path("data/reports/dinas_orphan_deep_dive.md")

CUTOFF      = datetime.date(2025, 9, 26)
GAP_DAYS    = 60   # letzte Aktivität ≤ 60 Tage vor Cutoff → kandidat für ax_coverage_gap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _last_active(rows: pd.DataFrame) -> datetime.date | None:
    dates = pd.to_datetime(rows["leistungsdatum"], errors="coerce").dropna()
    return dates.max().date() if len(dates) else None


def _days_to_cutoff(last: datetime.date | None) -> int | None:
    if last is None:
        return None
    return (CUTOFF - last).days


def classify_dinas_orphan(
    fkey: str,
    dinas_rows: pd.DataFrame,
    all_ax: pd.DataFrame,
) -> tuple[str, str, pd.DataFrame | None]:
    """
    Returns (classification, explanation, candidate_ax_rows | None).

    Classification: 'likely_ax_successor_found' | 'ax_coverage_gap' | 'no_ax_successor_plausible'
    """
    parts = fkey.split("|")
    if len(parts) != 4:
        return "no_ax_successor_plausible", "Ungültiger family_key", None
    kunde, abs_plz, empf_plz, tg = parts

    last = _last_active(dinas_rows)
    days = _days_to_cutoff(last)

    # Derive expected empf_land from Dinas rows
    lands = dinas_rows["empf_land"].dropna().unique()
    primary_land = lands[0] if len(lands) else ""

    # Search AX for same kunde
    ax_same_kunde = all_ax[all_ax["kunde_normalisiert"] == kunde]

    # --- Criterion a: same kunde + same abs_plz + any empf_plz (different PLZ coding?)
    ax_same_abs = ax_same_kunde[ax_same_kunde["abs_plz_2"] == abs_plz]

    # --- Criterion b: same kunde + same empf_land + same tarifgruppe (different abs?)
    ax_same_land = pd.DataFrame()
    if primary_land:
        ax_same_land = ax_same_kunde[
            ax_same_kunde["empf_land"].str.upper() == primary_land.upper()
        ]

    # --- Criterion c: same kunde + same tarifgruppe + any PLZ, first 3 months post-migration
    post_cutoff = pd.Timestamp("2025-09-27")
    post_90d    = pd.Timestamp("2025-12-27")
    ax_early_post = ax_same_kunde[
        (pd.to_datetime(ax_same_kunde["leistungsdatum"], errors="coerce") >= post_cutoff) &
        (pd.to_datetime(ax_same_kunde["leistungsdatum"], errors="coerce") <= post_90d) &
        (ax_same_kunde["tarifgruppe"] == tg)
    ]

    # --- Decision logic ---

    # 1. Same abs_plz AND same empf_land → high plausibility successor
    if primary_land:
        cand = ax_same_abs[ax_same_abs["empf_land"].str.upper() == primary_land.upper()]
        if len(cand):
            return (
                "likely_ax_successor_found",
                f"AX hat {len(cand['family_key'].unique())} Familie(n) mit gleicher abs_plz={abs_plz} "
                f"und gleichem Land={primary_land}, aber anderer empf_plz",
                cand,
            )

    # 2. Same empf_land + same tg → different abs? (inbound/re-routed)
    if len(ax_same_land) and primary_land:
        cand = ax_same_land[ax_same_land["tarifgruppe"] == tg]
        if len(cand):
            return (
                "likely_ax_successor_found",
                f"AX hat {len(cand['family_key'].unique())} Familie(n) mit gleichem Land={primary_land} "
                f"und tarifgruppe={tg}, aber anderer PLZ-Kombination",
                cand,
            )

    # 3. ax_coverage_gap: route was active near cutoff, no plausible successor
    if days is not None and days <= GAP_DAYS:
        return (
            "ax_coverage_gap",
            f"Letzter Dinas-Cluster {days} Tage vor Cutoff ({last}), kein plausibles AX-Pendant gefunden",
            None,
        )

    # 4. early post migration AX activity by same kunde+tg → might be same lane re-keyed
    if len(ax_early_post):
        return (
            "likely_ax_successor_found",
            f"AX hat {len(ax_early_post['family_key'].unique())} Familie(n) mit gleichem Kunden "
            f"in den ersten 90 Tagen post-Migration, jedoch andere PLZ",
            ax_early_post,
        )

    # 5. Fallback: truly discontinued
    last_str = str(last) if last else "unbekannt"
    return (
        "no_ax_successor_plausible",
        f"Letzter Dinas-Cluster: {last_str} ({days or '?'} Tage vor Cutoff). Kein AX-Pendant gefunden.",
        None,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    result = pd.read_parquet(PARQUET)
    dinas_rows = result[result["cluster_source"] == "DINAS"]
    ax_rows    = result[result["cluster_source"] == "AX"]

    # Top-10 Dinas orphan families by total fracht
    orphan_dinas = dinas_rows[dinas_rows["is_orphan_dinas"] == True].copy()

    fam_vol = (
        orphan_dinas.groupby("family_key")["fracht_ohne_diesel_eur"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    lines: list[str] = []
    lines += [
        "# Etappe 8e — Dinas-Orphan Deep Dive",
        "",
        f"**Stand:** 2026-04-19  ",
        f"**Cutoff:** {CUTOFF}  ",
        f"**Quelle:** `{PARQUET}`",
        "",
        "Analysiert werden die Top-10 Dinas-Orphan-Familien nach Fracht-Volumen (€).  ",
        "Klassifikationsschema:",
        "- `likely_ax_successor_found` – AX hat einen plausiblen Nachfolger (gleicher Kunde, ähnliche Route, andere PLZ-Kodierung)",
        "- `ax_coverage_gap` – Route war ≤ 60 Tage vor Cutoff aktiv, kein AX-Pendant → potenziell unabgerechnet",
        "- `no_ax_successor_plausible` – Route länger inaktiv vor Cutoff oder klar eingestellt",
        "",
        "---",
        "",
    ]

    # Aggregated summary (all orphan Dinas)
    all_orphan_fkeys = orphan_dinas["family_key"].unique()
    summary: dict[str, list] = {
        "likely_ax_successor_found": [],
        "ax_coverage_gap": [],
        "no_ax_successor_plausible": [],
    }
    for fkey in all_orphan_fkeys:
        rows = orphan_dinas[orphan_dinas["family_key"] == fkey]
        clf, _, _ = classify_dinas_orphan(fkey, rows, ax_rows)
        summary[clf].append(fkey)

    gap_fkeys = summary["ax_coverage_gap"]
    gap_vol = orphan_dinas[orphan_dinas["family_key"].isin(gap_fkeys)]["fracht_ohne_diesel_eur"].sum()
    likely_vol = orphan_dinas[orphan_dinas["family_key"].isin(summary["likely_ax_successor_found"])]["fracht_ohne_diesel_eur"].sum()
    no_vol = orphan_dinas[orphan_dinas["family_key"].isin(summary["no_ax_successor_plausible"])]["fracht_ohne_diesel_eur"].sum()

    lines += [
        "## Aggregierte Klassifikation (alle Dinas-Orphans)",
        "",
        f"| Klassifikation | Familien | Gesamt-Fracht |",
        f"|----------------|---------|--------------|",
        f"| `likely_ax_successor_found` | {len(summary['likely_ax_successor_found'])} | {likely_vol:,.0f} € |",
        f"| `ax_coverage_gap` | {len(summary['ax_coverage_gap'])} | {gap_vol:,.0f} € |",
        f"| `no_ax_successor_plausible` | {len(summary['no_ax_successor_plausible'])} | {no_vol:,.0f} € |",
        "",
        "---",
        "",
        "## Top-10 Dinas-Orphan-Familien (nach Fracht-Volumen)",
        "",
    ]

    for rank, (fkey, total_fracht) in enumerate(fam_vol.items(), 1):
        fam_rows = orphan_dinas[orphan_dinas["family_key"] == fkey].copy()
        clf, explanation, cands = classify_dinas_orphan(fkey, fam_rows, ax_rows)

        parts = fkey.split("|")
        kunde, abs_plz, empf_plz, tg = parts if len(parts) == 4 else (fkey, "", "", "")

        last = _last_active(fam_rows)
        days = _days_to_cutoff(last)
        n_clusters = len(fam_rows)

        lines += [
            f"### {rank}. `{fkey}`",
            "",
            f"| Feld | Wert |",
            f"|------|------|",
            f"| Kunde (KNR) | {kunde} |",
            f"| Absender-PLZ 2-st. | {abs_plz or '–'} |",
            f"| Empfänger-PLZ 2-st. | {empf_plz or '–'} |",
            f"| Tarifgruppe | {tg} |",
            f"| Gesamt-Fracht | {total_fracht:,.0f} € |",
            f"| Anzahl Dinas-Cluster | {n_clusters} |",
            f"| Letzter Cluster | {last} |",
            f"| Tage vor Cutoff | {days} |",
            f"| **Klassifikation** | `{clf}` |",
            "",
            "**Dinas-Cluster:**",
            "",
            "| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |",
            "|-------|-----------|-----------|------------|----------|",
        ]

        for _, row in fam_rows.sort_values("leistungsdatum", ascending=False).iterrows():
            ldt = str(row["leistungsdatum"])[:10]
            cid = str(row["cluster_id"])
            fr  = f"{row['fracht_ohne_diesel_eur']:,.2f}" if pd.notna(row["fracht_ohne_diesel_eur"]) else "–"
            bw  = f"{row['basiseinheit_wert']:.0f}" if pd.notna(row.get("basiseinheit_wert")) else "–"
            ep  = f"{row['eur_pro_einheit']:.2f}" if pd.notna(row.get("eur_pro_einheit")) else "–"
            lines.append(f"| {ldt} | {cid} | {fr} | {bw} | {ep} |")

        lines += ["", f"**Near-Match-Analyse auf AX-Seite:**", ""]
        lines.append(f"> {explanation}")
        lines.append("")

        if cands is not None and len(cands):
            sample_fkeys = cands["family_key"].unique()[:3]
            lines += [
                "Plausible AX-Nachfolger-Familien (bis 3):",
                "",
                "| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |",
                "|--------------|---------|----------------|-----------|-----------------|",
            ]
            for sfkey in sample_fkeys:
                sc = cands[cands["family_key"] == sfkey]
                avg_fr = sc["fracht_ohne_diesel_eur"].mean()
                land   = sc["empf_land"].iloc[0] if len(sc) else ""
                last_s = str(pd.to_datetime(sc["leistungsdatum"], errors="coerce").max())[:10]
                lines.append(
                    f"| `{sfkey}` | {len(sc)} | {avg_fr:,.0f} € | {land} | {last_s} |"
                )
            lines.append("")

        lines += ["---", ""]

    # ax_coverage_gap detail
    lines += [
        "## ax_coverage_gap – Vollständige Liste",
        "",
        "Familien, bei denen der letzte Dinas-Cluster ≤ 60 Tage vor Migrations-Cutoff lag  ",
        "und kein plausibles AX-Pendant existiert. Das sind potenziell **unabgerechnete Lanes**.",
        "",
        f"| Family-Key | Letzter Dinas | Tage vor Cutoff | Gesamt-Fracht |",
        f"|-----------|-------------|----------------|--------------|",
    ]

    for fkey in sorted(gap_fkeys, key=lambda k: orphan_dinas[orphan_dinas["family_key"]==k]["fracht_ohne_diesel_eur"].sum(), reverse=True):
        rows = orphan_dinas[orphan_dinas["family_key"] == fkey]
        last = _last_active(rows)
        days = _days_to_cutoff(last)
        vol  = rows["fracht_ohne_diesel_eur"].sum()
        lines.append(f"| `{fkey}` | {last} | {days} | {vol:,.0f} € |")

    total_gap_vol = orphan_dinas[orphan_dinas["family_key"].isin(gap_fkeys)]["fracht_ohne_diesel_eur"].sum()
    lines += [
        "",
        f"**Gesamt ax_coverage_gap Volumen: {total_gap_vol:,.0f} €**",
        "",
        "---",
        "",
        "*Bericht automatisch generiert von `scripts/dinas_orphan_deep_dive.py`.*",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report geschrieben: {OUT_MD} ({len(lines)} Zeilen)")

    print("\n=== Aggregierte Klassifikation ===")
    print(f"likely_ax_successor_found : {len(summary['likely_ax_successor_found'])} Familien, {likely_vol:,.0f} €")
    print(f"ax_coverage_gap           : {len(summary['ax_coverage_gap'])} Familien, {gap_vol:,.0f} €")
    print(f"no_ax_successor_plausible : {len(summary['no_ax_successor_plausible'])} Familien, {no_vol:,.0f} €")
    if gap_fkeys:
        print(f"\nax_coverage_gap Familien:")
        for fkey in sorted(gap_fkeys, key=lambda k: orphan_dinas[orphan_dinas["family_key"]==k]["fracht_ohne_diesel_eur"].sum(), reverse=True):
            rows = orphan_dinas[orphan_dinas["family_key"] == fkey]
            last = _last_active(rows)
            vol  = rows["fracht_ohne_diesel_eur"].sum()
            print(f"  {fkey}  last={last}  {vol:,.0f} €")


if __name__ == "__main__":
    main()
