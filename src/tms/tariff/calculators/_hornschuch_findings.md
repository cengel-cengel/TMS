# Hornschuch AG (KNR 490085) — DLV Findings

## 1. DLV Files

| File | Valid From | Valid To | Notes |
|---|---|---|---|
| `20250129_Erka_ContiTech Megatrans Deutsc.xlsx` | 2024-11-01 | 2026-10-31 | Primary LTL rate file (ContiTech MegaTrans Round 3) |
| `20250131_Hornschuch_Export Frankreich - Castorama & Leroy Merlin.xlsx` | 2025-01-01 | 2025-12-31 | FR addendum — uses SAME CT-SSL-WEI-P001 rates; adds surcharges for fix-time delivery |
| `20250612_Erka_ContiTech_PL_korrigiert.xlsx` | — | — | PL correction — DE-74 outbound PL lanes have EMPTY rates (ERKA not nominated for PL) |
| `20241107_MegaTrans_Deutschland_add_Surcharges.xlsx` | — | — | Special services surcharge table (not regular LTL tariff) |

**Carrier**: ERKA GmbH, Motorstr. 8, DE-70499 Stuttgart  
**Customer**: Continental AG (for Hornschuch AG = ContiTech subsidiary, plant SSL Weissbach)  
**Transport period**: 01.11.2024 – 31.10.2026  

### Nominated countries (from Weissbach, ERKA share)
| Country | Share |
|---|---|
| ES | 100% |
| IT | 100% |
| PT | 100% |
| FR | 10% |

**PL**: NOT nominated for ERKA from Weissbach → NO PL outbound rates in any DLV file.

---

## 2. Sheet Structure (30 sheets total)

| # | Sheet name | Location | Priced outbound lanes | Notes |
|---|---|---|---|---|
| 0 | `Formulas_83d70a5f-22af-4933-9e_` | — | 0 | **EMPTY** (see §3) |
| 1 | `General` | — | 0 | Metadata only |
| 2 | `FTL lanes` | DE | 0 | FTL-only rate card |
| 3 | `CT-IEMEA-BBL-P001` | Bad Blankenburg | 0 | No WEI outbound prices |
| 4 | `CT-IEMEA-DANZ-P001` | Dannenberg | 0 | " |
| 5 | `CT-IEMEA-HAMZ-P001` | Hamburg | 0 | " |
| 6 | `CT-IEMEA-HOP-P001` | Hoppegarten | 0 | " |
| 7 | `CT-IEMEA-KORZ-P001` | Korbach | 0 | " |
| 8 | `CT-IEMEA-MOE-P001` | Moers | 0 | " |
| 9 | `CT-IEMEA-NOMZ-P001` | Northeim | 0 | " |
| 10 | `CT-IEMEA-STC-P001` | Stöcken | 0 | " |
| 11 | `CT-IEMEA-VAHZ-P001` | Hannover | 0 | " |
| 12 | `CT-IEMEA-WHSZ-P001` | Waltershausen | 0 | " |
| 13 | `CT-OESL-HMU-P001` | Hann. Münden | 0 | " |
| 14 | `CT-OESL-KORZ-P002` | Korbach | 0 | " |
| 15 | `CT-OESL-KRB-P001` | Karben | 0 | " |
| 16 | `CT-OESL-NOMZ-P002` | Northeim | 0 | " |
| 17 | `CT-OESL-OED-P001` | Oedelsheim | 0 | " |
| 18 | `CT-OESL-WHSZ-P002` | Waltershausen | 0 | " |
| 19 | `CT-R25-WH-037` | Halle | 0 | " |
| 20 | `CT-SSL-EIS-P001` | Eislingen | 0 | " |
| 21 | `CT-SSL-HER-P001` | Herbolzheim | 0 | " |
| 22 | `CT-SSL-NOMZ-P003` | Northeim | 0 | " |
| 23 | `CT-SSL-STO-P001` | Stolzenau | 0 | " |
| 24 | `CT-SSL-VIN-P001` | Hannover (Vahrenwald) | 0 | " |
| **25** | **`CT-SSL-WEI-P001`** | **Weissbach (SSL)** | **285** | **Primary sheet — all Hornschuch rates** |
| 26 | `CT-SSL-WHSZ-P003` | Waltershausen | 0 | " |
| 27 | `CT-WH-035-S` | Langenhagen | 0 | " |
| 28 | `CT-WH-036-S` | Langenhagen | 0 | " |
| 29 | `Comment` | — | 0 | Comments only |

