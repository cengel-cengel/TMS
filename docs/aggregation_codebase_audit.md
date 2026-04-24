# Aggregation Codebase Audit — v1.9 Methodik-Vorbereitung

**Stand:** 2026-04-24 | **Zweck:** Empirische Prüfung, wie abgeschlossene Kunden
mit Dinas- und AX-Aggregation umgehen. Basis für v1.9-Methodik-Formulierung.

---

## Aggregations-Regel v1.9 (Referenz)

```
DINAS-Seite:  Aggregations-Schlüssel = (Sender_PLZ, Empfänger_PLZ, Ladedatum)
              → ein "virtuelles Aggregat" pro Schlüssel

AX-Seite:     Aggregations-Schlüssel = Master-Auftragsnummer
              ("zusammengefasst in" / Mastersendung-Feld)
              Master + alle Zeilen mit Mastersendung → dieses Masters werden gebündelt

Vergleich:    Dinas-Aggregat ↔ AX-Master-Aggregat
```

---

## Status pro Kunde

### CHT Germany (KNR 486073) — 5 Länder: BE, IT, ES, AT, GR

**Analyse-Typ:** AX vs. DLV (kein Dinas-Vergleich; CHT-Scripts prüfen nur,
ob AX-Erlöse mit DLV-Basispreisen übereinstimmen)

**Dinas-Aggregation:** n/a — Dinas-Daten nicht Teil der CHT-Analyse

**AX-Aggregation:**
- BE/IT/ES/AT: `Tonnage (eff.) > 0` als impliziter Filter in `build_9c2a/b/d_*.py`
- Alle 38 CHT-Sub-Rows (Mastersendung gesetzt, kein eigener Unterauftrag)
  haben `Tonnage = 0` → werden durch den `~is_t0`-Filter vollständig ausgeschlossen
- GR: `RNLevelCalculator` aggregiert Positionen explizit per RN → kein Sub-Row-Problem

**Vergleichs-Ebene:** Position-Ebene (BE/IT/ES/AT), RN-Ebene prorated (GR)

**Status:** `aggregation_korrekt_de_facto`

**Quell-Dateien:**
- `src/build_9c2a_cht_be_calculator_test.py` (Filter Zeile 110: `be[~be['is_t0']]`)
- `src/build_9c2b_cht_es_calculator_test.py`
- `src/build_9c2c_cht_gr_calculator_test.py` (RNLevelCalculator)
- `src/build_9c2d_cht_at_calculator_test.py`
- `src/tms/tariff/calculators/cht_be.py` u.a.

**Risiko:** Keines aktiv. Latentes Risiko: Falls ein zukünftiger CHT-Sub-Row
Tonnage > 0 erhält (z.B. durch AX-Konfigurationsänderung), würde der
`Tonnage > 0`-Proxy versagen. Explizite `is_sub`-Prüfung wäre robuster.

---

### GEZE GmbH (KNR 406035)

**Analyse-Typ:** Unit-Tests gegen DLV-Referenzwerte (kein BI-Pass-Rate-Vergleich,
kein Dinas-Vergleich)

**Dinas-Aggregation:** n/a

**AX-Aggregation:** n/a — kein BI-Daten-Vergleich in aktuellen GEZE-Scripts

**Vergleichs-Ebene:** Unit-Test (isolierte DLV-Lookup-Prüfung)

**Status:** `aggregation_nicht_anwendbar` (kein BI-Pass-Rate aktiv)

**Quell-Dateien:** `src/build_9b1_geze_calculator_test.py`

**Risiko:** **Latent, mittleres Volumen.**
In `bi_top20_data.pkl` (POST, Fracht > 0) hat GEZE 1.718 Sub-Rows (25,2% aller
GEZE-Zeilen), davon **140 mit Tonnage > 0** (≈ 143.407 EUR Erlöse Fracht).
Sobald ein BI-Pass-Rate-Vergleich für GEZE eingeführt wird (z.B. Etappe 9b.2),
müssen diese 140 Sub-Rows explizit über `is_sub`-Filter ausgeschlossen werden.
Ohne diesen Filter würden 140 Positionen fälschlich mit per-Positions-DLV-Rate
verglichen, obwohl ihre Erlöse anteilige Master-Beträge sind.

---

### Fischerwerke GmbH (KNR 409480)

**Analyse-Typ:** AX vs. Dinas (Cluster-Familien-Matching + Dinas-PDF-NK-Abgleich)

**Dinas-Aggregation:** Per Rechnung (`rechnung_nr` = Cluster-ID in
`src/tms/clustering/dinas_cluster.py`). **Nicht** nach `(Sender_PLZ, Empfänger_PLZ,
Ladedatum)`. Eine Dinas-Rechnung = ein Dinas-Cluster, unabhängig davon, ob die
Rechnung Positionen mit unterschiedlichen Routing-Keys enthält.

