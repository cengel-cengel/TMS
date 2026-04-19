# Etappe 8e — Dinas-Orphan Deep Dive

**Stand:** 2026-04-19  
**Cutoff:** 2025-09-26  
**Quelle:** `output/etappe8_cluster_families.parquet`

Analysiert werden die Top-10 Dinas-Orphan-Familien nach Fracht-Volumen (€).  
Klassifikationsschema:
- `likely_ax_successor_found` – AX hat einen plausiblen Nachfolger (gleicher Kunde, ähnliche Route, andere PLZ-Kodierung)
- `ax_coverage_gap` – Route war ≤ 60 Tage vor Cutoff aktiv, kein AX-Pendant → potenziell unabgerechnet
- `no_ax_successor_plausible` – Route länger inaktiv vor Cutoff oder klar eingestellt

---

## Aggregierte Klassifikation (alle Dinas-Orphans)

| Klassifikation | Familien | Gesamt-Fracht |
|----------------|---------|--------------|
| `likely_ax_successor_found` | 29 | 1,311,887 € |
| `ax_coverage_gap` | 3 | 34,863 € |
| `no_ax_successor_plausible` | 0 | 0 € |

---

## Top-10 Dinas-Orphan-Familien (nach Fracht-Volumen)

### 1. `491063|70|AB|sika_de_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 491063 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | AB |
| Tarifgruppe | sika_de_stellplatz |
| Gesamt-Fracht | 233,487 € |
| Anzahl Dinas-Cluster | 11 |
| Letzter Cluster | 2025-08-01 |
| Tage vor Cutoff | 56 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-08-01 | 3776567 | 23,839.10 | 168 | 141.90 |
| 2025-07-01 | 3772975 | 22,639.70 | 229 | 98.86 |
| 2025-06-17 | 3770612 | 12,983.40 | 99 | 131.15 |
| 2025-05-16 | 3766897 | 25,645.01 | 222 | 115.52 |
| 2025-05-13 | 3769110 | 21,180.96 | 146 | 145.08 |
| 2025-04-17 | 3762980 | 21,324.60 | 151 | 141.22 |
| 2025-03-27 | 3760753 | 20,438.04 | 142 | 143.93 |
| 2025-03-14 | 3758253 | 24,356.05 | 212 | 114.89 |
| 2025-03-03 | 3756116 | 18,141.82 | 176 | 103.08 |
| 2025-02-18 | 3753809 | 15,234.63 | 144 | 105.80 |
| 2025-01-31 | 3751546 | 27,703.51 | 207 | 133.83 |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 3 Familie(n) mit gleicher abs_plz=70 und gleichem Land=GB, aber anderer empf_plz

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `491063|70|LU|sika_de_stellplatz` | 49 | 1,213 € | GB | 2026-03-27 |
| `491063|70|PO|sika_de_stellplatz` | 8 | 1,894 € | GB | 2026-02-27 |
| `491063|70|S8|sika_de_stellplatz` | 1 | 336 € | GB | 2026-01-13 |

---

