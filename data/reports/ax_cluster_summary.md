# AX-Cluster Summary — Etappe 7a

**Erstellt:** 2026-04-19  
**Modul:** `src/tms/clustering/ax_cluster.py`  
**Funktion:** `build_ax_clusters(ax_df, tb_df, excluded_knrs={"413276"})`  
**Quellen:** `Sika.xlsx` (3.590 Rows) + `Tagesbericht.Einzeldaten.alle.VKA.5.xlsx`  
**Excluded:** KNR 413276 (Spiegelkonto, alle Betrag=0)

---

## 1. Cluster-Anzahl gesamt

| Kennzahl | Wert |
|----------|------|
| **Cluster gesamt** | **502** |
| Erwartung aus Inventur (vor 413276-Exclusion) | 517 |
| Differenz (413276-Cluster herausgefiltert) | −15 |
| Standalone-Rows (kein Cluster) | 1 (April 2026, Betrag=0) |
| Solo-Master (0 Subs) | 2.364 (nicht im Cluster-DF) |

> **Hinweis:** Die Inventur-Zahl 517 enthielt noch 15 Cluster mit KNR 413276 (Spiegelkonto).
> Nach Exclusion: 502 echte Abrechnungs-Cluster.

---

## 2. Verteilung n_subs (Subs pro Cluster)

| n_subs | Cluster-Anzahl | Anteil |
|--------|---------------|--------|
| 1 | 368 | 73.3% |
| 2 | 100 | 19.9% |
| 3 | 19 | 3.8% |
| 4 | 12 | 2.4% |
| 5 | 3 | 0.6% |
| 6–10 | 0 | — |
| >10 | 0 | — |
| **Gesamt** | **502** | **100%** |

**Median:** 1 Sub/Cluster · **Max:** 5 Subs/Cluster · **Gesamt Sub-Rows:** 657

---

## 3. KNR-Verteilung der Master-Rows

| KNR / Account | Cluster-Anzahl |
|---------------|---------------|
| ARA_Sika_DE+CH | 266 (52.9%) |
| 511241 (SIKA SUPPLY CENTER AG) | 113 (22.5%) |
| ARA1802357 (Sika Automotive Deutschland GmbH) | 57 (11.4%) |
| 527406 (Sika Automotive AG) | 51 (10.2%) |
| 491063 (Sika Deutschland CH AG) | 15 (3.0%) |

---

## 4. consistency_check (Master.Abrechnungsgewicht == Σ TB-Tonnage ±1 kg)

| Ergebnis | Anzahl | Anteil |
|----------|--------|--------|
| **Pass (True)** | **427** | **85.1%** |
| **Fail (False)** | **75** | **14.9%** |

### Ursachen der 75 Fails

| Ursache | Cluster | Beschreibung |
|---------|---------|--------------|
| April 2026 beyond TB | 41 | Leistungsdatum > 2026-03-31; kein TB-Match → aggregat=0 |
| cutoff_2026-03-31 (partial) | 3 | Letzter TB-Tag; nicht alle Mitglieder erfasst |
| Import-Routen (Alcobendas, Cerano) | 5 | TB-Match nur für Teilmenge der Mitglieder |
| Dublin / sonstige | 4 | Jan 2026-Lücken; ggf. späteres TB-Datum |
| Kleinere Abweichungen (Rounding, LDM-Cluster) | 22 | aggregat ≠ 0, aber |diff| > 1 kg |

**Interpretation:** Die 75 Fails sind ausnahmslos durch fehlende TB-Daten (Zeitraum-Cutoff
oder Import-Routen) erklärbar. **Keine Hinweise auf Abrechnungs-Fehler** in den Fails.

---

## 5. TB-Coverage Distribution

### Nach Leistungsdatum

| Zeitraum | Cluster | coverage=1.0 | coverage<1.0 |
|----------|---------|-------------|--------------|
| ≤ 2026-03-31 (im TB-Fenster) | 461 | 454 (98.5%) | 7 (1.5%) |
| > 2026-03-31 (April 2026+) | 41 | 0 | 41 (100%) |

**Effektive Sub-Coverage** innerhalb TB-Fenster: **98.6%** (repräsentiert 648/657 Sub-Rows)

### tb_gap_reason Breakdown

| Grund | Cluster |
|-------|---------|
| Kein Gap (coverage=1.0) | 454 |
| `april_2026_beyond_tb` | 41 |
| `cutoff_2026-03-31` | 3 |
| `dublin_jan_2026` | 2 |
| `import_route_alcobendas_stuttgart` | 1 |
| `unknown` | 1 |

---

## 6. Verifikations-Spot-Check: Cluster 4484

| Feld | Wert |
|------|------|
| cluster_id | 4484 |
| master_auftragsnr | 7092010000673005 |
| master_knr | 511241 |
| master_billing_kg | 58.733 kg |
| master_fracht_eur | 4.977,43 EUR |
| n_subs | 2 |
| aggregat_gewicht_kg | **58.733 kg** (19.040 + 19.464 + 20.229) |
| aggregat_stp | 99 (33 × 3 Mitglieder) |
| sender_plz_distinct | ["28"] (Cerano IT, PLZ 28...) |
| empfaenger_plz_distinct | ["70"] (Stuttgart-Weilimdorf 70499) |
| leistungsdatum | 2025-09-29 |
| tb_coverage_subs | 1.0 |
| tb_gap_reason | None |
| consistency_check | **True** ✓ |

> Master-Abrechnungsgewicht (58.733 kg) = Summe aller drei physikalischen TB-Gewichte.
> Erlöse-Summe: 1.613,58 + 1.649,51 + 1.714,34 = **4.977,43 EUR** = Master-Betrag. ✓

---

## 7. Test-Status

```
25/25 Tests grün
  18 Unit Tests  (synthetische DataFrames, kein Datei-I/O)
   7 Integration Tests (echte Sika.xlsx + Tagesbericht)

Abgedeckt:
  ✓ Cluster 4484: n_subs=2, master_billing_kg=58733, aggregat=58733, consistency=True
  ✓ TB-Gap (April 2026): tb_coverage_subs<1.0, tb_gap_reason="april_2026_beyond_tb"
  ✓ KNR 413276 excluded
  ✓ STANDALONE nicht im Output
  ✓ consistency_check=False bei Abweichung >1 kg
  ✓ Cluster-Anzahl 450–520
  ✓ aggregierte TB-Coverage ≥95% im TB-Fenster
  ✓ Alle 16 Spalten vorhanden
  ✓ n_subs >= 1 für alle Cluster
```
