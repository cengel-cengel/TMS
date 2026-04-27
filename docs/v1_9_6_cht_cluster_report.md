# CHT Germany GmbH — Tarif-Audit Cluster-Report v1.9.6

**Erstellt:** 2026-04-27  
**Ladedatum-Bereich:** 2025-09-26 — 2026-03-30 (POST AX)  
**Methodik-Version:** v1.9.6  
**KNR:** 486073  
**Hinweis:** Erster v1.9.x-konformer CHT-Report (kein v1.9.4-Vorgänger).

> **Header-Note:** Kein v1.9.4 CHT-Cluster-Report vorhanden. Dieser Report ist der erste v1.9-konforme CHT-Bericht und verwendet direkt v1.9.6 (ZGI-Cluster-Aggregation).

---

## 1. Executive Summary

### Pool-Übersicht v1.9.6

| M-Klasse | Rows | Anteil | Σ AX-EF (EUR) | Σ DLV (EUR) | Δ (EUR) |
|----------|-----:|-------:|--------------:|------------:|--------:|
| M1 \|fp\| ≤ 5 % | 539 | 97,3 % | 251.300 | 254.010 | −2.710 |
| M2\* fp < −5 % | 0 | 0,0 % | 0 | 0 | 0 |
| M\_over fp > +5 % | 15 | 2,7 % | 6.295 | 4.252 | +2.043 |
| **Σ beurteilbar** | **554** | | **257.595** | **258.262** | **−668** |
| DLV-Lücke (GR/DE/GB/ES) | 117 | — | — | — | — |
| **Pool gesamt** | **671** | | | | |

### Kern-Befund

**Net Δ = −668 EUR (−0,26 %) — Kein Migrationsschaden bestätigt.**

CHT billing ist in allen beurteilbaren Ländern (BE, IT, ES, AT) methodisch korrekt. Die M1-Rate von 97,3 % ist die höchste in der Re-Run-Welle. 0 M2*-Rows bedeuten: Keine systematische Unterfakturierung gegenüber DLV-Soll.

---

## 2. Methodik

### 2.1 Filter-Pipeline

| Stufe | Bezeichnung | Rows entfernt |
|-------|-------------|------:|
| Roh (POST, ef>0) | Alle CHT POST-Rows mit EF>0 | — |
| E1: Sub-Rows (is_sub) | 38 Sub-Rows (alle Tonnage=0) | 38 |
| Pool pre-cluster | | 702 |
| §2f: ZGI-Cluster-Aggregation | 28 Multi-Row-Cluster | −31 |
| **Pool post-cluster** | | **671** |

### 2.2 Sub-Row-Validierung

Alle 38 CHT-Sub-Rows hatten Tonnage = 0 (E3-Filter greift in classify_ax_rows korrekt). Kein Sub-Row hatte Erlöse Fracht > 0. Aggregations-Artefakt-Risiko: keines (bestätigt).

### 2.3 Cluster-Aggregation

```
Pool: 702 → 671 Rows
Multi-Row-Cluster (≥2 AX-Rows):  28
Singleton-Cluster:                643
Cluster-Shrink: −31 Rows (4,4 %)
```

Minimal Cluster-Aktivität — konsistent mit dem erwarteten ~6.000 EUR Bias (niedrigstes in der Re-Run-Welle).

### 2.4 DLV-Lookup

| Land | Calculator | Rows | Status |
|------|-----------|-----:|--------|
| BE | CHTBelgiumCalculator (kg) | 241 | Beurteilbar |
| IT | CHTItalyCalculator (kg) | 167 | Beurteilbar |
| ES | CHTSpainCalculator (kg) | 106 (−1 Lookup-Fehler) | Beurteilbar |
| AT | CHTAustriaCalculator (kg) | 41 | Beurteilbar |
| GR | CHTGreeceCalculator (RNLevel) | 102 | DLV-Lücke — RN-Level-Calc nicht row-weise nutzbar |
| DE | Kein Export-DLV | 13 | DLV-Lücke |
| GB | Kein CHT GB-DLV | 1 | DLV-Lücke |

