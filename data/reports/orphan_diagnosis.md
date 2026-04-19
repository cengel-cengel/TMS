# Etappe 8c — Orphan-Familien-Diagnose

**Stand:** 2026-04-19  
**Quelle:** `output/etappe8_cluster_families.parquet`  
**Scope:** TMS-Migrationsprüfung Dinas PRE → AX POST  

## Zusammenfassung

### Orphan-Familien nach Seite

| | AX-Orphans | Dinas-Orphans | Gesamt |
|---|---|---|---|
| Anzahl Familien | 41 | 36 | 77 |
| Gesamt-Fracht | 227,483.65 € | 1,558,190.87 € | 1,785,674.52 € |

### Diagnose-Verteilung (alle Orphan-Familien)

| Diagnose | AX-Orphans | Dinas-Orphans | Gesamt |
|---------|-----------|--------------|--------|
| Tarifgruppen-Mismatch | 0 | 0 | 0 |
| PLZ-Präzisions-Mismatch | 10 | 13 | 23 |
| Echter Route-Orphan | 31 | 23 | 54 |
| **Gesamt** | **41** | **36** | **77** |

---

## Orphan-AX Stichprobe (Top 10 nach Fracht)

#### `511241|||ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 511241 |
| Abs.-PLZ 2-stellig   |  |
| Empf.-PLZ 2-stellig  |  |
| Tarifgruppe          | ssc_stellplatz |
| Gesamt-Fracht        | 38,485.20 € |
| Cluster-Anzahl       | 11 |

**Cluster auf AX-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2026-03-31 | 469495 | 3,593.20 € | – | – |
| 2026-04-01 | 473977 | 3,319.00 € | – | – |
| 2026-04-02 | 478156 | 3,319.00 € | – | – |
| 2026-04-03 | 483196 | 3,319.00 € | – | – |
| 2026-04-07 | 483192 | 3,319.00 € | – | – |
| 2026-04-08 | 487444 | 3,319.00 € | – | – |
| 2026-04-09 | 491938 | 3,319.00 € | – | – |
| 2026-04-10 | 496074 | 3,319.00 € | – | – |
| 2026-04-13 | 501371 | 3,319.00 € | – | – |
| 2026-04-15 | 509853 | 5,021.00 € | – | – |
| 2026-04-16 | 514195 | 3,319.00 € | – | – |

**Near-Match-Suche auf Dinas-Seite:**

> **Echter Route-Orphan** – Lane nur in AX-Ära vorhanden; keine ähnliche Familie in Dinas gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in AX-Ära vorhanden

---

#### `491063|70|19|sika_de_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 491063 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | 19 |
| Tarifgruppe          | sika_de_stellplatz |
| Gesamt-Fracht        | 37,604.13 € |
| Cluster-Anzahl       | 46 |

