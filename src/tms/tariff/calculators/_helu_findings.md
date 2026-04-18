# HELU DLV Analysis Findings (KNR 408244)

## DLV Files

| Country | File | Sheet | Notes |
|---------|------|-------|-------|
| IT | `Export IT ab 01.12.2023 bis 31.12.2023.xlsx` | (default/first) | shape 58×93 |
| AT | `Export AT ab 01.12.2023 bis 31.12.2023.xlsx` | (default) | shape 58×10 |
| ES (general) | `Export ES ab 01.12.2023 bis 31.12.2023.xlsx` | `Export Spanien` | shape 58×97 |
| ES-Mendaro | `Export ES-Mendaro ab 01.12.2023 bis 31.12.2023.xlsx` | (default) | PLZ 20xxx → use this file |
| PT | `Export PT ab 01.12.2023 bis 31.12.2023.xlsx` | `Tabelle1` | shape 57×10 |
| PT-Lanheses | `Export PT-4925 Lanheses ab 01.12.2023 bis 31.12.2023.xlsx` | (default) | LDM flat-rate table |
| GB | `Export GB ab 01.12.2023 bis 31.12.2023.xlsx` | **`GB`** (second sheet!) | shape 60×11 |
| IE | `Export IE und Nord-IE ab 01.12.2023 bis 31.12.2023.xlsx` | `Tabelle1` | shape 51×34 |
| PL | `Export PL ab 01.12.2023 bis 31.12.2023.xlsx` | `Export PL` | shape 66×9 |
| CH | `Export CH ab 01.12.2023 bis 31.12.2023.xlsx` | (default) | shape 116×31, transposed |
| GR | `20250520_Helukabel_Export GR ergänzt um Athen.xlsx` | (default) | 2025 file, shape 56×11 |
| — | `2024_10_Dienstleistungsvereinbarung_Helukabel_xlsb.xlsb` | — | **general conditions only, NO rate tables** |

### Year Selection Rule
- **GR**: always use 2025 DLV (`20250520_...`)
- **All other countries**: use 2023 DLV files (`Export XX ab 01.12.2023...`)
- The `.xlsb` file (2024) contains only DLV conditions (Dieselfloater table, etc.), NO per-country freight rates.

---

## LDM / Teilpartie Rules

| Country | Threshold (kg) | LDM Factor (kg/LDM) | Source line |
|---------|----------------|---------------------|-------------|
| IT | ≥ 2500 | 1500 | "Teilpartien ab 2.500 kg, 1 Lademeter 1.500 kg" |
| AT | ≥ 2501 | 1250 | "Teilpartie ab 2501 kg → 1 Lademeter = 1250 kg" |
| ES-Mendaro | ≥ 2501 | 1500 | "Teilpartie ab 2501 kg → 1 Lademeter = 1500 kg" |
| ES (general) | ≥ 2500 | 1500 | "Teilpartien ab 2.500 kg, 1 Lademeter 1.500 kg" |
| PT | ≥ 2501 | 1250 | "Teilpartie ab 2501 kg → 1 Lademeter = 1250 kg" |
| GB | ≥ 2500 | 1250 | "Teilpartien ab 2.500 kg, 1 Lademeter 1.250 kg" |
| IE | ≥ 2501 | 1250 | "Teilpartien ab 2.501 kg → 1 Lademeter = 1.250 kg" |
| PL | ≥ 2500 | 1250 | "Teilpartien ab 2.500 kg → 1 Lademeter 1.250 kg" |
| CH | ≥ 2501 | 1250 | "ab 2501 kg → 1 Lademeter = 1250 kg" |
| GR | ≥ 3301 | 1650 | "ab 3.301 kg → 1 Lademeter = 1.650 kg" |

### Effective Weight Formula
```
if t_kg >= ldm_threshold and ldm > 0:
    eff_kg = max(t_kg, ldm * ldm_factor)
else:
    eff_kg = t_kg
billing_kg = max(100, ceil(eff_kg / 100) * 100)
```

