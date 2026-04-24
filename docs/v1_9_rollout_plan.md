# v1.9 Rollout — Gesamtrahmen Phase 1

**Stand:** 2026-04-24 | **Methodik:** v1.9.1 (`docs/AUDIT_METHODOLOGY.md`)
**Beschluss:** v1.9 zuerst an allen bereits bearbeiteten Kunden validieren;
Sika Re-Run erst nach empirischer Bestätigung bei 3–4 Kunden.

---

## Strategie

v1.9 führt zwei strukturelle Neuerungen ein, die bei keinem Kunden produktiv gelaufen sind:

| Neuerung | v1.9-Regel | Kundenwirkung |
|----------|-----------|---------------|
| is_sub-Filter statt Tonnage>0-Proxy | §2e Rule A | Zeilen-Scope ändert sich bei GEZE (140 Sub-Rows raus), ggf. Fischerwerke |
| Routing-Key-Aggregation Dinas | §2e Rule B | Dinas-Vergleich granularer; Multi-Group-RNs separat markiert |
| Zweistufigkeit (Sub + unbeurteilbar) | §2e Rule D | Verhindert falsche Calculator-Inputs bei Zeilen ohne Billing-Dimension |

Ziel von Phase 1: Stabilität dieser drei Regeln an bekannten Kunden belegen,
bevor Sika (höchstes kommunikatives Risiko) neu gerechnet wird.

---

## Kunden-Übersicht Phase 1

| Reihenfolge | Kunde | KNR | Hauptlücke | Regression-Risiko | Schätzung |
|-------------|-------|-----|------------|-------------------|-----------|
| 1 | **GEZE** | 406035 | (b) Dinas-AX systematisch fehlt ganz | Mittel (140 Sub-Rows) | 3–4 Sessions |
| 2 | **EBM-Papst** | 410844 | (b)+(d) fehlen; (a) bestätigt | Gering (0 FP/FN in Regression) | 1–2 Sessions |
| 3 | **Fischerwerke** | 409480 | (a) 4 RFs offen; (b) Dinas-Aggregation sub-optimal | Mittel (63 FP abgedeckt) | 2–3 Sessions |
| 4 | **HERMA** | 423650 | (a)+(b)+(d) fehlen komplett | n/a (keine Prior-Findings) | 4–5 Sessions |

---

## §1 GEZE GmbH (KNR 406035)

### Ist-Stand

| Prüfungsart | Status | Vorbehalt |
|-------------|--------|-----------|
| (a) Calculator-vs-AX | ~ | Tonnage>0-Proxy statt v1.9 is_sub; 140 Sub-Rows fälschlicherweise im Scope |
| (b) Dinas-vs-AX systematisch | **✗ OFFEN** | Nie durchgeführt; STOP-Kriterium ausgelöst (8,54 % EUR in 15 Multi-Group-RNs) |
| (c) Dinas-vs-AX Spot | ~ | Explorer-Datei 149 Zeilen; 78 aus Multi-Group-RNs, nicht re-aggregiert |
| (d) Unit-Tests | ✓ | 9b.1 vollständig; Basis aller bisherigen Findings |

### v1.9-Schritte

| Schritt | Inhalt | Aufwand | Blocker |
|---------|--------|---------|---------|
| 1a | `filter_comparison_set()` in 9b.3-Pipeline integrieren | 0,5 Sess. | Keiner |
| 1b | Regression-Check: Überschneidung 140 Sub-Rows mit 12 Muster-B-Kandidaten? | 0,5 Sess. | Keiner |
| 2 | `aggregate_dinas_per_invoice()` auf `dinas_cache_406035.pkl` | 0,5 Sess. | Keiner |
| 3 | Systematischer Dinas-AX-Vergleich aufbauen (759 Routing-Keys × AX-Gruppen) | 1–2 Sess. | Kein 2026-DLV (2025-Fallback reicht für Dinas-Vergleich) |
| 4 | 15 Multi-Group-RNs separat markieren, Befund-Dokumentation | 0,5 Sess. | Keiner |
| 5 | Explorer-Datei `geze_dinas_vergleich.xlsx` mit v1.9-Aggregation refreshen | 0,5 Sess. | Keiner |

### Regression-Check-Punkte