**Cluster auf AX-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-10-02 | 7622 | 0.00 € | 18.00 | – |
| 2025-10-02 | 282707 | 1,035.04 € | 15.00 | 69.0027 |
| 2025-10-14 | 40712 | 0.00 € | 21.00 | – |
| 2025-10-17 | 51596 | 0.00 € | 16.00 | – |
| 2025-10-21 | 59203 | 0.00 € | 17.00 | – |
| 2025-10-21 | 282731 | 629.30 € | 7.00 | 89.9000 |
| 2025-10-24 | 66824 | 0.00 € | 28.00 | – |
| 2025-10-28 | 73373 | 0.00 € | 17.00 | – |
| 2025-11-04 | 92293 | 0.00 € | 18.00 | – |
| 2025-11-04 | 286506 | 629.30 € | 7.00 | 89.9000 |
| 2025-11-07 | 102206 | 0.00 € | 13.00 | – |
| 2025-11-11 | 109092 | 0.00 € | 34.00 | – |
| 2025-11-14 | 119773 | 0.00 € | 13.00 | – |
| 2025-11-14 | 286521 | 749.13 € | 9.00 | 83.2367 |
| 2025-11-21 | 141907 | 0.00 € | 32.00 | – |
| 2025-11-24 | 127832 | 0.00 € | 22.00 | – |
| 2025-11-25 | 286594 | 1,483.19 € | 20.00 | 74.1595 |
| 2025-11-25 | 145109 | 0.00 € | 22.00 | – |
| 2025-11-28 | 154932 | 0.00 € | 32.00 | – |
| 2025-11-28 | 155010 | 0.00 € | 21.00 | – |
| 2025-12-02 | 286681 | 543.94 € | 6.00 | 90.6567 |
| 2025-12-02 | 169816 | 0.00 € | 6.00 | – |
| 2025-12-09 | 187982 | 0.00 € | 12.00 | – |
| 2025-12-09 | 182102 | 0.00 € | 26.00 | – |
| 2025-12-09 | 286692 | 1,869.24 € | 26.00 | 71.8938 |
| 2025-12-09 | 286698 | 1,025.91 € | 12.00 | 85.4925 |
| 2025-12-12 | 286703 | 691.66 € | 8.00 | 86.4575 |
| 2025-12-12 | 199435 | 0.00 € | 8.00 | – |
| 2026-01-13 | 227735 | 1,073.84 € | 13.00 | 82.6031 |
| 2026-01-16 | 245448 | 1,475.29 € | 17.00 | 86.7818 |
| 2026-01-20 | 249388 | 1,276.81 € | 16.00 | 79.8006 |
| 2026-01-23 | 265037 | 1,010.02 € | 12.00 | 84.1683 |
| 2026-01-27 | 297437 | 2,320.67 € | 33.00 | 70.3233 |
| 2026-02-06 | 305915 | 2,096.28 € | 28.00 | 74.8671 |
| 2026-02-10 | 315316 | 1,615.08 € | 21.00 | 76.9086 |
| 2026-02-13 | 326483 | 1,276.81 € | 16.00 | 79.8006 |
| 2026-02-20 | 349417 | 1,953.35 € | 26.00 | 75.1288 |
| 2026-02-24 | 358879 | 860.72 € | 10.00 | 86.0720 |
| 2026-02-27 | 371691 | 782.95 € | 9.00 | 86.9944 |
| 2026-03-03 | 380264 | 2,229.20 € | 27.00 | 82.5630 |
| 2026-03-06 | 394331 | 2,442.50 € | 32.00 | 76.3281 |
| 2026-03-10 | 403527 | 1,718.78 € | 21.00 | 81.8467 |
| 2026-03-13 | 415415 | 1,510.94 € | 18.00 | 83.9411 |
| 2026-03-17 | 424313 | 2,442.50 € | 31.00 | 78.7903 |
| 2026-03-20 | 438219 | 1,430.84 € | 17.00 | 84.1671 |
| 2026-03-27 | 460975 | 1,430.84 € | 17.00 | 84.1671 |

**Near-Match-Suche auf Dinas-Seite:**

**PLZ-Präzisions-Mismatch – empf_plz_2 weicht um 1 Zeichen ab** (bis zu 3 Beispiele):

| Familie-Key | Datum | Cluster-ID | empf_plz_2 | Tarifgruppe | Fracht (€) |
|-------------|-------|-----------|-----------|------------|-----------|
| 491063|70|13|sika_de_stellplatz | 2025-07-01 | 1104568 | 13 | sika_de_stellplatz | 384.25 € |
| 491063|70|09|sika_de_stellplatz | 2025-02-03 | 3751545 | 09 | sika_de_stellplatz | 14,510.33 € |
| 491063|70|15|sika_de_stellplatz | 2025-02-03 | 3751547 | 15 | sika_de_stellplatz | 8,077.07 € |

**Diagnose:** PLZ-Präzisions-Mismatch – Empfänger-PLZ in Dinas geringfügig abweichend

---

#### `491063|70|D1|sika_de_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 491063 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | D1 |
| Tarifgruppe          | sika_de_stellplatz |
| Gesamt-Fracht        | 26,218.17 € |
| Cluster-Anzahl       | 22 |

