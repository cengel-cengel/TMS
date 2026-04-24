# GEZE v1.9.4 — Cluster-Report: PRE-Dinas × POST-AX

**Stand:** 2026-04-24 | **KNR:** 406035 | **Methodik:** v1.9.4 §2e Rule F
**Periodenversatz:** Dinas PRE (2024-09-25–2025-08-15) × AX POST (2025-09-26–2026-03-30)

---

## §1 Methodik

**Vergleichslogik (Option B — Periodenversatz strukturell):**
Der Periodenversatz ist die Kernfrage des Audits. Dinas = PRE-System (vor Migration),
AX = POST-System (nach Migration). Jede Seite wird gegen den periodenkorrekten DLV-Tarif
bewertet. Ein Periodenversatz ist kein Datenfehler, sondern dokumentiert ob dieselbe Lane
vor und nach der Migration korrekt abgerechnet wurde.

**Cluster-Key:** `(Empf-Land, Empf-PLZ, Tarifgruppe, Gewichtsklasse)`
**Billing-Axis:** kg (GEZE-Tarif ist gewichtsbasiert)
**Stichprobe:** Top-5 AX by Δ aufsteigend (schlechteste zuerst) × Top-5 Dinas by kg-Nähe zum AX-Median
**DLV-Soll:** GEZECalculator.calculate(plz, land, tonnage_kg) — berechnet für AX einzeln pro Zeile
(Display); für Gruppen-Pass/Fail: DLV(Σ Tonnage pro RN×Land×PLZ-Gruppe)

**Vier Root-Cause-Muster (v1.9.4 §2e):**

| Muster | Dinas-Δ | AX-Δ | Diagnose |
|--------|---------|------|----------|
| M1 | ≈ 0 | ≈ 0 | Korrekt (oder kein Scope) |
| M2 | ≈ 0 | < 0 | AX-Konfigurationsfehler — Dinas war korrekt |
| M3 | < 0 | < 0 | Tarifproblem beidseitig (oder Dinas-Datenqualität) |
| M4 | < 0 | ≈ 0 | Migration hat Unterfakturierung behoben |

**Hinweis Dinas-Datenqualität:** Der PRE-Cache enthält Korrekturrechnungen (negative
Fracht-Werte) und Anpassungspositionen (unplausibel niedrige/hohe Beträge). Die M3-
Klassifikation ist daher vorläufig — finale Bewertung erfordert manuelle Prüfung der
Dinas-Anomalien.

---

## §2 Cluster-Übersicht (alle 14 Muster-B-Gruppen)

Scope: 14 Muster-B-Gruppen aus 1.098 beurteilbaren Gruppen (POST, ~is_sub-Filter).
Gesamt-Δ Muster-B: −1.778 EUR. Von 14 Gruppen haben 5 passende PRE-Dinas-Einträge.

