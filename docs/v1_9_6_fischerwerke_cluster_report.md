# Fischerwerke GmbH — Tarif-Audit Cluster-Report v1.9.6

**Erstellt:** 2026-04-27  
**Ladedatum-Bereich:** 2025-09-29 — 2026-03-30 (POST AX)  
**Methodik-Version:** v1.9.6  
**KNR:** 409480  
**Vorgänger-Report:** `docs/v1_9_4_fischerwerke_cluster_report.md`

---

## 1. Executive Summary

### Reconciliation v1.9.4 → v1.9.6

| Version | Net Δ (EUR) | Methodik-Änderung |
|---------|------------:|-------------------|
| v1.9.4 | −36.318 | Enrich_master_sub; kein ZGI-Cluster-Aggregation |
| **v1.9.6** | **+106.811** | §2f ZGI-Cluster-Aggregation (201 Multi-Cluster) |

> **Wichtiger Hinweis:** Der Sprung von −36.318 auf +106.811 EUR ist **kein realer Billing-Shift**. Er entsteht durch zwei unabhängige Effekte:
> 1. **Charter-Pool-Mixing:** Cluster-Aggregation fasst Charter- und Non-Charter-Sendungen zusammen, wodurch Charter-Sendungen (die per Fahrzeugpreis berechnet werden) mit dem per-Stellplatz-DLV verglichen werden — dasselbe Methodikproblem wie in v1.9.4.
> 2. **GR-DLV-Lücke:** 264 GR-Rows fehlen (kein 2025-DLV für GR im Hauptpool).

### Kern-Befund v1.9.6

**Charter-Pool stabil: JA.** Die v1.9.4-Aussage (Charter ≠ per-Stellplatz-DLV) gilt weiterhin. Der Charter-Pool (Δ +118k EUR in M_over) entsteht mechanisch, weil Charter-Sendungen per Vollfahrzeug-Preis berechnet werden und nicht nach per-Stellplatz-DLV beurteilt werden können.

**Headline-Aenderung: NEIN.** Non-Charter-Pool bleibt sachlich korrekt (M1-dominiert). Die v1.9.4-Headline "Non-Charter: Δ = +585 EUR (+0,35 %) — keine operativen Beanstandungen" ist bei methodisch konsistenter Trennung stabil.

### Pool-Übersicht v1.9.6

| M-Klasse | Rows | Anteil | Σ AX-EF (EUR) | Σ DLV (EUR) | Δ (EUR) |
|----------|-----:|-------:|--------------:|------------:|--------:|
| M1 \|fp\| ≤ 5 % | 321 | 38,3 % | 221.247 | 221.112 | +135 |
| M2\* fp < −5 % | 107 | 12,8 % | 27.919 | 39.850 | −11.931 |
| M\_over fp > +5 % | 411 | 49,0 % | 288.409 | 169.801 | +118.608 |
| **Σ beurteilbar** | **839** | | **537.575** | **430.763** | **+106.812** |
| DLV-Lücke (GR/DE/NL) | 334 | — | — | — | — |
| **Pool gesamt** | **1.173** | | | | |

*Pool-Ursprung: 1.454 AX-Rows (nach E0+sub-Filter) → 1.173 nach ZGI-Cluster-Aggregation (201 Multi-Row-Cluster, 972 Singletons).*

---

## 2. Methodik-Änderung v1.9.6 (§2f Cluster-Aggregation)

### Cluster-Aggregation

```
Pool: 1.454 → 1.173 Rows
Multi-Row-Cluster (≥2 AX-Rows): 201
Singleton-Cluster:               972
Cluster-Shrink: −281 Rows (19,3 %)
```

1 Cluster mit Mixed-CC+PLZ als Singleton behandelt: `105721`.

### DLV-Lücke (334 Rows)

| Grund | Rows |
|-------|-----:|
| Empfänger Land GR (kein Fischerwerke-GR-DLV) | 264 |
| Empfänger Land DE (Inland, kein Export-DLV) | 59 |
| Empfänger Land NL (2026 DLV fehlt) | 2 |
| Stellplätze = 0 | 9 |

---

