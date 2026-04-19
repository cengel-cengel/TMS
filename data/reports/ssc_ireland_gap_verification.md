# Etappe 8g — SSC Irland ax_coverage_gap Verifikation

**Stand:** 2026-04-19  
**Scope:** 17 ax_coverage_gap-Familien (827.784 €) aus Etappe 8f  
**Migration-Cutoff:** 2025-09-26

---

## 1. Datenquellen-Check AX

### 1a. SSC (KNR 511241) in Sika.xlsx

- Gesamt SSC-Rows in Sika.xlsx: **499**
- Leistungsdatum: 2025-09-29 – 2026-04-16
- Gesamt Betrag: 825,548.94 €
- SSC-Rows mit Irland-Zielort ('Nach Ort' contains IE/Dublin/Ireland): **0**
- Row-Typ Verteilung: MASTER=366, SUB=133, STANDALONE=0
- Cluster-Master-Rows: 366, Sub-Rows: 133, unique Cluster-IDs (via SUB): 113

### 1b. Weitere Abrechnungsstrecken-Dateien

- `Bitzer.xlsx`: Spalten=['Abrechnungsstrecke', 'Erstellungsdatum', 'Abrechnungsart', 'Tournummer', 'Position - Transportschritt', 'Von Land'] — kein SSC-KNR erwartet
- `CHT.xlsx`: Spalten=['Abrechnungsstrecke', 'Erstellungsdatum', 'Abrechnungsart', 'Tournummer', 'Position - Transportschritt', 'Von Land'] — kein SSC-KNR erwartet
- `EBM.xlsx`: Spalten=['Abrechnungsstrecke', 'Erstellungsdatum', 'Abrechnungsart', 'Tournummer', 'Position - Transportschritt', 'Von Land'] — kein SSC-KNR erwartet
- `Fischerwerke.xlsx`: Spalten=['Abrechnungsstrecke', 'Erstellungsdatum', 'Abrechnungsart', 'Tournummer', 'Position - Transportschritt', 'Von Land'] — kein SSC-KNR erwartet
- `Geze.xlsx`: Spalten=['Abrechnungsstrecke', 'Erstellungsdatum', 'Abrechnungsart', 'Tournummer', 'Position - Transportschritt', 'Von Land'] — kein SSC-KNR erwartet
- `Groz.xlsx`: Spalten=['Abrechnungsstrecke', 'Erstellungsdatum', 'Abrechnungsart', 'Tournummer', 'Position - Transportschritt', 'Von Land'] — kein SSC-KNR erwartet
- `Helu.xlsx`: Spalten=['Abrechnungsstrecke', 'Erstellungsdatum', 'Abrechnungsart', 'Tournummer', 'Position - Transportschritt', 'Von Land'] — kein SSC-KNR erwartet
- `Herma.xlsx`: Spalten=['Abrechnungsstrecke', 'Erstellungsdatum', 'Abrechnungsart', 'Tournummer', 'Position - Transportschritt', 'Von Land'] — kein SSC-KNR erwartet
- `Hornschuch.xlsx`: Spalten=['Abrechnungsstrecke', 'Erstellungsdatum', 'Abrechnungsart', 'Tournummer', 'Position - Transportschritt', 'Von Land'] — kein SSC-KNR erwartet

## 2. Dinas-Seite Detail

### 2a. Letztes leistung_date und Abbruchmuster pro Gap-Familie

| Familie | Letzter Dinas | Cluster | Fracht € | Rechnungs-Rhythmus |
|---------|-------------|---------|---------|------------------|
| `511241|70|17|ssc_stellplatz` | 2025-06-03 | 4 | 159,611 | ~32d |
| `511241|70|19|ssc_stellplatz` | 2025-07-01 | 7 | 152,151 | ~30d |
| `511241|70|20|ssc_stellplatz` | 2025-06-30 | 6 | 106,617 | ~31d |
| `511241|70|IP|ssc_stellplatz` | 2025-06-03 | 3 | 103,302 | ~75d |
| `511241|70|LS|ssc_stellplatz` | 2025-05-02 | 3 | 83,097 | ~75d |
| `511241|70|AL|ssc_stellplatz` | 2025-07-01 | 2 | 73,777 | ~147d |
| `511241|70|DU|ssc_stellplatz` | 2025-07-18 | 14 | 60,794 | ~17d |
| `527406|70|28|sika_atm_ch` | 2025-08-13 | 10 | 34,172 | ~17d |
| `511241|70|28|ssc_stellplatz` | 2025-05-02 | 3 | 26,896 | ~75d |
| `527406|70|36|sika_atm_ch` | 2025-06-16 | 5 | 20,126 | ~24d |
| `511241|70|41|ssc_stellplatz` | 2025-06-30 | 5 | 4,211 | ~49d |
| `511241|70|LU|ssc_stellplatz` | 2025-07-11 | 1 | 1,808 | – |
| `527406|70|29|sika_atm_ch` | 2025-08-01 | 1 | 528 | – |
| `491063|72|95|sika_de_stellplatz` | 2025-03-10 | 2 | 296 | ~12d |
| `491063|41|72|sika_de_stellplatz` | 2025-02-20 | 1 | 234 | – |
| `491063|47|70|sika_de_stellplatz` | 2025-07-28 | 1 | 164 | – |
| `491063|LU|72|sika_de_stellplatz` | 2025-02-25 | 2 | 0 | ~0d |