| RN | Land | PLZ | Zone | GK | n_AX | Σ Fracht | Σ DLV-Soll | Δ | n_Din | Muster |
|----|------|-----|------|----|------|----------|-----------|---|-------|--------|
| 2578458 | GB | WS13 8SY | geze_gb_zone1 | <100 kg | 27 | 1.479,91 | 2.447,20 | −967,29 | 0 | n/a |
| 4251011138 | FR | 59273 | geze_fr_zone4 | 100–300 kg | 4 | 2.348,90 | 2.560,48 | −211,58 | 3 | **M3** |
| 2573273 | ES | 38639 | geze_es_zone7 | <100 kg | 1 | 24,02 | 165,61 | −141,59 | 0 | n/a |
| 2586869 | FR | 81000 | geze_fr_zone6 | 1000–2000 kg | 1 | 808,44 | 891,65 | −83,21 | 0 | n/a |
| 2573273 | FR | 77164 | geze_fr_zone2 | 100–300 kg | 4 | 225,63 | 294,65 | −69,02 | 3 | **M3** |
| 2563945 | AT | 8055 | geze_at_zone7 | 100–300 kg | 4 | 213,03 | 265,50 | −52,47 | 0 | n/a |
| 4251011138 | FR | 57600 | geze_fr_zone3 | <100 kg | 1 | 29,46 | 75,70 | −46,24 | 3 | **M3** |
| 4251017635 | IT | 10070 | geze_it_zone3 | <100 kg | 1 | 17,92 | 53,87 | −35,95 | 0 | n/a |
| 2557006-2 | IT | 20871 | geze_it_zone2 | 300–500 kg | 1 | 117,82 | 149,36 | −31,54 | 5 | **M3** |
| 2582348 | IT | 16138 | geze_it_zone3 | <100 kg | 5 | 222,54 | 253,38 | −30,84 | 0 | n/a |
| 2573273 | ES | 36400 | geze_es_zone5 | <100 kg | 2 | 107,54 | 137,28 | −29,74 | 1 | **M3** |
| 2582348 | IT | 16152 | geze_it_zone3 | <100 kg | 1 | 27,32 | 53,87 | −26,55 | 0 | n/a |
| 2563945 | FR | 40000 | geze_fr_zone6 | 500–1000 kg | 2 | 603,00 | 629,40 | −26,40 | 1 | **M3** |
| 2582348 | IT | 10070 | geze_it_zone3 | <100 kg | 1 | 35,95 | 53,87 | −17,92 | 0 | n/a |

**Muster-Verteilung:** M2 = 0 | M3 = 5 | M4 = 0 | n/a (kein PRE-Dinas) = 9

**Rang 1 (GB/WS13 8SY, −967 EUR):** Bekanntes Aggregationsartefakt (9b4). n_pos=27
entspricht dem bekannten Muster. Kein PRE-Dinas im Cache. → Bereits klassifiziert.

---

## §3 Beispiel-Cluster 1 — FR/59273

**RN:** 4251011138 | **Zone:** geze_fr_zone4 | **GK:** 100–300 kg (Median AX)
**AX-POST:** n=4 | Σ Fracht: 2.348,90 EUR | Σ DLV-Soll: 2.560,48 EUR | **Δ: −211,58 EUR**
**Dinas-PRE:** n=3 | Σ Fracht: 2.354,68 EUR | Σ DLV-Soll: 4.210,86 EUR | Δ: −1.856,18 EUR
**Klassifikation: M3 (vorläufig)** — beide Seiten negativ, aber Dinas-Daten stark anomal

> Hinweis: Zwei Dinas-Positionen (7135 kg, nur 20,32 EUR Fracht) sind Anpassungsbuchungen,
> keine realen Sendungen. Dinas-Δ-Summe durch diese Einträge verzerrt.

**AX-POST — Top-5 by Δ aufsteigend (POST 2025-10):**

| Identifier | Datum | kg | LDM | Stp | Vol | Fracht | Diesel | Maut | NK_Total | Gesamt | DLV-Soll | Δ |
|------------|-------|----|-----|-----|-----|--------|--------|------|----------|--------|----------|---|
| 4251011138 | 2025-10-22 | 9952 | 0,00 | 0,00 | 19,400 | 2.072,15 | 41,44 | 0,00 | 0,00 | 2.113,59 | 2.642,00 | −569,85 |
| 4251011138 | 2025-10-22 | 213 | 0,00 | 0,00 | 0,340 | 44,35 | 0,89 | 0,00 | 0,00 | 45,24 | 220,77 | −176,42 |
| 4251011138 | 2025-10-16 | 46 | 0,00 | 0,00 | 0,120 | 85,22 | 1,70 | 0,00 | 0,00 | 86,92 | 85,22 | 0,00 |
| 4251011138 | 2025-10-30 | 108 | 0,00 | 0,00 | 0,450 | 147,18 | 2,94 | 0,00 | 0,00 | 150,12 | 147,18 | 0,00 |

