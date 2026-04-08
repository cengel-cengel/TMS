"""
gb_invoice_reconciliation.py
============================
Groz-Beckert: Vergleich Dinas-Rechnungen (PRE) vs. AX-Rechnungen (POST).

Basis:      Dinas (PRE) gilt als korrekte Abrechnung → Referenz.
Prüfung:    POST-Erlöse (AX) >5% unter PRE-Median = Unterfakturierung.
DLV-Check:  POST Erlöse Fracht vs. Vertrags-Soll aus DLV 01.05.25-30.06.26.
NK:         Nebenbedingungen Dinas (z.B. Portugal min. 3 LDM) einbezogen.

Usage:
    python src/gb_invoice_reconciliation.py
"""

import math
import re
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

warnings.filterwarnings("ignore")


# ── Pfade ──────────────────────────────────────────────────────────────────────
BASE        = Path("/home/user/TMS")
BI_PATH     = BASE / "data/bi_report/Tagesbericht.Einzeldaten.alle.VKA.5.xlsx"
DLV_PATH    = BASE / "data/groz_beckert/DLV/2025/20250408_Erka_Groz Beckert_Templates_LKW Ausschreibung_01.05.25 - 30.06.26.xlsx"
NK_PATH     = BASE / "data/groz_beckert/Nebenbedingungen DINAS/NK Groz.xlsx"
OUTPUT_PATH = BASE / "output/gb_dinas_ax_vergleich.xlsx"

# ── Zeitschnitt PRE/POST ────────────────────────────────────────────────────────
MIGRATION_DATE = pd.Timestamp("2025-09-26")

# ── Schwellen ──────────────────────────────────────────────────────────────────
DEVIATION_THRESHOLD_PCT = 5.0   # Ausreißer-Grenze
MIN_SHIPMENTS_PRE       = 3     # Mindest-Sendungen Dinas für Vergleich

# ── Gewichtsbuckets ────────────────────────────────────────────────────────────
WEIGHT_BUCKETS = [100, 300, 500, 1_000, 2_000, 5_000, 10_000, 50_000, float("inf")]
WEIGHT_LABELS  = ["0-100", "101-300", "301-500", "501-1k", "1k-2k", "2k-5k",
                  "5k-10k", "10k-50k", ">50k"]

# ── DLV Gewichts-Stufen (General Cargo, 36 Spalten) ───────────────────────────
GC_WEIGHT_STEPS = [
    30, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500,
    600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500,
    1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500,
    2600, 2700, 2800, 2900, 3000,
]

# ── LTL-FTL LDM-Stufen (23 Spalten: 1.0 bis 12.0 in 0,5-Schritten) ───────────
LTL_LDM_STEPS = [round(1.0 + 0.5 * i, 1) for i in range(23)]   # 1.0..12.0

# ── NK-Sonderregel: Portugal Mindestabrechnung ────────────────────────────────
PT_MIN_LDM = 3.0     # lt. Nebenbedingung 153832: "MINIMUMABR. 3 LM"

# ── Erlös-Detailspalten ────────────────────────────────────────────────────────
ERLOES_DETAIL_COLS = [
    "Erlöse Fracht", "Erlöse Diesel", "Erlöse Maut",
    "Erlöse Nebengebühr", "Erlöse EUST Zoll", "Erlöse Transportversicherung",
]

# ── Farben ─────────────────────────────────────────────────────────────────────
C_HEADER  = "1F3864"
C_SUBHDR  = "2E75B6"
C_PRE_ROW = "D6E4F7"
C_POST_ROW= "F7E4D6"
C_WARN    = "FFD700"
C_LOSS    = "FF6B6B"
C_OK      = "C6EFCE"


# ═══════════════════════════════════════════════════════════════════════════════
# A  DATA LOADER
# ═══════════════════════════════════════════════════════════════════════════════