1. Sind die 12 Muster-B-Kandidaten aus (a) Master- oder Sub-Rows? → Bestimmt ob Befunde stabil bleiben
2. Verändert sich der Scope (260.886 EUR / 1.098 Gruppen) nach Sub-Row-Exclusion?
3. Bleibt der +51.187 EUR Floater-Delta strukturell gleich?

### Abhängigkeiten

- Kein 2026-DLV für GEZE vorhanden — kein Blocker für v1.9-Rollout, nur für `in_dlv_2026`-Erweiterung
- 12 Muster-B-Kandidaten erfordern manuelle Prüfung — unabhängig von v1.9 und parallelisierbar

**Detailplan:** `docs/v1_9_rollout_geze_findings.md`

---

## §2 EBM-Papst Mulfingen (KNR 410844)

### Ist-Stand

| Prüfungsart | Status | Vorbehalt |
|-------------|--------|-----------|
| (a) Calculator-vs-AX | ✓ | 9a.4 abgeschlossen, +41.283 EUR dokumentiert |
| (b) Dinas-vs-AX systematisch | **✗** | Explorer-Datei vorhanden (14 KB), v1.9-Aggregation nicht angewendet |
| (c) Dinas-vs-AX Spot | ~ | `ebm_dinas_vergleich.xlsx` existiert |
| (d) Unit-Tests | ✗ | Kein dediziertes Unit-Test-Script |

### v1.9-Schritte

| Schritt | Inhalt | Aufwand | Blocker |
|---------|--------|---------|---------|
| 1 | is_sub-Regression-Befund für EBM verifizieren (0 FP/FN bekannt) | 0,5 Sess. | Keiner |
| 2 | `aggregate_dinas_per_invoice()` auf EBM Dinas-Cache | 0,5 Sess. | Dinas-Cache EBM vorhanden? Prüfen |
| 3 | Systematischer Dinas-AX-Vergleich (kleines Volumen, 14 KB Explorer) | 0,5–1 Sess. | Keiner |

### Regression-Check-Punkte

1. Regression-Analyse bestätigt 0 FP, 0 FN für EBM → (a)-Findings bleiben unverändert
2. Dinas-AX-Vergleich kann bestehende +41.283 EUR-Befund ergänzen oder widerlegen

### Abhängigkeiten

- Geringste Komplexität in Phase 1 — gut als zweites Validierungs-Beispiel nach GEZE
- Kein ERKA-Indexschreiben-Blocker für Dinas-AX-Vergleich selbst

---

## §3 Fischerwerke GmbH (KNR 409480)

### Ist-Stand

| Prüfungsart | Status | Vorbehalt |
|-------------|--------|-----------|
| (a) Calculator-vs-AX | ~ | 9a.3.1–9a.3.2 Zwischenstand; 4 RFs blockieren Final-Report |
| (b) Dinas-vs-AX systematisch | **✗** | `fischerwerke_dinas_vergleich.xlsx` (126 KB) nach rechnung_nr, nicht v1.9 Routing-Key |
| (c) Dinas-vs-AX Spot | ✓ | `build_fischer_report.py` Cluster-Matching mit `enrich_master_sub()` |
| (d) Unit-Tests | ✗ | Kein dediziertes Unit-Test-Script |

### v1.9-Schritte

| Schritt | Inhalt | Aufwand | Blocker |
|---------|--------|---------|---------|
| 1 | `filter_comparison_set()` ersetzt `enrich_master_sub()` in 9a-Pipeline prüfen | 0,5 Sess. | RF-1 (ERKA) nicht blockierend für diesen Schritt |
| 2 | Regression: 63 FP (Sub-Rows Tonnage>0) — bereits von `enrich_master_sub()` abgedeckt? | 0,5 Sess. | Keiner |
| 3 | `fischerwerke_dinas_vergleich.xlsx` mit v1.9 Routing-Key re-aggregieren | 1–2 Sess. | Keiner |
| 4 | Offene RFs prüfen: RF-1 (ERKA), RF-2 (GB), RF-3 (GR), RF-4 (IT-Verona) | — | RF-1: extern (ERKA); RF-2/3: Kunden-DLV |

### Regression-Check-Punkte

1. 63 FP Sub-Rows sind durch `enrich_master_sub()` bereits ausgeschlossen — v1.9 `filter_comparison_set()` erzeugt dasselbe Ergebnis auf anderem Weg → Findings stabil erwartet
2. `enrich_master_sub()` kann nach Verifikation als obsolet markiert werden (durch v1.9 ersetzt)
3. Dinas re-Aggregation auf Routing-Key-Ebene: 126 KB = substanziell; mögliche neue Befunde