**Cluster auf AX-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-10-07 | 15548 | 0.00 € | 6.00 | – |
| 2025-10-08 | 23695 | 0.00 € | 5.00 | – |
| 2025-11-11 | 117216 | 0.00 € | 19.00 | – |
| 2025-11-14 | 127454 | 0.00 € | 1.00 | – |
| 2025-11-21 | 144700 | 0.00 € | 2.00 | – |
| 2025-11-21 | 145262 | 0.00 € | – | – |
| 2025-11-21 | 286634 | 481.35 € | 1.00 | 481.3500 |
| 2025-11-25 | 151277 | 0.00 € | 4.00 | – |
| 2025-12-05 | 181794 | 0.00 € | 5.00 | – |
| 2025-12-05 | 286724 | 748.10 € | 5.00 | 149.6200 |
| 2025-12-12 | 191755 | 0.00 € | 20.00 | – |
| 2025-12-12 | 286727 | 3,491.45 € | 23.00 | 151.8022 |
| 2026-01-09 | 219668 | 4,013.27 € | 13.00 | 308.7131 |
| 2026-01-23 | 262632 | 3,149.75 € | 2.50 | 1259.9000 |
| 2026-01-27 | 270944 | 1,735.78 € | 13.00 | 133.5215 |
| 2026-02-03 | 301306 | 332.46 € | 2.00 | 166.2300 |
| 2026-02-06 | 305916 | 3,684.22 € | 27.00 | 136.4526 |
| 2026-02-17 | 345099 | 3,154.55 € | 25.00 | 126.1820 |
| 2026-02-24 | 358863 | 1,851.24 € | 14.00 | 132.2314 |
| 2026-03-03 | 384502 | 1,143.37 € | 7.00 | 163.3386 |
| 2026-03-06 | 403317 | 952.94 € | 5.00 | 190.5880 |
| 2026-03-27 | 469251 | 1,479.69 € | 9.00 | 164.4100 |

**Near-Match-Suche auf Dinas-Seite:**

**PLZ-Präzisions-Mismatch – empf_plz_2 weicht um 1 Zeichen ab** (bis zu 3 Beispiele):

| Familie-Key | Datum | Cluster-ID | empf_plz_2 | Tarifgruppe | Fracht (€) |
|-------------|-------|-----------|-----------|------------|-----------|
| 491063|70|DU|sika_de_stellplatz | 2025-01-28 | 1102810 | DU | sika_de_stellplatz | 407.50 € |
| 491063|70|DU|sika_de_stellplatz | 2025-02-25 | 1103236 | DU | sika_de_stellplatz | 786.65 € |
| 491063|70|DU|sika_de_stellplatz | 2025-01-28 | 3751156 | DU | sika_de_stellplatz | 701.84 € |

**Diagnose:** PLZ-Präzisions-Mismatch – Empfänger-PLZ in Dinas geringfügig abweichend

---

#### `491063|||sika_de_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 491063 |
| Abs.-PLZ 2-stellig   |  |
| Empf.-PLZ 2-stellig  |  |
| Tarifgruppe          | sika_de_stellplatz |
| Gesamt-Fracht        | 25,592.21 € |
| Cluster-Anzahl       | 20 |

**Cluster auf AX-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2026-04-01 | 482963 | 1,357.56 € | – | – |
| 2026-04-02 | 478251 | 1,451.91 € | – | – |
| 2026-04-02 | 478254 | 845.21 € | – | – |
| 2026-04-02 | 478257 | 2,975.15 € | – | – |
| 2026-04-02 | 487222 | 1,509.75 € | – | – |
| 2026-04-07 | 483275 | 558.28 € | – | – |
| 2026-04-07 | 483278 | 567.68 € | – | – |
| 2026-04-07 | 483337 | 412.29 € | – | – |
| 2026-04-07 | 491704 | 332.04 € | – | – |
| 2026-04-08 | 495817 | 1,356.93 € | – | – |
| 2026-04-08 | 495824 | 524.15 € | – | – |
| 2026-04-09 | 496202 | 634.59 € | – | – |
| 2026-04-09 | 492003 | 1,136.32 € | – | – |
| 2026-04-10 | 496230 | 2,117.81 € | – | – |
| 2026-04-10 | 496231 | 1,450.31 € | – | – |
| 2026-04-10 | 501441 | 2,507.62 € | – | – |
| 2026-04-14 | 506226 | 1,916.66 € | – | – |
| 2026-04-14 | 513973 | 326.45 € | – | – |
| 2026-04-16 | 514296 | 968.46 € | – | – |
| 2026-04-16 | 514297 | 2,643.04 € | – | – |

**Near-Match-Suche auf Dinas-Seite:**

> **Echter Route-Orphan** – Lane nur in AX-Ära vorhanden; keine ähnliche Familie in Dinas gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in AX-Ära vorhanden

---

#### `491063|70|PO|sika_de_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 491063 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | PO |
| Tarifgruppe          | sika_de_stellplatz |
| Gesamt-Fracht        | 15,155.11 € |
| Cluster-Anzahl       | 8 |