**AX-Aggregation:** `enrich_master_sub()` in `src/build_fischer_report.py`
(Zeilen 65–92) konsolidiert Sub-Rows korrekt in den Master:
- Sub-Erlöse werden auf den Master-Row summiert
- Sub-Rows werden aus dem Vergleichsdatensatz entfernt
→ AX-Seite nach v1.9-Regel korrekt implementiert

**Vergleichs-Ebene:** Auftragsnummer (nach Master/Sub-Konsolidierung),
dann Cluster-Familien-Matching auf `Land|PLZ2|GewichtsBand`-Ebene

**Status:** `aggregation_korrekt_ax_seite` / `aggregation_fehlt_dinas`

**Quell-Dateien:**
- `src/build_fischer_report.py` (`enrich_master_sub` Zeilen 65–92)
- `src/tms/clustering/dinas_cluster.py` (Dinas-Aggregation per rechnung_nr)

**Risiko:** Gering bis mittel. Das Cluster-Familien-Matching (auf `Land|PLZ2`-Ebene)
kaschiert bisher fehlende Dinas-Aggregation nach Routing-Key: Einzelne Dinas-Positionen
mit gleichem Schlüssel (Sender+Empf+Ladedatum) landen in derselben Familie und werden
statistisch aggregiert. Für den Einzelsendungs-Vergleich (Schritt 2 Etappe 9a.3)
wäre eine exakte Routing-Key-Aggregation auf Dinas-Seite notwendig.
Bekannte aktive §8-Findings: RF-1/RF-2/RF-3/RF-4 (nicht durch Aggregationsfehler verursacht).

---

### HERMA GmbH (KNR 423650)

**Analyse-Typ:** AX vs. Dinas (Cluster-Familien-Matching + Dinas-NK-Abgleich)

**Dinas-Aggregation:** Gleich wie Fischerwerke — per Rechnung, nicht per Routing-Key.

**AX-Aggregation:** `enrich_master_sub()` in `src/build_herma_report.py`
(Zeilen 64–92) — identische Implementierung wie Fischerwerke. Korrekt.

**Vergleichs-Ebene:** Auftragsnummer (nach Konsolidierung), Cluster-Familien

**Status:** `aggregation_korrekt_ax_seite` / `aggregation_fehlt_dinas`

**Quell-Dateien:**
- `src/build_herma_report.py` (`enrich_master_sub` Zeilen 64–92)

**Risiko:** Gering. Sub-Row-Zahlen: 408 is_sub gesamt, davon **nur 2 mit Tonnage > 0**
(65.136 EUR gesamt, aber 2 Positionen = vernachlässigbar). Dinas-Aggregation nach
Routing-Key fehlt formal, aber EUR-Auswirkung auf HERMA-Befunde voraussichtlich minimal.
HERMA-Analyse steht noch unter Vorbehalt (DLV-Validierung ausstehend).

---

## Gesamtübersicht

| Kunde | KNR | Dinas-Aggregation | AX-Aggregation | Status |
|-------|-----|-------------------|----------------|--------|
| CHT (BE/IT/ES/AT/GR) | 486073 | n/a | Tonnage>0-Filter (faktisch korrekt) | `aggregation_korrekt_de_facto` |
| GEZE | 406035 | n/a | n/a (nur Unit-Tests) | `aggregation_nicht_anwendbar` |
| Fischerwerke | 409480 | per Rechnung (nicht Routing-Key) | `enrich_master_sub` ✓ | `korrekt_ax / fehlt_dinas` |
| HERMA | 423650 | per Rechnung (nicht Routing-Key) | `enrich_master_sub` ✓ | `korrekt_ax / fehlt_dinas` |

---

## Fazit für v1.9

1. **Kein abgeschlossener Kunde hat einen aktiven Aggregations-Fehler**, der
   bestehende Audit-Findings verfälscht.

2. **GEZE** hat latentes Risiko (140 Sub-Rows, Tonnage > 0): expliziter `is_sub`-Filter
   muss vor jeder GEZE BI-Pass-Rate-Prüfung implementiert werden.

3. **Fischerwerke/HERMA**: AX-Seite korrekt durch `enrich_master_sub`. Dinas-Seite
   aggregiert per Rechnung, nicht per Routing-Key — formale v1.9-Lücke, aber im
   Cluster-Familien-Matching bisher ohne nachgewiesene Auswirkung.

4. **CHT-Gate-6 rn_level_adjustment** ist kein Aggregations-Artefakt
   (→ Realitäts-Check in `aggregation_retroactive_risk.md`).

---

*Erstellt: 2026-04-24 | Basis: empirische Codebase-Prüfung + bi_top20_data.pkl-Analyse*
*Keine Code-Änderungen vorgenommen. Kein Commit bestehender Reports.*