def load_groz_beckert_bi(path: Path) -> pd.DataFrame:
    """BI-Extrakt laden, GB filtern, PRE/POST zuweisen, KPIs berechnen."""
    print(f"[DataLoader] Lese {path.name} …")
    df = pd.read_excel(path, dtype={"Rechnungsnummer": str, "Auftragsnummer": str})
    print(f"  Gesamt: {len(df):,} Zeilen")

    mask = df["Kunden Name"].astype(str).str.contains(r"Groz|Beckert", case=False, na=False)
    df = df[mask].copy()
    print(f"  Groz-Beckert: {len(df):,} Zeilen ({df['Kunden Nr BK'].nunique()} Kunden-IDs)")

    df["periode"] = np.where(
        pd.to_datetime(df["Leistungsdatum"]) < MIGRATION_DATE, "PRE", "POST"
    )
    print(f"  PRE (Dinas)={( df['periode']=='PRE').sum()}, POST (AX)={(df['periode']=='POST').sum()}")

    # PLZ / Land normalisieren
    for col in ["Versender PLZ", "Versender Land", "Empfänger PLZ", "Empfänger Land",
                "Empfänger Stadt", "Versender Name", "Empfänger Name"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Abrechnungsgewicht (auf 100 kg aufgerundet) & €/100kg
    tonnage = df["Tonnage (eff.)"].fillna(0).clip(lower=0)
    df["billing_weight_kg"]   = tonnage.apply(lambda t: math.ceil(t / 100) * 100 if t > 0 else 0)
    df["billing_100kg_units"] = df["billing_weight_kg"] / 100
    df["erloes_je_100kg"] = np.where(
        df["billing_100kg_units"] > 0,
        df["Erloese"] / df["billing_100kg_units"], np.nan
    )
    df["erloes_je_sendung"] = df["Erloese"]

    # Gewichtsbucket
    df["gewicht_bucket"] = pd.cut(
        tonnage, bins=[0] + WEIGHT_BUCKETS, labels=WEIGHT_LABELS, right=True
    ).astype(str)

    # Relation-Key (Versender-PLZ|Land → Empf-PLZ-2-Stellen|Land)
    def plz2(plz: str, land: str) -> str:
        clean = re.sub(r"[\s\-]", "", plz)
        digits = re.sub(r"\D", "", clean)
        if land == "GB":
            letters = re.sub(r"[^A-Za-z]", "", clean)
            return letters[:2].upper()
        return digits[:2]

    df["sender_key"]   = df["Versender PLZ"] + "|" + df["Versender Land"]
    df["receiver_key"] = df.apply(
        lambda r: plz2(r["Empfänger PLZ"], r["Empfänger Land"]) + "|" + r["Empfänger Land"],
        axis=1,
    )
    df["relation_key"] = df["sender_key"] + " → " + df["receiver_key"]

    # Erlöse-Detailspalten auffüllen
    for col in ERLOES_DETAIL_COLS:
        df[col] = df.get(col, pd.Series(0.0, index=df.index)).fillna(0.0)

    return df


# ═══════════════════════════════════════════════════════════════════════════════
# B  DLV TARIFF PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def _expand_zone_codes(zone_str: str):
    """
    Parse Zonenangabe aus DLV General Cargo.
    Rückgabe: (codes:list[str], is_alle:bool, is_rest:bool)
    Codes sind 2-stellige Strings (z.B. "10","29") oder GB-Districte ("WF").
    """
    z = str(zone_str).strip()
    if not z or z.lower() in ("nan", "alle", "all"):
        return [], True, False
    if z.lower() == "rest":
        return [], False, True

    codes = []
    for token in re.split(r",\s*", z.replace("\n", ",")):
        token = token.strip()
        if not token:
            continue
        # Numerischer Bereich: "10-29" oder "54-55"
        m = re.match(r"^(\d{1,2})-(\d{1,2})$", token)
        if m:
            for i in range(int(m.group(1)), int(m.group(2)) + 1):
                codes.append(str(i).zfill(2))
        else:
            codes.append(token.strip())
    return codes, False, False


def _plz_prefix(empf_plz: str, empf_land: str) -> str:
    """2-stelliger Präfix für Zonen-Matching."""
    clean = re.sub(r"[\s\-]", "", str(empf_plz))
    if empf_land == "GB":
        letters = re.sub(r"[^A-Za-z]", "", clean).upper()
        return letters[:2]  # z.B. "WF" aus "WF12AB"
    digits = re.sub(r"\D", "", clean)
    return digits[:2] if len(digits) >= 2 else digits


def parse_dlv_general_cargo(path: Path) -> list:
    """
    General Cargo sheet → Liste von Rate-Einträgen.
    Jeder Eintrag: {iso, codes, is_alle, is_rest, prices (Liste 36 float)}
    """
    raw = pd.read_excel(path, sheet_name="General Cargo", header=None)
    entries = []
    for _, row in raw.iloc[3:31].iterrows():
        iso = str(row.iloc[5]).strip().upper()
        if iso in ("NAN", "", "ISO-CODE"):
            continue
        zone_str = str(row.iloc[6])
        prices = []
        for ci in range(7, 43):
            try:
                prices.append(float(row.iloc[ci]))
            except (ValueError, TypeError):
                prices.append(None)
        codes, is_alle, is_rest = _expand_zone_codes(zone_str)
        entries.append(dict(iso=iso, codes=codes, is_alle=is_alle,
                            is_rest=is_rest, prices=prices))
    print(f"  DLV GC: {len(entries)} Zonen-Einträge geladen")
    return entries


def parse_dlv_ltl_ftl(path: Path) -> list:
    """
    LTL-FTL sheet → Liste von Routen-Einträgen.
    Jeder Eintrag: {from_plz, from_iso, to_plz, to_iso, prices (23 float)}
    """
    raw = pd.read_excel(path, sheet_name="LTL-FTL", header=None)
    entries = []
    for _, row in raw.iloc[3:9].iterrows():
        from_iso = str(row.iloc[3]).strip().upper()
        to_iso   = str(row.iloc[6]).strip().upper()
        if from_iso in ("NAN", "") or to_iso in ("NAN", ""):
            continue
        from_plz = re.sub(r"[\s\-]", "", str(row.iloc[1]))
        to_plz   = re.sub(r"[\s\-]", "", str(row.iloc[7]))
        prices = []
        for ci in range(10, 33):  # LDM 1.0 … 12.0 (23 Werte)
            try:
                prices.append(float(row.iloc[ci]))
            except (ValueError, TypeError):
                prices.append(None)
        entries.append(dict(from_plz=from_plz, from_iso=from_iso,
                            to_plz=to_plz, to_iso=to_iso, prices=prices))
    print(f"  DLV LTL-FTL: {len(entries)} Routen geladen")
    return entries


def _price_for_weight(entry: dict, tonnage_kg: float):
    """Ersten Schritt >= tonnage_kg suchen, Preis zurückgeben."""
    for step, price in zip(GC_WEIGHT_STEPS, entry["prices"]):
        if tonnage_kg <= step and price is not None:
            return price
    # Übergewicht: letzten Preis nutzen
    for p in reversed(entry["prices"]):
        if p is not None:
            return p
    return None


def lookup_gc(gc_entries: list, empf_plz: str, empf_land: str, tonnage_kg: float):
    """General Cargo Rate nachschlagen. Gibt (preis, zone_str) oder (None, None)."""
    empf_land = str(empf_land).strip().upper()
    if not empf_land or empf_land == "NAN":
        return None, None
    prefix = _plz_prefix(empf_plz, empf_land)
    country = [e for e in gc_entries if e["iso"] == empf_land]
    if not country:
        return None, None
    # 1) Exakte Zone
    for e in country:
        if not e["is_alle"] and not e["is_rest"]:
            if prefix in e["codes"]:
                return _price_for_weight(e, tonnage_kg), "GC-Zone"
    # 2) Alle
    for e in country:
        if e["is_alle"]:
            return _price_for_weight(e, tonnage_kg), "GC-Alle"
    # 3) Rest
    for e in country:
        if e["is_rest"]:
            return _price_for_weight(e, tonnage_kg), "GC-Rest"
    return None, None


def lookup_ltl(ltl_entries: list, sender_plz: str, sender_iso: str,
               empf_plz: str, empf_iso: str, lademeter: float):
    """LTL-FTL Rate nachschlagen. Gibt (preis, route_str) oder (None, None)."""
    s_plz = re.sub(r"[\s\-]", "", str(sender_plz))
    e_plz = re.sub(r"[\s\-]", "", str(empf_plz))
    s_iso = str(sender_iso).strip().upper()
    e_iso = str(empf_iso).strip().upper()
    for entry in ltl_entries:
        if entry["from_iso"] != s_iso or entry["to_iso"] != e_iso:
            continue
        # PLZ-Prefix-Vergleich (mind. 4 Zeichen)
        fp = entry["from_plz"].replace("-", "")
        tp = entry["to_plz"].replace("-", "")
        if (s_plz[:4] == fp[:4] or fp[:4] == s_plz[:4]) and \
           (e_plz[:4] == tp[:4] or tp[:4] == e_plz[:4]):
            for ldm_step, price in zip(LTL_LDM_STEPS, entry["prices"]):
                if lademeter <= ldm_step and price is not None:
                    return price, f"LTL {entry['from_plz']}→{entry['to_plz']}"
            # Überschreitung: letzten Preis
            for p in reversed(entry["prices"]):
                if p is not None:
                    return p, f"LTL {entry['from_plz']}→{entry['to_plz']} (>12LDM)"
    return None, None


def lookup_dlv(gc_entries, ltl_entries, row: pd.Series):
    """
    Soll-Fracht aus DLV ermitteln.
    Rückgabe: (soll_fracht, methode) oder (None, None).
    NK-Sonderregel: Portugal min. 3 LDM.
    """
    sender_plz  = str(row.get("Versender PLZ", "")).strip()
    sender_land = str(row.get("Versender Land", "")).strip().upper()
    empf_plz    = str(row.get("Empfänger PLZ", "")).strip()
    empf_land   = str(row.get("Empfänger Land", "")).strip().upper()
    tonnage     = float(row.get("Tonnage (eff.)", 0) or 0)
    lademeter   = float(row.get("Lademeter", 0) or 0)

    # NK: Portugal Mindest-LDM 3,0
    if empf_land == "PT" or sender_land == "PT":
        lademeter = max(lademeter, PT_MIN_LDM)

    # LTL-FTL zuerst (wenn Lademeter > 0)
    if lademeter > 0:
        price, method = lookup_ltl(ltl_entries, sender_plz, sender_land,
                                   empf_plz, empf_land, lademeter)
        if price is not None:
            return price, method

    # General Cargo (gewichtsbasiert)
    if tonnage > 0:
        price, method = lookup_gc(gc_entries, empf_plz, empf_land, tonnage)
        if price is not None:
            return price, method

    return None, None


# ═══════════════════════════════════════════════════════════════════════════════
# C  NK NEBENBEDINGUNGEN PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def parse_nk_conditions(path: Path) -> pd.DataFrame:
    """NK Groz.xlsx einlesen, relevante Abrechnungshinweise extrahieren."""
    try:
        raw = pd.read_excel(path, sheet_name=0)
    except Exception as e:
        print(f"  [NK] Warnung: {e}")
        return pd.DataFrame()

    # Spalten vereinfachen
    col_map = {}
    for c in raw.columns:
        cs = str(c).replace("\n", " ").strip()
        if "Schlüssel" in cs:
            col_map[c] = "Schluessel"
        elif "Aktiv" in cs and "Sendung" not in cs:
            col_map[c] = "Aktiv"
        elif "Prüfung ERKA" in cs or "ERKA" in cs:
            col_map[c] = "ERKA_Pruefung"
        elif "Bemerkung" in cs and "AX" in cs:
            col_map[c] = "Bemerkung_AX"
        elif "Umsatz 2024" in cs and "PSS" not in cs:
            col_map[c] = "Umsatz_2024"
        elif "PSS Umsatz" in cs:
            col_map[c] = "PSS_Umsatz"
        elif "Name" in cs and "Straße" in cs:
            col_map[c] = "Kundenname_Adresse"
        elif "Prüfungshinweis" in cs:
            col_map[c] = "Pruefungshinweis"
        elif "Hinweis" in cs and "AX" in cs:
            col_map[c] = "Hinweis_AX"
        elif "SSS" in cs or "Transportart" in cs:
            col_map[c] = "Transportart_Land"
    raw = raw.rename(columns=col_map)

    keep = ["Schluessel", "Aktiv", "ERKA_Pruefung", "Bemerkung_AX",
            "Umsatz_2024", "PSS_Umsatz", "Kundenname_Adresse",
            "Hinweis_AX", "Pruefungshinweis", "Transportart_Land"]
    keep_existing = [c for c in keep if c in raw.columns]
    nk = raw[keep_existing].copy()
    nk = nk[nk["Schluessel"].notna()].copy()

    # Wichtige Hinweise aus Pruefungshinweis extrahieren
    hint_col = "Pruefungshinweis" if "Pruefungshinweis" in nk.columns else None
    if hint_col:
        nk["Abrechnungshinweis"] = (
            nk[hint_col].astype(str)
            .str.replace(r"\|", "\n", regex=False)
            .str.replace(r"  +", " ", regex=True)
            .str.strip()
        )
    print(f"  NK: {len(nk)} Einträge geladen")
    return nk


# ═══════════════════════════════════════════════════════════════════════════════
# D  OUTLIER ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def compute_relation_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    PRE-Medianrate (€/100kg) je (Relation, Gewichtsbucket) als Referenz.
    Dinas = korrekte Abrechnung; POST-Abweichung > 5% = Ausreißer.
    """
    rows = []
    for (rel, bucket), grp in df.groupby(["relation_key", "gewicht_bucket"], observed=True):
        pre  = grp[grp["periode"] == "PRE"]
        post = grp[grp["periode"] == "POST"]
        if len(pre) < MIN_SHIPMENTS_PRE or len(post) == 0:
            continue
        pre_rate  = pre["erloes_je_100kg"].median()
        post_rate = post["erloes_je_100kg"].median()
        if pd.isna(pre_rate) or pd.isna(post_rate) or pre_rate == 0:
            continue
        abw = (post_rate - pre_rate) / abs(pre_rate) * 100
        if abs(abw) <= DEVIATION_THRESHOLD_PCT:
            continue
        # Erwarteter Verlust (positiv = AX zu niedrig = Unterfakturierung)
        verlust = (pre_rate - post_rate) * post["billing_100kg_units"].sum()
        rows.append(dict(
            relation_key=rel, gewicht_bucket=bucket,
            sender_key=pre["sender_key"].iloc[0],
            receiver_key=pre["receiver_key"].iloc[0],
            versender_land=pre["Versender Land"].iloc[0],
            empf_land=pre["Empfänger Land"].iloc[0],
            empf_plz=post["Empfänger PLZ"].iloc[0],
            empf_stadt=post.get("Empfänger Stadt", pd.Series([""])).iloc[0],
            n_pre=len(pre), sum_erloes_pre=pre["Erloese"].sum(),
            avg_erloes_pre=pre["Erloese"].mean(),
            median_rate_pre=pre_rate,
            avg_gewicht_pre=pre["Tonnage (eff.)"].mean(),
            n_post=len(post), sum_erloes_post=post["Erloese"].sum(),
            avg_erloes_post=post["Erloese"].mean(),
            median_rate_post=post_rate,
            avg_gewicht_post=post["Tonnage (eff.)"].mean(),
            abweichung_pct=abw,
            erwarteter_verlust_eur=verlust,
            unterfakturierung=(abw < 0),
        ))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("erwarteter_verlust_eur", ascending=False)


def find_post_outliers(df: pd.DataFrame, rel_stats: pd.DataFrame) -> pd.DataFrame:
    """POST-Sendungen, deren €/100kg >5% unter Dinas-Median liegen."""
    parts = []
    for _, stat in rel_stats.iterrows():
        pre_rate = stat["median_rate_pre"]
        sub = df[
            (df["relation_key"] == stat["relation_key"]) &
            (df["gewicht_bucket"] == stat["gewicht_bucket"]) &
            (df["periode"] == "POST")
        ].copy()
        sub["ppu_dinas_referenz"] = pre_rate
        sub["abweichung_pct"] = (sub["erloes_je_100kg"] - pre_rate) / abs(pre_rate) * 100
        sub["erwarteter_verlust_eur"] = (
            (pre_rate - sub["erloes_je_100kg"]) * sub["billing_100kg_units"]
        )
        parts.append(sub[sub["abweichung_pct"].abs() > DEVIATION_THRESHOLD_PCT])
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).sort_values(
        "erwarteter_verlust_eur", ascending=False
    )


def compute_dlv_comparison(df: pd.DataFrame, gc_entries: list,
                            ltl_entries: list) -> pd.DataFrame:
    """
    Für alle POST-Sendungen: DLV Soll-Fracht ermitteln und
    mit tatsächlicher Erlöse Fracht (bzw. Erloese) vergleichen.
    Basis für Vergleich: Erlöse Fracht (POST), wenn > 0; sonst Erloese gesamt.
    """
    post = df[df["periode"] == "POST"].copy()
    solls, methods = [], []
    for _, row in post.iterrows():
        soll, meth = lookup_dlv(gc_entries, ltl_entries, row)
        solls.append(soll)
        methods.append(meth)
    post["dlv_soll_fracht"] = solls
    post["dlv_methode"]     = methods

    # Vergleichsbasis: Erlöse Fracht wenn vorhanden, sonst Erloese gesamt
    post["ist_fracht"] = np.where(
        post["Erlöse Fracht"].fillna(0) > 0,
        post["Erlöse Fracht"],
        post["Erloese"]
    )
    post["ist_basis"] = np.where(
        post["Erlöse Fracht"].fillna(0) > 0,
        "Erlöse Fracht", "Erloese gesamt"
    )

    # Abweichung (nur wenn Soll bekannt)
    has_soll = post["dlv_soll_fracht"].notna() & (post["dlv_soll_fracht"] > 0)
    post["dlv_abweichung_pct"] = np.where(
        has_soll,
        (post["ist_fracht"] - post["dlv_soll_fracht"]) / post["dlv_soll_fracht"] * 100,
        np.nan
    )
    post["dlv_differenz_eur"] = np.where(
        has_soll,
        post["ist_fracht"] - post["dlv_soll_fracht"],
        np.nan
    )

    # Sortierung: größte Unterfakturierung (negativste Differenz) oben
    result = post[post["dlv_soll_fracht"].notna()].copy()
    return result.sort_values("dlv_differenz_eur", ascending=True)


def get_dinas_nebenkosten(df: pd.DataFrame) -> pd.DataFrame:
    """Dinas (PRE) Nebenkosten nach Relation aggregieren."""
    pre = df[df["periode"] == "PRE"].copy()
    nk_cols = [c for c in ERLOES_DETAIL_COLS if c in pre.columns]
    agg = (
        pre.groupby(["relation_key", "Empfänger Land"])[nk_cols + ["Erloese"]]
        .agg(["count", "sum", "mean"])
    )
    agg.columns = ["_".join(c) for c in agg.columns]
    agg = agg.reset_index()
    return agg.sort_values("Erloese_sum", ascending=False)


# ═══════════════════════════════════════════════════════════════════════════════
# E  EXCEL WRITER  (Hilfsfunktionen)
# ═══════════════════════════════════════════════════════════════════════════════

def _hdr(cell, bg=C_HEADER, fc="FFFFFF", bold=True, sz=10):
    cell.fill      = PatternFill("solid", fgColor=bg)
    cell.font      = Font(bold=bold, color=fc, name="Calibri", size=sz)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

def _dat(cell, bg=None, right=False):
    if bg:
        cell.fill = PatternFill("solid", fgColor=bg)
    cell.font      = Font(name="Calibri", size=9)
    cell.alignment = Alignment(
        horizontal="right" if right or isinstance(cell.value, (int, float)) else "left",
        vertical="center", wrap_text=False
    )

def _border():
    s = Side(border_style="thin", color="CCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)

def _autofit(ws, mn=10, mx=50):
    for col in ws.columns:
        w = max((len(str(c.value or "")) for c in col), default=0)
        ws.column_dimensions[get_column_letter(col[0].column)].width = max(mn, min(w + 2, mx))

def _pct_color(cell, val):
    if isinstance(val, float) and not math.isnan(val):
        cell.fill = PatternFill("solid", fgColor=C_WARN if val < 0 else C_OK)

def _eur_color(cell, val):
    if isinstance(val, float) and not math.isnan(val):
        cell.fill = PatternFill("solid", fgColor=C_LOSS if val > 0 else C_OK)


# ── Sheet 0: Zusammenfassung ──────────────────────────────────────────────────

def write_summary_sheet(ws, df, rel_stats, dlv_comp):
    ws.title = "Zusammenfassung"
    pre  = df[df["periode"] == "PRE"]
    post = df[df["periode"] == "POST"]

    uf_stats  = rel_stats[rel_stats["unterfakturierung"]] if len(rel_stats) else pd.DataFrame()
    dlv_under = dlv_comp[dlv_comp["dlv_differenz_eur"].fillna(0) < 0] if len(dlv_comp) else pd.DataFrame()

    rows = [
        ("GROZ-BECKERT – Dinas vs. AX Rechnungsvergleich", ""),
        ("Auswertung", pd.Timestamp.today().strftime("%d.%m.%Y")),
        ("", ""),
        ("Basis: Dinas (PRE) = korrekte Abrechnung / Referenz", ""),
        ("", ""),
        ("── PRE (Dinas-System) ──────────────────────", ""),
        ("Sendungen", len(pre)),
        ("Zeitraum", f"{str(pre['Leistungsdatum'].min())[:10]} – {str(pre['Leistungsdatum'].max())[:10]}" if len(pre) else ""),
        ("Σ Erlöse", f"{pre['Erloese'].sum():,.2f} €"),
        ("Ø Erlöse/Sendung", f"{pre['Erloese'].mean():,.2f} €"),
        ("Median €/100kg", f"{pre['erloes_je_100kg'].median():,.4f}"),
        ("Ø Gewicht kg", f"{pre['Tonnage (eff.)'].mean():,.1f}"),
        ("", ""),
        ("── POST (AX-System) ────────────────────────", ""),
        ("Sendungen", len(post)),
        ("Zeitraum", f"{str(post['Leistungsdatum'].min())[:10]} – {str(post['Leistungsdatum'].max())[:10]}" if len(post) else ""),
        ("Σ Erlöse", f"{post['Erloese'].sum():,.2f} €"),
        ("Ø Erlöse/Sendung", f"{post['Erloese'].mean():,.2f} €"),
        ("Median €/100kg", f"{post['erloes_je_100kg'].median():,.4f}"),
        ("Ø Gewicht kg", f"{post['Tonnage (eff.)'].mean():,.1f}"),
        ("", ""),
        ("── Dinas-Referenz vs. AX (>5% Abw.) ───────", ""),
        ("Auffällige Relationen+Buckets", len(rel_stats)),
        ("Davon Unterfakturierung AX < Dinas", len(uf_stats)),
        ("Erw. Gesamtverlust Unterfakturierung", f"{uf_stats['erwarteter_verlust_eur'].sum():,.2f} €" if len(uf_stats) else "0,00 €"),
        ("", ""),
        ("── DLV-Vertragscheck (POST vs. Soll) ──────", ""),
        ("POST-Sendungen mit DLV-Rate ermittelt", len(dlv_comp)),
        ("Davon unter Soll-Fracht (Unterfakturierung)", len(dlv_under)),
        ("Gesamtdifferenz Ist < Soll", f"{dlv_under['dlv_differenz_eur'].sum():,.2f} €" if len(dlv_under) else "0,00 €"),
        ("", ""),
        ("── NK-Sonderregeln (Dinas) ─────────────────", ""),
        ("Portugal Mindest-LDM", f"{PT_MIN_LDM} LDM (lt. NK 153832)"),
        ("CH Incoterm", "DDP – Zölle durch Groz-Beckert (lt. NK 306503CH)"),
        ("DLV-Gültigkeit", "01.05.2025 – 30.06.2026"),
    ]

    for ri, (lbl, val) in enumerate(rows, 1):
        cl = ws.cell(ri, 1, lbl)
        cv = ws.cell(ri, 2, val)
        if lbl.startswith("GROZ"):
            cl.font = Font(bold=True, name="Calibri", size=13, color=C_HEADER)
            ws.merge_cells(f"A{ri}:B{ri}")
        elif lbl.startswith("──"):
            cl.font = Font(bold=True, name="Calibri", size=10, color=C_HEADER)
        elif lbl.startswith("Basis"):
            cl.font = Font(italic=True, name="Calibri", size=10, color="555555")
            ws.merge_cells(f"A{ri}:B{ri}")
        else:
            cl.font = Font(name="Calibri", size=10)
            cv.font = Font(bold=True, name="Calibri", size=10)

    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 28


# ── Sheet 1: Relationen-Übersicht ─────────────────────────────────────────────

def write_uebersicht_sheet(ws, rel_stats):
    ws.title = "Übersicht_Relationen"
    header = [
        "Relation", "Gewichtsbucket", "Versender Land", "Empfänger Land",
        "Empfänger PLZ", "Empfänger Ort",
        "n Dinas (PRE)", "Σ Erlöse Dinas €", "Ø Erlöse Dinas €", "Median €/100kg Dinas",
        "n AX (POST)", "Σ Erlöse AX €", "Ø Erlöse AX €", "Median €/100kg AX",
        "Abweichung %", "Erw. Verlust €", "Unterfakturierung",
        "Ø Gewicht Dinas kg", "Ø Gewicht AX kg",
    ]
    for ci, h in enumerate(header, 1):
        _hdr(ws.cell(1, ci, h))
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"

    for ri, (_, r) in enumerate(rel_stats.iterrows(), 2):
        vals = [
            r["relation_key"], r["gewicht_bucket"],
            r["versender_land"], r["empf_land"],
            r["empf_plz"], r.get("empf_stadt", ""),
            int(r["n_pre"]), round(r["sum_erloes_pre"], 2),
            round(r["avg_erloes_pre"], 2), round(r["median_rate_pre"], 4),
            int(r["n_post"]), round(r["sum_erloes_post"], 2),
            round(r["avg_erloes_post"], 2), round(r["median_rate_post"], 4),
            round(r["abweichung_pct"], 2),
            round(r["erwarteter_verlust_eur"], 2),
            "JA" if r["unterfakturierung"] else "NEIN",
            round(r["avg_gewicht_pre"], 1) if not pd.isna(r["avg_gewicht_pre"]) else "",
            round(r["avg_gewicht_post"], 1) if not pd.isna(r["avg_gewicht_post"]) else "",
        ]
        bg = C_POST_ROW if r["unterfakturierung"] else C_PRE_ROW
        for ci, v in enumerate(vals, 1):
            cell = ws.cell(ri, ci, v)
            _dat(cell, bg)
            cell.border = _border()
            if ci == 15:
                _pct_color(cell, v if isinstance(v, float) else float("nan"))
            if ci == 16:
                _eur_color(cell, v if isinstance(v, float) else float("nan"))
    _autofit(ws)


# ── Sheet 2: Ausreißer Sendungsebene ──────────────────────────────────────────

def write_ausreisser_sheet(ws, outliers):
    ws.title = "Ausreißer_Sendungen"
    base = ["Auftragsnummer", "Rechnungsnummer", "Leistungsdatum",
            "Versender Name", "Versender PLZ", "Versender Land",
            "Empfänger Name", "Empfänger PLZ", "Empfänger Stadt", "Empfänger Land",
            "Relation Ausgang", "relation_key", "gewicht_bucket"]
    kpi  = ["Tonnage (eff.)", "billing_weight_kg", "Lademeter", "Volumen",
            "Stellplätze", "Colli",
            "Erloese", "erloes_je_100kg", "erloes_je_sendung",
            "ppu_dinas_referenz", "abweichung_pct", "erwarteter_verlust_eur"]
    nk   = [c for c in ERLOES_DETAIL_COLS if c in outliers.columns]
    cols = [c for c in base + kpi + nk if c in outliers.columns]

    labels = {
        "erloes_je_100kg": "Erlöse/100kg AX €",
        "erloes_je_sendung": "Erlöse/Sdg AX €",
        "ppu_dinas_referenz": "Ref €/100kg Dinas",
        "abweichung_pct": "Abw. % (AX vs Dinas)",
        "erwarteter_verlust_eur": "Erw. Verlust €",
        "billing_weight_kg": "Abrech.-Gew. kg",
    }
    for ci, c in enumerate(cols, 1):
        _hdr(ws.cell(1, ci, labels.get(c, c)), bg=C_SUBHDR)
    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"

    rel_colors = {r: ("EAF0FB" if i % 2 == 0 else "FFFFFF")
                  for i, r in enumerate(outliers["relation_key"].unique())}

    for ri, (_, row) in enumerate(outliers.iterrows(), 2):
        bg = rel_colors.get(row.get("relation_key", ""), "FFFFFF")
        for ci, col in enumerate(cols, 1):
            val = row.get(col, "")
            if pd.isna(val): val = ""
            elif isinstance(val, float): val = round(val, 4)
            cell = ws.cell(ri, ci, val)
            _dat(cell, bg)
            cell.border = _border()
            if col == "abweichung_pct":
                _pct_color(cell, val if isinstance(val, float) else float("nan"))
            if col == "erwarteter_verlust_eur":
                _eur_color(cell, val if isinstance(val, float) else float("nan"))
    _autofit(ws)


# ── Sheet 3: DLV-Vertragscheck ────────────────────────────────────────────────

def write_dlv_sheet(ws, dlv_comp):
    ws.title = "DLV_Vertragscheck"
    base = ["Auftragsnummer", "Rechnungsnummer", "Leistungsdatum",
            "Versender Name", "Versender PLZ", "Versender Land",
            "Empfänger Name", "Empfänger PLZ", "Empfänger Stadt", "Empfänger Land",
            "relation_key"]
    dim  = ["Tonnage (eff.)", "Lademeter", "Volumen", "Stellplätze", "Colli"]
    dlv  = ["dlv_soll_fracht", "ist_fracht", "ist_basis", "dlv_methode",
            "dlv_abweichung_pct", "dlv_differenz_eur",
            "Erlöse Fracht", "Erlöse Diesel", "Erlöse Maut",
            "Erlöse Nebengebühr", "Erlöse EUST Zoll", "Erloese"]
    cols = [c for c in base + dim + dlv if c in dlv_comp.columns]

    labels = {
        "dlv_soll_fracht":    "DLV Soll-Fracht €",
        "ist_fracht":         "Ist-Fracht €",
        "ist_basis":          "Vergleichsbasis",
        "dlv_methode":        "DLV-Methode",
        "dlv_abweichung_pct": "Abw. % (Ist vs. Soll)",
        "dlv_differenz_eur":  "Differenz € (Ist-Soll)",
        "Erloese":            "Erloese gesamt €",
        "relation_key":       "Relation",
    }
    for ci, c in enumerate(cols, 1):
        _hdr(ws.cell(1, ci, labels.get(c, c)), bg=C_HEADER)
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"

    for ri, (_, row) in enumerate(dlv_comp.iterrows(), 2):
        # Zeilenhintergrund: rot bei Unterfakturierung (Ist < Soll)
        diff = float(row.get("dlv_differenz_eur", 0) or 0)
        bg = "FFE0E0" if diff < -5 else ("E0FFE0" if diff > 5 else "FFFFFF")
        for ci, col in enumerate(cols, 1):
            val = row.get(col, "")
            if pd.isna(val): val = ""
            elif isinstance(val, float): val = round(val, 4)
            cell = ws.cell(ri, ci, val)
            _dat(cell, bg)
            cell.border = _border()
            if col == "dlv_abweichung_pct":
                _pct_color(cell, val if isinstance(val, float) else float("nan"))
            if col == "dlv_differenz_eur":
                # Negative Differenz = Unterfakturierung
                v = val if isinstance(val, float) else float("nan")
                if not math.isnan(v):
                    cell.fill = PatternFill("solid", fgColor=C_LOSS if v < 0 else C_OK)
    _autofit(ws)


# ── Sheet 4: Dinas Nebenkosten ────────────────────────────────────────────────

def write_nebenkosten_sheet(ws, nk_df):
    ws.title = "Dinas_Nebenkosten"
    header = list(nk_df.columns)
    for ci, h in enumerate(header, 1):
        _hdr(ws.cell(1, ci, h))
    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"
    for ri, (_, row) in enumerate(nk_df.iterrows(), 2):
        bg = "F0F8FF" if ri % 2 == 0 else "FFFFFF"
        for ci, h in enumerate(header, 1):
            val = row.get(h, "")
            if pd.isna(val): val = ""
            elif isinstance(val, float): val = round(val, 2)
            cell = ws.cell(ri, ci, val)
            _dat(cell, bg)
            cell.border = _border()
    _autofit(ws)


# ── Sheet 5: NK Nebenbedingungen ──────────────────────────────────────────────

def write_nk_sheet(ws, nk_cond):
    ws.title = "NK_Nebenbedingungen"

    # Titelzeile mit Hinweis
    note_cell = ws.cell(1, 1, "DINAS Nebenbedingungen Groz-Beckert (Abrechnungsrelevante Einträge)")
    note_cell.font = Font(bold=True, name="Calibri", size=11, color=C_HEADER)
    ws.merge_cells("A1:F1")
    ws.row_dimensions[1].height = 22

    # Hinweis-Zeile Portugal
    ws.cell(2, 1, f"NK-Sonderregel Portugal: Mindestabrechnung {PT_MIN_LDM} LDM (Schlüssel 153832 – lt. NK: 'MINIMUMABR. 3 LM LT. SST.')")
    ws.cell(2, 1).font = Font(italic=True, name="Calibri", size=9, color="AA0000")
    ws.merge_cells("A2:F2")
    ws.cell(3, 1, "NK-Sonderregel CH: Immer DDP (Incoterm 95) – Groz-Beckert zahlt Zölle, separate Rechnung (Schlüssel 306503CH/187453CH)")
    ws.cell(3, 1).font = Font(italic=True, name="Calibri", size=9, color="AA0000")
    ws.merge_cells("A3:F3")

    if nk_cond.empty:
        ws.cell(4, 1, "(NK-Datei nicht geladen)")
        return

    header = list(nk_cond.columns)
    for ci, h in enumerate(header, 1):
        _hdr(ws.cell(5, ci, str(h)[:40]), bg=C_SUBHDR)
    ws.row_dimensions[5].height = 28
    ws.freeze_panes = "A6"

    for ri, (_, row) in enumerate(nk_cond.iterrows(), 6):
        bg = "F5F5F5" if ri % 2 == 0 else "FFFFFF"
        aktiv_val = row.get("Aktiv", "")
        if isinstance(aktiv_val, pd.Series):
            aktiv_val = aktiv_val.iloc[0] if len(aktiv_val) else ""
        aktiv = str(aktiv_val).strip()
        if aktiv.lower() == "nein":
            bg = "EEEEEE"  # inaktive Einträge grau
        for ci, col_val in enumerate(row.iloc[:len(header)], 1):
            # iloc avoids duplicate-column ambiguity
            val = col_val
            if isinstance(val, pd.Series):
                val = val.iloc[0] if len(val) else ""
            try:
                is_na = pd.isna(val)
            except Exception:
                is_na = False
            if is_na:
                val = ""
            cell = ws.cell(ri, ci, str(val)[:200])
            _dat(cell, bg)
            cell.border = _border()
    _autofit(ws, mn=8, mx=60)


# ═══════════════════════════════════════════════════════════════════════════════
# F  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 65)
    print("Groz-Beckert | Dinas vs. AX Rechnungsvergleich")
    print("Basis: Dinas = korrekte Abrechnung / Referenz")
    print("=" * 65)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 1. BI-Daten laden
    df = load_groz_beckert_bi(BI_PATH)

    # 2. DLV-Tarife parsen
    print(f"\n[DLV] Lese {DLV_PATH.name} …")
    gc_entries  = parse_dlv_general_cargo(DLV_PATH)
    ltl_entries = parse_dlv_ltl_ftl(DLV_PATH)

    # 3. NK Nebenbedingungen
    print(f"\n[NK] Lese {NK_PATH.name} …")
    nk_cond = parse_nk_conditions(NK_PATH)

    # 4. Relationen-Statistik (Dinas-Referenz vs. AX)
    print("\n[OutlierEngine] Dinas-Referenz vs. AX …")
    rel_stats = compute_relation_stats(df)
    print(f"  Auffällige Relationen+Buckets: {len(rel_stats)}")
    if len(rel_stats):
        uf = rel_stats[rel_stats["unterfakturierung"]]
        verlust = uf["erwarteter_verlust_eur"].sum()
        print(f"  Unterfakturierung AX < Dinas:  {len(uf)}")
        print(f"  Erw. Gesamtverlust:            {verlust:,.2f} €")

    # 5. Sendungsebene Ausreißer
    print("\n[OutlierEngine] POST-Ausreißer-Sendungen …")
    outliers = find_post_outliers(df, rel_stats) if len(rel_stats) else pd.DataFrame()
    print(f"  Ausreißer-Sendungen: {len(outliers)}")

    # 6. DLV-Vertragscheck (POST)
    print("\n[DLV] Soll-Fracht für POST-Sendungen berechnen …")
    dlv_comp = compute_dlv_comparison(df, gc_entries, ltl_entries)
    has_soll   = dlv_comp["dlv_soll_fracht"].notna().sum()
    dlv_under  = dlv_comp[dlv_comp["dlv_differenz_eur"].fillna(0) < 0]
    print(f"  DLV-Rate ermittelt:             {has_soll} / {(df['periode']=='POST').sum()} POST-Sendungen")
    print(f"  Unterfakturierung (Ist < Soll): {len(dlv_under)}")
    if len(dlv_under):
        print(f"  Gesamtdifferenz Ist < Soll:    {dlv_under['dlv_differenz_eur'].sum():,.2f} €")

    # 7. Dinas Nebenkosten
    nebenkosten = get_dinas_nebenkosten(df)

    # 8. Excel schreiben
    print(f"\n[ExcelWriter] Schreibe {OUTPUT_PATH.name} …")
    wb = Workbook()

    ws0 = wb.active
    write_summary_sheet(ws0, df, rel_stats, dlv_comp)

    ws1 = wb.create_sheet()
    write_uebersicht_sheet(ws1, rel_stats)

    ws2 = wb.create_sheet()
    write_ausreisser_sheet(ws2, outliers)

    ws3 = wb.create_sheet()
    write_dlv_sheet(ws3, dlv_comp)

    ws4 = wb.create_sheet()
    write_nebenkosten_sheet(ws4, nebenkosten)

    ws5 = wb.create_sheet()
    write_nk_sheet(ws5, nk_cond)

    wb.save(OUTPUT_PATH)
    print(f"  Gespeichert: {OUTPUT_PATH}")

    # ── Konsolenausgabe ────────────────────────────────────────────────────────
    SEP = "─" * 65
    print(f"\n{SEP}")
    print("Top-Ausreißer (Dinas-Referenz vs. AX, >5% Abw.):")
    print(SEP)
    if len(rel_stats):
        show = ["relation_key", "gewicht_bucket", "n_pre", "n_post",
                "median_rate_pre", "median_rate_post",
                "abweichung_pct", "erwarteter_verlust_eur"]
        print(rel_stats[show].head(10).to_string(index=False))
    else:
        print("  Keine Ausreißer.")

    print(f"\n{SEP}")
    print("Top-DLV-Unterfakturierungen (POST Ist < DLV Soll):")
    print(SEP)
    if len(dlv_under):
        show2 = ["Auftragsnummer", "Empfänger Land", "Tonnage (eff.)",
                 "Lademeter", "dlv_soll_fracht", "ist_fracht",
                 "dlv_differenz_eur", "dlv_methode"]
        show2 = [c for c in show2 if c in dlv_under.columns]
        print(dlv_under[show2].head(10).to_string(index=False))
    else:
        print("  Keine DLV-Unterfakturierungen gefunden.")

    print("\nFertig.")


if __name__ == "__main__":
    main()