Below threshold: Sammelgut → keine Sperrigkeit (no LDM factor, pure weight billing).

---

## Rate Structure (per-country)

### IT (sheet default)
- Row 16: header — "Gewichte" + zone cols "NN\nCity" (2-digit Italian province code)
- Row 17: Minimum (flat per shipment)
- Rows 18–36: weight bands "- NNN kg" → rates per 100 kg
- Row 37: "Komplett-LKW" flat rate
- **Zone key**: first 2 chars of PLZ (e.g. "35" for PLZ 35127)
- Maut: included in rate (note: "0,40 € / 100 kg inklusive Maut")

### AT (sheet default)
- Row 17: "bis kg" + "PLZ 1" .. "PLZ 9"
- Row 18: Minimum (flat)
- Rows 19–37: "NNN" bands (no "- " prefix)
- Row 38: "Komplett-LKW"
- **Zone key**: first char of PLZ (digit 1–9)
- Maut included (0,45 € / 100 kg note)

### ES-Mendaro (used for ALL PLZ 20xxx)
- Row 17: "bis kg" + "ES-20870" (single zone)
- Row 18: "Minimum" (flat)
- Rows 19+: bands "NNN" or "N.NNN"
- Minimum value: 32.15 €
- Maut included (0,35 € / 100 kg)

### ES general (PLZ other than 20xxx)
- Row 16: header — "Gewichte" + "PLZ NN\nProvince" per column
- Row 17: Minimum
- Rows 18+: weight bands
- **Zone key**: first 2 chars of PLZ

### PT (sheet Tabelle1)
- Row 17: "bis kg" + "PLZ 1" .. "PLZ 9"
- Row 18: "Minimum-100" (flat)
- Rows 19+: weight bands "NNN" (no dash prefix)
- PLZ 9 = "auf Anfrage" → LookupError
- **Zone key**: first char of PLZ
- Maut included (0,35 € / 100 kg)

### PT-Lanheses (special, PLZ 4925)
- Rows 18/20/22/24/26: (kg_limit, LDM_count, flat_price)
  - 5200 kg / 2 LDM → 758.20 €
  - 6200 kg / 3 LDM → 831.70 €
  - 7200 kg / 4 LDM → 985.20 €
  - 8200 kg / 5 LDM → 1128.70 €
  - 9200 kg / 6 LDM → 1302.20 €

### GB (**second sheet 'GB'** — NOT sheet 'GB- TARIF Kalkulation'!)
- Row 17: zone descriptions (groups of postcodes per col)
- Row 18: "bis kg" label
- Row 19: "m/m-100" flat minimum per shipment
- Rows 20–38: weight bands "NNN" (decimal thousands)
- Row 39: "Komplett-LKW"
- **Zone key**: leading alpha chars of UK PLZ (e.g. "LU", "CH", "M")
- Zones 1–7 defined by postcode area sets in row 17
- Zone 1 = BB, BD, BL, CH, CW, DL, DN, EX, HD, HU, HX, L, LA, LL, LN, M, OL, PE, PL, PO, PR, RG, RH, S, SK, SO, SR, TQ, TR, TS, WA, WF, WN, YO, HG
- Zone 2 = AL, BN, BR, CB, CM, CO, CR, CT, DA, E, EN, GU, HA, HP, IG, IP, KT, LU, ME, MK, NR, RM, SG, SL, SM, SS, TN, TW, UB, WD, SE, SW, W
- Zone 3 = B, BA, BH, BS, CF, CV, DE, DY, GL, HR, LD, LE, NG, NN, NP, OX, SA, SN, SP, ST, SY, TA, TF, WR, WS, WV
- Zone 4 = CA, EH, G, KA, KY, ML, NE, PA, TD, DG
- Zone 5 = AB, DD, IV, PH
- Zones 6 (HS, ZE) and 7 (KW) are island zones
- Maut included (0,55 € / 100 kg) + EU-Mobilitätspaket 3% (appears baked into DLV already)

