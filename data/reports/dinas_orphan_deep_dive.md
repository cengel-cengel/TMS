# Etappe 8e — Dinas-Orphan Deep Dive

**Stand:** 2026-04-19  
**Cutoff:** 2025-09-26  
**Quelle:** `output/etappe8_cluster_families.parquet`

Analysiert werden die Top-10 Dinas-Orphan-Familien nach Fracht-Volumen (€).  
Klassifikationsschema (zeitunabhängig, Etappe 8f):
- `likely_ax_successor_found` – AX hat plausiblen Nachfolger (gleicher Kunde + Land, andere PLZ-Kodierung)
- `ax_coverage_gap` – kein plausibles AX-Pendant; Lane könnte in POST-Ära unabgerechnet sein

---

## Aggregierte Klassifikation (alle Dinas-Orphans)

| Klassifikation | Familien | Gesamt-Fracht |
|----------------|---------|--------------|
| `likely_ax_successor_found` | 18 | 1,020,257 € |
| `ax_coverage_gap` | 7 | 55,520 € |

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

> AX hat 3 Familie(n) mit gleicher abs_plz=70 und Land=GB, andere empf_plz

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `491063|70|LU|sika_de_stellplatz` | 45 | 1,176 € | GB | 2026-03-27 |
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

> AX hat 2 Familie(n) mit gleicher abs_plz=70 und Land=ES, andere empf_plz

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|70|28|ssc_stellplatz` | 3 | 922 € | ES | 2026-01-16 |
| `511241|70|19|ssc_stellplatz` | 6 | 1,169 € | ES | 2026-03-03 |

---

### 3. `491063|70|13|sika_de_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 491063 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | 13 |
| Tarifgruppe | sika_de_stellplatz |
| Gesamt-Fracht | 130,275 € |
| Anzahl Dinas-Cluster | 11 |
| Letzter Cluster | 2025-08-01 |
| Tage vor Cutoff | 56 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-08-01 | 3776566 | 14,628.22 | – | – |
| 2025-07-15 | 3774970 | 14,006.59 | – | – |
| 2025-07-01 | 1104568 | 384.25 | – | – |
| 2025-06-16 | 3770611 | 16,178.19 | – | – |
| 2025-05-30 | 3769109 | 11,625.46 | – | – |
| 2025-05-16 | 3766896 | 12,407.64 | – | – |
| 2025-04-29 | 3764491 | 17,022.15 | – | – |
| 2025-04-01 | 3760752 | 11,723.36 | – | – |
| 2025-03-07 | 3758252 | 11,126.29 | – | – |
| 2025-02-28 | 3756114 | 8,669.29 | – | – |
| 2025-02-14 | 3753807 | 12,503.30 | – | – |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 3 Familie(n) mit gleicher abs_plz=70 und Land=ES, andere empf_plz

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `491063|70|15|sika_de_stellplatz` | 40 | 765 € | ES | 2026-03-27 |
| `491063|70|28|sika_de_stellplatz` | 15 | 511 € | ES | 2026-03-20 |
| `491063|70|08|sika_de_stellplatz` | 1 | 223 € | ES | 2026-01-16 |

---

### 4. `511241|70|20|ssc_stellplatz`

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

> AX hat 2 Familie(n) mit gleicher abs_plz=70 und Land=IT, andere empf_plz

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|70|41|ssc_stellplatz` | 7 | 578 € | IT | 2026-02-04 |
| `511241|70|28|ssc_stellplatz` | 2 | 140 € | IT | 2025-10-15 |

---

### 5. `511241|70|IP|ssc_stellplatz`

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

> AX hat 1 Familie(n) mit gleicher abs_plz=70 und Land=GB, andere empf_plz

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|70|LU|ssc_stellplatz` | 4 | 1,633 € | GB | 2026-01-23 |

---

### 6. `511241|70|LS|ssc_stellplatz`

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

> AX hat 1 Familie(n) mit gleicher abs_plz=70 und Land=GB, andere empf_plz

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|70|LU|ssc_stellplatz` | 4 | 1,633 € | GB | 2026-01-23 |

---

### 7. `511241|70|AL|ssc_stellplatz`

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

> AX hat 1 Familie(n) mit gleicher abs_plz=70 und Land=GB, andere empf_plz

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|70|LU|ssc_stellplatz` | 4 | 1,633 € | GB | 2026-01-23 |

---