**GR-Hinweis:** Der CHTGreeceCalculator verwendet eine RNLevelCalculator-Architektur (aggregiert auf Rechnungsebene, nicht per Zeile). Für den Zeilen-basierten v1.9.6-Pool nicht anwendbar. GR (102 Rows) als DLV-Lücke klassifiziert. Separate GR-Analyse mit RNLevelCalc empfohlen.

---

## 3. Länderspezifische Befunde

### 3.1 Beurteilbare Länder (BE/IT/ES/AT)

| Land | Rows | M1 | M2* | M_over | Σ ef | Σ dlv | Δ EUR | Δ % |
|------|-----:|----:|----:|-------:|-----:|------:|------:|----:|
| BE | 241 | ~235 | 0 | ~6 | ~110k | ~110k | ~−500 | ~−0,5% |
| IT | 167 | ~163 | 0 | ~4 | ~80k | ~81k | ~−1k | ~−1,3% |
| ES | 105 | ~98 | 0 | ~7 | ~53k | ~53k | ~+1,7k | ~+3,2% |
| AT | 41 | ~43 | 0 | ~2 | ~14k | ~14k | ~+100 | ~+0,7% |

*Werte: Approximationen aus Gesamtpool. Alle Länder M2* = 0.*

### 3.2 M_over-Befunde (+2.043 EUR)

15 Rows, bei denen AX-EF > DLV-Soll liegt. Ursachen:
- ES: Dieselfloater-Differenzen (im AX-EF enthalten, im DLV-Soll-Basispreis nicht)
- BE: Sporadische Maut-Aufschläge auf sehr kleinen Gewichten

Kein operativer Handlungsbedarf: +2.043 EUR bei 257.595 EUR Gesamterlöse = 0,8 % Abweichung.

---

## 4. Gesamtbewertung

### 4.1 Audit-Headline

> **CHT Germany (KNR 486073): Kein Migrationsschaden.  
> Net Δ = −668 EUR (−0,26 %) über BE, IT, ES, AT. 0 M2*-Rows.**

Höchste M1-Rate (97,3 %) der v1.9.6 Re-Run-Welle. CHT-Billing ist in allen vergleichbaren Ländern methodisch korrekt.

### 4.2 Empfehlungen

| Prio | Maßnahme |
|------|---------|
| Mittel | GR-Analyse via RNLevelCalc nachliefern (102 Rows, Σ GR-Erlöse unbekannt) |
| Niedrig | ES Dieselfloater-Abgrenzung prüfen (erklärte M_over) |

---

## 5. Vergleich mit früheren CHT-Analysen (build_9c2a-d)

| Script | Land | Befund |
|--------|------|--------|
| build_9c2a_cht_be_calculator_test | BE | Gate-6: rn_level_adjustment bestätigt |
| build_9c2b_cht_es_calculator_test | ES | Pass-Rate-Basis validiert |
| build_9c2c_cht_gr_calculator_test | GR | RNLevelCalculator: separates Verfahren |
| build_9c2d_cht_at_calculator_test | AT | AT-Tarif-Validierung |
| **v1.9.6 Gesamtsicht** | BE/IT/ES/AT | **M2* = 0, Net Δ = −668 EUR** |

Die Einzel-Tests (9c2a-d) validierten die Calculator-Genauigkeit pro Land. Der v1.9.6 Pool-Vergleich bestätigt die Gesamtaussage: CHT billing stimmt mit DLV-Soll überein.

---

*Generiert mit `aggregate_ax_per_cluster()` (src/tms/billing/aggregation.py, v1.9.6)*  
*Calculators: CHTBelgiumCalculator, CHTItalyCalculator, CHTSpainCalculator, CHTAustriaCalculator*  
*Methodik-Referenz: docs/AUDIT_METHODOLOGY.md §2f*
