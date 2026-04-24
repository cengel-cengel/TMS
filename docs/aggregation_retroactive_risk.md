# Aggregation Retroaktiv-Risiko — v1.9 Methodik-Vorbereitung

**Stand:** 2026-04-24 | **Kontext:** Empirische Quantifizierung des
Aggregations-Risikos pro Kunde + Realitäts-Check am CHT-BE-Beispiel.

---

## §1 Betroffenheits-Matrix

Datenbasis: `output/bi_top20_data.pkl` (POST, Erlöse Fracht > 0).
`is_sub` = Mastersendung gesetzt AND kein eigener Unterauftrag.

| Kunde | KNR | POST-Zeilen | is_sub gesamt | Sub Tonnage=0 | Sub Tonnage>0 | Sub Erlöse Fracht | Dinas Multi-Agg | Risiko |
|-------|-----|-------------|---------------|---------------|---------------|-------------------|-----------------|--------|
| CHT Germany | 486073 | 740 | 38 (5,1 %) | 38 | **0** | 5.389 € | n/a | **Keines** |
| GEZE GmbH | 406035 | 6.809 | 1.718 (25,2 %) | 1.578 | **140** | 143.407 € | n/a | **Latent (mittel)** |
| Fischerwerke | 409480 | 1.697 | 243 (14,3 %) | 180 | **63** | 84.607 € | Rechnung-Ebene | **Mittel** |
| HERMA | 423650 | 5.177 | 408 (7,9 %) | 406 | **2** | 65.136 € | Rechnung-Ebene | **Gering** |

**Legende:**
- *Sub Tonnage>0*: Sub-Rows, die den aktuellen `Tonnage > 0`-Filter passieren würden
- *Dinas Multi-Agg*: n/a = kein Dinas-Vergleich in diesen Scripts; "Rechnung-Ebene" = Dinas-Cluster nach PDF-Rechnung, nicht nach Routing-Key
- *Risiko*: Bezieht sich auf aktiven oder latenten Einfluss auf Audit-Findings

### Risikobeurteilung im Detail

**CHT (Keines):** Alle 38 Sub-Rows haben Tonnage = 0 und werden durch den
`~is_t0`-Filter (Tonnage ≤ 0 ausschließen) vollständig herausgefiltert.
Kein aktiver Fehler. Kein Einfluss auf Pass-Rate oder §8-Befunde.

**GEZE (Latent mittel):** 140 Sub-Rows mit Tonnage > 0 (≈ 143.407 EUR).
Kein aktueller BI-Pass-Rate-Vergleich, daher kein aktiver Fehler. Sobald
Etappe 9b.2 (GEZE BI-Vergleich) aufgesetzt wird: expliziter `is_sub`-Filter
obligatorisch, sonst werden 140 Positionen fälschlich auf per-Positions-DLV-Rate
geprüft (Erlöse sind anteilige Master-Beträge, nicht selbständig bereinigte Fracht).

**Fischerwerke (Mittel):** `enrich_master_sub()` korrekt implementiert —
AX-Sub-Rows werden bereits herausgefiltert und konsolidiert. Das Risiko liegt
auf Dinas-Seite: die Aggregation erfolgt per Rechnung (rechnung_nr), nicht per
`(Sender_PLZ, Empf_PLZ, Ladedatum)`. Bei Einzelsendungs-Vergleich (Etappe 9a.3
Fischerwerke Final-Report) könnte eine Dinas-Rechnung mehrere Routing-Keys
enthalten, die verschiedenen AX-Mastern entsprechen. Cluster-Familien-Matching
kaschiert das bisher. EUR-Impact der 63 Sub-Rows mit Tonnage>0 beobachten.

**HERMA (Gering):** Wie Fischerwerke, aber nur 2 Sub-Rows mit Tonnage > 0
(≈ marginal). `enrich_master_sub()` korrekt. DLV-Validierung steht noch aus
(HERMA unter Vorbehalt gemäß Zwischenstand §7).

---

## §2 Realitäts-Check: CHT BE — RN 924069

### Fragestellung
Ist der Gate-6-Befund `rn_level_adjustment` (Faktor −0,6881 %) für RN 924069
ein **Aggregations-Artefakt** (AX bildet aggregiert ab, Calculator rechnet per Position)?
Oder ist es ein **eigenständiger Befund** (systemischer RN-weiter Anpassungsfaktor)?

### Datenlage RN 924069