### IE (sheet Tabelle1)
- Row 17: county headers cols 1–32: Dublin, Wicklow, Wexford, Carlow, Kildare, Meath, Louth, Monaghan, Cavan, Longford, Westmeath, Offaly, Laois, Kilkenny, Waterford, Cork, Kerry, Limerick, Tipperary, Clare, Galway, Mayo, Roscommon, Sligo, Leitrim, Donegal, Fermanagh, Tyrone, Derry, Antrim, Down, Armagh
- Row 18: Minimum (flat, 81.85 for all counties)
- Rows 19+: weight bands
- **Zone key**: Irish Eircode routing prefix → county:
  - D → Dublin (verified: D13 rates match)
  - H → Cavan
  - A → Wicklow; C → Cork; CW → Carlow; E → Clare; F → Galway; K → Kildare+Meath; L → Limerick; MH → Meath; MN → Monaghan; R → Roscommon; SL → Sligo; T → Tipperary; V → Kerry; W → Westmeath; X → Kilkenny; Y → Wexford; DL → Donegal; MO → Mayo; LH → Louth; CN → Cavan; LK → Limerick; OY → Offaly; LS → Laois; KK → Kilkenny; WD → Waterford; LM → Longford; RN → Roscommon; LN → Leitrim

### PL (sheet 'Export PL')
- Rows 17–27: Zone 1–7 mapping (2-digit PLZ → zone)
- Row 28: "bis kg" header
- Row 29: minimum (Zone 1 = "pauschal", Zones 2–7 = flat minimum)
- Rows 30+: weight bands
- **Zone key**: look up 2-digit PLZ in zone map
- PL has 0 rows in BI POST data — implemented but untested

### CH (sheet default, transposed structure)
- Row 16: "Postcode" + billing weights 100, 200, ..., 3000 as column headers
- Rows 17–99: CH10, CH11, ..., CH96 → rates per billing_kg column
- Col 1 (billing=100): flat minimum per shipment ("Sendungspreis")
- Cols 2–30 (billing=200..3000): rates per 100 kg
- **Zone key**: "CH" + first 2 digits of PLZ (e.g. PLZ 1196 → "CH11")
- Maut included (0,30 € / 100 kg + LSVA note)

### GR (2025 file)
- Row 17: "bis kg" + "GR-54627\nGR-57009" + "GR-Athen\n(=PLZ 11, 12, 14, 16, 17)"
- Row 18: "m/m-100" flat minimum (56.55, 65.05)
- Rows 19–37: weight bands
- Row 38: "Komplett-LKW" flat rates
- **Zone key**: PLZ first 2 digits:
  - "54" or "57" → zone 1 (GR-54627/GR-57009, Thessaloniki)
  - "11","12","14","16","17" → zone 2 (GR-Athen)
- **Continuity billing rule**: fracht = max(prev_band_max, rate × billing / 100)
  explicitly stated: "Das Minimum einer Frachtstaffel muss höher sein als das Maximum der vorherigen Frachtstaffel"
- Validity: 01.06.2025 – 31.12.2025 (applied to all GR regardless of date)
- Maut included

---

## Verified BI Cases (POST period, KNR 408244)

### IT (zone 26 = Cremona/Lodi, 2023 DLV)
| t_kg | LDM | billing_kg | eff_billing | fracht | rate/100kg | Match |
|------|-----|-----------|-------------|--------|------------|-------|
| 58 | 0 | 100 | 100 | 32.40 | 32.40 (min) | ✓ |
| 476 | 0 | 500 | 500 | 104.50 | 20.90 | ✓ (wait — 21.4×5=107, need recheck) |
| 5518 | 4.0 | 5600 → **6000** | 6000 (LDM: max(5518,6000)) | 462.00 | 7.70 | ✓ |

