# Dinas Routing-Key-Aggregation — Validierung an GEZE (KNR 406035)

**Stand:** 2026-04-24 | **Datenbasis:** `output/dinas_cache_406035.pkl`
**Methodik:** v1.9 §2e Rule B — Aggregation per Rechnung nach
`(rechnung_nr, empf_land, empf_plz, leistungsdatum)`

---

## §1 Ergebnisse

| Metrik | Wert |
|--------|------|
| Positionen gesamt | 792 |
| Rechnungen gesamt | 129 |
| Routing-Keys gesamt (nach Aggregation) | 759 |
| Davon Einzelsendungen (1 Position/RK) | 736 (97,0 %) |
| Davon Mehrfach-Gruppen (>1 Position/RK) | 23 (3,0 % aller RKs) |
| Rechnungen mit mindestens einer Mehrfach-Gruppe | 15 (11,6 % aller Rechnungen) |
| Durch Aggregation eingesparte Positionen | 33 (792 − 759) |

---

## §2 Verteilung Positionen pro Routing-Key

| n Positionen | Anzahl Gruppen | Anteil |
|-------------|---------------|--------|
| 1 | 736 | 97,0 % |
| 2 | 18 | 2,4 % |
| 3 | 2 | 0,3 % |
| 4 | 2 | 0,3 % |
| 6 | 1 | 0,1 % |

---

## §3 Top Mehrfach-Gruppen

| Rechnung | Empfänger | Leistungsdatum | n Pos. | Fracht EUR |
|----------|-----------|----------------|--------|------------|
| 57019719 | (leer) | 28.02.2025 | 6 | 90,00 |
| 57019569 | AT-2514 | 12.12.2024 | 4 | 83,10 |
| 57019719 | AT-4020 | 28.02.2025 | 4 | 35,73 |
| 57019719 | CY-2033 | 28.02.2025 | 3 | 763,02 |
| 03775180 | CH-3661 | 17.07.2025 | 3 | 32,01 |
| 01103261 | CH-8200 | 19.03.2025 | 2 | 192,22 |
| 01102816 | ES-50001 | 12.02.2025 | 2 | 4,74 |
| 03748371 | FR-60230 | 02.12.2024 | 2 | 73,57 |

RN 57019719 enthält drei Mehrfach-Gruppen an einem einzigen Leistungsdatum
(28.02.2025) für AT, CY und eine leere Empfänger-PLZ — wahrscheinlich eine
Sammelrechnung mit mehreren Positionen pro Zielland-Routing-Key.

---

## §4 Bewertung

### §8-Relevanz (STOP-Kriterium-Check)

> STOP-Kriterium: "Wenn GEZE-Validierung zeigt, dass Mehrfach-Gruppen >10 %
> der Rechnungen betreffen: §8-Relevanz der Aggregation klarer."

**Ergebnis: 11,6 % der Rechnungen haben mindestens eine Mehrfach-Gruppe —
STOP-Kriterium formal ausgelöst.**

### EUR-Impact-Quantifizierung (Schritt 1 Nachklärung)

| Metrik | Wert | Anteil |
|--------|------|--------|
| Dinas Gesamt-Fracht (792 Positionen) | 49.665 EUR | — |
| Fracht in Mehrfach-Gruppen (56 Positionen) | 4.242 EUR | **8,54 %** |
| Geschätzte EUR der 33 „eingesparten" Positionen | 2.500 EUR | **5,03 %** |
| Davon im Vergleichs-Sheet `geze_dinas_vergleich.xlsx` | 2.897 EUR | **18,9 % des Sheets** |

Der Anteil von 8,54 % am Dinas-Gesamtvolumen ist **nicht vernachlässigbar**
(Grenzwert war implizit ~5 %). Das Sheet `geze_dinas_vergleich.xlsx` enthält
78 von 149 Zeilen aus Multi-Group-RNs (52 % der Zeilen, 18,9 % des Volumens).

### Spot-Check: Überschneidung mit bestehenden GEZE-Findings

**Ergebnis: Keine Überschneidung mit aktiven Findings.**

Die bestehenden GEZE-Findings stammen ausschließlich aus:
- `build_9b1_geze_calculator_test.py` — Unit-Tests gegen DLV (keine Dinas-
  Daten beteiligt)
- `build_9b3_geze_phase_rollout.py` — Cluster-Phase-Statistik (keine
  Einzel-Sendungs-§8-Funde)
- Gate-6 retroaktiv: kein `rn_level_adjustment` bei GEZE (§7 AUDIT_METHODOLOGY)

Das Explorer-Sheet `geze_dinas_vergleich.xlsx` ist kein offizielles Findings-
Dokument — es existiert als Vorarbeit ohne aktiven Pass-Rate-Nachweis.

**Die 15 Multi-Group-RNs berühren keine bestehenden §8-Einträge oder
reportierten Findings.** Der 8,54 %-Anteil ist latent und wird erst aktiv,
wenn Etappe 9b.2 (GEZE BI-Vergleich) gestartet wird.

### Entscheidung: GEZE-Zwischenstand-Eintrag anpassen?

**Nein — kein Revisionsbedarf für bestehende GEZE-Dokumente.**

Begründung:
1. Keine aktiven Pass-Rate-Berechnungen auf Dinas-Basis für GEZE
2. Keine reportierten §8-Findings, die Dinas-Einzelsendungs-Vergleich voraussetzen
3. Der 8,54 %-Anteil wird als latentes Risiko in §5 dokumentiert

Revisionsbedarf entsteht erst, wenn Etappe 9b.2 gestartet wird.

### Methodische Einordnung

Die Mehrfach-Gruppen entstehen aus Sammelrechnungen (mehrere Abholtermine
gleicher Empfänger-PLZ auf einer Rechnung). Unter der aktuellen Dinas-Aggregation
pro `rechnung_nr` (wie in `dinas_cluster.py`) werden diese in einer Cluster-Einheit
erfasst. Die v1.9-Aggregation nach `(rechnung_nr, empf_plz, leistungsdatum)` ist
feingranularer — sie unterscheidet innerhalb einer Rechnung zwischen
unterschiedlichen Leistungsdaten.

### Empfehlung

> **Wenn Etappe 9b.2 (GEZE BI-Vergleich) gestartet wird:**
> 1. `filter_comparison_set()` für AX-Seite (is_sub via Mastersendung)
> 2. `dinas_rk_agg` aus `aggregate_dinas_per_invoice()` als Dinas-Vergleichsbasis
> 3. Die 15 Multi-Group-RNs gesondert markieren (`n_positionen > 1`)
> 4. Die 78 Vergleichszeilen im Explorer-Sheet neu aggregieren bevor Pass-Rate
>    berechnet wird (18,9 % des Volumens betroffen)
> 5. §8-Dokumentation der Mehrfach-Gruppen: "Dinas-Rechnung enthält ≥2 Positionen
>    mit gleichem Routing-Key — AX-Master-Matchingpflicht gemäß v1.9 §2e"

---

*Aktualisiert: 2026-04-24 (EUR-Impact-Quantifizierung und Spot-Check ergänzt)*
*Erstellt: 2026-04-24 | Kein Code-Eingriff in bestehende GEZE-Scripts.*
*Datenbasis: dinas_cache_406035.pkl (792 Positionen, 129 Rechnungen)*
