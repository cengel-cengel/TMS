# Audit-Scope-Matrix — Ist-Aufstellung je Kunde

**Stand:** 2026-04-24 | **Methodik-Referenz:** v1.9 (`docs/AUDIT_METHODOLOGY.md`)
**Zweck:** Ehrliche Ist-Aufstellung per Kunde und Prüfungsart. Keine Interpretation, keine Empfehlung.

---

## Prüfungsarten (Definitionen)

| Kürzel | Prüfungsart | Kriterium für "durchgeführt" |
|--------|-------------|------------------------------|
| **(a)** | **Calculator-vs-AX (Integration-Test)** | TMS Calculator auf echten AX-Sendungsdaten ausgeführt; Ergebnis gegen tatsächliche AX-Rechnungsbeträge verglichen; Pass-Rate oder strukturierter Befund dokumentiert |
| **(b)** | **Dinas-vs-AX systematisch (v1.9 Aggregation)** | Systematischer Vergleich Dinas-Trägerpositionen gegen AX-Kundenpositionen unter Anwendung von v1.9 §2e Rule A (is_sub-Filter) + Rule B (Routing-Key-Aggregation per Rechnung); Ergebnisse dokumentiert |
| **(c)** | **Dinas-vs-AX spot-basiert (Einzelfälle)** | Exploratorischer Cluster-/Familien-Level-Vergleich Dinas vs. AX ohne vollständige systematische Abdeckung; Explorer-Datei oder Familien-Matching existiert |
| **(d)** | **Unit-Tests (Calculator-Logik)** | Isolierte Tests der Calculator-Formel ohne echte Sendungsdaten gegen bekannte DLV-Eingabe-Ausgabe-Paare |

---

## Statuslegende

| Symbol | Bedeutung |
|--------|-----------|
| ✓ | durchgeführt — abgeschlossen und dokumentiert |
| ~ | teilweise — Prüfung begonnen, nicht finalisiert oder mit methodischen Vorbehalten |
| ✗ | nicht durchgeführt |
| n/a | nicht anwendbar (Prüfungsart strukturell nicht relevant für diesen Kunden) |

---

## Matrix

| Kunde | KNR | **(a) Calc-vs-AX** | **(b) Dinas-vs-AX syst. (v1.9)** | **(c) Dinas-vs-AX Spot** | **(d) Unit-Tests** |
|-------|-----|-------------------|----------------------------------|--------------------------|-------------------|
| EBM-Papst Mulfingen | 410844 | ✓ 9a.4 | ✗ | ~ Explorer | ✗ |
| GEZE GmbH | 406035 | ~ 9b.3–9b.4 (Tonnage-Proxy) | **✗ OFFEN** | ~ Explorer (149 Z.) | ✓ 9b.1 |
| Fischerwerke GmbH | 409480 | ~ 9a.3.1–9a.3.2 (4 RFs offen) | ✗ | ✓ Cluster-Matching | ✗ |
| Sika DE | 491063 | ✗ | ✗ | ~ 8i Familien | ✗ |
| SSC Sika | 511241 | ✗ | ✗ | ~ 8i Familien | ✗ |
| Sika 527406 (ATM/CH) | 527406 | ✗ | ✗ | ~ 8i Familien | ✗ |
| CHT IT | 486073 | ✓ 9c.1 (100 %) | n/a | n/a | ✓ 9c.1 |
| CHT BE | 486073 | ✓ 9c.2a (100 %) | n/a | n/a | ✓ 9c.2a |
| CHT ES | 486073 | ✓ 9c.2b (93,3 %) | n/a | n/a | ✓ 9c.2b |
| CHT GR | 486073 | ✓ 9c.2c (97,8 %) | n/a | n/a | ✓ 9c.2c |
| CHT AT | 486073 | ✓ 9c.2d (100 %) | n/a | n/a | ✓ 9c.2d |
| HERMA GmbH | 423650 | ✗ | ✗ | ~ Explorer | ✗ |

---

## Methodische Vorbehalte pro Zeile

### EBM-Papst (410844)
- **(a) ✓:** 339 beurteilbare Zeilen geprüft; +41.283 EUR Gesamt-Delta dokumentiert; Final-Report `docs/9a43_report.md`
- **(b) ✗:** `ebm_dinas_vergleich.xlsx` in `output/billing_report/` existiert, aber v1.9 Rule A/B nicht angewendet
- **(c) ~:** Explorer-Datei vorhanden, kein dokumentierter Befund auf Basis der Datei

### GEZE GmbH (406035)
- **(a) ~:** 1.098 Gruppen / 260.886 EUR geprüft (9b.3–9b.4); Findings dokumentiert (`docs/9b4_geze_report.md`). Vorbehalt: Tonnage>0-Proxy statt v1.9 is_sub; 140 Sub-Rows mit Tonnage>0 waren im Vergleichs-Set (Regression-Analyse: `docs/is_sub_regression_analysis.md`)
- **(b) ✗ OFFEN:** Systematischer Dinas-AX-Vergleich auf Basis v1.9 §2e wurde nie durchgeführt. Explorer-Validierung zeigt 8,54 % des Dinas-Gesamt-Volumens (4.242 EUR) in 15 Multi-Group-Rechnungen (`docs/dinas_aggregation_validation_geze.md`). STOP-Kriterium formal ausgelöst (>10 % Rechnungen mit Multi-Gruppen).
- **(c) ~:** `geze_dinas_vergleich.xlsx` (149 Zeilen, 15.300 EUR Dinas-Fracht) — Explorer-Datei ohne aktiven Pass-Rate-Nachweis
- **(d) ✓:** 9b.1 Unit-Tests gegen DLV (Basis aller aktuellen GEZE-Findings)