### 2b. SSC IE-Lanes: Monatliche Fracht-Zeitreihe

**511241|70|17|ssc_stellplatz** (`Spanien ES-17 (Girona)`):

| Monat | Fracht € |
|-------|---------|
| 2025-02 | 45,088 |
| 2025-03 | 38,541 |
| 2025-05 | 39,206 |
| 2025-06 | 36,777 |

**511241|70|19|ssc_stellplatz** (`Spanien ES-19 (Guadalajara)`):

| Monat | Fracht € |
|-------|---------|
| 2024-12 | 13,001 |
| 2025-01 | 42,404 |
| 2025-04 | 45,337 |
| 2025-05 | 2,138 |
| 2025-06 | 8,551 |
| 2025-07 | 40,721 |

**511241|70|20|ssc_stellplatz** (`Spanien ES-20 (Gipuzkoa)`):

| Monat | Fracht € |
|-------|---------|
| 2025-01 | 19,217 |
| 2025-03 | 16,977 |
| 2025-04 | 19,918 |
| 2025-05 | 32,254 |
| 2025-06 | 18,251 |

**511241|70|IP|ssc_stellplatz** (`Dublin IE (IP postcode)`):

| Monat | Fracht € |
|-------|---------|
| 2025-01 | 31,847 |
| 2025-04 | 38,154 |
| 2025-06 | 33,301 |

**511241|70|LS|ssc_stellplatz** (`Dublin IE (LS postcode)`):

| Monat | Fracht € |
|-------|---------|
| 2024-12 | 17,070 |
| 2025-03 | 30,191 |
| 2025-05 | 35,836 |

### 2c. Dinas-Rohdaten: SSC IE/GB-Sendungen nach Zeitraum

- Gesamt SSC-Dinas-Rows (alle ERKAs): 1,198
- Davon mit Land=IE/GB: 204
- PRE-Migration (≤ 2025-09-26): 204 Rows, bis 2025-07-31
- POST-Migration (> 2025-09-26): 0 Rows

## 3. Tagesbericht Cross-Check

- TB gesamt: 250,950 Rows
- TB POST-Migration (>2025-09-26): 132,937 Rows

### 3a. SSC-Sendungen im TB POST-Migration

- 16-stellige Auftragsnummern (AX-Seite): 132,539 Rows
- TB POST mit Empfänger Land=IE: **1,474** Rows
  - davon 16-digit (AX): 1472
  - davon 8-digit (Dinas): 1
  - Zeitraum (16-digit IE): 2025-09-29 – 2026-03-30
  - Sample Auftragsnummern: ['7090100000512007', '7801001480271003', '7092010017941005', '7090100000515008', '7092010000761009']

### 3b. Stichproben-Lanes im TB (IP/LS/AL Postleitzahlen)

#### Lane `511241|70|IP|ssc_stellplatz` (empf_plz_2='IP')

- TB-Rows mit Empfänger-PLZ-Präfix `IP` (gesamt): 71
- Davon POST-Migration: 31
  - 16-digit (AX): 31, 8-digit (Dinas): 0
  - Zeitraum 16-digit: 2025-09-30 – 2026-03-27
  - Sample 16-digit Auftragsnr.: ['7090100000445008', '7092010002200001', '7092010004972005']
  - Davon in Sika.xlsx vorhanden: 16 von 31
    → Vorhanden in Sika.xlsx → sollte in ax_clusters sein!

#### Lane `511241|70|LS|ssc_stellplatz` (empf_plz_2='LS')

- TB-Rows mit Empfänger-PLZ-Präfix `LS` (gesamt): 266
- Davon POST-Migration: 118
  - 16-digit (AX): 118, 8-digit (Dinas): 0
  - Zeitraum 16-digit: 2025-09-29 – 2026-03-30
  - Sample 16-digit Auftragsnr.: ['7090100000449006', '7092010003070009', '7092010003046004']
  - Davon in Sika.xlsx vorhanden: 33 von 118
    → Vorhanden in Sika.xlsx → sollte in ax_clusters sein!