### 2. `511241|70|17|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 511241 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | 17 |
| Tarifgruppe | ssc_stellplatz |
| Gesamt-Fracht | 159,611 € |
| Anzahl Dinas-Cluster | 4 |
| Letzter Cluster | 2025-06-03 |
| Tage vor Cutoff | 115 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-06-03 | 3771124 | 36,777.26 | – | – |
| 2025-05-02 | 3767096 | 39,205.81 | – | – |
| 2025-03-04 | 3758462 | 38,540.75 | – | – |
| 2025-02-04 | 3754035 | 45,087.65 | – | – |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 2 Familie(n) mit gleichem Kunden in den ersten 90 Tagen post-Migration, jedoch andere PLZ

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|28|70|ssc_stellplatz` | 52 | 3,646 € | DE | 2025-12-19 |
| `511241|70|54|ssc_stellplatz` | 1 | 2,177 € | PT | 2025-11-03 |

---

### 3. `511241|70|19|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 511241 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | 19 |
| Tarifgruppe | ssc_stellplatz |
| Gesamt-Fracht | 152,151 € |
| Anzahl Dinas-Cluster | 7 |
| Letzter Cluster | 2025-07-01 |
| Tage vor Cutoff | 87 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-07-01 | 3775371 | 40,721.11 | – | – |
| 2025-06-26 | 3771132 | 8,550.80 | – | – |
| 2025-05-28 | 3767155 | 2,137.70 | – | – |
| 2025-04-25 | 3763115 | 350.03 | – | – |
| 2025-04-01 | 3763113 | 44,986.67 | – | – |
| 2025-01-03 | 3749646 | 42,404.37 | – | – |
| 2024-12-03 | 3744960 | 13,000.66 | – | – |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 2 Familie(n) mit gleichem Kunden in den ersten 90 Tagen post-Migration, jedoch andere PLZ

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|28|70|ssc_stellplatz` | 52 | 3,646 € | DE | 2025-12-19 |
| `511241|70|54|ssc_stellplatz` | 1 | 2,177 € | PT | 2025-11-03 |

---

### 4. `511241|70|38|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 511241 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | 38 |
| Tarifgruppe | ssc_stellplatz |
| Gesamt-Fracht | 106,637 € |
| Anzahl Dinas-Cluster | 8 |
| Letzter Cluster | 2025-07-03 |
| Tage vor Cutoff | 85 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-07-03 | 3775373 | 19,092.93 | 141 | 135.41 |
| 2025-05-30 | 3771126 | 10,779.89 | 87 | 123.91 |
| 2025-04-30 | 3767098 | 12,531.95 | 135 | 92.83 |
| 2025-04-03 | 3763116 | 20,139.03 | 154 | 130.77 |
| 2025-03-06 | 3758464 | 8,073.60 | 96 | 84.10 |
| 2025-02-06 | 3754037 | 12,647.35 | 161 | 78.55 |
| 2025-01-09 | 3749648 | 16,643.33 | 135 | 123.28 |
| 2024-12-05 | 3744963 | 6,728.56 | 23 | 292.55 |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 1 Familie(n) mit gleicher abs_plz=70 und gleichem Land=PT, aber anderer empf_plz

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|70|54|ssc_stellplatz` | 2 | 2,360 € | PT | 2026-02-18 |

---

### 5. `511241|70|20|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 511241 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | 20 |
| Tarifgruppe | ssc_stellplatz |
| Gesamt-Fracht | 106,617 € |
| Anzahl Dinas-Cluster | 6 |
| Letzter Cluster | 2025-06-30 |
| Tage vor Cutoff | 88 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-06-30 | 3775372 | 18,250.72 | 431 | 42.35 |
| 2025-05-23 | 3771125 | 14,666.43 | 372 | 39.43 |
| 2025-05-02 | 3767097 | 17,587.12 | 433 | 40.62 |
| 2025-04-01 | 3763114 | 19,918.50 | 459 | 43.40 |
| 2025-03-03 | 3758463 | 16,976.70 | 423 | 40.13 |
| 2025-01-08 | 3749647 | 19,217.22 | 545 | 35.26 |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 2 Familie(n) mit gleichem Kunden in den ersten 90 Tagen post-Migration, jedoch andere PLZ

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|28|70|ssc_stellplatz` | 52 | 3,646 € | DE | 2025-12-19 |
| `511241|70|54|ssc_stellplatz` | 1 | 2,177 € | PT | 2025-11-03 |

---

### 6. `511241|70|IP|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 511241 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | IP |
| Tarifgruppe | ssc_stellplatz |
| Gesamt-Fracht | 103,302 € |
| Anzahl Dinas-Cluster | 3 |
| Letzter Cluster | 2025-06-03 |
| Tage vor Cutoff | 115 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-06-03 | 3771127 | 33,300.81 | 299 | 111.37 |
| 2025-04-01 | 3763117 | 38,153.65 | 438 | 87.11 |
| 2025-01-03 | 3749649 | 31,847.29 | 332 | 95.93 |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 2 Familie(n) mit gleichem Kunden in den ersten 90 Tagen post-Migration, jedoch andere PLZ

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|28|70|ssc_stellplatz` | 52 | 3,646 € | DE | 2025-12-19 |
| `511241|70|54|ssc_stellplatz` | 1 | 2,177 € | PT | 2025-11-03 |

---

### 7. `511241|70|LS|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 511241 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | LS |
| Tarifgruppe | ssc_stellplatz |
| Gesamt-Fracht | 83,097 € |
| Anzahl Dinas-Cluster | 3 |
| Letzter Cluster | 2025-05-02 |
| Tage vor Cutoff | 147 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-05-02 | 3767099 | 35,836.39 | 386 | 92.84 |
| 2025-03-04 | 3758465 | 30,191.15 | 351 | 86.01 |
| 2024-12-03 | 3744964 | 17,069.68 | 98 | 174.18 |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 2 Familie(n) mit gleichem Kunden in den ersten 90 Tagen post-Migration, jedoch andere PLZ

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|28|70|ssc_stellplatz` | 52 | 3,646 € | DE | 2025-12-19 |
| `511241|70|54|ssc_stellplatz` | 1 | 2,177 € | PT | 2025-11-03 |

---

### 8. `511241|70|AL|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 511241 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | AL |
| Tarifgruppe | ssc_stellplatz |
| Gesamt-Fracht | 73,777 € |
| Anzahl Dinas-Cluster | 2 |
| Letzter Cluster | 2025-07-01 |
| Tage vor Cutoff | 87 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-07-01 | 3775374 | 32,696.52 | 343 | 95.33 |
| 2025-02-04 | 3754038 | 41,080.30 | 477 | 86.12 |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 2 Familie(n) mit gleichem Kunden in den ersten 90 Tagen post-Migration, jedoch andere PLZ

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|28|70|ssc_stellplatz` | 52 | 3,646 € | DE | 2025-12-19 |
| `511241|70|54|ssc_stellplatz` | 1 | 2,177 € | PT | 2025-11-03 |

---

### 9. `511241|70|DU|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 511241 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | DU |
| Tarifgruppe | ssc_stellplatz |
| Gesamt-Fracht | 60,794 € |
| Anzahl Dinas-Cluster | 14 |
| Letzter Cluster | 2025-07-18 |
| Tage vor Cutoff | 70 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-07-18 | 3775597 | 3,886.50 | 35 | 111.04 |
| 2025-07-04 | 3775375 | 7,810.97 | 37 | 211.11 |
| 2025-06-06 | 3771128 | 6,289.24 | 50 | 125.78 |
| 2025-05-02 | 3767100 | 5,274.70 | 36 | 146.52 |
| 2025-04-04 | 3763118 | 7,307.69 | 57 | 128.21 |
| 2025-03-07 | 3758466 | 11,253.40 | 97 | 116.01 |
| 2025-02-14 | 1103235 | 2,145.25 | – | – |
| 2025-01-28 | 3750569 | 1,160.55 | 9 | 128.95 |
| 2025-01-17 | 3749650 | 1,630.69 | – | – |
| 2025-01-10 | 3749651 | 3,706.45 | 34 | 109.01 |
| 2025-01-10 | 3754039 | 8,183.35 | 67 | 122.14 |
| 2025-01-03 | 3753086 | 180.05 | 1 | 180.05 |
| 2024-12-06 | 3744965 | 1,386.95 | 10 | 138.69 |
| 2024-11-29 | 3745727 | 578.05 | – | – |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 2 Familie(n) mit gleichem Kunden in den ersten 90 Tagen post-Migration, jedoch andere PLZ

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|28|70|ssc_stellplatz` | 52 | 3,646 € | DE | 2025-12-19 |
| `511241|70|54|ssc_stellplatz` | 1 | 2,177 € | PT | 2025-11-03 |

---

### 10. `491063|70|15|sika_de_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 491063 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | 15 |
| Tarifgruppe | sika_de_stellplatz |
| Gesamt-Fracht | 45,756 € |
| Anzahl Dinas-Cluster | 4 |
| Letzter Cluster | 2025-07-14 |
| Tage vor Cutoff | 74 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-07-14 | 3774972 | 13,318.86 | 262 | 50.84 |
| 2025-06-16 | 3770613 | 12,147.91 | 171 | 71.04 |
| 2025-04-30 | 3764493 | 12,211.80 | 172 | 71.00 |
| 2025-02-03 | 3751547 | 8,077.07 | 98 | 82.42 |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 5 Familie(n) mit gleicher abs_plz=70 und gleichem Land=IT, aber anderer empf_plz

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `491063|70|41|sika_de_stellplatz` | 62 | 584 € | IT | 2026-03-30 |
| `491063|70|74|sika_de_stellplatz` | 2 | 2,801 € | IT | 2026-03-27 |
| `491063|70|28|sika_de_stellplatz` | 2 | 140 € | IT | 2025-10-15 |

---

## ax_coverage_gap – Vollständige Liste

Familien, bei denen der letzte Dinas-Cluster ≤ 60 Tage vor Migrations-Cutoff lag  
und kein plausibles AX-Pendant existiert. Das sind potenziell **unabgerechnete Lanes**.

| Family-Key | Letzter Dinas | Tage vor Cutoff | Gesamt-Fracht |
|-----------|-------------|----------------|--------------|
| `527406|70|28|sika_atm_ch` | 2025-08-13 | 44 | 34,172 € |
| `527406|70|29|sika_atm_ch` | 2025-08-01 | 56 | 528 € |
| `491063|47|70|sika_de_stellplatz` | 2025-07-28 | 60 | 164 € |

**Gesamt ax_coverage_gap Volumen: 34,863 €**

---

*Bericht automatisch generiert von `scripts/dinas_orphan_deep_dive.py`.*