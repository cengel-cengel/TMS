"""
05_top20_analysis.py
====================
Top-20 customer analysis with structural break detection at migration date.

For each customer:
  - Rank by total revenue (12 months)
  - Compare pre vs. post migration on COMPARABLE ROUTES ONLY
  - Statistical significance test of price change
  - Error type distribution
  - Cumulative damage estimate (€)

Usage:
    python src/05_top20_analysis.py --bi output/bi_report_clean.csv --output output/
"""

import pandas as pd
import numpy as np
from scipy import stats
import argparse
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

MIGRATION_DATE = pd.Timestamp("2025-09-26")


def load_bi_clean(filepath: Path) -> pd.DataFrame:
    df = pd.read_csv(filepath, sep=";", dtype=str, encoding="utf-8-sig")
    # Parse dates and numbers
    for col in ["ladedatum"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ["frachtkosten_netto", "gewicht_kg", "lademeter", "stellplaetze",
                "preis_je_kg", "preis_je_ldm", "delta_eur", "delta_pct"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")
    if "ladedatum" in df.columns:
        df["migration_periode"] = np.where(df["ladedatum"] < MIGRATION_DATE, "pre", "post")
    return df


def compute_top20(df: pd.DataFrame) -> pd.DataFrame:
    """Rank customers by total net revenue."""
    key = "kundenname" if "kundenname" in df.columns else "kundennummer" if "kundennummer" in df.columns else None
    if not key or "frachtkosten_netto" not in df.columns:
        return pd.DataFrame()

    top = (df.groupby(key)
           .agg(
               umsatz_gesamt=("frachtkosten_netto", "sum"),
               anzahl_sendungen=("frachtkosten_netto", "count"),
               pre_sendungen=("migration_periode", lambda x: (x == "pre").sum()),
               post_sendungen=("migration_periode", lambda x: (x == "post").sum()),
           )
           .reset_index()
           .sort_values("umsatz_gesamt", ascending=False)
           .head(20)
           .reset_index(drop=True))

    top["rang"] = range(1, len(top) + 1)
    top["umsatz_anteil_pct"] = top["umsatz_gesamt"] / top["umsatz_gesamt"].sum() * 100
    return top


def structural_break_test(df_kunde: pd.DataFrame, price_col: str = "frachtkosten_netto"
                           ) -> dict:
    """
    Test for significant price change at migration date on comparable routes.
    Uses Mann-Whitney U test (non-parametric, robust to outliers).
    Also computes Cohen's d effect size.
    """
    if price_col not in df_kunde.columns or "migration_periode" not in df_kunde.columns:
        return {}

    pre = df_kunde[df_kunde["migration_periode"] == "pre"][price_col].dropna()
    post = df_kunde[df_kunde["migration_periode"] == "post"][price_col].dropna()

    if len(pre) < 5 or len(post) < 5:
        return {"n_pre": len(pre), "n_post": len(post), "insufficient_data": True}

    # Mann-Whitney U test
    stat, p_value = stats.mannwhitneyu(pre, post, alternative="two-sided")

    # Mean difference
    mean_pre = pre.mean()
    mean_post = post.mean()
    delta_abs = mean_post - mean_pre
    delta_pct = (delta_abs / mean_pre * 100) if mean_pre > 0 else 0

    # Cohen's d (effect size)
    pooled_std = np.sqrt((pre.std() ** 2 + post.std() ** 2) / 2)
    cohens_d = delta_abs / pooled_std if pooled_std > 0 else 0

    # Interpret effect
    if abs(cohens_d) < 0.2:
        effect = "vernachlässigbar"
    elif abs(cohens_d) < 0.5:
        effect = "klein"
    elif abs(cohens_d) < 0.8:
        effect = "mittel"
    else:
        effect = "GROSS"

    return {
        "n_pre": int(len(pre)),
        "n_post": int(len(post)),
        "mean_pre": round(mean_pre, 2),
        "mean_post": round(mean_post, 2),
        "delta_abs": round(delta_abs, 2),
        "delta_pct": round(delta_pct, 2),
        "p_value": round(p_value, 4),
        "signifikant": p_value < 0.05,
        "cohens_d": round(cohens_d, 3),
        "effektstaerke": effect,
        "mwu_statistic": round(stat, 0),
    }


def analyse_route_groups(df_kunde: pd.DataFrame,
                          customer_name: str) -> pd.DataFrame:
    """
    Analyse price changes per route group (comparable routes only).
    Returns DataFrame with one row per route group.
    """
    route_col = "route_group" if "route_group" in df_kunde.columns else \
                "route_exakt" if "route_exakt" in df_kunde.columns else \
                "route_zone" if "route_zone" in df_kunde.columns else None

    if not route_col or "migration_periode" not in df_kunde.columns:
        return pd.DataFrame()

    price_col = "frachtkosten_netto"
    if price_col not in df_kunde.columns:
        return pd.DataFrame()

    results = []
    for route, grp in df_kunde.groupby(route_col):
        pre = grp[grp["migration_periode"] == "pre"][price_col].dropna()
        post = grp[grp["migration_periode"] == "post"][price_col].dropna()

        if len(pre) < 2 or len(post) < 2:
            continue

        avg_pre = pre.mean()
        avg_post = post.mean()
        delta = avg_post - avg_pre
        delta_pct = (delta / avg_pre * 100) if avg_pre > 0 else 0

        # Comparable dimensions
        avg_kg_pre = grp[grp["migration_periode"] == "pre"]["gewicht_kg"].mean() if "gewicht_kg" in grp.columns else np.nan
        avg_kg_post = grp[grp["migration_periode"] == "post"]["gewicht_kg"].mean() if "gewicht_kg" in grp.columns else np.nan
        avg_ldm_pre = grp[grp["migration_periode"] == "pre"]["lademeter"].mean() if "lademeter" in grp.columns else np.nan
        avg_ldm_post = grp[grp["migration_periode"] == "post"]["lademeter"].mean() if "lademeter" in grp.columns else np.nan

        # KG change normalized
        kg_change = ((avg_kg_post - avg_kg_pre) / avg_kg_pre * 100) if avg_kg_pre and avg_kg_pre > 0 else np.nan
        ldm_change = ((avg_ldm_post - avg_ldm_pre) / avg_ldm_pre * 100) if avg_ldm_pre and avg_ldm_pre > 0 else np.nan

        # Verdict: price change not explained by volume change?
        price_change_unexplained = (abs(delta_pct) > 5 and
            (pd.isna(kg_change) or abs(kg_change) < abs(delta_pct) * 0.5))

        results.append({
            "kunde": customer_name,
            "route": route,
            "n_pre": len(pre),
            "n_post": len(post),
            "avg_preis_pre": round(avg_pre, 2),
            "avg_preis_post": round(avg_post, 2),
            "delta_eur": round(delta, 2),
            "delta_pct": round(delta_pct, 2),
            "avg_kg_pre": round(avg_kg_pre, 1) if not pd.isna(avg_kg_pre) else None,
            "avg_kg_post": round(avg_kg_post, 1) if not pd.isna(avg_kg_post) else None,
            "avg_ldm_pre": round(avg_ldm_pre, 3) if not pd.isna(avg_ldm_pre) else None,
            "avg_ldm_post": round(avg_ldm_post, 3) if not pd.isna(avg_ldm_post) else None,
            "kg_change_pct": round(kg_change, 1) if not pd.isna(kg_change) else None,
            "ldm_change_pct": round(ldm_change, 1) if not pd.isna(ldm_change) else None,
            "preisstieg_unerklaert": price_change_unexplained,
            "migrationsfehler_verdacht": (delta_pct > 5 and price_change_unexplained),
        })

    return pd.DataFrame(results).sort_values("delta_pct", ascending=False)


def compute_damage_estimate(df_kunde: pd.DataFrame) -> dict:
    """
    Estimate cumulative billing damage since migration date.
    Assumes the pre-migration average price (on same routes) is the baseline.
    """
    if "migration_periode" not in df_kunde.columns:
        return {}

    price_col = "frachtkosten_netto"
    if price_col not in df_kunde.columns:
        return {}

    pre = df_kunde[df_kunde["migration_periode"] == "pre"]
    post = df_kunde[df_kunde["migration_periode"] == "post"]

    # Use per-route baseline to normalize
    route_col = next((c for c in ["route_exakt", "route_zone", "route_group"]
                      if c in df_kunde.columns), None)

    if route_col:
        baseline = pre.groupby(route_col)[price_col].mean().rename("baseline_preis")
        post_with_baseline = post.merge(baseline, on=route_col, how="left")
        post_with_baseline["delta_zur_baseline"] = (
            post_with_baseline[price_col] - post_with_baseline["baseline_preis"]
        )
        total_overcharge = post_with_baseline["delta_zur_baseline"].sum()
        n_with_baseline = post_with_baseline["baseline_preis"].notna().sum()
    else:
        baseline_price = pre[price_col].mean()
        post_avg = post[price_col].mean()
        total_overcharge = (post_avg - baseline_price) * len(post)
        n_with_baseline = len(post)

    return {
        "schaden_gesamt_eur": round(total_overcharge, 2),
        "sendungen_post": len(post),
        "sendungen_mit_baseline": n_with_baseline,
        "richtung": "ZU VIEL" if total_overcharge > 0 else "ZU WENIG",
        "schaden_je_sendung": round(total_overcharge / len(post), 2) if len(post) > 0 else 0,
    }


def run_top20_analysis(bi_file: Path, output_dir: Path):
    """Main top-20 analysis pipeline."""
    print(f"\n{'='*70}")
    print(f"TOP-20 KUNDENANALYSE — TMS-MIGRATIONSAUDIT")
    print(f"Migrationsdatum: {MIGRATION_DATE.date()}")
    print(f"{'='*70}")

    df = load_bi_clean(bi_file)
    if df.empty:
        print("[ERROR] Could not load BI data")
        return

    print(f"Datenbasis: {len(df):,} Sendungen, "
          f"{df['ladedatum'].min().date() if 'ladedatum' in df.columns else '?'} – "
          f"{df['ladedatum'].max().date() if 'ladedatum' in df.columns else '?'}")

    # Compute Top 20
    top20 = compute_top20(df)
    if top20.empty:
        print("[ERROR] Could not compute Top-20 ranking")
        return

    customer_col = "kundenname" if "kundenname" in top20.columns else "kundennummer"

    print(f"\n{'─'*70}")
    print(f"{'RANG':>4} {'KUNDE':40} {'UMSATZ':>12} {'ANTEIL':>7} {'PRE':>6} {'POST':>6}")
    print(f"{'─'*70}")
    for _, row in top20.iterrows():
        print(f"  #{row['rang']:2d}  {str(row[customer_col])[:40]:40}  "
              f"{row['umsatz_gesamt']:>10,.0f}€  "
              f"{row['umsatz_anteil_pct']:>5.1f}%  "
              f"{row['pre_sendungen']:>6,}  {row['post_sendungen']:>6,}")

    # Detailed analysis per top-20 customer
    results_all = []
    route_results_all = []

    for _, kunde_row in top20.iterrows():
        kunde_name = kunde_row[customer_col]
        print(f"\n{'─'*60}")
        print(f"ANALYSE: {kunde_name}")

        # Filter BI data for this customer
        mask = df[customer_col].str.lower().str.strip() == str(kunde_name).lower().strip()
        df_k = df[mask].copy()

        if len(df_k) < 10:
            print(f"  [SKIP] Zu wenige Datensätze ({len(df_k)})")
            continue

        # Identify comparable routes
        # Add route columns if not present
        if "route_exakt" not in df_k.columns and "absender_plz" in df_k.columns:
            df_k["route_exakt"] = (df_k["absender_plz"].astype(str) + "→" +
                                    df_k["empfaenger_plz"].astype(str))
            df_k["route_zone"] = (df_k["absender_plz"].astype(str).str[:2] + "→" +
                                   df_k["empfaenger_plz"].astype(str).str[:2])

        # Statistical break test
        bruch = structural_break_test(df_k)
        if bruch:
            sig_marker = "*** SIGNIFIKANT ***" if bruch.get("signifikant") else ""
            print(f"  Ø Preis PRE:    {bruch.get('mean_pre', 0):,.2f} €  (n={bruch.get('n_pre', 0)})")
            print(f"  Ø Preis POST:   {bruch.get('mean_post', 0):,.2f} €  (n={bruch.get('n_post', 0)})")
            print(f"  Delta:          {bruch.get('delta_abs', 0):+,.2f} € ({bruch.get('delta_pct', 0):+.1f}%) {sig_marker}")
            print(f"  p-Wert:         {bruch.get('p_value', 1):.4f}  |  Effektgröße: {bruch.get('effektstaerke', '?')}")

        # Route-level analysis
        route_df = analyse_route_groups(df_k, kunde_name)
        if not route_df.empty:
            n_verdacht = route_df["migrationsfehler_verdacht"].sum()
            print(f"  Routen analysiert:        {len(route_df)}")
            print(f"  Routen mit Fehlerv.:      {n_verdacht} ({n_verdacht/len(route_df)*100:.0f}%)")
            if n_verdacht > 0:
                worst = route_df[route_df["migrationsfehler_verdacht"]].nlargest(3, "delta_pct")
                print(f"  Top-3 auffällige Routen:")
                for _, r in worst.iterrows():
                    print(f"    {r['route']:20s}: {r['avg_preis_pre']:.2f}€ → {r['avg_preis_post']:.2f}€ "
                          f"(+{r['delta_pct']:.1f}%)")
            route_results_all.append(route_df)

        # Damage estimate
        schaden = compute_damage_estimate(df_k)
        if schaden:
            print(f"  SCHADENSSCHÄTZUNG:")
            print(f"    Gesamt:         {schaden.get('schaden_gesamt_eur', 0):+,.2f} € "
                  f"({schaden.get('richtung', '?')})")
            print(f"    Je Sendung:     {schaden.get('schaden_je_sendung', 0):+,.2f} €")

        results_all.append({
            "rang": kunde_row["rang"],
            "kunde": kunde_name,
            "umsatz_gesamt": kunde_row["umsatz_gesamt"],
            **{f"bruch_{k}": v for k, v in bruch.items()},
            **{f"schaden_{k}": v for k, v in schaden.items()},
        })

    # Save results
    if results_all:
        df_results = pd.DataFrame(results_all)
        df_results.to_csv(output_dir / "top20_analyse.csv",
                          index=False, sep=";", encoding="utf-8-sig")
        print(f"\n→ Gespeichert: {output_dir}/top20_analyse.csv")

        # Summary of total damage
        total_schaden = df_results.get("schaden_schaden_gesamt_eur", pd.Series(dtype=float)).sum()
        if total_schaden != 0:
            print(f"\n{'='*70}")
            print(f"GESAMTSCHADEN TOP-20 KUNDEN SEIT {MIGRATION_DATE.date()}:")
            print(f"  {total_schaden:+,.2f} €  "
                  f"({'ZU VIEL BERECHNET' if total_schaden > 0 else 'ZU WENIG BERECHNET'})")
            print(f"{'='*70}")

    if route_results_all:
        df_routes = pd.concat(route_results_all, ignore_index=True)
        df_routes.to_csv(output_dir / "top20_routen_analyse.csv",
                         index=False, sep=";", encoding="utf-8-sig")
        print(f"→ Gespeichert: {output_dir}/top20_routen_analyse.csv")


def main():
    parser = argparse.ArgumentParser(description="TMS Top-20 Customer Analysis")
    parser.add_argument("--bi", type=str, default="output/bi_report_clean.csv",
                        help="Path to cleaned BI report CSV")
    parser.add_argument("--output", type=str, default="output/",
                        help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    run_top20_analysis(Path(args.bi), output_dir)


if __name__ == "__main__":
    main()
