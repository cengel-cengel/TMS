# Sika Pre-Flight-Briefing für v1.9.7-Re-Run

**Stand:** 2026-04-28  
**Betrifft:** KNR 491063, 511241, 527406  
**Status:** BLOCKIERT — kein v1.9.6/v1.9.7 Pipeline-Script  

---

## 1. Kontext

Die Sika-Gruppe wurde in Etappe 8i (Stand 2026-04-19) mit Methodik v1.0
(Familien-Vergleich Dinas PRE × AX POST) analysiert. Report: `docs/sika_findings_summary.md`.

| Kennzahl (v1.0) | Wert |
|---|---|
| Familien bilateral vergleichbar | 25 von 81 |
| Unterfakturierung (AX < DLV) | 8 Familien, Muster A–D |
| Coverage-Gaps (keine AX-Cluster) | 7 Familien, ~55.520 EUR hist. Volumen |
| Muster A (AX < DLV): sofortige Prüfung | 2 Familien (SSC PLZ-38, PLZ-47) |
| ATM-CH-Gaps: aktive Sendungen ohne Abrechnung | 3 Familien |

Eine v1.9.7-Neuanalyse (Methodik AX POST × DLV-Soll, ZGI-Cluster-Aggregation)
wird nach Abschluss von Welle 2 (Groz-Beckert, HELU, Hornschuch) durchgeführt.

---

## 2. KNR-spezifische Analyse

### 2.1 KNR 491063 — Sika Deutschland GmbH / CH AG & Co. KG

**BI-Daten (bi_top20_data.pkl):**

- Rows gesamt: 2.355
- ef>0: **1.407 Rows**, Σef = **1.290.687 EUR**

**Calculator:** `src/tms/tariff/calculators/sika_de.py`

- Commit: 7500102
- pricing_basis: `stellplaetze`
- DLV: Stellplatz-basiert, `SIKA DE & SSC Export div. LKZ_Stellplatzofferte[_2026].xlsx`
- shipment_date-Dispatch: 2025 DLV (bis 2025-12-31) / 2026 DLV (ab 2026-01-01) ✓

**DLV-Verzeichnis:** `data/extracted/v1/Noerpel AI/SIka/DLV/SIKA Deutschland GmbH Stuttgart/`

Aktive Dateien:
```
20250109_SIKA DE & SSC Export div. LKZ_Stellplatzofferte.xlsx        (613 KB, 2025)
20251216_SIKA DE & SSC Export div. LKZ_Stellplatzofferte_2026.xlsx   (627 KB, 2026-v1)
20260211_SIKA DE & SSC Export div. LKZ_Stellplatzofferte_2026.xlsx   (627 KB, 2026-v2, aktuell)
V_FRA_7042_O_GB_ALL_Sika.xlsx   (40 KB, GB-Sonderrouten)
V_FRA_7042_O_IE_ALL_Sika.xlsx   (34 KB, IE-Sonderrouten)
V_FRA_7042_O_ES_ALL_Sika.xlsx   (37 KB, ES-Sonderrouten)
V_FRA_7042_O_IT_ALL_Sika.xlsx   (39 KB, IT-Sonderrouten)
V_FRA_7042_O_PT_ALL_Sika.xlsx   (38 KB, PT-Sonderrouten)
V_FRA_7042_I_ES_ALL_Sika.xlsx   (525 KB, Import ES — NICHT Audit-relevant)
V_FRA_7042_I_IT_ALL_Sika.xlsx   (525 KB, Import IT — NICHT Audit-relevant)
```

**P14-Risiko (Archiv-Filter):** kein `durch neue`-Unterordner identifiziert. Import-DLVs
(`_I_ES`, `_I_IT`) sind direkt im Verzeichnis — vor Re-Run prüfen, ob Calculator diese
lädt (P10-Risiko wie Fischerwerke).

**P16-Risiko (Upload vs. Standard):** kein Upload-Ordner in Sika-DLV — nicht anwendbar.