**Dinas-PRE — Top-3 by kg-Nähe zum AX-Median (PRE 2025-02 bis 2025-05):**

| Identifier | Datum | kg | LDM | Stp | Vol | Fracht | Diesel | Maut | NK_Total | Gesamt | DLV-Soll | Δ |
|------------|-------|----|-----|-----|-----|--------|--------|------|----------|--------|----------|---|
| 03769532 | 26.05.25 | 175 | — | — | — | 2.314,04 | 46,28 | 0,00 | 0,00 | 2.360,32 | 147,18 | +2.166,86 |
| 03753283 | 03.03.25 | 7135 | — | — | — | 20,32 | 0,00 | 0,00 | 0,00 | 20,32 | 2.031,84 | −2.011,52 |
| 57019719 | 28.02.25 | 7135 | — | — | — | 20,32 | 0,00 | 0,00 | 0,00 | 20,32 | 2.031,84 | −2.011,52 |

**Beobachtung:** AX-Zeile (9952 kg, 2.072 EUR) vs. DLV-Soll 2.642 EUR → Δ −570 EUR.
Zeilen mit 46 kg und 108 kg sind exakt korrekt (Δ=0). Dinas-Einträge zeigen
Korrekturbuchungen (2× 7135 kg, 20 EUR) und eine anomale Hochrechnung (175 kg, 2.314 EUR) —
keine verwertbaren Benchmark-Vergleichswerte. M3-Zuordnung bleibt bis Klärung der
Dinas-Einträge vorläufig.

---

## §4 Beispiel-Cluster 2 — FR/77164

**RN:** 2573273 | **Zone:** geze_fr_zone2 | **GK:** 100–300 kg (Median AX)
**AX-POST:** n=4 | Σ Fracht: 225,63 EUR | Σ DLV-Soll: 294,65 EUR | **Δ: −69,02 EUR**
**Dinas-PRE:** n=3 | Σ Fracht: 187,18 EUR | Σ DLV-Soll: 812,88 EUR | Δ: −625,70 EUR
**Klassifikation: M3 (vorläufig)** — Dinas-Cache enthält 1 Kreditnote + Anpassungsbuchung

> Hinweis: Dinas enthält eine negative Fracht-Position (−72,58 EUR, Kreditnote) und
> eine Buchung mit unplausiblem Verhältnis (1073 kg, 41,72 EUR). Δ-Summe verzerrt.

**AX-POST — Top-4 by Δ aufsteigend (POST 2025-11):**

| Identifier | Datum | kg | LDM | Stp | Vol | Fracht | Diesel | Maut | NK_Total | Gesamt | DLV-Soll | Δ |
|------------|-------|----|-----|-----|-----|--------|--------|------|----------|--------|----------|---|
| 2573273 | 2025-11-21 | 118 | 0,00 | 0,00 | 0,330 | 29,77 | 0,00 | 0,00 | 0,00 | 29,77 | 128,26 | −98,49 |
| 2573273 | 2025-11-25 | 32 | 0,00 | 0,00 | 0,040 | 20,83 | 0,00 | 0,00 | 0,00 | 20,83 | 73,39 | −52,56 |
| 2573273 | 2025-11-27 | 198 | 0,00 | 0,00 | 0,300 | 101,64 | 0,00 | 0,00 | 0,00 | 101,64 | 128,26 | −26,62 |
| 2573273 | 2025-11-26 | 89 | 0,00 | 0,00 | 0,380 | 73,39 | 1,47 | 0,00 | 0,00 | 74,86 | 73,39 | 0,00 |

**Dinas-PRE — Top-3 by kg-Nähe zum AX-Median (PRE 2025-01 bis 2025-07):**

