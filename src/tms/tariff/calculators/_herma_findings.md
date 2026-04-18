# HERMA GmbH (KNR 423650) — DLV Findings

## 1. Applicable Rate Files

### POST period (Sep–Oct 2025)

| Country | Rate Source | File Path |
|---|---|---|
| ES, IT, FR, GB, IRL, CH | 2025 BiddingMatrix Workbook_1 ohne VL | `Herma Haftmaterial/2025/ohne Vorholung/BiddingMatrix_T2307040744_Workbook_1_2023-07-04T13-49-35.xlsx` |
| ES, IT, FR, GB, IRL, CH (>3000 kg) | 2025 BiddingMatrix Workbook_1 mit VL | `Herma Haftmaterial/2025/mit Vorholung/R2_BiddingMatrix_T2306201202_Workbook_1_2023-07-03T14-39-24.xlsx` |
| PT, RS, RO, SE, SK, SLO, TR | 2025 BiddingMatrix Workbook_4 ohne VL | `Herma Haftmaterial/2025/ohne Vorholung/BiddingMatrix_T2307041343_Workbook_4_2023-07-04T15-58-35.xlsx` |
| AT (and other zero-rate countries) | 2026 Haftmaterial ohne VL | `Herma Haftmaterial/2026/20251212_Herma_Frachtraten ohne VL_2026-2028.xlsx` |
| AT (>3000 kg) | 2026 Haftmaterial mit VL | `Herma Haftmaterial/2026/20251212_Herma_Frachtraten mit VL_2026-2028.xlsx` |

**Key insight**: The 2025 BiddingMatrix files (dated 2023-07) were the 2024–2026 tender submission.
AT has all-zero rates in the 2025 file → uses 2026 DLV exclusively.

### Sub-customer discrimination
- `Versender Name` contains "Haftmaterial" → Haftmaterial DLV
- `Versender Name` contains "Etiketten" → Etiketten DLV (BUT: no Etiketten 2025 BiddingMatrix exists)
- **Finding**: Etiketten uses the SAME Haftmaterial BiddingMatrix rates for all ≤3000 kg weights and mit VL for >3000 kg (confirmed by data matching).
- Exception: Etiketten GB from 2025-05-02 → special file `20250227_Herma Tender 2024-2026_Tarif GB mit und ohne Vorholung ab 02.05.2025.xlsx`

## 2. Rate Structure

### Billing Price Type
- **"Preis pro Sendung"** = flat price per shipment (NOT per-100 kg!)
- All entries are labeled "Preis pro Sendung" in column 0
- No minimum column — the rate IS the rate for that weight band

### Weight Bands
- Columns 4–244: weight bands from "bis 50 kg" to "bis 24.000 kg" (241 bands in 100-kg steps)
- Lookup rule: find smallest band where `band_kg >= billing_weight`

### mit VL vs ohne VL
- For billing_weight ≤ 3000 kg: ohne VL = mit VL (rates are IDENTICAL)
- For billing_weight > 3000 kg: rates differ. ALL verified large-weight BI cases match **mit VL** rates.
- Rule: `billing_weight > 3000 → use mit VL rates`

## 3. Billing Weight Formula (per country)

`billing_weight = max(tonnage_kg, lademeter × ldm_factor, volume_cbm × vol_factor)`

| Country | ldm_factor (kg/ldm) | vol_factor (kg/cbm) |
|---|---|---|
| ES | 1500 | 300 |
| AT | 1500 | 300 |
| GB | 1500 | 300 |
| IRL | 1500 | 300 |
| PT | 1500 | 300 (inferred) |
| RS | 1500 | – |
| IT (PLZ 38–39 Bozen) | 1500 | 300 |
| IT (all other PLZ) | 1250 | 250 |
| FR | 1250 | 250 |
| BA | 1650 | 333 |
| MK | 1650 | 333 |

## 4. Sheet Structures

### Type A: Von/Bis/Zone (ES, AT, RS, MK, BA)
```
Row 0: HERMA GmbH, ..., Abrechnungsgrundlage:, 1500 kg / ldm
Row 1: Country name, ..., 300 kg / cbm
Row 3: [Bezeichnung, Von, Bis, Zone, bis 50 kg, bis 100 kg, ..., bis 24.000 kg]
Row 4: [None, None, None, None, [Unit price], ...]
Row 5+: [Preis pro Sendung, von_plz, bis_plz, zone_num, r1, r2, ..., r241]
```
- 244 data columns (4 label + 241 weight bands)

### Type B: 2-digit PLZ (FR)
```
Row 3: [Bezeichnung, 2-st PLZ, bis 50 kg, bis 100 kg, ..., bis 5.000 kg]
Row 5+: [Preis pro Sendung, plz_2digit, r1, r2, ..., r51]
```
- 53 data columns (2 label + 51 weight bands)
- FR ldm factor: 1250 kg/ldm, 250 kg/cbm