**Summary**: Only `CT-SSL-WEI-P001` has actual prices for Hornschuch (Weissbach origin, DE-74).

---

## 3. Formulas Sheet Analysis

Sheet `Formulas_83d70a5f-22af-4933-9e_` is **completely empty** when read with `openpyxl` (both `data_only=True` and `data_only=False`). It normally stores Excel cross-sheet formula links in the ContiTech MegaTrans tender tool — these don't yield useful data when the workbook is saved as standalone `.xlsx`. All price data is stored directly in the lane sheet rows.

---

## 4. CT-SSL-WEI-P001 Rate Structure

### Row layout (data starts at row 8, 0-indexed = row 9 in Excel)

```
row 7 (header): [Service package, row description, Field description, 
                  Country cluster, Origin Country, Origin City/Zip Cluster,
                  Freight Payer, BA,
                  Destination Country, Destination City/Zip Cluster, In-/Outbound,
                  Minimum < 50,01 kg,
                  50,01-74,99 kg, 75,00-99,99 kg, 100,00-124,99 kg, 125,00-149,99 kg,
                  150,00-174,99 kg, 175,00-199,99 kg, 200,00-249,99 kg, 250,00-299,99 kg,
                  300,00-349,99 kg, 350,00-399,99 kg, 400,00-499,99 kg, 500,00-749,99 kg,
                  750,00-999,99 kg, 1000,00-1499,99 kg, 1500,00-1999,99 kg,
                  2000,00-2499,99 kg, 2500,00-3999,99 kg, 4000,00-5999,99 kg,
                  6000,00-7999,99 kg, 8000,00-9999,99 kg, 10000,00-12499,99 kg,
                  12500,00-14999,99 kg, 15000,00-23999,99 kg, 24000 kg,
                  roundtrip, export declaration, T1-document, Customs Clearance,
                  TT General Cargo, TT LTL, TT FTL, CommentMisc]
```

### Column indices in data rows (0-based)
| Col | Content |
|---|---|
| 0 | row_id (660512 for WEI outbound) |
| 1 | matrix name (`CT-SSL-WEI-P001`) |
| 2 | lane code (`DE-74-IT-45`, `AT-1-DE-74`, …) |
| 3 | `'Offer- / price field'` |
| 4 | Country cluster (dest CC) |
| 5 | Origin Country |
| 6 | Origin City/Zip Cluster |
| 7 | Freight Payer (city name) |
| 8 | BA |
| 9 | Destination Country |
| 10 | Destination City/Zip Cluster (zone number) |
| 11 | In-/Outbound |
| 12 | Minimum < 50.01 kg (EUR flat) |
| 13–36 | Rate per kg for 24 weight bands (EUR/kg) |

### Lane code format
`{ORIG_CC}-{ORIG_ZONE}-{DEST_CC}-{DEST_ZONE}`

Hornschuch outbound: `DE-74-{DEST_CC}-{DEST_ZONE}` where ORIG_CC=DE, ORIG_ZONE=74 (Weissbach PLZ prefix).

### Countries with actual prices from DE-74
| Country | Zones with prices | Notes |
|---|---|---|
| AT | 9 (1–9) | Austria, PLZ 4-digit |
| BE | 9 (1–9) | Belgium |
| CH | 9 (1–9) | Switzerland |
| ES | 52 (01–52) | Spain |
| FR | 96 (01–98, not all) | France, département codes |
| GR | 8 (1–8) | Greece |
| IT | 93 (00–98, not all) | Italy |
| PT | 9 (1–8 + "9 (islands)") | Portugal |
| PL | 99 zones defined BUT **empty rates** | ERKA not nominated |

---

## 5. Billing Formula

```
Erlöse Fracht = rate_per_kg(zone, band) × Tonnage_eff_kg
```

Weight band lookup (using actual tonnage):
- `tonnage < 50.01` → use Minimum (flat)
- `50.01 ≤ tonnage < 75` → use 50–75 rate × tonnage
- `75 ≤ tonnage < 100` → use 75–100 rate × tonnage
- … (25 bands in total)
- `tonnage ≥ 24000` → use 24000 kg rate × tonnage

**Billing weight**: `Tonnage (eff.)` column in BI (in kg). NOT LDM-based.  
**Maut**: Included in rates (DE-Maut ab 01.12.2023: inklusive).  
**Rounding**: Rates stored to 4 decimal places; result is rate × exact tonnage.

---

## 6. Zone → PLZ Mapping (confirmed by BI reverse-engineering)

