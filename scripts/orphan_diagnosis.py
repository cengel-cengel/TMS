"""
Orphan family diagnosis for Etappe 8 cluster-matching output.
Generates data/reports/orphan_diagnosis.md
"""

import sys
import os
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from datetime import date

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df = pd.read_parquet('output/etappe8_cluster_families.parquet')

# Separate by source
dinas_df = df[df['cluster_source'] == 'DINAS'].copy()
ax_df    = df[df['cluster_source'] == 'AX'].copy()

# Orphan subsets
orphan_ax    = ax_df[ax_df['is_orphan_ax']].copy()
orphan_dinas = dinas_df[dinas_df['is_orphan_dinas']].copy()

# ---------------------------------------------------------------------------
# Helper: Levenshtein distance == 1 for 2-char strings
# ---------------------------------------------------------------------------
def lev1_2char(a: str, b: str) -> bool:
    """Return True if a and b have Levenshtein distance == 1 (2-char strings)."""
    if a == b:
        return False
    if len(a) != len(b):
        # length difference of 1: insertion/deletion
        if abs(len(a) - len(b)) == 1:
            shorter, longer = (a, b) if len(a) < len(b) else (b, a)
            # check if shorter is a prefix or suffix with one char missing
            for i in range(len(longer)):
                if longer[:i] + longer[i+1:] == shorter:
                    return True
        return False
    else:
        # same length: exactly one substitution
        diffs = sum(1 for x, y in zip(a, b) if x != y)
        return diffs == 1

# ---------------------------------------------------------------------------
# Near-match logic
# ---------------------------------------------------------------------------
def classify_near_match(fam_row, other_df):
    """
    fam_row: a dict with keys: kunde_normalisiert, abs_plz_2, empf_plz_2, tarifgruppe
    other_df: the full dataframe of the OTHER side (dinas_df or ax_df)
    Returns: (category, near_match_rows_or_None)
      category: 'tarifgruppen_mismatch' | 'plz_praezisions_mismatch' | 'echter_route_orphan'
    """
    kunde = fam_row['kunde_normalisiert']
    abs2  = fam_row['abs_plz_2']
    empf2 = fam_row['empf_plz_2']
    tarif = fam_row['tarifgruppe']

    # Filter to same kunde
    same_kunde = other_df[other_df['kunde_normalisiert'] == kunde]
    if same_kunde.empty:
        return 'echter_route_orphan', None

    # Case 1: same abs_plz_2 AND same empf_plz_2 BUT different tarifgruppe
    case1 = same_kunde[
        (same_kunde['abs_plz_2'] == abs2) &
        (same_kunde['empf_plz_2'] == empf2) &
        (same_kunde['tarifgruppe'] != tarif)
    ]
    if not case1.empty:
        return 'tarifgruppen_mismatch', case1

    # Case 2: same abs_plz_2, empf_plz_2 differs by exactly 1 char
    case2 = same_kunde[
        (same_kunde['abs_plz_2'] == abs2) &
        (same_kunde['empf_plz_2'] != empf2) &
        same_kunde['empf_plz_2'].apply(lambda x: lev1_2char(str(x), str(empf2)))
    ]
    if not case2.empty:
        return 'plz_praezisions_mismatch', case2

    # Case 3: same kunde, different PLZ combo, same tarifgruppe (or no match at all)
    return 'echter_route_orphan', None


# ---------------------------------------------------------------------------
# Aggregate ALL orphans
# ---------------------------------------------------------------------------
def get_family_representative(group_df):
    """Get one representative row per family (first row with key fields)."""
    row = group_df.iloc[0]
    return {
        'kunde_normalisiert': row['kunde_normalisiert'],
        'abs_plz_2':          row['abs_plz_2'],
        'empf_plz_2':         row['empf_plz_2'],
        'tarifgruppe':        row['tarifgruppe'],
    }


def compute_all_orphan_stats(orphan_set, other_df):
    """Classify every orphan family and count categories."""
    counts = {'tarifgruppen_mismatch': 0, 'plz_praezisions_mismatch': 0, 'echter_route_orphan': 0}
    by_family = orphan_set.groupby('family_key')
    for fkey, grp in by_family:
        rep = get_family_representative(grp)
        cat, _ = classify_near_match(rep, other_df)
        counts[cat] += 1
    return counts


print("Computing aggregate stats for ALL orphan families...")
ax_counts    = compute_all_orphan_stats(orphan_ax,    dinas_df)
dinas_counts = compute_all_orphan_stats(orphan_dinas, ax_df)
print("AX orphan counts:",    ax_counts)
print("Dinas orphan counts:", dinas_counts)


# ---------------------------------------------------------------------------
# Top-10 by total fracht_ohne_diesel_eur
# ---------------------------------------------------------------------------
def top10_families(orphan_set):
    totals = (orphan_set
              .groupby('family_key')['fracht_ohne_diesel_eur']
              .sum()
              .sort_values(ascending=False)
              .head(10))
    return totals.index.tolist()


top10_ax_keys    = top10_families(orphan_ax)
top10_dinas_keys = top10_families(orphan_dinas)


