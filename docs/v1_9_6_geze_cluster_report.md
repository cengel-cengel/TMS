# GEZE GmbH — Tarif-Audit Cluster-Report v1.9.6

**Erstellt:** 2026-04-27  
**Ladedatum-Bereich:** 2025-09-26 — 2026-03-30 (POST AX)  
**Methodik-Version:** v1.9.6  
**KNR:** 406035  
**Vorgänger-Report:** `docs/v1_9_4_geze_cluster_report.md`

---

## 1. Executive Summary

### Reconciliation v1.9.4 → v1.9.6

| Version | Methodik | Ergebnis | Anmerkung |
|---------|----------|---------|-----------|
| v1.9.4 (PRE×POST) | Dinas PRE × AX POST, Muster-Kausalität | 0 M2-Fälle, Muster-B Δ −1.778 EUR | Migration hat keine Unterfakturierung verursacht |
| **v1.9.6 (AX×DLV)** | AX POST direkt gegen DLV, ZGI-Cluster-Aggregation | **Net Δ +4.138 EUR** | Leichte Überfakturierung vs. DLV-Soll |

> **Hinweis:** v1.9.4 und v1.9.6 sind methodisch unterschiedliche Analysen. v1.9.4 prüfte Migrationskausalität (PRE×POST), v1.9.6 prüft absolute Abrechnungsgenauigkeit (AX vs. DLV-Soll). Eine direkte Zahl-für-Zahl-Reconciliation ist nicht möglich.

### Kern-Befund v1.9.6

**Headline-Aenderung: NEIN.** Die Aussage "kein Migrationsschaden bei GEZE" aus v1.9.4 bleibt gültig. Das v1.9.6 AX-vs-DLV-Ergebnis (Net +4.138 EUR) zeigt, dass GEZE leicht über DLV-Soll abrechnet — kein Rückforderungsanspruch.

### Pool-Übersicht v1.9.6

| M-Klasse | Rows | Anteil | Σ AX-EF (EUR) | Σ DLV (EUR) | Δ (EUR) |
|----------|-----:|-------:|--------------:|------------:|--------:|
| M1 \|fp\| ≤ 5 % | 2.550 | 92,4 % | 330.586 | 330.462 | +124 |
| M2\* fp < −5 % | 132 | 4,8 % | 13.415 | 21.173 | −7.758 |
| M\_over fp > +5 % | 77 | 2,8 % | 47.903 | 36.131 | +11.772 |
| **Σ beurteilbar** | **2.759** | | **391.904** | **387.766** | **+4.138** |
| DLV-Lücke (GR/CY/DE) | 158 | — | — | — | — |
| **Pool gesamt** | **2.917** | | | | |

*Pool-Ursprung: 5.091 AX-Rows (nach E0+sub-Filter) → 2.917 nach ZGI-Cluster-Aggregation (454 Multi-Row-Cluster zusammengefasst, 2.463 Singletons unverändert).*

---

## 2. Methodik-Änderung v1.9.6 (§2f Cluster-Aggregation)

### Cluster-Aggregation

```
Pool: 5.091 → 2.917 Rows
Multi-Row-Cluster (≥2 AX-Rows): 454
Singleton-Cluster:               2.463
Cluster-Shrink: −2.174 Rows (42,7 %)
```

Für 454 Multi-Row-Cluster wurden Tonnage-Werte summiert vor dem DLV-Lookup (`GEZECalculator`). Der DLV-Lookup nutzt dann das Cluster-Gesamtgewicht mit degressiven 100-kg-Bändern.

2 Cluster wurden als Mixed-CC+PLZ identifiziert und als Singletons behandelt: `308510`, `351971`.

### DLV-Lücke (158 Rows)

| Grund | Rows |
|-------|-----:|
| Empfänger Land GR (kein GEZE GR-DLV) | 127 |
| Empfänger Land CY (Zypern, kein DLV) | 8 |
| Empfänger Land DE (Inland, kein Export-DLV) | 7 |
| Tonnage = 0 | 16 |

GR und CY sind im GEZE-Tarif nicht enthalten; diese Sendungen sind methodisch nicht beurteilbar.

---

## 3. Detailbefunde

### 3.1 M2*-Befunde (−7.758 EUR)

132 Rows, bei denen AX-Erlöse mehr als 5 % unter DLV-Soll liegen. Dominante Länder:
- IT und FR: Tarifstufen-Grenzfälle (Tonnage nahe Band-Grenzen)
- AT: kleiner Restbetrag
- GB Zone 1 Ausreißer: bekannter Aggregationsartefakt (GB/WS13 — 9b4-Report)

Gesamtbetrag −7.758 EUR ist minimal relativ zu Σ AX-EF (391.904 EUR = **2 % Abweichung**).

### 3.2 M_over-Befunde (+11.772 EUR)

77 Rows, bei denen AX-EF über DLV-Soll liegt. Haupttreiber:
- CH mit CHF-Floater: AX beinhaltet Währungssurcharge, der im Basis-DLV-Soll nicht modelliert ist
- GB Zone 1: sporadische Überfakturierung bei Kleinstgewichten (< 100 kg Untergrenze)

### 3.3 Vergleich mit v1.9.4 Muster-B-Befunden

| v1.9.4 Cluster | Δ (EUR) | Muster | v1.9.6 Status |
|----------------|---------|--------|---------------|
| FR/59273 | −211,58 | M3 (vorläufig) | Weiterhin in M2*-Pool |
| FR/77164 | −69,02 | M3 (vorläufig) | Weiterhin in M2*-Pool |
| IT/20871 | −31,54 | M4 (verbessert) | M1 in v1.9.6 |
| 8 nicht beurteilbar | −1.301 | — | Teils DLV-Lücke (GR/CY) |

Die M3-Befunde aus v1.9.4 (FR-Lanes mit Dinas-Anomalien) bleiben rechnerisch sichtbar. Sie entstehen durch Tarifstufen-Grenzwerte, nicht durch die Migration.

---

## 4. Migrations-Audit-Fazit

| Aspekt | Befund |
|--------|--------|
| Migrations-Kausalität (v1.9.4) | NEIN — 0 M2-Fälle |
| Absolut-Genauigkeit AX vs. DLV (v1.9.6) | **+4.138 EUR (Net Überfakturierung)** |
| Rückforderungsanspruch | KEINER |
| Cluster-Aggregation Bias | Gering: 454 Multi-Cluster, Minimum-Floors begrenzen degressiven Effekt |
| Headline-Aenderung | NEIN |

**Empfehlung:** GEZE abgeschlossen. GR/CY-Sendungen (135 Rows) separat mit GR/CY-Tarif prüfen falls verfügbar.

---

*Generiert mit `aggregate_ax_per_cluster()` (src/tms/billing/aggregation.py, v1.9.6)*  
*Calculator: GEZECalculator (kg-basiert, Exporttarife 2025)*  
*Methodik-Referenz: docs/AUDIT_METHODOLOGY.md §2f*