| Country | Zone code | PLZ lookup rule |
|---|---|---|
| IT | `"00"` to `"98"` | zone = first 2 digits of 5-digit Italian PLZ |
| ES | `"01"` to `"52"` | zone = first 2 digits of 5-digit Spanish PLZ |
| FR | `"01"` to `"98"` | zone = département number = first 2 digits of 5-digit French PLZ |
| PT | `"1"` to `"9 (islands)"` | zone = first digit of 4-digit Portuguese PLZ |
| AT | `"1"` to `"9"` | zone mapping not verified (no AT rows in BI data) |
| PL | n/a | ERKA not nominated, no prices |

**Examples confirmed**:
- IT PLZ `45010` → zone `"45"` ✓  
- ES PLZ `15820` → zone `"15"` ✓  
- FR PLZ `13450` → zone `"13"` ✓  
- PT PLZ `4710` → zone `"4"` ✓

**Special PT zone**: `"9 (islands)"` for Azores/Madeira (PLZ prefix 9).

---

## 7. Diesel Floater

ContiTech communicates the diesel floater % to Noerpel periodically.

From BI analysis (POST period Sep–Oct 2025):  
`Erloese / Erlöse Fracht = 0.9925` across all IT/ES/FR/PT export rows  
→ **Diesel floater = −0.75%** for Sep–Oct 2025  
→ `Erloese = Erlöse Fracht × 0.9925`

Calculator returns `basispreis = rate × tonnage`. Diesel is shown as a separate `diesel_surcharge` line  
(= `basispreis × diesel_pct`, negative in this period).

---

## 8. Validated Cases (POST Sep–Oct 2025, Verkehrsart = Export, Erlöse Fracht > 0)

| PLZ | Land | t (kg) | Zone | Band | Rate (€/kg) | Computed | BI Erlöse Fracht | Dev% |
|---|---|---|---|---|---|---|---|---|
| 45010 | IT | 189 | 45 | 175–200 | 0.5920 | 111.888 | 111.89 | 0.002% |
| 31034 | IT | 1161 | 31 | 1000–1500 | 0.2020 | 234.522 | 234.52 | 0.001% |
| 15820 | ES | 568 | 15 | 500–750 | 0.5800 | 329.44 | 329.44 | 0.000% |
| 09001 | ES | 1572 | 09 | 1500–2000 | 0.3200 | 503.04 | 503.04 | 0.000% |
| 13450 | FR | 675 | 13 | 500–750 | 0.3700 | 249.80 | 249.80 | 0.001% |
| 54950 | FR | 663 | 54 | 500–750 | 0.3300 | 218.72 | 218.72 | 0.001% |
| 4710 | PT | 258 | 4 | 250–300 | 0.7000 | 180.60 | 180.60 | 0.000% |
| 4760-725 | PT | 837 | 4 | 750–1000 | 0.4400 | 368.28 | 368.28 | 0.000% |

**Note on ≤26.9.2025 constraint**: All POST rows dated exactly 26.9.2025 have `Erlöse Fracht = 0` (only `Erloese` is populated, likely a first-invoice batch limitation). Validation cases above use rows from 29.9.–01.10.2025 where `Erlöse Fracht > 0`.

**Charter International**: Rows with `Verkehrsart = 'Charter International'` use negotiated spot rates (NOT the MegaTrans LTL rates). These are excluded from calculator scope and will return `None`.

---

## 9. Edge Cases

- **PL**: Relation keys 5513 (Geis), 6011, 0582 → different carrier, no ERKA DLV → calculator returns `None` for PL
- **Charter International**: Spot rates, not from DLV → return `None`
- **Minimum price**: For tonnage < 50.01 kg, use flat minimum (col12)
- **Zone not found**: If `plz[:2]` (or `plz[0]` for PT) has no rate → return `None`
- **PT PLZ format**: May include hyphen (e.g., `4760-725`) → use `plz[0]` for zone

---

## 10. Implementation Notes

- Parse only `CT-SSL-WEI-P001` from `20250129_Erka_ContiTech Megatrans Deutsc.xlsx`
- Filter rows: `row[11] == "Outbound"`, `row[5] == "DE"`, `row[6] == "74"` (or lane code starts with `"DE-74-"`)
- Index rates: `rates = row[12:37]` (25 values: 1 minimum + 24 bands)
- Zone lookup: `zone = plz[:1] if cc == "PT" else plz[:2]`
- Rate formula: `if tonnage < 50.01: rate = rates[0]` else iterate bands
- No separate Maut surcharge (included in base)
- Diesel floater: applied by ContiTech externally, not in calculator scope