# ---------------------------------------------------------------------------
# Markdown formatting helpers
# ---------------------------------------------------------------------------
def fmt_eur(v):
    if pd.isna(v):
        return "–"
    return f"{v:,.2f} €"

def fmt_float(v, decimals=4):
    if pd.isna(v):
        return "–"
    return f"{v:.{decimals}f}"

def cluster_table(grp):
    """Render clusters for one family as markdown table."""
    cols = ['leistungsdatum', 'cluster_id', 'fracht_ohne_diesel_eur',
            'basiseinheit_wert', 'eur_pro_einheit']
    grp_sorted = grp.sort_values('leistungsdatum')
    lines = []
    lines.append("| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |")
    lines.append("|-------|-----------|-----------|-------------|----------|")
    for _, row in grp_sorted.iterrows():
        datum = str(row['leistungsdatum'])[:10] if pd.notna(row['leistungsdatum']) else '–'
        cid   = str(row['cluster_id'])
        fracht = fmt_eur(row['fracht_ohne_diesel_eur'])
        basis  = fmt_float(row['basiseinheit_wert'], 2)
        epre   = fmt_float(row['eur_pro_einheit'], 4)
        lines.append(f"| {datum} | {cid} | {fracht} | {basis} | {epre} |")
    return "\n".join(lines)


def near_match_table(nm_df, label):
    """Render near-match clusters as markdown table (up to 3)."""
    nm_df = nm_df.head(3)
    lines = []
    lines.append(f"**{label}** (bis zu 3 Beispiele):")
    lines.append("")
    lines.append("| Familie-Key | Datum | Cluster-ID | empf_plz_2 | Tarifgruppe | Fracht (€) |")
    lines.append("|-------------|-------|-----------|-----------|------------|-----------|")
    for _, row in nm_df.iterrows():
        datum = str(row['leistungsdatum'])[:10] if pd.notna(row['leistungsdatum']) else '–'
        lines.append(f"| {row['family_key']} | {datum} | {row['cluster_id']} | {row['empf_plz_2']} | {row['tarifgruppe']} | {fmt_eur(row['fracht_ohne_diesel_eur'])} |")
    return "\n".join(lines)


CAT_LABEL = {
    'tarifgruppen_mismatch':    'Tarifgruppen-Mismatch',
    'plz_praezisions_mismatch': 'PLZ-Präzisions-Mismatch',
    'echter_route_orphan':      'Echter Route-Orphan',
}

SIDE_LABEL = {
    'ax':    'AX',
    'dinas': 'Dinas',
}


def render_family_section(family_key, side, source_df, other_df):
    """
    side: 'ax' or 'dinas'
    source_df: the full df for the orphan side (ax_df or dinas_df)
    other_df:  the full df of the other side
    """
    grp = source_df[source_df['family_key'] == family_key]
    row0 = grp.iloc[0]

    kunde = row0['kunde_normalisiert']
    abs2  = row0['abs_plz_2']
    empf2 = row0['empf_plz_2']
    tarif = row0['tarifgruppe']
    total_fracht = grp['fracht_ohne_diesel_eur'].sum()

    rep = {
        'kunde_normalisiert': kunde,
        'abs_plz_2':          abs2,
        'empf_plz_2':         empf2,
        'tarifgruppe':        tarif,
    }
    cat, nm_df = classify_near_match(rep, other_df)

    lines = []
    lines.append(f"#### `{family_key}`")
    lines.append("")
    lines.append(f"| Feld | Wert |")
    lines.append(f"|------|------|")
    lines.append(f"| Kunde (normalisiert) | {kunde} |")
    lines.append(f"| Abs.-PLZ 2-stellig   | {abs2} |")
    lines.append(f"| Empf.-PLZ 2-stellig  | {empf2} |")
    lines.append(f"| Tarifgruppe          | {tarif} |")
    lines.append(f"| Gesamt-Fracht        | {fmt_eur(total_fracht)} |")
    lines.append(f"| Cluster-Anzahl       | {len(grp)} |")
    lines.append("")

    # Cluster table (existing side)
    existing_side = SIDE_LABEL[side]
    lines.append(f"**Cluster auf {existing_side}-Seite:**")
    lines.append("")
    lines.append(cluster_table(grp))
    lines.append("")

    # Near-match section
    missing_side = 'Dinas' if side == 'ax' else 'AX'
    lines.append(f"**Near-Match-Suche auf {missing_side}-Seite:**")
    lines.append("")

    if cat == 'tarifgruppen_mismatch':
        lines.append(near_match_table(nm_df, "Tarifgruppen-Mismatch – gleiche PLZ, andere Tarifgruppe"))
        lines.append("")
        diag = f"**Diagnose:** Tarifgruppen-Mismatch – Route existiert in {missing_side} unter anderer Tarifgruppe"
    elif cat == 'plz_praezisions_mismatch':
        lines.append(near_match_table(nm_df, f"PLZ-Präzisions-Mismatch – empf_plz_2 weicht um 1 Zeichen ab"))
        lines.append("")
        diag = f"**Diagnose:** PLZ-Präzisions-Mismatch – Empfänger-PLZ in {missing_side} geringfügig abweichend"
    else:
        lines.append(f"> **Echter Route-Orphan** – Lane nur in {existing_side}-Ära vorhanden; keine ähnliche Familie in {missing_side} gefunden.")
        lines.append("")
        diag = f"**Diagnose:** Echter Route-Orphan – Lane nur in {existing_side}-Ära vorhanden"

    lines.append(diag)
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def render_sample_section(title, keys, side, source_df, other_df):
    lines = []
    lines.append(f"## {title}")
    lines.append("")
    for fkey in keys:
        lines.append(render_family_section(fkey, side, source_df, other_df))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Build the markdown document