**Cluster auf AX-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-10-31 | 91905 | 1,011.44 € | 2.00 | 505.7200 |
| 2025-12-09 | 187988 | 2,354.23 € | 6.00 | 392.3717 |
| 2026-01-09 | 227283 | 2,318.83 € | 5.00 | 463.7660 |
| 2026-01-23 | 270955 | 1,055.47 € | 2.00 | 527.7350 |
| 2026-01-30 | 293500 | 2,328.83 € | 5.00 | 465.7660 |
| 2026-02-06 | 314957 | 1,055.47 € | 2.00 | 527.7350 |
| 2026-02-20 | 358472 | 2,489.62 € | 6.00 | 414.9367 |
| 2026-02-27 | 379995 | 2,541.22 € | 7.00 | 363.0314 |

**Near-Match-Suche auf Dinas-Seite:**

> **Echter Route-Orphan** – Lane nur in AX-Ära vorhanden; keine ähnliche Familie in Dinas gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in AX-Ära vorhanden

---

#### `491063|70|28|sika_de_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 491063 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | 28 |
| Tarifgruppe          | sika_de_stellplatz |
| Gesamt-Fracht        | 10,706.52 € |
| Cluster-Anzahl       | 20 |

**Cluster auf AX-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-10-15 | 47643 | 0.00 € | – | – |
| 2025-10-15 | 282838 | 279.19 € | – | – |
| 2025-10-17 | 55129 | 0.00 € | 4.00 | – |
| 2025-10-24 | 66821 | 0.00 € | 16.00 | – |
| 2025-10-24 | 282734 | 1,153.39 € | 15.00 | 76.8927 |
| 2025-11-14 | 119703 | 0.00 € | 11.00 | – |
| 2025-11-18 | 127825 | 0.00 € | 3.00 | – |
| 2025-11-18 | 286583 | 237.68 € | 2.00 | 118.8400 |
| 2025-11-25 | 145019 | 0.00 € | 4.00 | – |
| 2025-12-05 | 178194 | 0.00 € | 7.00 | – |
| 2025-12-05 | 286686 | 629.30 € | 7.00 | 89.9000 |
| 2026-01-08 | 249316 | 2,407.45 € | 35.00 | 68.7843 |
| 2026-01-16 | 240455 | 1,611.88 € | 20.00 | 80.5940 |
| 2026-01-23 | 265038 | 568.54 € | 6.00 | 94.7567 |
| 2026-01-27 | 279264 | 338.16 € | 3.00 | 112.7200 |
| 2026-02-13 | 326482 | 1,073.84 € | 13.00 | 82.6031 |
| 2026-02-24 | 366946 | 248.47 € | 2.00 | 124.2350 |
| 2026-02-27 | 371692 | 484.33 € | 5.00 | 96.8660 |
| 2026-03-06 | 394332 | 462.13 € | 4.00 | 115.5325 |
| 2026-03-20 | 438218 | 1,212.16 € | 14.00 | 86.5829 |

**Near-Match-Suche auf Dinas-Seite:**

**PLZ-Präzisions-Mismatch – empf_plz_2 weicht um 1 Zeichen ab** (bis zu 3 Beispiele):

| Familie-Key | Datum | Cluster-ID | empf_plz_2 | Tarifgruppe | Fracht (€) |
|-------------|-------|-----------|-----------|------------|-----------|
| 491063|70|38|sika_de_stellplatz | 2025-02-06 | 3751549 | 38 | sika_de_stellplatz | 816.83 € |
| 491063|70|20|sika_de_stellplatz | 2025-02-17 | 3753810 | 20 | sika_de_stellplatz | 10,288.11 € |
| 491063|70|38|sika_de_stellplatz | 2025-02-20 | 3753812 | 38 | sika_de_stellplatz | 1,995.39 € |

**Diagnose:** PLZ-Präzisions-Mismatch – Empfänger-PLZ in Dinas geringfügig abweichend

---

#### `527406|85|66|sika_atm_ch`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 527406 |
| Abs.-PLZ 2-stellig   | 85 |
| Empf.-PLZ 2-stellig  | 66 |
| Tarifgruppe          | sika_atm_ch |
| Gesamt-Fracht        | 6,619.20 € |
| Cluster-Anzahl       | 9 |

**Cluster auf AX-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-10-02 | 10558 | 758.80 € | 7.00 | 108.4000 |
| 2025-10-10 | 27923 | 758.80 € | 8.00 | 94.8500 |
| 2025-10-17 | 47538 | 723.80 € | 8.00 | 90.4750 |
| 2025-10-31 | 84114 | 723.80 € | 7.00 | 103.4000 |
| 2025-11-07 | 102213 | 758.80 € | 7.00 | 108.4000 |
| 2025-11-21 | 138192 | 723.80 € | 7.00 | 103.4000 |
| 2025-11-28 | 155019 | 723.80 € | 7.00 | 103.4000 |
| 2026-01-09 | 219733 | 723.80 € | 7.00 | 103.4000 |
| 2026-01-23 | 262515 | 723.80 € | 7.00 | 103.4000 |