### Type C: UK Area Codes (GB)
```
Row 4: [Bezeichnung, Bis, bis 100 kg, bis 200 kg, ..., bis 24.000 kg]
Row 6+: [Preis pro Sendung, area_code_list_string, r1, r2, ...]
```
- "Bis" column contains space-separated area code lists like "DA, CV, LE, DY, WV, ..."
- UK PLZ → extract leading letters (e.g. "LE4 5GH" → "LE", "SW1A 1AA" → "SW")

### Type D: IT (two sub-tables)
```
Sub-table 1 — Bozen:
  Row 4: [Bezeichung, Plz, MM, bis 200 kg, bis 300 kg, ..., bis 24.000 kg]
  Row 6:  [Preis pro Sendung, "38 - 39", mm_value, r1, r2, ...]
  
Sub-table 2 — General Italy:
  Row 9:  "Auslastung : 250 kg pro cbm; 1.250 kg pro Ldm"
  Row 11: [Bezeichung, Plz, bis 150 kg, bis 200 kg, ..., bis 24.000 kg]
  Row 13+: [Preis pro Sendung, "00 - 06", r1, r2, ...]
```
- Bozen (38–39): factors 1500/300, bands start at bis 200 kg
- General IT: factors 1250/250, bands start at bis 150 kg
- PLZ lookup: first 2 digits → match "XX - YY" ranges

### Type E: Zone names + map (PT)
```
Row 4: [Bezeichnung, Zone, bis 50 kg, bis 100 kg, ..., bis 24.000 kg]
Row 6+: [Preis pro Sendung, Zone 1/2/3/4/5, r1, r2, ...]
Row 12: [Zone 1, "1000-2199;", "2500-2999;", ...]
Row 13: [Zone 2, ...]
...
```
- Zone map at rows 12–16 with semicolon-separated ranges per row
- Portuguese PLZ format: XXXX-YYY; use 4-digit prefix for zone lookup

### Type F: Zone names (IRL)
```
Row 4: [Bezeichnung, Zone, bis 50 kg, ...]
Row 6+: [Preis pro Sendung, county/city_name, r1, ...]
```
- Zones: Dublin, Cork, Gatway, Carlow, Cavan, Clare, Donegal, Kerry, Kildare, Kilkenny, Laois, Leitrim, Limerick, Longford, Louth, Mayo, Meath, Monaghan, Offaly, Roscommon, Sligo, Tipperary, Waterford, Westmeath, Wexford, Wicklow, Antrim, Armagh, Down, Fermanagh, Londonderry, Tyrone

## 5. Diesel Floater

File: `Herma Haftmaterial/2025/Dieselfloater 2024_2026.xlsx`
```
€1.68–1.77 → 0%  (neutral band)
€1.58–1.67 → -1%
€1.78–1.87 → +1%
... (±1% per €0.10 step)
```
- September 2025: diesel was in -1% band (confirmed by BI: Erlöse Diesel = -1% × Erlöse Fracht)
- `Erloese = Erlöse Fracht + Erlöse Diesel = Erlöse Fracht × (1 + diesel_pct)`

## 6. Kundenfaktor

- BI column `Kundenfaktor` = 1.34 for ALL HERMA rows
- This is PURELY an internal BI cost allocation factor (Kostenverteilung)
- NOT applied to DLV rates — do NOT multiply rates by 1.34

## 7. Validated Cases (Sep–Oct 2025)

| PLZ | Land | Versender | frpfl | billing_det | Erlöse Fracht | DLV Rate | Match |
|---|---|---|---|---|---|---|---|
| 08830 | ES | Haftmaterial | 1050 (LDM×1500) | ldm=0.7 | 194.25 | Zone1 bis1100 ohne/mit VL | ✓ 0.00% |
| 46410 | ES | Haftmaterial | 4800 (LDM×1500) | ldm=3.2 | 594.45 | Zone4 bis4800 mit VL | ✓ 0.00% |
| 31870 | ES | Etiketten/In | 4800 (LDM×1500) | ldm=3.2 | 507.65 | Zone4(31k) bis4800 mit VL | ✓ 0.00% |
| 08110 | ES | Haftmaterial | 1280.1 (Vol×300) | vol=4.27 | 211.10 | Zone1 bis1300 ohne/mit VL | ✓ 0.00% |
| 5162 | AT | Haftmaterial | 600 (LDM×1500) | ldm=0.4 | 67.90 | Zone1(1k-3039) bis600 2026 | ✓ 0.00% |

## 8. Edge Cases / NONE-matching rows

~5 rows (Verkehrsart="Charter International") have frpfl between ohne VL and mit VL rates.
These appear to be Charter/spot rates negotiated outside the BiddingMatrix.
The calculator returns `LookupError` for rates not found in tables (graceful skip).

## 9. Abrechnungsstrecken vs BI

- `Betrag` in Abrechnungsstrecken = `Erloese` in BI (includes diesel surcharge)
- `Erlöse Fracht` in BI = DLV base rate (flat per shipment)
- `Abrechnungsgewicht` ≈ `Tonnage (frpfl.)` (slight rounding differences observed)