| Identifier | Datum | kg | LDM | Stp | Vol | Fracht | Diesel | Maut | NK_Total | Gesamt | DLV-Soll | Δ |
|------------|-------|----|-----|-----|-----|--------|--------|------|----------|--------|----------|---|
| 03773311 | 11.07.25 | 323 | — | — | — | −72,58 | 0,00 | 0,00 | 0,00 | −72,58 | 235,72 | −308,30 |
| 03773387 | 10.07.25 | 323 | — | — | — | 218,04 | 3,27 | 0,00 | 0,00 | 221,31 | 235,72 | −17,68 |
| 03749833 | 10.01.25 | 1073 | — | — | — | 41,72 | 0,00 | 0,00 | 0,00 | 41,72 | 341,44 | −299,72 |

**Beobachtung:** AX zeigt konsistente kleine Unterfakturierung: 3 von 4 Positionen negativ,
davon 118 kg mit nur 29,77 EUR (vs. DLV-Soll 128,26 → −98 EUR = 77 % Unterdeckung).
Eine Position ist exakt korrekt (Δ=0 bei 89 kg). Dinas-Kreditnote (03773311) und
Anpassungsbuchung (03749833) erschweren Muster-Bewertung. Der einzige verwertbare
Dinas-Vergleich (03773387: 323 kg, 218 EUR, Δ −17,68 EUR) zeigt ebenfalls leichte
Unterfakturierung → stützt M3-Einordnung. Weitere Prüfung empfohlen.

---

## §5 Beispiel-Cluster 3 — IT/20871

**RN:** 2557006-2 | **Zone:** geze_it_zone2 | **GK:** 300–500 kg (Median AX)
**AX-POST:** n=1 | Σ Fracht: 117,82 EUR | Σ DLV-Soll: 149,36 EUR | **Δ: −31,54 EUR**
**Dinas-PRE:** n=5 | Σ Fracht: 120,98 EUR | Σ DLV-Soll: 1.275,86 EUR | Δ: −1.154,88 EUR
**Klassifikation: M3 (vorläufig)** — Dinas stark anomal (Kreditnoten + Kleinstbeträge)

> Hinweis: Dinas-Cache enthält multiple Anomalien: Kreditnote (−44,52 EUR), sehr kleine
> Beträge (9,22 EUR auf 534 kg, 6,28 EUR auf 959 kg). Diese sind Korrekturbuchungen,
> keine Vergleichsbasis. Nur 03745429 (412 kg, 80 EUR) und 03763151 (901 kg, 70 EUR)
> könnten reale Sendungen sein — beide zeigen ebenfalls starke Unterdeckung.

**AX-POST — Einzelposition (POST 2025-10-01):**

| Identifier | Datum | kg | LDM | Stp | Vol | Fracht | Diesel | Maut | NK_Total | Gesamt | DLV-Soll | Δ |
|------------|-------|----|-----|-----|-----|--------|--------|------|----------|--------|----------|---|
| 2557006-2 | 2025-10-01 | 322 | 0,00 | 0,00 | 0,000 | 117,82 | 2,94 | 0,00 | 0,00 | 120,76 | 149,36 | −31,54 |

**Dinas-PRE — Top-5 by kg-Nähe (PRE 2024-12 bis 2025-04):**

| Identifier | Datum | kg | LDM | Stp | Vol | Fracht | Diesel | Maut | NK_Total | Gesamt | DLV-Soll | Δ |
|------------|-------|----|-----|-----|-----|--------|--------|------|----------|--------|----------|---|
| 03745056 | 31.12.24 | 412 | — | — | — | −44,52 | 0,00 | 0,00 | 0,00 | −44,52 | 186,70 | −231,22 |
| 03745429 | 08.01.25 | 412 | — | — | — | 80,00 | 0,00 | 0,00 | 0,00 | 80,00 | 186,70 | −106,70 |
| 57019897 | 30.04.25 | 534 | — | — | — | 9,22 | 0,00 | 0,00 | 0,00 | 9,22 | 208,26 | −199,04 |
| 03763151 | 16.04.25 | 901 | — | — | — | 70,00 | 0,00 | 0,00 | 0,00 | 70,00 | 347,10 | −277,10 |
| 57019897 | 30.04.25 | 959 | — | — | — | 6,28 | 0,00 | 0,00 | 0,00 | 6,28 | 347,10 | −340,82 |