**ARA-Mapping (P3):** bi_top20_data.pkl enthält KNR 491063 mit Name
"Sika Deutschland CH AG & Co KG". Normalisierung: alle Rows unter KNR 491063 =
Sika DE (keine SSC-Vermischung wenn KNR korrekt gesetzt ist).

**Prüfen vor Re-Run:**
- Laden Import-DLVs (`V_FRA_7042_I_`) fälschlich als Export? → Calculator-Code prüfen
- 2026-DLV: welche der zwei Versionen (20251216 vs. 20260211) ist aktiv? → Calculator-Konstante prüfen
- `Versender PLZ` in BI für Dispatch: Sika DE Origin = 70439 Stuttgart (Kornwestheimer Str.)

**Erwarteter Pool:** ~1.407 Rows ef>0, ~1,29 MEUR Scope.

---

### 2.2 KNR 511241 — SIKA SUPPLY CENTER AG (SSC)

**BI-Daten (bi_top20_data.pkl):**

- Rows gesamt: 1.238
- ef>0: **415 Rows**, Σef = **681.512 EUR**

**Calculator:** `src/tms/tariff/calculators/ssc.py`

```python
# ssc.py ist ein Thin-Wrapper:
from tms.tariff.calculators.sika_de import SSCCalculator
```

Derselbe `SSCCalculator` wie in `sika_de.py` — identisches DLV, identische Logik.

**KNR-Normalisierungs-Bug (P3, historisch):** Etappe 8i dokumentierte einen Bug,
bei dem SSC-Rows unter KNR 491063 geführt wurden (~772k EUR Scheindefizit).
In bi_top20_data.pkl ist KNR 511241 korrekt als separate Entität vorhanden.

**Prüfen vor Re-Run (P3):**
- `bi[bi['Kunden Nr BK']==511241]['Von Name'].value_counts()` ausgeben
- Alle Rows unter 511241 sollten Versender "Sika Supply Center AG" enthalten
- Wenn gemischt (491063-Rows unter 511241 oder vice versa): KNR-Filter-Logik im
  Pipeline-Script explizit auf KNR filtern, NICHT auf 'Von Name'

**Erwarteter Pool:** ~415 Rows ef>0, ~682 TEUR Scope.

---

### 2.3 KNR 527406 — Sika ATM CH (Sika Automotive Tiefbau/Mobility)

**BI-Daten:** NICHT in bi_top20_data.pkl (KNR 527406 ist nicht im TOP-20-Datensatz).

Separate BI-Caches vorhanden:
```
output/bi_cache_sika_527406.pkl    (517 KB)
output/bi_cache_sika_atm_de.pkl    (664 KB)
```

**Calculator:** `src/tms/tariff/calculators/sika_atm.py`

- Commit: f005e63
- pricing_basis: Gewicht (EUR/Sendung, flat rate per band) — NICHT Stellplatz
- DLV: `Anlage 1 KORRIGIERT`, valid 2024-07-01 – 2026-06-30
- Keine Stellplatz-Daten in Dinas (stp=NaN) → kein stp-Vergleich möglich

**DLV-Verzeichnis:** `data/extracted/v1/Noerpel AI/SIka/DLV/SIKA Automotive/`

```
Anlage 1_Sika ATM_ERKA...01.07.2024 bis 30.06.2026.xlsx     (Basis)
20250728_Anlage 1_Sika ATM_ERKA...01.07.2024 bis 30.06.2026_KORRIGIERT.xlsx  (aktiv)
Anlage 2_ERKA_Sika ATM Laufzeiten...1.7.2024 bis 30.06.2026.xlsx
2025/20240626_Anlage 2_ERKA_Sika ATM Laufzeiten...xlsx
2025/20250728_Anlage 1_Sika ATM_ERKA...KORRIGIERT.xlsx
```