**Near-Match-Suche auf Dinas-Seite:**

> **Echter Route-Orphan** – Lane nur in AX-Ära vorhanden; keine ähnliche Familie in Dinas gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in AX-Ära vorhanden

---

#### `ARA1802357|22|B7|sika_atm_de`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | ARA1802357 |
| Abs.-PLZ 2-stellig   | 22 |
| Empf.-PLZ 2-stellig  | B7 |
| Tarifgruppe          | sika_atm_de |
| Gesamt-Fracht        | 6,007.95 € |
| Cluster-Anzahl       | 11 |

**Cluster auf AX-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-10-30 | 114912 | 344.95 € | 3.00 | 114.9833 |
| 2025-11-06 | 105511 | 153.45 € | 2.00 | 76.7250 |
| 2025-11-13 | 138126 | 895.65 € | 10.00 | 89.5650 |
| 2025-11-20 | 148073 | 712.15 € | 6.00 | 118.6917 |
| 2025-11-27 | 170100 | 1,152.65 € | 13.00 | 88.6654 |
| 2025-12-11 | 196160 | 441.35 € | 3.00 | 147.1167 |
| 2025-12-11 | 196162 | 197.90 € | 2.00 | 98.9500 |
| 2026-01-08 | 240383 | 974.60 € | 11.00 | 88.6000 |
| 2026-01-15 | 245101 | 153.45 € | 2.00 | 76.7250 |
| 2026-01-22 | 267662 | 197.50 € | 2.00 | 98.7500 |
| 2026-01-29 | 289251 | 784.30 € | 7.00 | 112.0429 |

**Near-Match-Suche auf Dinas-Seite:**

> **Echter Route-Orphan** – Lane nur in AX-Ära vorhanden; keine ähnliche Familie in Dinas gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in AX-Ära vorhanden

---

#### `527406|85|80|sika_atm_ch`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 527406 |
| Abs.-PLZ 2-stellig   | 85 |
| Empf.-PLZ 2-stellig  | 80 |
| Tarifgruppe          | sika_atm_ch |
| Gesamt-Fracht        | 5,741.35 € |
| Cluster-Anzahl       | 9 |

**Cluster auf AX-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-10-10 | 27925 | 689.25 € | 6.00 | 114.8750 |
| 2025-10-17 | 47540 | 559.10 € | 5.00 | 111.8200 |
| 2025-10-31 | 84111 | 573.85 € | 6.00 | 95.6417 |
| 2025-11-07 | 102215 | 608.85 € | 5.00 | 121.7700 |
| 2025-11-14 | 119791 | 654.25 € | 6.00 | 109.0417 |
| 2025-12-12 | 191759 | 654.25 € | 6.00 | 109.0417 |
| 2026-01-09 | 219735 | 756.00 € | 9.00 | 84.0000 |
| 2026-01-16 | 240460 | 591.55 € | 6.00 | 98.5917 |
| 2026-01-23 | 262514 | 654.25 € | 6.00 | 109.0417 |

**Near-Match-Suche auf Dinas-Seite:**

> **Echter Route-Orphan** – Lane nur in AX-Ära vorhanden; keine ähnliche Familie in Dinas gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in AX-Ära vorhanden

---

#### `527406|70|34|sika_atm_ch`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 527406 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | 34 |
| Tarifgruppe          | sika_atm_ch |
| Gesamt-Fracht        | 5,687.95 € |
| Cluster-Anzahl       | 4 |

**Cluster auf AX-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2026-02-06 | 315028 | 1,222.45 € | 5.00 | 244.4900 |
| 2026-02-23 | 363063 | 1,063.00 € | 5.00 | 212.6000 |
| 2026-03-18 | 430267 | 1,850.00 € | 11.00 | 168.1818 |
| 2026-03-20 | 438321 | 1,552.50 € | 8.00 | 194.0625 |

**Near-Match-Suche auf Dinas-Seite:**

**PLZ-Präzisions-Mismatch – empf_plz_2 weicht um 1 Zeichen ab** (bis zu 3 Beispiele):

