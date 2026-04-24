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
STOP-Kriterium überschritten.**

Allerdings betreffen die Mehrfach-Gruppen nur **3,0 % aller Routing-Keys**
und **4,2 % aller Positionen** (33 von 792). Der EUR-Impact ist begrenzt:
Die größte Gruppe (RN 57019719, CY) hat 763,02 EUR Fracht — plausibel für
einen Zypern-Inbound mit mehreren Teillieferungen in einer Rechnung.

### Methodische Einordnung

Die Mehrfach-Gruppen entstehen aus Sammelrechnungen (mehrere Abholtermine
gleicher Empfänger-PLZ auf einer Rechnung). Unter der aktuellen Dinas-Aggregation
pro `rechnung_nr` (wie in `dinas_cluster.py`) werden diese korrekt in einer
Cluster-Einheit erfasst. Die v1.9-Aggregation nach `(rechnung_nr, empf_plz,
leistungsdatum)` ist feingranularer — sie unterscheidet innerhalb einer
Rechnung zwischen unterschiedlichen Leistungsdaten.

Für GEZE ist **kein aktiver BI-Pass-Rate-Vergleich** implementiert — der
Aggregationsfehler ist latent (vgl. `aggregation_codebase_audit.md`).
Die Mehrfach-Gruppen erhalten §8-Kandidaten-Status für Etappe 9b.2 (GEZE
BI-Vergleich), sobald dieser gestartet wird.

### Empfehlung

> **Wenn Etappe 9b.2 (GEZE BI-Vergleich) gestartet wird:**
> 1. `filter_comparison_set()` für AX-Seite verwenden (is_sub via Mastersendung)
> 2. `dinas_rk_agg` aus `aggregate_dinas_per_invoice()` als Dinas-Vergleichsbasis
> 3. Die 15 Rechnungen mit Mehrfach-Gruppen gesondert prüfen (manuell oder
>    automatisch mit n_positionen > 1 Flag)

---

*Erstellt: 2026-04-24 | Kein Code-Eingriff in bestehende GEZE-Scripts.*
*Datenbasis: dinas_cache_406035.pkl (792 Positionen, 129 Rechnungen)*