#### Lane `511241|70|AL|ssc_stellplatz` (empf_plz_2='AL')

- TB-Rows mit Empfänger-PLZ-Präfix `AL` (gesamt): 10
- Davon POST-Migration: 3
  - 16-digit (AX): 3, 8-digit (Dinas): 0
  - Zeitraum 16-digit: 2025-10-24 – 2026-01-09
  - Sample 16-digit Auftragsnr.: ['7092010011474004', '7092010024615005', '7092010026881002']
  - Davon in Sika.xlsx vorhanden: 3 von 3
    → Vorhanden in Sika.xlsx → sollte in ax_clusters sein!

### 3c. Gibt es 16-stellige TB-Einträge mit SSC-Kunden post-Migration?

16-digit TB-Rows POST mit Land=IE: **1472**

Häufigste Rechnungsnummern dieser Rows:

| Rechnungsnummer | Anzahl |
|----------------|--------|
| 0 | 208 |
| 4251018369 | 28 |
| 4251025038 | 24 |
| 4251018354 | 18 |
| 4251025036 | 16 |
| 5105714848 | 15 |
| 4251016740 | 14 |
| 4251022806 | 14 |
| 4251001069 | 13 |
| 4251018327 | 13 |

## 4. Klassifikation pro Gap-Familie

| Familie | Letzter Dinas | TB POST IE? | In Sika.xlsx? | Klassifikation |
|---------|-------------|------------|--------------|----------------|
| `511241|70|17|ssc_stellplatz` | 2025-06-03 | Ja (509 Rows) | Ja | fehlt_in_ax_clusters |
| `511241|70|19|ssc_stellplatz` | 2025-07-01 | Ja (1001 Rows) | Ja | fehlt_in_ax_clusters |
| `511241|70|20|ssc_stellplatz` | 2025-06-30 | Ja (3414 Rows) | Ja | fehlt_in_ax_clusters |
| `511241|70|IP|ssc_stellplatz` | 2025-06-03 | Ja (31 Rows) | Ja | fehlt_in_ax_clusters |
| `511241|70|LS|ssc_stellplatz` | 2025-05-02 | Ja (118 Rows) | Ja | fehlt_in_ax_clusters |
| `511241|70|AL|ssc_stellplatz` | 2025-07-01 | Ja (3 Rows) | Nein | **echte_rechnungsstellung_fehlt** |
| `511241|70|DU|ssc_stellplatz` | 2025-07-18 | Nein | – | **vermutlich_eingestellt** |
| `527406|70|28|sika_atm_ch` | 2025-08-13 | Ja (2076 Rows) | Ja | fehlt_in_ax_clusters |
| `511241|70|28|ssc_stellplatz` | 2025-05-02 | Ja (2076 Rows) | Ja | fehlt_in_ax_clusters |
| `527406|70|36|sika_atm_ch` | 2025-06-16 | Ja (1319 Rows) | Nein | **echte_rechnungsstellung_fehlt** |
| `511241|70|41|ssc_stellplatz` | 2025-06-30 | Ja (2352 Rows) | Ja | fehlt_in_ax_clusters |
| `511241|70|LU|ssc_stellplatz` | 2025-07-11 | Ja (224 Rows) | Ja | fehlt_in_ax_clusters |
| `527406|70|29|sika_atm_ch` | 2025-08-01 | Ja (621 Rows) | Nein | **echte_rechnungsstellung_fehlt** |
| `491063|72|95|sika_de_stellplatz` | 2025-03-10 | Ja (393 Rows) | Nein | **echte_rechnungsstellung_fehlt** |
| `491063|41|72|sika_de_stellplatz` | 2025-02-20 | Ja (10012 Rows) | Nein | **echte_rechnungsstellung_fehlt** |
| `491063|47|70|sika_de_stellplatz` | 2025-07-28 | Ja (9024 Rows) | Ja | fehlt_in_ax_clusters |
| `491063|LU|72|sika_de_stellplatz` | 2025-02-25 | Ja (10012 Rows) | Nein | **echte_rechnungsstellung_fehlt** |

**Legende:**
- `vermutlich_eingestellt`: Keine TB-Aktivität POST → Lane eingestellt
- `fehlt_in_ax_clusters`: TB hat Sendungen, diese sind in Sika.xlsx → build_ax_clusters-Bug oder Filterung
- `echte_rechnungsstellung_fehlt`: TB hat Sendungen, aber nicht in Sika.xlsx → fehlt in AX-Extraktion

## 5. Zusammenfassung und Empfehlung

*(wird nach Analyse-Befunden ergänzt)*

---

*Bericht generiert von `scripts/ssc_ireland_gap_verification.py`.*