| Familie-Key | Datum | Cluster-ID | empf_plz_2 | Tarifgruppe | Fracht (€) |
|-------------|-------|-----------|-----------|------------|-----------|
| 527406|70|35|sika_atm_ch | 2025-02-03 | 3751489 | 35 | sika_atm_ch | 723.50 € |
| 527406|70|36|sika_atm_ch | 2025-02-17 | 3753750 | 36 | sika_atm_ch | 5,640.65 € |
| 527406|70|B4|sika_atm_ch | 2025-02-13 | 3753751 | B4 | sika_atm_ch | 6,931.55 € |

**Diagnose:** PLZ-Präzisions-Mismatch – Empfänger-PLZ in Dinas geringfügig abweichend

---

## Orphan-Dinas Stichprobe (Top 10 nach Fracht)

#### `491063|70|AB|sika_de_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 491063 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | AB |
| Tarifgruppe          | sika_de_stellplatz |
| Gesamt-Fracht        | 233,486.82 € |
| Cluster-Anzahl       | 11 |

**Cluster auf Dinas-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-01-31 | 3751546 | 27,703.51 € | 207.00 | 133.8334 |
| 2025-02-18 | 3753809 | 15,234.63 € | 144.00 | 105.7960 |
| 2025-03-03 | 3756116 | 18,141.82 € | 176.00 | 103.0785 |
| 2025-03-14 | 3758253 | 24,356.05 € | 212.00 | 114.8870 |
| 2025-03-27 | 3760753 | 20,438.04 € | 142.00 | 143.9299 |
| 2025-04-17 | 3762980 | 21,324.60 € | 151.00 | 141.2225 |
| 2025-05-13 | 3769110 | 21,180.96 € | 146.00 | 145.0751 |
| 2025-05-16 | 3766897 | 25,645.01 € | 222.00 | 115.5181 |
| 2025-06-17 | 3770612 | 12,983.40 € | 99.00 | 131.1455 |
| 2025-07-01 | 3772975 | 22,639.70 € | 229.00 | 98.8633 |
| 2025-08-01 | 3776567 | 23,839.10 € | 168.00 | 141.8994 |

**Near-Match-Suche auf AX-Seite:**

> **Echter Route-Orphan** – Lane nur in Dinas-Ära vorhanden; keine ähnliche Familie in AX gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in Dinas-Ära vorhanden

---

#### `511241|70|17|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 511241 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | 17 |
| Tarifgruppe          | ssc_stellplatz |
| Gesamt-Fracht        | 159,611.47 € |
| Cluster-Anzahl       | 4 |

**Cluster auf Dinas-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-02-04 | 3754035 | 45,087.65 € | – | – |
| 2025-03-04 | 3758462 | 38,540.75 € | – | – |
| 2025-05-02 | 3767096 | 39,205.81 € | – | – |
| 2025-06-03 | 3771124 | 36,777.26 € | – | – |

**Near-Match-Suche auf AX-Seite:**

> **Echter Route-Orphan** – Lane nur in Dinas-Ära vorhanden; keine ähnliche Familie in AX gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in Dinas-Ära vorhanden

---

#### `511241|70|19|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 511241 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | 19 |
| Tarifgruppe          | ssc_stellplatz |
| Gesamt-Fracht        | 152,151.34 € |
| Cluster-Anzahl       | 7 |

**Cluster auf Dinas-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2024-12-03 | 3744960 | 13,000.66 € | – | – |
| 2025-01-03 | 3749646 | 42,404.37 € | – | – |
| 2025-04-01 | 3763113 | 44,986.67 € | – | – |
| 2025-04-25 | 3763115 | 350.03 € | – | – |
| 2025-05-28 | 3767155 | 2,137.70 € | – | – |
| 2025-06-26 | 3771132 | 8,550.80 € | – | – |
| 2025-07-01 | 3775371 | 40,721.11 € | – | – |

**Near-Match-Suche auf AX-Seite:**

> **Echter Route-Orphan** – Lane nur in Dinas-Ära vorhanden; keine ähnliche Familie in AX gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in Dinas-Ära vorhanden

---

#### `491063|70|13|sika_de_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 491063 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | 13 |
| Tarifgruppe          | sika_de_stellplatz |
| Gesamt-Fracht        | 130,274.74 € |
| Cluster-Anzahl       | 11 |