**Spezielle Einschränkungen:**
- Nicht in bi_top20_data.pkl → separates BI-Loading aus `bi_cache_sika_527406.pkl`
- RS-Serbien (PLZ 34104): DLV-Satz +25 % über Dinas-Ist → DLV-Konfiguration prüfen
- ATM-CH-Gaps (3 Familien): FR/IT-Routen ohne AX-Cluster — POST-Aktivität bestätigt

**Pipeline-Anforderung:**
ATM muss separat vom DE+SSC Pipeline-Script behandelt werden (anderes billing_axis,
anderer Calculator, andere BI-Quelle).

---

## 3. Pipeline-Script-Anforderungen für v1.9.7

### 3.1 build_sika_step23_v197.py (für KNR 491063 + 511241)

```python
# Struktur analog build_bitzer_step23_v196.py
# KNRs: [491063, 511241]
# Filter: Erlöse Fracht > 0
# billing_axis: Stellplätze (stp_eff = max(1, ceil(stp))); LDM-Fallback: ceil(LDM/0.4)
# Dispatch: shipment_date aus Leistungsdatum → 2025-DLV / 2026-DLV
# Sub-Row-Filter: is_sub = has_ms AND NOT has_ua (P9)
# ZGI-Cluster: bi_top20_data.pkl hat keine ZGI-Spalten → kein Cluster-Bias erwartet
#   aber empirisch prüfen: ist_Mastersendung-Verteilung in D1 ausgeben
# Out-of-scope: DE (Inland), ggf. andere ohne DLV
# Output: sika_step23_results_v197.pkl (mit knr-Spalte für Trennung)
```

### 3.2 build_sika_atm_step23_v197.py (für KNR 527406)

```python
# Separate Pipeline:
# BI-Quelle: output/bi_cache_sika_527406.pkl (nicht bi_top20_data.pkl)
# billing_axis: tonnage_kg (flat EUR/Sendung, Gewichtsband)
# Calculator: SikaATMChCalculator aus sika_atm.py
# Sub-Row-Filter: wie oben
# Out-of-scope: DE, CH (ERKA nicht nominiert laut Calculator-Docstring)
# Output: sika_atm_step23_results_v197.pkl
```

---

## 4. Pre-Flight-Skill-Anwendungs-Hinweise

| Pitfall | Relevanz für Sika | Prüfpunkt |
|---|---|---|
| P3 (KNR-Normalisierung) | KRITISCH für 511241 | `bi[bi['KNR']==511241]['Von Name'].value_counts()` |
| P10 (Import-DLV kontaminiert Pool) | MITTEL | `V_FRA_7042_I_ES/IT` im DLV-Verzeichnis — Calculator laden? |
| P11 (vollst. Coverage) | Standard | Full-Run über alle Pool-Rows |
| P12 (Pricing-Mode-Wechsel) | NIEDRIG | 2025→2026 DLV: Stellplatz-basiert bleibt gleich |
| P14 (Archiv-Filter) | NIEDRIG | Kein Archiv-Unterordner in Sika-DE-DLV |
| P15/P16 (Upload DLV) | NICHT ANWENDBAR | Kein Upload-Ordner |

---

## 5. Empfohlene Reihenfolge

1. **Vor Re-Run:** Calculator-Code für P10 prüfen (Import-DLV-Loading)
2. **D1 — KNR-Normalisierung:** bi_top20 für beide KNRs auszählen (P3)
3. **D2 — DLV-Struktur:** 2026-DLV-Version bestätigen (20260211 > 20251216)
4. **D3 — Coverage:** Vollständige Lane-Discovery über beide KNRs
5. **D4 — Pool:** Scope-Entscheidungen, Cluster-Aggregation-Check
6. **Build-Scripts:** Zwei separate Python-Scripts (DE+SSC vs. ATM)
7. **Re-Run:** Outputs in separaten Pkl-Files, dann Reconciliation v1.0 → v1.9.7

**Geschätzter Aufwand:** ~3–4 Stunden (2 h pre-flight + 1 h build-scripts + 1 h run + report).
