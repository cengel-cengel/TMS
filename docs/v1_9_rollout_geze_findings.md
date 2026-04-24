# v1.9 Rollout GEZE — Findings-First-Inventur

**Stand:** 2026-04-24 | **Kunde:** GEZE GmbH (KNR 406035)
**Zweck:** Exakte Ist-Aufstellung bevor Arbeit beginnt. Was existiert, was fehlt, was brauchen wir?
**Status:** STOP — Inventur abgeschlossen. Arbeitsbeginn nach Freigabe.

---

## §1 Was existiert heute (Prior-Findings)

### §1a Findings aus 9b.1 Unit-Tests (vollständig ✓)

Quelle: `src/build_9b1_geze_calculator_test.py`

| Befund | Detail |
|--------|--------|
| Calculator-Logik für AT/CH/ES/FR/GB/IE/IT/PT | Gegen DLV-Tarife getestet (isoliert, ohne echte AX-Daten) |
| Abgedeckte Routing-Strukturen | Tonnage-Band-Lookup, Maut-Inklusiv-Flag, CHF-Floater-Modell |
| Keine realen Sendungsdaten | Unit-Tests sind DLV-basiert, nicht AX-basiert |

Diese Findings sind stabil — v1.9 hat **keine Auswirkung** auf Unit-Tests.

### §1b Findings aus 9b.3–9b.4 Calculator-vs-AX (mit Vorbehalt ~)

Quelle: `src/build_9b3_geze_phase_rollout.py`, `docs/9b4_geze_report.md`

| Kennzahl | Wert |
|----------|------|
| Gesamt-Scope (beurteilbar) | 1.098 Gruppen, 3.120 Positionen |
| AX-Erlöse Fracht (Scope) | 260.886 EUR |
| Gesamt-Delta | **+51.187 EUR** (Ist > DLV) |
| Muster-A (ERKA) | 0 Treffer |
| Muster-B-Kandidaten | 13 gesamt: 1 Aggregationsartefakt + **12 unvalidiert** |
| DLV | 2025-Fallback; kein 2026-DLV |
| Aktiver Filter | `Tonnage > 0` (Zeile 102 in build_9b3) |
| Gate-1 | Aktiv: 25,5 % Tonnage=0 (1.109/4.349 Positionen) |

**Methodik-Vorbehalt v1.9:** Der Filter `Tonnage > 0` (Zeile 102) entspricht **nicht** v1.9 §2e Rule A.
Korrekt wäre `filter_comparison_set()` (is_sub = has_ms & ~has_ua).
Die Differenz: 140 Sub-Rows mit Tonnage>0 waren im Scope — in v1.9 korrekt ausgeschlossen.

### §1c Explorer-Datei (Spot-basiert ~)

| Datei | Inhalt | v1.9-Status |
|-------|--------|-------------|
| `output/billing_report/geze_dinas_vergleich.xlsx` | 149 Zeilen, 15.300 EUR Dinas-Fracht | Nicht v1.9-konform: 78 von 149 Zeilen aus Multi-Group-RNs nicht re-aggregiert |

Diese Datei hat keinen aktiven Pass-Rate-Nachweis — rein exploratorisch.

---

## §2 Was fehlt (Audit-Lücken)

### §2a Lücke 1: Dinas-AX systematisch (b) — kritisch

**Status:** Nie durchgeführt.

Empirische Grundlage (`docs/dinas_aggregation_validation_geze.md`):

| Kennzahl | Wert |
|----------|------|
| Dinas-Positionen gesamt | 792 |
| Rechnungen | 129 |
| Routing-Keys nach v1.9-Aggregation | 759 |
| Rechnungen mit Multi-Group (>1 Pos/RK) | **15 (11,6 %)** |
| EUR-Anteil Multi-Group | **4.242 EUR = 8,54 % des Dinas-Gesamt-Volumens** |
| STOP-Kriterium | Formal ausgelöst (>10 % Rechnungen) |