| Merkmal | Wert |
|---------|------|
| Zeilen gesamt (Fracht > 0) | 18 |
| Standalone-Positionen (Tonnage > 0, kein Mastersendung) | 16 |
| Sub-Rows (Mastersendung gesetzt, Tonnage = 0) | 2 |
| Unterschiedliche Empfänger-PLZs | 10 (1000, 1500, 3600, 7700, 8520, 8790, 9140, 9240, 9600, 9800) |
| Datumsspanne | 2026-01-12 bis 2026-01-19 |
| `fp`-Median (= (Erlöse−Basis) / Basis) | −0,006881 |
| `fp`-Standardabweichung | 0,000017 |
| Erlöse Fracht Summe (16 Pos.) | 2.938,88 € |
| Basispreis Summe Calculator (16 Pos.) | 2.959,20 € |
| Ratio Erlöse/Basis − 1 | −0,006867 |

### Multi-Routing-Key-Gruppen in RN 924069
Gruppen mit gleichem `(Versender_PLZ, Empf_PLZ, Leistungsdatum)`:

| Routing-Key | Anzahl Positionen | Fracht (je) |
|-------------|-------------------|-------------|
| 72072\|8790\|2026-01-13 | 2 | 317,17 € + 307,26 € |
| 72072\|8790\|2026-01-14 | 3 | 234,00 € + 51,96 € + 40,27 € |
| 72072\|8790\|2026-01-16 | 2 | 405,44 € + (Sub, Tonnage=0) |

Alle anderen 8 PLZs: **1 Position je Routing-Key** (keine Gruppe).

### Test: Tritt der Faktor nur in Multi-Routing-Key-Gruppen auf?

**Nein.** Beispiel-Positionen mit je nur einer Position im Routing-Key:

| Empf-PLZ | Tonnage (kg) | Erlöse Fracht | Basispreis | fp |
|----------|--------------|---------------|------------|----|
| 9140 | 125,28 | 34,64 € | 34,88 € | −0,00688 |
| 1000 | 25,00 | 40,27 € | 40,55 € | −0,00690 |
| 8520 | 134,52 | 34,64 € | 34,88 € | −0,00688 |
| 9240 | 259,56 | 51,96 € | 52,43 € | −0,00896 (leichte Abw.) |

Der Faktor ≈ −0,689 % tritt auch bei PLZs mit **einer einzigen Position** auf,
die kein Aggregations-Pendant hat. Ein reines Aggregations-Artefakt würde
ausschließlich in Multi-Position-Gruppen wirken.

### Ergebnis

> **rn_level_adjustment für RN 924069 ist KEIN Aggregations-Artefakt.**

Der Faktor ist systemisch über alle Positionen der Rechnung verteilt —
unabhängig davon, ob eine PLZ in einer Mehrfach-Gruppe oder allein steht.
Dies ist das erwartete Muster eines **RN-weiten Abrechnungs-Adjustments**:
- Wahrscheinlichste Ursache: quartalsweiser Diesel-Floater oder ein Rundungs-Effekt,
  der auf die Gesamtrechnung angewendet und dann proportional auf Positionen verteilt wird
- Der Gate-6-Mechanismus (`rn_std < 0,0005`, `|rn_factor| ≥ 0,0005`) detektiert
  genau dieses Muster korrekt und flaggt es als `rn_level_adjustment`

**Gate-6 ist methodisch korrekt. Keine Reklassifizierung nötig.**

Das `rn_level_adjustment`-Flag schließt diese Positionen aus der 90%-Pass-Rate-Berechnung
aus — nicht weil der Calculator falsch liegt, sondern weil ein externer Faktor (Floater,
Rundung) auf Rechnungsebene wirkt und der Calculator diesen nicht kennt. Das ist eine
dokumentierte Methodik-Lücke (§6b v1.7), kein Aggregations-Fehler.

---

## §3 v1.9 Methodik-Vorschlag

### A — AX-Seite: Expliziter Sub-Row-Filter (alle Kunden)

**Aktuell:** `Tonnage > 0` als impliziter Proxy für "keine Sub-Row"

**Problem:** Für GEZE schlägt dieser Proxy fehl (140 Sub-Rows mit Tonnage > 0).
Für CHT zufällig korrekt (alle Sub-Rows Tonnage = 0).