**Cluster auf Dinas-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-02-14 | 3753807 | 12,503.30 € | – | – |
| 2025-02-28 | 3756114 | 8,669.29 € | – | – |
| 2025-03-07 | 3758252 | 11,126.29 € | – | – |
| 2025-04-01 | 3760752 | 11,723.36 € | – | – |
| 2025-04-29 | 3764491 | 17,022.15 € | – | – |
| 2025-05-16 | 3766896 | 12,407.64 € | – | – |
| 2025-05-30 | 3769109 | 11,625.46 € | – | – |
| 2025-06-16 | 3770611 | 16,178.19 € | – | – |
| 2025-07-01 | 1104568 | 384.25 € | – | – |
| 2025-07-15 | 3774970 | 14,006.59 € | – | – |
| 2025-08-01 | 3776566 | 14,628.22 € | – | – |

**Near-Match-Suche auf AX-Seite:**

**PLZ-Präzisions-Mismatch – empf_plz_2 weicht um 1 Zeichen ab** (bis zu 3 Beispiele):

| Familie-Key | Datum | Cluster-ID | empf_plz_2 | Tarifgruppe | Fracht (€) |
|-------------|-------|-----------|-----------|------------|-----------|
| 491063|70|19|sika_de_stellplatz | 2025-10-02 | 7622 | 19 | sika_de_stellplatz | 0.00 € |
| 491063|70|19|sika_de_stellplatz | 2025-10-14 | 40712 | 19 | sika_de_stellplatz | 0.00 € |
| 491063|70|19|sika_de_stellplatz | 2025-10-17 | 51596 | 19 | sika_de_stellplatz | 0.00 € |

**Diagnose:** PLZ-Präzisions-Mismatch – Empfänger-PLZ in AX geringfügig abweichend

---

#### `511241|70|38|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 511241 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | 38 |
| Tarifgruppe          | ssc_stellplatz |
| Gesamt-Fracht        | 106,636.64 € |
| Cluster-Anzahl       | 8 |

**Cluster auf Dinas-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2024-12-05 | 3744963 | 6,728.56 € | 23.00 | 292.5461 |
| 2025-01-09 | 3749648 | 16,643.33 € | 135.00 | 123.2839 |
| 2025-02-06 | 3754037 | 12,647.35 € | 161.00 | 78.5550 |
| 2025-03-06 | 3758464 | 8,073.60 € | 96.00 | 84.1000 |
| 2025-04-03 | 3763116 | 20,139.03 € | 154.00 | 130.7729 |
| 2025-04-30 | 3767098 | 12,531.95 € | 135.00 | 92.8293 |
| 2025-05-30 | 3771126 | 10,779.89 € | 87.00 | 123.9068 |
| 2025-07-03 | 3775373 | 19,092.93 € | 141.00 | 135.4109 |

**Near-Match-Suche auf AX-Seite:**

> **Echter Route-Orphan** – Lane nur in Dinas-Ära vorhanden; keine ähnliche Familie in AX gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in Dinas-Ära vorhanden

---

#### `511241|70|20|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 511241 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | 20 |
| Tarifgruppe          | ssc_stellplatz |
| Gesamt-Fracht        | 106,616.69 € |
| Cluster-Anzahl       | 6 |

**Cluster auf Dinas-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-01-08 | 3749647 | 19,217.22 € | 545.00 | 35.2610 |
| 2025-03-03 | 3758463 | 16,976.70 € | 423.00 | 40.1340 |
| 2025-04-01 | 3763114 | 19,918.50 € | 459.00 | 43.3954 |
| 2025-05-02 | 3767097 | 17,587.12 € | 433.00 | 40.6169 |
| 2025-05-23 | 3771125 | 14,666.43 € | 372.00 | 39.4259 |
| 2025-06-30 | 3775372 | 18,250.72 € | 431.00 | 42.3451 |

**Near-Match-Suche auf AX-Seite:**

> **Echter Route-Orphan** – Lane nur in Dinas-Ära vorhanden; keine ähnliche Familie in AX gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in Dinas-Ära vorhanden

---

#### `511241|70|IP|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 511241 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | IP |
| Tarifgruppe          | ssc_stellplatz |
| Gesamt-Fracht        | 103,301.75 € |
| Cluster-Anzahl       | 3 |

**Cluster auf Dinas-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-01-03 | 3749649 | 31,847.29 € | 332.00 | 95.9256 |
| 2025-04-01 | 3763117 | 38,153.65 € | 438.00 | 87.1088 |
| 2025-06-03 | 3771127 | 33,300.81 € | 299.00 | 111.3739 |

**Near-Match-Suche auf AX-Seite:**

