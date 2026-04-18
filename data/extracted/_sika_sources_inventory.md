# Sika ATM — Quellen-Inventur

Generated: 2026-04-18  
Scope: ALL Sika-related files across `/home/user/TMS/data/extracted/`

---

## 1. SIKA Automotive DLV (KNRs 413276, 493163, 527406)

**Path:** `v1/Noerpel AI/SIka/DLV/SIKA Automotive/`

### 1.1 Anlage 1 — Tarifblätter (4 Versionen)

| Label | Filename | Size (B) | MD5 |
|---|---|---|---|
| **root-v1** | `Anlage 1_Sika ATM_ERKA_Sonderleistungen_Tarifblätter_HH_u. Roman. ex. LSU M7_1.7.2024 bis 30.06.2026.xlsx` | 563,871 | `fb2952fd505a7c71918b78c3dd707d27` |
| **root-v2** | `20250728_Anlage 1_Sika ATM_ERKA_Sonderleistungen_Tarifblätter_HH_u. Roman. ex. LSU M7_01.07.2024 bis 30.06.2026.xlsx` | 568,756 | `3443f65d4b1cad63b725b4c313cf5e0c` |
| **2025-v1** | `2025/20250115_Anlage 1_Sika ATM_ERKA_Sonderleistungen_Tarifblätter_HH_u. Roman. ex. LSU M7_01.07.2024 bis 30.06.2026.xlsx` | 565,072 | `811f57c74adcb12011ee14c3ee2f9c8e` |
| **KORRIGIERT** ★ | `2025/20250728_Anlage 1_Sika ATM_ERKA_Sonderleistungen_Tarifblätter_HH_u. Roman. ex. LSU M7_01.07.2024 bis 30.06.2026_KORRIGIERT.xlsx` | 569,313 | `bb5301f98b28a90b44a726e9ecced05e` |

★ **KORRIGIERT is the canonical version** — confirmed by exact match of 4 independent POST-period billing rows in Abrechnungsstrecken.

All 4 versions have **distinct MD5 hashes** (all different content). All 4 share the same 22-sheet structure. Key difference between versions: rate corrections in the per-country Tarif sheets (rates are not identical across versions). The KORRIGIERT version (latest, dated 2025-07-28, largest at 569 kB) is used for billing.

**CH rates are ALL ZERO in all 4 versions.** No ERKA rates exist for DE→CH destinations.

### 1.2 Anlage 2 — Laufzeiten & Thermozuschläge

| Filename | Size (B) | MD5 |
|---|---|---|
| `Anlage 2_ERKA_Sika ATM Laufzeiten und Thermozuschläge_1.7.2024 bis 30.06.2026.xlsx` | 456,431 | `600a390c8227823f323241a01c7acfa0` |
| `2025/20240626_Anlage 2_ERKA_Sika ATM Laufzeiten und Thermozuschläge_1.7.2024 bis 30.06.2026.xlsx` | 456,965 | `4a7a28aae7dccc4dbb97f11e7fa1e21e` |

### 1.3 DLV-Rahmenvertrag

| Filename | Size (B) | MD5 | Format |
|---|---|---|---|
| `2024_10_Dienstleistungsvereinbarung_SIKA Automotive-.xlsb` | 179,765 | `de8c985d7dc0b6f3e1fa25c91c5fe0c1` | xlsb (not xlsx) |

Sheets: Kundenstammdaten, Stammdaten NL, Anschreiben, DLV nat+int, Ergänzung int., Zollabwicklung, Rückantwortfax Versicherung, Bestätigung Compliance, Dieselfloater ERKA V 2.  
Readable only with `pyxlsb` (openpyxl does not support .xlsb). Contains contractual metadata, not rate data.

### 1.4 2026 Upload-Dateien (FRA-System)

**Path:** `v1/Noerpel AI/SIka/DLV/SIKA Automotive/2026/Upload/`

9 per-country files in FRA-upload format (`V_FRA_7042_O_{CC}_ALL_Sika_Automotive.xlsx`):

| Country | Size (B) |
|---|---|
| AT | 48,287 |
| BE | 42,959 |
| ES | 41,699 |
| FR | 61,827 |
| GB | 66,575 |
| IT | 67,985 |
| NL | 43,598 |
| PT | 39,650 |
| RS | 22,277 |

**No CH file** in 2026 Upload (consistent with zero CH rates in Anlage 1).

**Important:** 2026 Upload files have different rates from Anlage 1 KORRIGIERT (example IT-00/IT0 band-0: 60.2 in KORRIGIERT vs 62.91 in 2026 Upload). These are FRA-system upload files and do **NOT** match actual billing amounts. Do not use for calculator.

Zone format difference: Anlage 1 uses `IT-00`, `IT-01` etc.; 2026 Upload uses `IT0`, `IT1` etc.

### 1.5 Email

| Filename | Size (B) |
|---|---|
| `2026/ERKA Kunden - Preiserhöhung.msg` | 513,024 |

---

## 2. SIKA Deutschland GmbH Stuttgart DLV (KNRs 491063, 511241)

**Path:** `v1/Noerpel AI/SIka/DLV/SIKA Deutschland GmbH Stuttgart/`