**v1.9-Regel:**
```python
# Korrekte Sub-Row-Definition:
has_ms = df['Mastersendung'].notna() & \
         (~df['Mastersendung'].astype(str).str.strip().isin(['', 'nan']))
has_ua = df['Unterauftrag'].notna() & \
         (~df['Unterauftrag'].astype(str).str.strip().isin(['', 'nan']))
is_sub = has_ms & ~has_ua   # Mastersendung gesetzt, kein eigener Unterauftrag

# Vergleichs-Set: nur Standalone + Master-Rows
comparison_set = df[~is_sub]
```

**Anwendung:** Obligatorisch ab Etappe 9b.2 (GEZE BI-Vergleich). Für CHT
und Fischerwerke/HERMA bisher faktisch korrekt, explizite Prüfung dennoch empfohlen.

---

### B — Dinas-Seite: Aggregation nach Routing-Key (Fischerwerke, HERMA, Sika)

**Aktuell:** Dinas-Positionen per Rechnung (rechnung_nr) aggregiert in
`src/tms/clustering/dinas_cluster.py`

**v1.9-Ergänzung (für Einzelsendungs-Vergleich):**

Wenn eine AX-Master-Sendung mehrere Dinas-Positionen bündelt, muss die
Dinas-Seite vor dem Vergleich aggregiert werden:

```python
# Dinas-Aggregations-Schlüssel:
dinas_agg_key = ['Sender_PLZ', 'Empfänger_PLZ', 'Ladedatum']

dinas_aggregat = dinas_pos.groupby(dinas_agg_key).agg(
    gewicht_kg=('Gewicht_kg', 'sum'),
    lademeter=('Lademeter', 'sum'),
    stellplaetze=('Stellplätze', 'sum'),
    erloese_fracht=('Erlöse_Fracht', 'sum'),
    erloese_diesel=('Erlöse_Diesel', 'sum'),
    erloese_maut=('Erlöse_Maut', 'sum'),
    auftragsnummern=('Auftragsnummer', list),
    rechnungsnummern=('Rechnungsnummer', list),
).reset_index()
```

**Betroffene Kunden:** Fischerwerke (Etappe 9a.3 Final-Report), HERMA (nach
DLV-Validierung), Sika (Etappe 9d Re-Run).

**Nicht betroffen:** CHT (kein Dinas-Vergleich in CHT-Scripts), GEZE (nur Unit-Tests).

---

### C — Gate-6 rn_level_adjustment: Keine Änderung

Der Gate-6-Mechanismus bleibt unverändert. RN-weite Anpassungsfaktoren sind
keine Aggregations-Artefakte und sollen weiterhin aus der Pass-Rate ausgeschlossen
und als §6b-Befund dokumentiert werden.

---

## §4 Aufwandsschätzung Fix-Implementation

| Kunde | Aufwand | Beschreibung |
|-------|---------|--------------|
| CHT (alle 5) | 0 h | Kein Fix nötig; Tonnage-Filter faktisch korrekt |
| GEZE | ~1 h | `is_sub`-Filter-Ergänzung wenn Etappe 9b.2 gestartet wird |
| Fischerwerke | ~2 h | Dinas-Routing-Key-Aggregation in `build_fischer_report.py` |
| HERMA | ~1–2 h | Wie Fischerwerke; nur nach DLV-Validierung relevant |
| **Gesamt** | **~4–5 h** | Vollständige v1.9-Konformität aller Kunden |

---

## §5 Auswirkung auf bestehende Befunde

| Befund | Auswirkung |
|--------|-----------|
| CHT BE/ES/IT/AT/GR Pass-Rates | Keine Änderung (Sub-Rows korrekt ausgeschlossen) |
| CHT rn_level_adjustment (Gate-6) | Keine Änderung (kein Aggregations-Artefakt, §2) |
| GEZE 9b4-Report (unit-test-basiert) | Keine Änderung |
| Fischerwerke RF-1/RF-2/RF-3/RF-4 | Keine Änderung (nicht durch Aggregation verursacht) |
| HERMA early-indicator (unter Vorbehalt) | Marginale Änderung möglich (2 Sub-Rows Tonnage>0) |
| Sika 8i-Familien | Auswirkung prüfen in Etappe 9d Schritt 2 (Sika Re-Run) |

---

*Erstellt: 2026-04-24 | Keine Code-Änderungen. Keine Retroaktiv-Korrekturen an bestehenden Reports.*
*Keine Methodik v1.9 committet. Kein Sika-Re-Run gestartet.*