> **Echter Route-Orphan** – Lane nur in Dinas-Ära vorhanden; keine ähnliche Familie in AX gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in Dinas-Ära vorhanden

---

#### `511241|70|LS|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 511241 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | LS |
| Tarifgruppe          | ssc_stellplatz |
| Gesamt-Fracht        | 83,097.22 € |
| Cluster-Anzahl       | 3 |

**Cluster auf Dinas-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2024-12-03 | 3744964 | 17,069.68 € | 98.00 | 174.1804 |
| 2025-03-04 | 3758465 | 30,191.15 € | 351.00 | 86.0147 |
| 2025-05-02 | 3767099 | 35,836.39 € | 386.00 | 92.8404 |

**Near-Match-Suche auf AX-Seite:**

> **Echter Route-Orphan** – Lane nur in Dinas-Ära vorhanden; keine ähnliche Familie in AX gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in Dinas-Ära vorhanden

---

#### `511241|70|AL|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 511241 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | AL |
| Tarifgruppe          | ssc_stellplatz |
| Gesamt-Fracht        | 73,776.82 € |
| Cluster-Anzahl       | 2 |

**Cluster auf Dinas-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2025-02-04 | 3754038 | 41,080.30 € | 477.00 | 86.1222 |
| 2025-07-01 | 3775374 | 32,696.52 € | 343.00 | 95.3251 |

**Near-Match-Suche auf AX-Seite:**

> **Echter Route-Orphan** – Lane nur in Dinas-Ära vorhanden; keine ähnliche Familie in AX gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in Dinas-Ära vorhanden

---

#### `511241|70|DU|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (normalisiert) | 511241 |
| Abs.-PLZ 2-stellig   | 70 |
| Empf.-PLZ 2-stellig  | DU |
| Tarifgruppe          | ssc_stellplatz |
| Gesamt-Fracht        | 60,793.84 € |
| Cluster-Anzahl       | 14 |

**Cluster auf Dinas-Seite:**

| Datum | Cluster-ID | Fracht (€) | Basiseinheit | €/Einheit |
|-------|-----------|-----------|-------------|----------|
| 2024-11-29 | 3745727 | 578.05 € | – | – |
| 2024-12-06 | 3744965 | 1,386.95 € | 10.00 | 138.6950 |
| 2025-01-03 | 3753086 | 180.05 € | 1.00 | 180.0500 |
| 2025-01-10 | 3749651 | 3,706.45 € | 34.00 | 109.0132 |
| 2025-01-10 | 3754039 | 8,183.35 € | 67.00 | 122.1396 |
| 2025-01-17 | 3749650 | 1,630.69 € | – | – |
| 2025-01-28 | 3750569 | 1,160.55 € | 9.00 | 128.9500 |
| 2025-02-14 | 1103235 | 2,145.25 € | – | – |
| 2025-03-07 | 3758466 | 11,253.40 € | 97.00 | 116.0144 |
| 2025-04-04 | 3763118 | 7,307.69 € | 57.00 | 128.2051 |
| 2025-05-02 | 3767100 | 5,274.70 € | 36.00 | 146.5194 |
| 2025-06-06 | 3771128 | 6,289.24 € | 50.00 | 125.7848 |
| 2025-07-04 | 3775375 | 7,810.97 € | 37.00 | 211.1073 |
| 2025-07-18 | 3775597 | 3,886.50 € | 35.00 | 111.0429 |

**Near-Match-Suche auf AX-Seite:**

> **Echter Route-Orphan** – Lane nur in Dinas-Ära vorhanden; keine ähnliche Familie in AX gefunden.

**Diagnose:** Echter Route-Orphan – Lane nur in Dinas-Ära vorhanden

---

## Aggregate Diagnose-Verteilung (alle Orphan-Familien)

Diese Verteilung basiert auf der Near-Match-Klassifikation aller Orphan-Familien (nicht nur der Stichproben).

### AX-Orphans

- **Tarifgruppen-Mismatch**: 0 Familien (0.0 %)
- **PLZ-Präzisions-Mismatch**: 10 Familien (24.4 %)
- **Echter Route-Orphan**: 31 Familien (75.6 %)

### Dinas-Orphans

- **Tarifgruppen-Mismatch**: 0 Familien (0.0 %)
- **PLZ-Präzisions-Mismatch**: 13 Familien (36.1 %)
- **Echter Route-Orphan**: 23 Familien (63.9 %)

---

*Bericht automatisch generiert von `scripts/orphan_diagnosis.py`.*