**Bedeutung:** Es gibt keine Prüfung, ob die 759 Dinas-Routing-Keys korrekt gegen AX-Gruppen matchen.
Die 12 Muster-B-Kandidaten aus (a) wurden ausschließlich gegen DLV geprüft, nicht gegen Dinas-Trägerpreise.

### §2b Lücke 2: is_sub-Filter (a teilweise)

**Status:** 9b.3-Pipeline nutzt Tonnage>0-Proxy.

Konsequenz für bestehende Findings (Regression-Analyse §3):

| Frage | Bekannte Datenlage | Noch zu prüfen |
|-------|-------------------|----------------|
| Wie viele der 140 Sub-Rows Tonnage>0 fallen in den 9b.3-Scope? | is_sub regression zeigt 153 FP (POST, Erlöse>0) für GEZE | Welche der 1.098 Gruppen enthalten Sub-Row-Positionen? |
| Sind die 12 Muster-B-Kandidaten Master oder Sub? | Unbekannt | Zentrale Regression-Check-Frage |
| Ändert sich der +51.187 EUR Delta nach Sub-Exclusion? | Sub-EUR-Volumen: 143.407 EUR gesamt; nicht alle im Scope | Partieller Delta-Shift möglich |

### §2c Lücke 3: Zweistufigkeit Rule D (noch nicht geprüft)

**Status:** Stage-2-Filter (`~unbeurteilbar`) noch nicht implementiert in GEZE-Pipeline.

Relevante Datenpunkte:
- GEZE POST: 37 FN-Zeilen (Standalone, Tonnage=0, LDM=0) — v1.9 würde diese in den Scope nehmen; Stage-2 würde sie herausfiltern
- Ohne Stage-2: 37 Zeilen als `unbeurteilbar` im Calculator → Null-Outputs oder Fehlklassifikationen möglich
- Mit Stage-2: sauber ausgeschlossen bevor Calculator läuft

---

## §3 Was brauchen wir (Daten-Inventur)

### §3a Bereits vorhanden ✓

| Quelle | Pfad | Inhalt |
|--------|------|--------|
| AX GEZE POST-Daten | `output/bi_top20_data.pkl` (KNR 406035) | 7.752 Zeilen; inkl. Mastersendung/Unterauftrag-Felder |
| Dinas-Cache | `output/dinas_cache_406035.pkl` | 792 Positionen, 129 Rechnungen |
| DLV GEZE 2025 | `20250305_Geze_Export_incl.*.xlsx` | 2025-Tarife, Sheet "Exporttarife"; 2025-Fallback aktiv |
| Calculator-Modul | `src/tms/tariff/calculators/` (GEZE-Logik) | Tonnage-Band-Lookup implementiert |
| Aggregations-Modul | `src/tms/billing/aggregation.py` | `filter_comparison_set()`, `aggregate_dinas_per_invoice()` bereit |
| Unit-Tests | `src/tms/billing/tests/test_aggregation.py` | 17 Tests, alle grün |

### §3b Nicht vorhanden / Klärung nötig

| Was | Warum nötig | Beschaffungs-Weg |
|-----|-------------|------------------|
| 2026-DLV GEZE | Für `in_dlv_2026`-Erweiterung | Beim Kunden anfordern — kein Blocker für v1.9-Rollout selbst |
| Klärung 12 Muster-B-Kandidaten | Manuelles Review erforderlich | Interne Prüfung (kein Kunden-Input nötig) |

---

## §4 Konkrete Schritte für GEZE v1.9

Reihenfolge (sequenziell, jeder Schritt bestätigt vor dem nächsten):

