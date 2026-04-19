# Dinas-Cluster Summary — Etappe 7b

**Erstellt:** 2026-04-19  
**Modul:** `src/tms/clustering/dinas_cluster.py`  
**Funktion:** `build_dinas_clusters(dinas_df)`  
**Quelle:** `data/parsed/dinas_pdfs.parquet` (5.533 Sendungen aus 496 PDFs)  

---

## 0. Cluster-Schlüssel: Verifikation PDF = Cluster

| Prüfung | Ergebnis |
|---------|----------|
| Distinct pdf_paths | 496 |
| Distinct rechnung_nr | **496** |
| pdf_path ↔ rechnung_nr 1:1 | **JA** (0 Abweichungen) |
| erka_kundennr konstant pro PDF | **JA** |
| rechnung_date konstant pro PDF | **JA** |
| template konstant pro PDF | **JA** |
| leistung_date konstant pro PDF | **NEIN** — 1–15 distinkte Dates; min() verwendet |
| Bordero:Rechnung | n:m möglich (1 Rechnung kann mehrere Bordero-Nrn haben) |

**Fazit: PDF = rechnung_nr = Cluster-Key, 1:1 bestätigt.**

---

## 1. Cluster-Anzahl und Typen

| Kennzahl | Wert |
|----------|------|
| **Cluster gesamt** | **496** |
| davon `erka_standard` | 466 (94.0%) |
| davon `erka_correction` | **30** (6.0%) |

Die 30 Korrektur-Rechnungen sind im Output enthalten und über `is_correction=True` markiert.
Ihre `total_fracht_eur` ist meist NaN/0 (fracht-Spalte für corrections nahezu leer: 16/226 Rows).

---

## 2. Verteilung n_sendungen (Sendungen pro Cluster/Rechnung)

| n_sendungen | Cluster-Anzahl | Anteil |
|-------------|---------------|--------|
| 1 | 123 | 24.8% |
| 2–3 | 43 | 8.7% |
| 4–5 | 49 | 9.9% |
| 6–10 | 103 | 20.8% |
| 11–15 | 59 | 11.9% |
| 16–20 | 36 | 7.3% |
| 21–50 | 74 | 14.9% |
| 51–200 | 9 | 1.8% |
| **Gesamt** | **496** | |

**Median:** 7 Sendungen · **Max:** 157 (Rechnung 3773104, ERKA 97505) · **Total Sendungen:** 5.533

---

## 3. ERKA-Verteilung

| ERKA | Cluster | Beschreibung |
|------|---------|--------------|
| 25607 | 91 | — |
| 18748 | 70 | SikaATM CH |
| 18894 | 61 | SikaATM DE |
| 90107 | 54 | — |
| 15550 | 46 | — |
| 90123 | 26 | — |
| 14466 | 21 | — |
| (weitere 22 ERKAs) | 127 | — |

---

## 4. Nebenkosten-Separation (erka_standard, 466 Cluster)

| Kategorie | Ø je Cluster | Cluster mit Wert > 0 |
|-----------|-------------|---------------------|
| `total_fracht_eur` | **6.195 EUR** | — |
| `diesel_eur` | 166 EUR | — |
| `maut_eur` (inkl. D-MAUT aus sonstige) | 166 EUR | — |
| `thermo_eur` | 0.64 EUR | **2** (THERMOZUSCHLAG) |
| `sonstige_nk_eur` | 125 EUR | 295 (63%) |

**Hinweis D-MAUT-Konsolidierung:** D-MAUT-Positionen in der `sonstige`-Spalte werden in
`maut_eur` eingerechnet (nicht in `sonstige_nk_eur`), damit Maut-Gesamtsumme konsistent ist.

**Häufigste Sonstige-NK-Labels:**
| Label | Häufigkeit |
|-------|-----------|
| GEFAHRGUTZUSCHLAG 17 Gefahrgutzuschl | 969 |
| SONSTIGE NEBENGEBÜHREN 1 Administrationsgebühr | 927 |
| SSD F. GB / MAUT 2025 ANDERE LÄNDER | 792 |
| AVISGEBÜHR | 175 |
| NEBENKOSTENPAUSCHALE MAUT AT 2025 | 169 |
| GEFAHRGUTZUSCHLAG ADR FÄHRKOSTEN | 127 |
| TERMINZUSCHLAG F. FIXSENDUNGEN NEXT DAY | 97 |

---

## 5. Geografische Coverage (Empfänger-Land)

Basiert auf `empf_land` in den Parquet-Rohdaten (Anzahl Rechnungen mit ≥1 Sendung ins Land):

| Land | Rechnungen |
|------|-----------|
| DE | 153 |
| ES | 84 |
| GB | 82 |
| IT | 79 |
| PT | 60 |
| IE | 42 |
| AT | 18 |
| RS | 15 |
| GR | 12 |
| FR | 8 |
| NL | 6 |
| BE | 5 |
| DK | 4 |
| CH | 2 |

---

## 6. Bordero-Tracking

| Bordero-Nrn pro Cluster | Cluster-Anzahl |
|------------------------|---------------|
| 1 | 159 |
| 2 | 28 |
| 3 | 17 |
| 4 | 22 |
| 5 | 24 |
| 6 | 28 |
| 7 | 26 |
| 8 | 20 |
| 9 | 16 |
| 10 | 9 |
| > 10 | (restliche) |

Bordero ist **kein** Cluster-Level-Equivalent: Ein Cluster (Rechnung) kann mehrere Bordero-Nrn enthalten.
Umgekehrt teilen 151 Borderos ihre Nummer über 2 Rechnungen (seltene Mehrfachbuchung).

---

## 7. Physikalische Dimensionen

| Dimension | Non-Zero Cluster | Hinweis |
|-----------|-----------------|---------|
| `aggregat_gewicht_kg` | 174 / 496 (35%) | PDF-Parser extrahiert Gewicht nur wenn Regex-Match |
| `aggregat_stp` | 153 / 496 (31%) | Stellplätze nicht in allen PDF-Formaten |
| `aggregat_ldm` | sehr wenige | lm in parquet nur 16/5.533 non-null |
| `aggregat_volumen` | 0 | Keine Volumenspalte im aktuellen Parquet-Extract |

**Hinweis:** Die geringe Gewichts-Coverage (35%) ist eine bekannte Limitation des
PDF-Parsers. Für Abrechnungs-Validierung wird `fracht` (93%) als primäre Dimension
verwendet. Gewichts-Enrichment über Tagesbericht-Join ist möglich aber nicht in diesem Modul.

---

## 8. Test-Status

```
26/26 Tests grün
  18 Unit Tests  (synthetische DataFrames)
   8 Integration Tests (echte dinas_pdfs.parquet)

Abgedeckt:
  ✓ 11-Sendungen-Cluster: n_sendungen=11, aggregat korrekt, leistungsdatum=min
  ✓ Nebenkosten-Separation: diesel/maut/thermo/sonstige_nk getrennt
  ✓ D-MAUT aus sonstige → maut_eur konsolidiert
  ✓ is_correction Flag (erka_correction Template)
  ✓ bordero_nrs: distinct, sorted
  ✓ PLZ 2-stellig
  ✓ Leere Eingabe → leeres DataFrame mit korrekten Spalten
  ✓ Cluster-Anzahl == distinct rechnung_nr (496)
  ✓ Summe n_sendungen == 5.533 (alle Parquet-Rows)
  ✓ Max-Cluster 3773104: 157 Sendungen, ERKA 97505
  ✓ leistungsdatum ist Timestamp-Dtype
```