### Fischerwerke GmbH (409480)
- **(a) ~:** Etappen 9a.3.1–9a.3.2 abgeschlossen, Befunde dokumentiert (`docs/fischerwerke_findings_interim.md`); 4 Rückfragen (RF-1–RF-4) blockieren Final-Report; GR 2026 (360 Zeilen, 167 kEUR) unbeurteilbar mangels DLV
- **(b) ✗:** `fischerwerke_dinas_vergleich.xlsx` vorhanden; Aggregation nach `rechnung_nr`, nicht nach v1.9 Routing-Key `(rechnung_nr, empf_plz, leistungsdatum)`
- **(c) ✓:** `build_fischer_report.py` mit `enrich_master_sub()` — Cluster-Familien-Matching auf Auftragsnummer-Ebene; Befunde in Familien-Ebene dokumentiert
- **(d) ✗:** Kein dediziertes Unit-Test-Script

### Sika DE (491063)
- **(a) ✗:** Kein Calculator-vs-AX Integration-Test auf Positions-Ebene durchgeführt
- **(b) ✗:** v1.9 Routing-Key-Aggregation nicht angewendet; Fix B (`aggregate_dinas_per_invoice`) erst in `build_sika_report.py` integriert (aktuelle Session), nicht produktiv gelaufen
- **(c) ~:** 8i Familien-Matching; `sika_dinas_vergleich.xlsx` in `output/billing_report/`; 8 Unterfakturierungs-Familien und 7 Coverage-Gaps dokumentiert (`docs/sika_findings_summary.md`)
- **(d) ✗:** Kein dediziertes Unit-Test-Script

### SSC Sika (511241)
- **(a) ✗:** Kein Integration-Test
- **(b) ✗:** v1.9 Aggregation nicht angewendet; `build_ssc_report.py` und `build_ssc_import_es_report.py` mit Fix B aktualisiert (aktuelle Session), nicht produktiv gelaufen
- **(c) ~:** 8i Familien-Matching; `ssc_dinas_vergleich.xlsx`, `ssc_import_es_vollanalyse.xlsx` vorhanden
- **(d) ✗:** Kein dediziertes Unit-Test-Script

### Sika 527406 (ATM/CH)
- **(a) ✗:** Kein Integration-Test
- **(b) ✗:** v1.9 Aggregation nicht angewendet; `build_sika_527406_report.py`, `build_sika_atm_de_report.py` noch nicht mit Fix B aktualisiert
- **(c) ~:** 8i Familien-Matching; `sika_527406_dinas_vergleich.xlsx`, `sika_atm_de_dinas_vergleich.xlsx` vorhanden; 3 genuine ATM-CH-Gaps (FR/IT) mit POST-Aktivität
- **(d) ✗:** Kein dediziertes Unit-Test-Script

### CHT Germany (alle 5 Länder, KNR 486073)
- **(a) ✓:** Alle 5 Länder ≥ 93,3 % Pass-Rate; Calculator formal bestanden
- **(b) n/a:** CHT-Scripts vergleichen AX gegen DLV; kein Dinas-Cache in Calculator-Pipeline
- **(c) n/a:** Strukturell kein Dinas-vs-AX Vergleich für CHT
- **(d) ✓:** Dedizierte Test-Scripts für alle 5 Länder (9c.1, 9c.2a–9c.2d)

### HERMA GmbH (423650)
- **(a) ✗:** Calculator-Build nicht gestartet; kein Etappen-Report
- **(b) ✗:** v1.9 Aggregation nicht angewendet
- **(c) ~:** `build_herma_report.py` mit `enrich_master_sub()` laufbar; `herma_dinas_vergleich.xlsx` vorhanden; 73 Cluster mit |ΔEff| > 5 % — Früh-Indikator −167 kEUR (**nicht DLV-validiert**, gemäß §6 Zwischenstand keine operative Verwendung)
- **(d) ✗:** Kein dediziertes Unit-Test-Script

---

## Zusammenfassung offene Audit-Komponenten (b) Dinas-vs-AX systematisch

| Kunde | KNR | Grund für "nicht durchgeführt" | Risikostufe |
|-------|-----|-------------------------------|-------------|
| GEZE | 406035 | Findings rein unit-test-basiert; 8,54 % EUR in Multi-Group-RNs nie systematisch ausgewertet | **Hoch** (STOP-Kriterium ausgelöst) |
| Fischerwerke | 409480 | Dinas-Aggregation nach rechnung_nr statt v1.9 Routing-Key; kein positions-level Pass-Rate-Nachweis | Mittel |
| Sika DE/SSC/527406 | 491063/511241/527406 | Nur Familien-Matching (8i); kein systematischer positions-level Dinas-AX-Vergleich | **Hoch** (AX<DLV belegt, kein Calculator-Test) |
| HERMA | 423650 | Kein Calculator-Build; Früh-Indikator nicht DLV-validiert | Hoch (unkuantifiziert) |
| EBM-Papst | 410844 | Calculator-vs-AX bestätigt; Dinas-Explorer vorhanden aber nicht systematisch ausgewertet | Gering |
| CHT (alle Länder) | 486073 | Strukturell nicht anwendbar (AX vs DLV) | n/a |

---

*Erstellt: 2026-04-24 | Grundlage: Codebase-Analyse, Zwischenstand 2026-04-21, Regression-Analyse, GEZE Dinas-Validierung*
*Keine Code-Änderungen. Keine Korrekturen an bestehenden Report-Scripts.*
