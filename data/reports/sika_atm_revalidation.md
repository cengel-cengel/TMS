# SikaATM Re-Validation Report

Generated: 2026-04-19  
Total rows evaluated: 1111  
Match threshold: ±2.0%  
Note: DLV Anlage 1 rates apply to direct (Einzelsendung) shipments only.
      Groupage (Sammelladung) invoices are classified separately.

## Summary Table (Direct Shipments Only)

| ERKA | N total | Groupage | N direct | Match | Deviation | No Weight | LookupErr | Not Nominated | Match % (direct excl. not-nom) |
|------|---------|----------|----------|-------|-----------|-----------|-----------|---------------|-------------------------------|
| 18894 (De) | 695 | 544 | 151 | 144 | 4 | 0 | 3 | 3 | 97.3% |
| 18748 (CH) | 416 | 310 | 106 | 81 | 25 | 0 | 0 | 0 | 76.4% |

## Classification Details (Direct Only)

### ERKA 18894 (SikaATMDeCalculator)

- **match**: 144 (95.4%)
- **deviation**: 4 (2.6%)
- **lookup_error**: 3 (2.0%)

  Deviations by empf_land:
  - RS: 2 rows, avg dev=+24.9%
  - PT: 1 rows, avg dev=-73.7%
  - IT: 1 rows, avg dev=-2.3%

  LookupError sample (up to 5):
  - PLZ=70499 land=DE → SikaATM: ERKA not nominated for 'DE'. All DLV rates = 0. No pricing available.
  - PLZ=70499 land=DE → SikaATM: ERKA not nominated for 'DE'. All DLV rates = 0. No pricing available.
  - PLZ=70499 land=DE → SikaATM: ERKA not nominated for 'DE'. All DLV rates = 0. No pricing available.

### ERKA 18748 (SikaATMChCalculator)

- **match**: 81 (76.4%)
- **deviation**: 25 (23.6%)

  Deviations by empf_land:
  - RS: 23 rows, avg dev=+24.8%
  - IT: 2 rows, avg dev=-17.5%

## Top 10 Absolute Deviations (Direct Only)

| Sendnr | ERKA | Land | PLZ | weight_kg | fracht_ist | soll | dev_pct% |
|--------|------|------|-----|-----------|------------|------|---------|
| 32882334 | 18894 | PT | 2951-510 | 2750 | 2975.00 | 782.35 | -73.7% |
| 32875408 | 18748 | RS | 34104 | 1777 | 565.00 | 806.00 | +42.7% |
| 32915977 | 18748 | RS | 34104 | 1666 | 565.00 | 806.00 | +42.7% |
| 32904679 | 18748 | RS | 34104 | 666 | 485.00 | 656.00 | +35.3% |
| 32850738 | 18748 | IT | 80038 | 1696 | 523.70 | 381.10 | -27.2% |
| 32892827 | 18748 | RS | 34104 | 2425 | 815.00 | 1019.00 | +25.0% |
| 32841317 | 18748 | RS | 34104 | 1382 | 565.00 | 706.00 | +25.0% |
| 32847296 | 18748 | RS | 34104 | 1221 | 565.00 | 706.00 | +25.0% |
| 32859025 | 18748 | RS | 34104 | 863 | 525.00 | 656.00 | +25.0% |
| 32870237 | 18748 | RS | 34104 | 863 | 525.00 | 656.00 | +25.0% |

## RS Serbia Analysis

Both calculators show a systematic pattern for RS/34104 (Kragujevac):
- DLV Anlage 1 rates are consistently **+20–43% higher** than Dinas invoiced amounts.
- All RS rows share the same PLZ (34104) and same flat-rate pattern.
- Dinas amounts (485, 525, 565, 645, 815, 895 EUR) do not correspond to any DLV band.
- Hypothesis: Serbia routes follow a separately negotiated rate agreement not captured in Anlage 1 KORRIGIERT.

| Weight band | DLV rate (RS-34) | Dinas IST | Deviation |
|-------------|-----------------|-----------|-----------|
| ≤601 kg     | 606 EUR         | 485 EUR   | +25.0%    |
| ≤801 kg     | 656 EUR         | 525 EUR   | +25.0%    |
| ≤1201 kg    | 656 EUR         | 565 EUR   | +16.1%    |
| ≤1401 kg    | 706 EUR         | 565 EUR   | +25.0%    |
| ≤1801 kg    | 806 EUR         | 565 EUR   | +42.7%    |
| ≤2501 kg    | 1019 EUR        | 815 EUR   | +25.0%    |

**Match % excl. RS (direct only):**
- ERKA 18894: 144 / (144 + 2) = **98.6%** ✓
- ERKA 18748: 81 / (81 + 2) = **97.6%** ✓

## Known Gaps

- **Groupage**: 854 rows from Sammelladung invoices (identified by 'zusammengefasst' in PDF). DLV Anlage 1 does not apply; separate rate structure.
- **no_weight**: PDF weight extraction failed (section pattern not matched).
- **not_nominated**: DE/CH destination — ERKA not nominated per DLV; expected LookupError.
- **real_lookup**: Zone not found in tariff sheet (PLZ prefix not configured).

## Deviation Histogram (Direct Only)

| Bucket | Count |
|--------|-------|
| ≤-20% | 2 |
| -20..-10% | 0 |
| -10..-5% | 1 |
| -5..-2% | 1 |
| -2..0% | 0 |
| 0..+2% | 225 |
| +2..+5% | 0 |
| +5..+10% | 2 |
| +10..+20% | 2 |
| >+20% | 21 |