### 8. `511241|20|70|ssc_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 511241 |
| Absender-PLZ 2-st. | 20 |
| Empfänger-PLZ 2-st. | 70 |
| Tarifgruppe | ssc_stellplatz |
| Gesamt-Fracht | 38,335 € |
| Anzahl Dinas-Cluster | 1 |
| Letzter Cluster | 2025-07-01 |
| Tage vor Cutoff | 87 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-07-01 | 2384360 | 38,335.00 | – | – |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 1 Familie(n) mit Land=DE und tarifgruppe=ssc_stellplatz, andere PLZ-Kombination

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `511241|28|70|ssc_stellplatz` | 100 | 3,561 € | DE | 2026-03-30 |

---

### 9. `491063|70|BB|sika_de_stellplatz`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 491063 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | BB |
| Tarifgruppe | sika_de_stellplatz |
| Gesamt-Fracht | 35,197 € |
| Anzahl Dinas-Cluster | 2 |
| Letzter Cluster | 2025-07-15 |
| Tage vor Cutoff | 73 |
| **Klassifikation** | `likely_ax_successor_found` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-07-15 | 3774971 | 19,555.73 | 205 | 95.39 |
| 2025-05-02 | 3764492 | 15,641.00 | 136 | 115.01 |

**Near-Match-Analyse auf AX-Seite:**

> AX hat 3 Familie(n) mit gleicher abs_plz=70 und Land=GB, andere empf_plz

Plausible AX-Nachfolger-Familien (bis 3):

| AX-Family-Key | Clusters | ∅ Fracht/Cluster | Empf.-Land | Letzte Aktivität |
|--------------|---------|----------------|-----------|-----------------|
| `491063|70|LU|sika_de_stellplatz` | 45 | 1,176 € | GB | 2026-03-27 |
| `491063|70|PO|sika_de_stellplatz` | 8 | 1,894 € | GB | 2026-02-27 |
| `491063|70|S8|sika_de_stellplatz` | 1 | 336 € | GB | 2026-01-13 |

---

### 10. `527406|70|28|sika_atm_ch`

| Feld | Wert |
|------|------|
| Kunde (KNR) | 527406 |
| Absender-PLZ 2-st. | 70 |
| Empfänger-PLZ 2-st. | 28 |
| Tarifgruppe | sika_atm_ch |
| Gesamt-Fracht | 34,172 € |
| Anzahl Dinas-Cluster | 10 |
| Letzter Cluster | 2025-08-13 |
| Tage vor Cutoff | 44 |
| **Klassifikation** | `ax_coverage_gap` |

**Dinas-Cluster:**

| Datum | Cluster-ID | Fracht (€) | Basis.-Wert | €/Einheit |
|-------|-----------|-----------|------------|----------|
| 2025-08-13 | 3776369 | 213.60 | – | – |
| 2025-07-18 | 3774730 | 3,194.60 | – | – |
| 2025-06-30 | 3772895 | 5,113.85 | – | – |
| 2025-05-19 | 3766774 | 3,834.20 | – | – |
| 2025-05-02 | 3764377 | 3,929.70 | – | – |
| 2025-04-15 | 3762926 | 5,748.40 | – | – |
| 2025-03-31 | 3760707 | 2,582.95 | – | – |
| 2025-03-04 | 3758170 | 2,691.50 | – | – |
| 2025-02-17 | 3761831 | 2,164.25 | – | – |
| 2025-02-03 | 3751486 | 4,698.60 | – | – |

**Near-Match-Analyse auf AX-Seite:**

> Kein plausibles AX-Pendant. Letzter Dinas-Cluster: 2025-08-13 (44 Tage vor Cutoff).

---

## ax_coverage_gap – Vollständige Liste

Familien ohne plausibles AX-Pendant (zeitunabhängige Klassifikation).  
Das sind potenziell **unabgerechnete Lanes** in der POST-Ära.

| Family-Key | Letzter Dinas | Tage vor Cutoff | Gesamt-Fracht |
|-----------|-------------|----------------|--------------|
| `527406|70|28|sika_atm_ch` | 2025-08-13 | 44 | 34,172 € |
| `527406|70|36|sika_atm_ch` | 2025-06-16 | 102 | 20,126 € |
| `527406|70|29|sika_atm_ch` | 2025-08-01 | 56 | 528 € |
| `491063|72|95|sika_de_stellplatz` | 2025-03-10 | 200 | 296 € |
| `491063|41|72|sika_de_stellplatz` | 2025-02-20 | 218 | 234 € |
| `491063|47|70|sika_de_stellplatz` | 2025-07-28 | 60 | 164 € |
| `491063|LU|72|sika_de_stellplatz` | 2025-02-25 | 213 | 0 € |

**Gesamt ax_coverage_gap Volumen: 55,520 €**

---

*Bericht automatisch generiert von `scripts/dinas_orphan_deep_dive.py` (Etappe 8f).*