**Beobachtung:** AX Einzelposition: 322 kg, 117,82 EUR, Δ −31,54 EUR (21 % Unterdeckung).
Dinas zeigt für diese Lane historisch dramatisch höhere Unterfakturierung: selbst die beste
Position (03745429: 412 kg, 80 EUR) ergibt Δ −107 EUR (57 % Unterdeckung). Falls Dinas-
Qualität valide ist, deutet dies auf eine systemische Unterfakturierung dieser IT-Zone2-Lane
im PRE-System hin, die sich im POST-System bei −21 % leicht verbessert hat → mögliches
Muster 4-Kandidat nach Dinas-Qualitätsklärung.

---

## §6 Muster-Häufigkeit und Bewertung

### §6.1 Muster-Häufigkeit

| Muster | Anzahl | EUR | Diagnose |
|--------|--------|-----|----------|
| M2 — AX-Konfigurationsfehler | 0 | 0 EUR | Kein Befund: Dinas war nirgends korrekt während AX falsch war |
| M3 — Tarifproblem beidseitig | 5 | −477 EUR | Vorläufig — Dinas-Datenqualität muss validiert werden |
| M4 — Migration behoben | 0 | 0 EUR | Möglich für IT/20871 nach Klärung |
| n/a — kein PRE-Dinas | 9 | −1.301 EUR | Kein Benchmark möglich (inkl. GB/WS-Artefakt) |

### §6.2 Kernaussage

**Kein Muster 2 identifiziert.** Das wäre der kritische Befund (AX nach Migration
schlechter als vorher). Alle 5 Cluster mit PRE-Dinas-Daten zeigen M3, d.h. beide
Systeme liefern Unterfakturierung auf diesen Lanes — oder die Dinas-Daten enthalten
unveräußerliche Korrekturbuchungen, die das Bild verzerren.

**9 von 14 Muster-B-Gruppen haben keinen PRE-Dinas-Benchmark.** Das ist die
zentrale Datenlücke dieser Analyse. POST-Dinas-PDFs (ab Sep 2025) würden hier
direkten Vergleich ermöglichen.

### §6.3 Dinas-Datenqualität

Alle 5 Dinas-Cluster enthalten Anomalien:
- Kreditnoten (negative Fracht-Werte): 3 Positionen
- Kleinstbeträge auf hohen Tonnagen: 5 Positionen
- Anomal hohe Fracht auf kleiner Tonnage: 1 Position

**Empfehlung:** M3-Zuordnungen als vorläufig markieren. Vor finalem Bericht
manuelle Prüfung der jeweiligen Noerpel-Originalrechnungen für die 5 Dinas-Cluster.

### §6.4 Offener Punkt für EBM-Rollout

| Erkenntnis | Implikation |
|-----------|-------------|
| Kein M2 in GEZE | Bei EBM: M2-Befunde wären kritisch — gezielt nach Mustern suchen wo AX schlechter als Dinas |
| Dinas-Qualitätsproblem | Bei EBM: Kreditnoten/Anpassungsbuchungen aus Dinas-Cluster-Vergleich filtern |
| 9/14 ohne Dinas | Bei EBM: Dinas-Cache-Vollständigkeit vor Analyse prüfen |
| n=1-Gruppen anfällig | Einzelposition-Gruppen (n=1) bei GEZE: 7 von 14 — zu wenig für statistisch belastbaren Vergleich |

---

*Erstellt: 2026-04-24 | Grundlage: bi_top20_data.pkl POST + dinas_cache_406035.pkl PRE*