### Abhängigkeiten

- RF-1 (ERKA-Indexschreiben): extern, kein Blocker für v1.9-Rollout selbst
- RF-2/3 (GB/GR-DLV): blockiert Final-Report für diese Lanes, nicht v1.9-Rollout-Verifikation
- GR 2026 (360 Zeilen, 167 kEUR): bleibt unbeurteilbar bis DLV vorliegt — v1.9 ändert nichts daran

---

## §4 HERMA GmbH (KNR 423650)

### Ist-Stand

| Prüfungsart | Status | Vorbehalt |
|-------------|--------|-----------|
| (a) Calculator-vs-AX | **✗** | Calculator-Build nicht gestartet |
| (b) Dinas-vs-AX systematisch | **✗** | v1.9-Aggregation nicht angewendet |
| (c) Dinas-vs-AX Spot | ~ | `build_herma_report.py` laufbar; `herma_dinas_vergleich.xlsx` vorhanden; −167 kEUR Früh-Indikator nicht DLV-validiert |
| (d) Unit-Tests | ✗ | Kein dediziertes Unit-Test-Script |

### v1.9-Schritte

| Schritt | Inhalt | Aufwand | Blocker |
|---------|--------|---------|---------|
| 1 | DLV-Parser für HERMA aufbauen (FR/43 und PT/20 priorisiert) | 1–2 Sess. | DLV-Dateien müssen vorliegen |
| 2 | Calculator-Build analog CHT/EBM/GEZE — v1.9 von Anfang an | 2 Sess. | DLV-Parser (Schritt 1) |
| 3 | `filter_comparison_set()` + `~unbeurteilbar` als Standard (nicht als Nachkorrektur) | integriert in Schritt 2 | Keiner |
| 4 | Dinas-AX-Vergleich mit v1.9 Aggregation | 1 Sess. | Calculator-Build (Schritt 2) |
| 5 | −167 kEUR Früh-Indikator DLV-validieren | integriert in Schritt 2–4 | DLV-Vollständigkeit |

### Regression-Check-Punkte

Keine Prior-Findings → kein Regression-Risiko. v1.9 ist der Erstansatz.

### Abhängigkeiten

- 30 FN "unbeurteilbar"-Zeilen (Tonnage=0, LDM=0): werden durch v1.9 Stage-2-Filter korrekt behandelt
- 2 FP Sub-Rows (Tonnage>0, 1.816 EUR): durch v1.9 is_sub-Filter ausgeschlossen
- `enrich_master_sub()` in `build_herma_report.py`: deckt die 2 FP bereits ab — v1.9 ersetzt das konzeptuell
- HERMA DLV-Validierung aussstehend — größter Aufwandstreiber

---

## Phase-Zeitplanung (Richtwert)

| Phase | Kunden | Gesamt-Aufwand |
|-------|--------|----------------|
| Phase 1a | GEZE | 3–4 Sessions |
| Phase 1b | EBM-Papst | 1–2 Sessions |
| Phase 1c | Fischerwerke | 2–3 Sessions |
| Phase 1d | HERMA | 4–5 Sessions |
| **Phase 1 gesamt** | 4 Kunden | **10–14 Sessions** |

---

## Freigabe-Kriterium für Sika Re-Run (Phase 4)

Sika Re-Run beginnt, wenn **alle** der folgenden Bedingungen erfüllt:

1. v1.9 is_sub-Filter bei GEZE produktiv gelaufen und Regression-Check bestanden
2. v1.9 Routing-Key-Aggregation bei mindestens 2 Kunden (z.B. GEZE + Fischerwerke) angewendet und stabil
3. Zweistufigkeit (Rule D) bei mindestens 1 Kunden empirisch bestätigt (keine falschen Calculator-Inputs)
4. Kein unerwarteter Befundsshift bei einem der Phase-1-Kunden, der Methodik-Revision erfordert

---

*Erstellt: 2026-04-24 | Keine Code-Änderungen. Keine Re-Runs.*
*Grundlage: audit_scope_per_customer.md, is_sub_regression_analysis.md, dinas_aggregation_validation_geze.md*