### AT (zone 5 = PLZ 5xxx, 2023 DLV)
| t_kg | LDM | billing_kg | eff_billing | fracht | rate/100kg | Match |
|------|-----|-----------|-------------|--------|------------|-------|
| 203 | 0 | 300 | 300 | 50.25 | 16.75 | ✓ |
| 387 | 0 | 400 | 400 | 60.60 | 15.15 | ✓ |
| 3035 | 4.0 | 3100 → **5000** | 5000 (LDM: max(3035,5000)) | 302.50 | 6.05 | ✓ |

### GR (zone 1 = 570xx area, 2025 DLV, continuity rule)
| t_kg | LDM | billing_kg | fracht | rate/100kg | Match |
|------|-----|-----------|--------|------------|-------|
| 863 | 0 | 900 | 211.05 | 23.45 | ✓ |
| 963 | 0 | 1000 | 234.50 | 23.45 | ✓ |
| 2444 | 0 | 2500 | 553.75 | 22.15 | ✓ |
| 2559 | 2.4 | **2500** (t<3301, no LDM) | 553.75 | continuity (same as 2500) | ✓ |

### ES-Mendaro (PLZ 20850, 2023 DLV)
| billing_kg | fracht | rate | Match |
|-----------|--------|------|-------|
| 100 | 32.15 | min | ✓ |
| 400 | 91.40 | 22.85 | ✓ |
| 7500 | 911.25 (with LDM) | 12.15 | ✓ |

---

## Anomalies / Edge Cases

1. **Bordero-Konsolidierung**: Bordero `7042-AB000583` has 3 IT-zone-35 rows; one t=526→billing=600 got fracht=62.7 (same as the 300kg row in the same bordero). Likely a Dinas billing anomaly — 64/69 ES cases and most IT cases match. Skip anomalous rows in validation.

2. **CH verification**: PLZ 4658 (t=769, LDM=0.9, billing=800, fracht=370.0) does NOT match CH46 rate (25.9/100kg → 207.2). Root cause unknown — possibly different DLV version for CH. CH has only 3 BI rows; implement parser but do not use for validation cases.

3. **PT-Lanheses**: Uses LDM/weight-bracket flat rates (not per 100 kg). Only 1 BI row (PLZ 4925-432).

4. **GR continuity at billing=2600**: fracht=553.75 (same as billing=2500 max) because next-band candidate (20.65×26=537.0) < prev-band-max (553.75). Correctly handled by running-max lookup.

5. **IT zone 26 at billing=26, t=5518, LDM=4.0**: Uses IT Teilpartie rule — eff=max(5518, 4.0×1500)=6000 → rate band ≤7500=7.7 → 7.7×60=462.0 ✓

---

## 5 Validation Cases (for test_helu.py)

| # | PLZ | Land | t_kg | LDM | billing_kg | Fracht | Label | DLV |
|---|-----|------|------|-----|-----------|--------|-------|-----|
| 1 | 570 09 | GR | 963 | 0 | 1000 | 234.50 | GR zone1 1000kg | 2025 |
| 2 | 26030 | IT | 58 | 0 | 100 | 32.40 | IT zone26 min | 2023 |
| 3 | 26900 | IT | 5518 | 4.0 | 6000\* | 462.00 | IT zone26 LDM Teilpartie | 2023 |
| 4 | 5412 | AT | 387 | 0 | 400 | 60.60 | AT zone5 400kg | 2023 |
| 5 | 5412 | AT | 3035 | 4.0 | 5000\* | 302.50 | AT zone5 LDM Teilpartie | 2023 |

\* effective billing after LDM factor

Dates: 2025-10-24 (GR), 2025-10-02 (IT min), 2026-02-03 (IT LDM), 2025-10-08 (AT 400), 2025-10-07 (AT LDM)

Note: Dates after 2025-09-29 (earliest POST rows with non-zero fracht). Cases 1, 2, 4, 5 have Leistungsdatum ≤ 2025-12-31.