# ---------------------------------------------------------------------------
def build_report():
    report_date = "2026-04-19"

    # Unique family counts
    n_ax_families    = orphan_ax['family_key'].nunique()
    n_dinas_families = orphan_dinas['family_key'].nunique()
    n_total_families = n_ax_families + n_dinas_families

    # Totals for summary
    total_ax_fracht    = orphan_ax['fracht_ohne_diesel_eur'].sum()
    total_dinas_fracht = orphan_dinas['fracht_ohne_diesel_eur'].sum()

    # Category totals
    def cat_total(counts):
        return sum(counts.values())

    lines = []

    # Header
    lines.append("# Etappe 8c — Orphan-Familien-Diagnose")
    lines.append("")
    lines.append(f"**Stand:** {report_date}  ")
    lines.append("**Quelle:** `output/etappe8_cluster_families.parquet`  ")
    lines.append("**Scope:** TMS-Migrationsprüfung Dinas PRE → AX POST  ")
    lines.append("")

    # Summary table
    lines.append("## Zusammenfassung")
    lines.append("")
    lines.append("### Orphan-Familien nach Seite")
    lines.append("")
    lines.append("| | AX-Orphans | Dinas-Orphans | Gesamt |")
    lines.append("|---|---|---|---|")
    lines.append(f"| Anzahl Familien | {n_ax_families} | {n_dinas_families} | {n_total_families} |")
    lines.append(f"| Gesamt-Fracht | {fmt_eur(total_ax_fracht)} | {fmt_eur(total_dinas_fracht)} | {fmt_eur(total_ax_fracht + total_dinas_fracht)} |")
    lines.append("")

    # Breakdown by cause
    lines.append("### Diagnose-Verteilung (alle Orphan-Familien)")
    lines.append("")
    lines.append("| Diagnose | AX-Orphans | Dinas-Orphans | Gesamt |")
    lines.append("|---------|-----------|--------------|--------|")
    for cat_key in ['tarifgruppen_mismatch', 'plz_praezisions_mismatch', 'echter_route_orphan']:
        ax_c = ax_counts[cat_key]
        di_c = dinas_counts[cat_key]
        lines.append(f"| {CAT_LABEL[cat_key]} | {ax_c} | {di_c} | {ax_c + di_c} |")
    lines.append(f"| **Gesamt** | **{n_ax_families}** | **{n_dinas_families}** | **{n_total_families}** |")
    lines.append("")

    lines.append("---")
    lines.append("")

    # AX orphan sample
    lines.append(render_sample_section(
        "Orphan-AX Stichprobe (Top 10 nach Fracht)",
        top10_ax_keys, 'ax', ax_df, dinas_df
    ))

    # Dinas orphan sample
    lines.append(render_sample_section(
        "Orphan-Dinas Stichprobe (Top 10 nach Fracht)",
        top10_dinas_keys, 'dinas', dinas_df, ax_df
    ))

    # Footer: aggregate distribution
    lines.append("## Aggregate Diagnose-Verteilung (alle Orphan-Familien)")
    lines.append("")
    lines.append("Diese Verteilung basiert auf der Near-Match-Klassifikation aller Orphan-Familien "
                 "(nicht nur der Stichproben).")
    lines.append("")
    lines.append("### AX-Orphans")
    lines.append("")
    for cat_key in ['tarifgruppen_mismatch', 'plz_praezisions_mismatch', 'echter_route_orphan']:
        pct = 100 * ax_counts[cat_key] / n_ax_families if n_ax_families > 0 else 0
        lines.append(f"- **{CAT_LABEL[cat_key]}**: {ax_counts[cat_key]} Familien ({pct:.1f} %)")
    lines.append("")
    lines.append("### Dinas-Orphans")
    lines.append("")
    for cat_key in ['tarifgruppen_mismatch', 'plz_praezisions_mismatch', 'echter_route_orphan']:
        pct = 100 * dinas_counts[cat_key] / n_dinas_families if n_dinas_families > 0 else 0
        lines.append(f"- **{CAT_LABEL[cat_key]}**: {dinas_counts[cat_key]} Familien ({pct:.1f} %)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Bericht automatisch generiert von `scripts/orphan_diagnosis.py`.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Write report
# ---------------------------------------------------------------------------
os.makedirs('data/reports', exist_ok=True)
report_text = build_report()
out_path = 'data/reports/orphan_diagnosis.md'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(report_text)

print(f"\nReport written to {out_path}")
print(f"Lines: {len(report_text.splitlines())}")