| # | Schritt | Input | Output | Aufwand |
|---|---------|-------|--------|---------|
| 1 | `bi_top20_data.pkl` → GEZE POST → `filter_comparison_set()` anwenden | Vorhandene Daten | Bereinigter DataFrame ohne Sub-Rows | 0,5 Sess. |
| 2 | Regression-Check: Welche der 12 Muster-B-Kandidaten sind Sub-Rows? | Schritt 1 Output + 9b4_report | Stabilitäts-Aussage für bisherige Findings | 0,5 Sess. |
| 3 | `~unbeurteilbar`-Stage-2-Filter anwenden; 37 FN-Zeilen korrekt ausschließen | Schritt 1 Output | Sauberer Calculator-Input | integriert |
| 4 | 9b.3-Pipeline mit v1.9-Filtern neu ausführen; Delta vergleichen | Schritt 3 Output | Aktualisierter +Delta-Wert; v1.9-konformer Scope | 1 Sess. |
| 5 | `aggregate_dinas_per_invoice()` auf `dinas_cache_406035.pkl` | Vorhandener Cache | 759 Routing-Keys; 15 Multi-Group-RNs markiert | 0,5 Sess. |
| 6 | AX-Gruppen (v1.9-Scope) gegen Dinas-Routing-Keys matchen | Schritt 4 + 5 | Systematischer Vergleich; neue §8-Kandidaten möglich | 1–2 Sess. |
| 7 | Multi-Group-RNs (15 Stk., 4.242 EUR) gesondert dokumentieren | Schritt 6 | §8-Dokumentation oder "kein Befund" | 0,5 Sess. |
| 8 | Explorer-Datei mit v1.9-Aggregation refreshen | Schritt 5 | `geze_dinas_vergleich_v1.9.xlsx` | 0,5 Sess. |

---

## §5 Entscheidungspunkte mid-Rollout (STOP-Kriterien)

| Trigger | Wann | Konsequenz |
|---------|------|------------|
| Mehr als 3 der 12 Muster-B-Kandidaten sind Sub-Rows | Nach Schritt 2 | Findings-Revision nötig; Abstimmung vor Fortführung |
| +Delta sinkt um >5 kEUR nach Sub-Exclusion | Nach Schritt 4 | Zwischenstand-Update; Abstimmung |
| Schritt 6 ergibt mehr als 3 neue §8-Kandidaten | Nach Schritt 6 | STOP und Befund-Review |
| Multi-Group-RNs zeigen Dinas < AX Muster (Muster-B analog) | Nach Schritt 7 | Neue Findings-Kategorie; Abstimmung |

---

## §6 Erwartete Outputs am Ende des GEZE v1.9 Rollouts

| Dokument | Inhalt |
|----------|--------|
| Aktualisierter `docs/9b4_geze_report.md` oder Nachfolger | v1.9-konformer Calculator-vs-AX-Befund; Regression bestätigt/revidiert |
| Neues `docs/geze_dinas_ax_systematic.md` | Erstmaliger systematischer Dinas-AX-Vergleich; Multi-Group-Behandlung dokumentiert |
| `output/billing_report/geze_dinas_vergleich_v1.9.xlsx` | Refreshte Explorer-Datei mit v1.9-Aggregation |

---

## §7 Freigabe-Entscheidung (STOP bis Bestätigung)

**Arbeit beginnt erst nach expliziter Freigabe.**

Folgende Entscheidungen werden nach Lektüre dieses Dokuments erbeten:

1. Sind die 4 Schritte der Pipeline (Schritt 1–4 vor Dinas-Vergleich) genehmigt?
2. Soll der Dinas-vs-AX-Vergleich (Schritt 5–8) direkt angeschlossen werden oder erst nach Regression-Check-Bestätigung?
3. Sind die STOP-Kriterien in §5 akzeptiert?

---

*Erstellt: 2026-04-24 | Keine Code-Änderungen. Keine Ausführungen.*
*Grundlage: 9b4_geze_report.md, dinas_aggregation_validation_geze.md, is_sub_regression_analysis.md, Codebase-Analyse*