| Filename | Size (B) | Notes |
|---|---|---|
| `2024_10_Dienstleistungsvereinbarung_SIKA.xlsb` | 172,719 | DLV contract (xlsb) |
| `SIKA DE - SSC 2023.xlsx` | 91,204 | Stellplatz tariff 2023 |
| `20241016 SIKA DE - SSC 2023_2024, um ES-19 und GB-WR ergänzt.xlsx` | 88,438 | Updated 2023/2024 tariff |
| `update_Sika Deutschland & Supply_Differenz-Mauttabelle ab Dez 2023.xlsx` | 70,316 | Maut diff table |
| `Tarife Sika Stuttgart.msg` | 788,480 | Email |
| `2025/20250109_SIKA DE & SSC Export div. LKZ_Stellplatzofferte.xlsx` | 628,179 | Stellplatz 2025 |
| `2025/20250109_Sika Supply_Import Spanien und Italien 2025.xlsx` | 555,406 | Import ES/IT 2025 |
| `2026/20251216_SIKA DE & SSC Export div. LKZ_Stellplatzofferte_2026.xlsx` | 642,887 | Stellplatz 2026 v1 |
| `2026/20260211_SIKA DE & SSC Export div. LKZ_Stellplatzofferte_2026.xlsx` | 642,051 | Stellplatz 2026 v2 |
| `2026/20251216_Sika Supply_Import Spanien und Italien 2026.xlsx` | 558,600 | Import ES/IT 2026 |
| `2026/Upload/V_FRA_7042_I_ES_ALL_Sika.xlsx` | 538,369 | FRA upload import ES |
| `2026/Upload/V_FRA_7042_I_IT_ALL_Sika.xlsx` | 538,107 | FRA upload import IT |
| `2026/Upload/V_FRA_7042_O_ES_ALL_Sika.xlsx` | 37,889 | FRA upload export ES |
| `2026/Upload/V_FRA_7042_O_GB_ALL_Sika.xlsx` | 41,271 | FRA upload export GB |
| `2026/Upload/V_FRA_7042_O_IE_ALL_Sika.xlsx` | 35,673 | FRA upload export IE |
| `2026/Upload/V_FRA_7042_O_IT_ALL_Sika.xlsx` | 40,161 | FRA upload export IT |
| `2026/Upload/V_FRA_7042_O_PT_ALL_Sika.xlsx` | 39,689 | FRA upload export PT |

**No CH-destination files** in Deutschland GmbH Stuttgart folder either.

---

## 3. Sika Rechnungen (Invoices)

**Path:** `v1/Noerpel AI/SIka/Rechnungen/Rechnungen AX/`

- **300 PDF invoices**
- Date range: 18.11.2019 – 21.02.2026
- Naming: `Rechnung - {ID} - {DD.MM.YYYY}.PDF`
- Size: ~80–200 kB per file

---

## 4. Sika Nebenbedingungen DINAS

**Path:** `v1/Noerpel AI/SIka/Nebenbedingungen DINAS/`

| Filename | Size (B) |
|---|---|
| `NK Sika.xlsx` | 492,269 |
| `~$NK Geze.xlsx` | 12,289 (temp file) |

---

## 5. Dinas SSC Rechnungen (PRE-period billing)

**Path:** `sika_ssc/Dinas SSC/`

- **107 PDF invoices**
- Date range: 2025-01-06 – 2025-08-27 (PRE period, before 2025-09-26 AX migration)
- Naming: `RECHNUNG{ID}.pdf`
- Size: ~103–212 kB per file
- **These are the primary source for ≤26.9.2025 validation cases** (PRE period)

---

## 6. Abrechnungsstrecken / Dinas Billing Records

**Path:** `abrechnungsstrecken/Abrechnungsstrecken/Sika.xlsx`  
**Size:** 597,504 B | **Modified:** 2026-04-17

- **3,590 rows** (POST period only: 2025-10-02 – 2026-04-17)
- 36 columns including: Abrechnungsgewicht, Betrag, Währung, Auftragsnummer, Kontonummer, Nach Land
- **No PLZ column** — use Auftragsnummer to join with BI data for PLZ lookup

| Kontonummer | Rows | Non-zero Betrag | Notes |
|---|---|---|---|
| `413276` | 89 | **0** | All betrag=0; sub-entity, billing rolls up elsewhere |
| `493163` | **0** | 0 | Completely absent from POST-period data |
| `527406` | 464 | 387 | Active billing; DE→IT/GB/ES/RS/PT; all EUR |
| `491063` | (mixed) | — | Sika Deutschland |
| `511241` | (mixed) | — | SIKA SUPPLY CENTER AG |
| `ARA_Sika_DE+CH` | 1,504 | 807 | Consolidated DE+CH group; IE/PT/ES/GB/IT |
| `ARA1802357` | — | — | Another ARA group |
| `529453` | — | — | Unknown entity |

---

## 7. Duplicate / Version Analysis Summary

| File type | Versions | All distinct? | Canonical |
|---|---|---|---|
| Anlage 1 | 4 | Yes (all 4 MD5 differ) | KORRIGIERT (bb5301f9) |
| Anlage 2 | 2 | Yes | `20240626_` version |
| DLV contract | 1 | — | `2024_10_...xlsb` |
| 2026 Upload | 9 per-country | — | **Not used for billing** |

---

## 8. Files NOT Found

- No CH-destination rate file for any Sika entity (Anlage 1 CH sheet = all zeros; no `V_FRA_7042_O_CH_*` file)
- No 2025-specific Anlage 1 for KNR 527406 vs 413276 distinction — both use the same Anlage 1 KORRIGIERT
- No per-KNR rate file — all 3 ATM KNRs use one shared Anlage 1