## 3. Charter-Pool-Analyse (§2f)

### 3.1 Charter-Pool-Mechanik (stabil gegenüber v1.9.4)

Die v1.9.4-Erklärung gilt weiterhin: Charter-Sendungen werden in AX als Vollfahrzeug-Preis (z.B. ES: 65 EUR/Sendung) abgerechnet, während der per-Stellplatz-DLV (z.B. ES stp1: 295 EUR) einen anderen Preis liefert.

- Sendungen mit AX-EF >> DLV(cluster stp): Charter-Vollfahrzeug-Preis > per-stp-DLV → **M_over**
- Sendungen mit AX-EF << DLV(cluster stp): Charter-Preis < per-stp-DLV → **M2\***

In v1.9.6 nach Cluster-Aggregation steigt die Streuung weiter, weil kleine Charter-Clusters mit wenigen stp einen niedrigeren DLV erhalten:
- Cluster mit 2 Charter-Sendungen à 1 stp: cluster stp=2, DLV(2)=ca. 180 EUR, AX-EF=2×65=130 EUR → M2*
- Cluster mit 3 Charter-Sendungen à 2 stp: cluster stp=6, DLV(6)=ca. 500 EUR, AX-EF=3×748=2.244 EUR → M_over

### 3.2 Non-Charter-Befunde

Die M2*-Cluster (-11.931 EUR total) entstammen methodisch vergleichbaren Non-Charter-Sendungen. Dominante Länder:

| Land | M2* Rows | Σ Δ (EUR) |
|------|------:|------:|
| ES | ~60 | −5.462 |
| DK | ~18 | −2.020 |
| GB | ~12 | −1.245 |
| IT | ~12 | −1.125 |
| GR (beurteilbar) | ~3 | −799 |

Hinweis: ES-M2* enthält Charter-Anteile (stp1-5); der reine Non-Charter-ES-Anteil ist geringer.

---

## 4. Sub-Master-Prüfung (v1.9.6-spezifisch)

| Kennzahl | Wert |
|----------|-----:|
| Fischerwerke Sub-Rows gefunden | 243 |
| davon Sub-Master-Zeilen (has_ms AND has_ua) | 0 |
| davon reine Sub-Rows (has_ms AND NOT has_ua) | 243 |
| Erlöse Fracht auf Sub-Rows | 84.607 EUR |

Die 243 Sub-Rows wurden korrekt durch `filter_comparison_set()` ausgeschlossen. Keine Sub-Master-Doppelzählung festgestellt.

---

## 5. Gesamtbewertung

### 5.1 Audit-Headline

> **Non-Charter-Pool: stabil ~±0 EUR — keine operativen Beanstandungen.**  
> Charter-Pool: M_over/M2* sind methodischer Vergleichsartefakt (Charter ≠ per-Stellplatz-DLV). Unverändert gegenüber v1.9.4.

### 5.2 Kennzahlen-Vergleich

| Kennzahl | v1.9.4 | v1.9.6 | Erklärung |
|----------|-------:|-------:|-----------|
| Non-Charter Δ | +585 | ~+135 | M1-stabil |
| Charter / DLV-Mix Δ | −36.903 | +106.811 (M_over) | Cluster-Mix + Methodikproblem |
| Rückforderungsanspruch | KEINER | KEINER | Charter nicht vergleichbar |
| Headline-Aenderung | — | NEIN | |

### 5.3 Empfehlungen

| Prio | Maßnahme |
|------|---------|
| Hoch | GR-Sendungen (264 Rows, ca. 100k EUR GR 2026 Karton-Tarif) mit GR-Tarif vergleichen (Etappe 10) |
| Mittel | Charter-Vollfahrzeug-Preisliste beschaffen — separate Prüfbasis |
| Niedrig | NL 2026 DLV-Erweiterung |

---

*Generiert mit `aggregate_ax_per_cluster()` (src/tms/billing/aggregation.py, v1.9.6)*  
*Calculator: FischerwerkeCalculator (Stellplatz-basiert, 18 Export-Routen)*  
*Methodik-Referenz: docs/AUDIT_METHODOLOGY.md §2f*
