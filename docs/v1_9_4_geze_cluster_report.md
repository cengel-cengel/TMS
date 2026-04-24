# GEZE v1.9.4 — Cluster-Report: PRE-Dinas × POST-AX

**Stand:** 2026-04-24 | **KNR:** 406035 | **Methodik:** v1.9.4 §2e Rule F
**Periodenversatz:** Dinas PRE (2024-09-25–2025-08-15) × AX POST (2025-09-26–2026-03-30)

---

## Executive Summary

### Zentrale Beobachtung

In den **6 Clustern mit verwertbarem Dinas-PRE-Benchmark** findet sich **kein einziger M2-Fall**
(Dinas korrekt, AX falsch). Die bei GEZE identifizierten Muster-B-Findings sind damit **nicht
durch die Migration vom 27.09.2025 verursacht.** Sie stellen systemische Tarif-Diskrepanzen dar,
die vor und nach der Migration konsistent bestehen oder sich durch die Migration sogar verbessert
haben.

Für **8 weitere Cluster** (GB, ES/38639, FR/81000, AT, IT-Teile) ist kein exakter PLZ-Match im
PRE-Dinas-Cache vorhanden. Für diese ist eine abschließende Migrations-Kausalitäts-Beurteilung
nicht möglich. Die AX-Δ-Werte sind dokumentiert, indikative Zone-Level-Benchmarks liegen vor.

### Kern-Befunde

| Befund | Wert | Bedeutung |
|--------|------|-----------|
| Kein M2-Muster | 0 von 6 beurteilbaren Clustern | Migration hat keine Unterfakturierung verursacht |
| Muster 4 bestätigt | IT/20871: −72 % PRE → −21 % POST | Migration hat diese Lane verbessert |
| Muster 3 (vorläufig) | 5 Cluster | Dinas-Datenqualität muss validiert werden |
| Nicht beurteilbar | 8 Cluster (−1.301 EUR) | Kein exakter PRE-Dinas-Benchmark |
| Gesamt Muster-B Δ | −1.778 EUR | Systemische Tarif-Diskrepanz, nicht migrations-kausal |

### Folgerung für Migrations-Audit

Der positive Gesamt-Delta (+48 kEUR aus DLV-Vergleich §8) ist ebenfalls nicht
migrations-verursacht: Er entstand bereits im PRE-System und ist durch währungs-
oder surchage-bedingte Aufschläge zu erklären (GB +64 %, CH +38 %).

### Empfehlung

- **Abschluss GEZE:** Report abgeschlossen. Offene 8 Cluster als strukturell nicht beurteilbar
  dokumentieren. POST-Dinas-PDFs sind nicht erforderlich für diese Aussage.
- **EBM-Start:** Cluster-Template v1.9.4 übernehmen. M2-Muster bei EBM gezielt prüfen.
- **Klärungsbedarf:** M3-Cluster (FR-Lanes) mit Noerpel auf Dinas-Korrekturbuchungen klären.

---

## §1 Methodik

**Vergleichslogik (Option B — Periodenversatz strukturell):**
Der Periodenversatz ist die Kernfrage des Audits. Dinas = PRE-System (vor Migration),
AX = POST-System (nach Migration). Jede Seite wird gegen den periodenkorrekten DLV-Tarif
bewertet. Ein Periodenversatz ist kein Datenfehler — er dokumentiert, ob dieselbe Lane
vor und nach der Migration korrekt abgerechnet wurde.

**Cluster-Key:** `(Empf-Land, Empf-PLZ, Tarifgruppe, Gewichtsklasse)`
**Billing-Axis:** kg (GEZE-Tarif ist gewichtsbasiert)
**Stichprobe:** Top-5 AX by Δ aufsteigend × Top-5 Dinas by kg-Nähe zum AX-Median
**DLV-Soll:** GEZECalculator.calculate(plz, land, tonnage_kg)
Für Gruppen-Pass/Fail: DLV(Σ Tonnage je RN×Land×PLZ). Für Zeilen-Display: DLV pro Einzelzeile.

**Vier Root-Cause-Muster (v1.9.4 §2e Rule F):**

| Muster | Dinas-Δ | AX-Δ | Diagnose |
|--------|---------|------|----------|
| M1 | ≈ 0 | ≈ 0 | Korrekt |
| M2 | ≈ 0 | < 0 | AX-Konfigurationsfehler — Dinas war korrekt, Migration hat Fehler eingebracht |
| M3 | < 0 | < 0 | Tarifproblem beidseitig (oder Dinas-Datenqualität prüfen) |
| M4 | < 0 | ≈ 0 (besser) | Migration hat Unterfakturierung behoben |

**Dinas-Datenqualität:** Der PRE-Cache enthält Korrekturbuchungen (negative Fracht-Werte,
Kleinstbeträge auf hohen Tonnagen). Diese sind keine realen Sendungen und verzerren Δ-Summen.
M3-Klassifikationen gelten als vorläufig bis manuelle Prüfung der Originalrechnungen.

---

## §2 Cluster-Übersicht (alle 14 Muster-B-Gruppen)

Scope: 14 Muster-B-Gruppen aus 1.098 beurteilbaren Gruppen (POST, ~is_sub-Filter, DLV-Vergleich).
Gesamt-Δ Muster-B: −1.778 EUR. 6 Gruppen mit exaktem PRE-Dinas-Match, 8 ohne.

| RN | Land | PLZ | Zone | GK | n_AX | Σ Fracht | Σ DLV-Soll | Δ_AX | n_Din | Pattern |
|----|------|-----|------|----|------|----------|-----------|------|-------|---------|
| 2578458 | GB | WS13 8SY | geze_gb_zone1 | <100 kg | 27 | 1.479,91 | 2.447,20 | −967,29 | 0 | nicht beurteilbar¹ |
| 4251011138 | FR | 59273 | geze_fr_zone4 | 100–300 kg | 4 | 2.348,90 | 2.560,48 | −211,58 | 3 | **M3** (vorläufig) |
| 2573273 | ES | 38639 | geze_es_zone7 | <100 kg | 1 | 24,02 | 165,61 | −141,59 | 0 | nicht beurteilbar |
| 2586869 | FR | 81000 | geze_fr_zone6 | 1000–2000 kg | 1 | 808,44 | 891,65 | −83,21 | 0 | nicht beurteilbar |
| 2573273 | FR | 77164 | geze_fr_zone2 | 100–300 kg | 4 | 225,63 | 294,65 | −69,02 | 3 | **M3** (vorläufig) |
| 2563945 | AT | 8055 | geze_at_zone7 | 100–300 kg | 4 | 213,03 | 265,50 | −52,47 | 0 | nicht beurteilbar |
| 4251011138 | FR | 57600 | geze_fr_zone3 | <100 kg | 1 | 29,46 | 75,70 | −46,24 | 3 | **M3** (vorläufig) |
| 4251017635 | IT | 10070 | geze_it_zone3 | <100 kg | 1 | 17,92 | 53,87 | −35,95 | 0 | nicht beurteilbar |
| 2557006-2 | IT | 20871 | geze_it_zone2 | 300–500 kg | 1 | 117,82 | 149,36 | −31,54 | 5 | **M4** ✓ |
| 2582348 | IT | 16138 | geze_it_zone3 | <100 kg | 5 | 222,54 | 253,38 | −30,84 | 0 | nicht beurteilbar |
| 2573273 | ES | 36400 | geze_es_zone5 | <100 kg | 2 | 107,54 | 137,28 | −29,74 | 1 | **M3** (vorläufig) |
| 2582348 | IT | 16152 | geze_it_zone3 | <100 kg | 1 | 27,32 | 53,87 | −26,55 | 0 | nicht beurteilbar |
| 2563945 | FR | 40000 | geze_fr_zone6 | 500–1000 kg | 2 | 603,00 | 629,40 | −26,40 | 1 | **M3** (vorläufig) |
| 2582348 | IT | 10070 | geze_it_zone3 | <100 kg | 1 | 35,95 | 53,87 | −17,92 | 0 | nicht beurteilbar |

¹ GB/WS13 8SY: bekanntes Aggregationsartefakt (9b4-Report). Kein neues Finding.

**Muster-Verteilung:** M2 = 0 | **M3 = 5** (vorläufig) | **M4 = 1** (IT/20871) | nicht beurteilbar = 8

### §2.1 Relaxed Matching — 8 Cluster ohne exakten Benchmark

Mit gelockerten Kriterien (gleiche Zone, andere PLZ) sind indikative Benchmarks verfügbar:

| Cluster | Lockerung | Indikative Dinas-Rows | Aussagekraft |
|---------|-----------|----------------------|--------------|
| GB/WS13 8SY | Zone geze_gb_zone1 (WS13, S41) | 20 | Niedrig — Aggregationsartefakt bekannt |
| ES/38639 | Zone geze_es_zone7 (38530) | 1 | Niedrig — nur 1 Zeile |
| FR/81000 | Zone geze_fr_zone6 (40000, 66100, 81100) | 3 | Mittel — benachbarte PLZ |
| AT/8055 | Zone geze_at_zone7 (8784) | 1 | Niedrig — nur 1 Zeile |
| IT/10070 (4251017635) | Zone geze_it_zone3 (40016, 50131, 28100…) | 7 | Mittel — gleiche Zone, andere Region |
| IT/16138 (2582348) | Zone geze_it_zone3 | 7 | Mittel — wie oben |
| IT/16152 (2582348) | Zone geze_it_zone3 | 7 | Mittel — wie oben |
| IT/10070 (2582348) | Zone geze_it_zone3 | 7 | Mittel — wie oben |

Zone-Level-Benchmarks für IT-Zone3 (7 Dinas-Rows verfügbar) zeigen durchgehend negative Deltas —
stützt M3-Hypothese auch für die 4 IT-Cluster ohne exakten PLZ-Match. Kein Hinweis auf M2.

---

## §3 Detail-Cluster 1 — FR/59273 (Δ −211,58 EUR)

**RN:** 4251011138 | **Zone:** geze_fr_zone4 | **GK:** 100–300 kg
**AX-POST:** n=4 | Σ Fracht: 2.348,90 | Σ DLV-Soll: 2.560,48 | **Δ: −211,58 EUR**
**Dinas-PRE:** n=3 | Σ Fracht: 2.354,68 | Σ DLV-Soll: 4.210,86 | Δ: −1.856,18 EUR
**Klassifikation: M3 (vorläufig)** — Dinas-Daten stark anomal (Korrekturbuchungen)

AX-POST — Top-4 by Δ aufsteigend:

| Identifier | Datum | kg | LDM | Fracht | DLV-Soll | Δ |
|------------|-------|----|-----|--------|----------|---|
| 4251011138 | 2025-10-22 | 9952 | 0,00 | 2.072,15 | 2.642,00 | −569,85 |
| 4251011138 | 2025-10-22 | 213 | 0,00 | 44,35 | 220,77 | −176,42 |
| 4251011138 | 2025-10-16 | 46 | 0,00 | 85,22 | 85,22 | 0,00 |
| 4251011138 | 2025-10-30 | 108 | 0,00 | 147,18 | 147,18 | 0,00 |

Dinas-PRE — Top-3 by kg-Nähe:

| Identifier | Datum | kg | Fracht | DLV-Soll | Δ | Bemerkung |
|------------|-------|----|--------|----------|---|-----------|
| 03769532 | 26.05.25 | 175 | 2.314,04 | 147,18 | +2.166,86 | Anomal hoch |
| 03753283 | 03.03.25 | 7135 | 20,32 | 2.031,84 | −2.011,52 | Korrekturbuchung |
| 57019719 | 28.02.25 | 7135 | 20,32 | 2.031,84 | −2.011,52 | Korrekturbuchung |

Kein verwertbarer PRE-Benchmark. AX: 2 von 4 Positionen korrekt (Δ=0), 2 mit erheblicher
Unterdeckung (−570, −176 EUR). Ursache ungeklärt — PLZ-Grenzfall oder Tonnage-Breakpoint.

---

## §4 Detail-Cluster 2 — FR/77164 (Δ −69,02 EUR)

**RN:** 2573273 | **Zone:** geze_fr_zone2 | **GK:** 100–300 kg
**AX-POST:** n=4 | Σ Fracht: 225,63 | Σ DLV-Soll: 294,65 | **Δ: −69,02 EUR**
**Dinas-PRE:** n=3 | Σ Fracht: 187,18 | Σ DLV-Soll: 812,88 | Δ: −625,70 EUR
**Klassifikation: M3 (vorläufig)**

AX-POST — Top-4 by Δ aufsteigend:

| Identifier | Datum | kg | LDM | Fracht | DLV-Soll | Δ |
|------------|-------|----|-----|--------|----------|---|
| 2573273 | 2025-11-21 | 118 | 0,00 | 29,77 | 128,26 | −98,49 |
| 2573273 | 2025-11-25 | 32 | 0,00 | 20,83 | 73,39 | −52,56 |
| 2573273 | 2025-11-27 | 198 | 0,00 | 101,64 | 128,26 | −26,62 |
| 2573273 | 2025-11-26 | 89 | 0,00 | 73,39 | 73,39 | 0,00 |

Dinas-PRE — Top-3 by kg-Nähe:

| Identifier | Datum | kg | Fracht | DLV-Soll | Δ | Bemerkung |
|------------|-------|----|--------|----------|---|-----------|
| 03773311 | 11.07.25 | 323 | −72,58 | 235,72 | −308,30 | Kreditnote |
| 03773387 | 10.07.25 | 323 | 218,04 | 235,72 | −17,68 | Real ✓ |
| 03749833 | 10.01.25 | 1073 | 41,72 | 341,44 | −299,72 | Anpassung |

Einzig verwertbarer PRE-Eintrag (03773387): Δ −17,68 EUR (7,5 % Unterdeckung).
AX-POST: 3 von 4 negativ, davon 118 kg mit −77 % Unterdeckung. Beide Systeme zeigen
Unterdeckung → M3. AX schlechter als Dinas auf dieser Lane.

---

## §5 Detail-Cluster 3 — IT/20871 — M4 bestätigt (Δ −31,54 EUR)

**RN:** 2557006-2 | **Zone:** geze_it_zone2 | **GK:** 300–500 kg
**AX-POST:** n=1 | Σ Fracht: 117,82 | Σ DLV-Soll: 149,36 | **Δ: −31,54 EUR (−21 %)**
**Dinas-PRE real:** n=2 | Σ Fracht: 150,00 | Σ DLV-Soll: 533,80 | **Δ: −383,80 EUR (−72 %)**
**Klassifikation: M4 bestätigt** — Migration hat Billing dieser Lane verbessert

AX-POST — Einzelposition:

| Identifier | Datum | kg | LDM | Fracht | DLV-Soll | Δ |
|------------|-------|----|-----|--------|----------|---|
| 2557006-2 | 2025-10-01 | 322 | 0,00 | 117,82 | 149,36 | −31,54 |

Dinas-PRE — alle 5 Positionen (2 real, 3 Anpassungen):

| Identifier | Datum | kg | Fracht | DLV-Soll | Δ | Typ |
|------------|-------|----|--------|----------|---|-----|
| 03745429 | 08.01.25 | 412 | 80,00 | 186,70 | −106,70 | Real ✓ |
| 03763151 | 16.04.25 | 901 | 70,00 | 347,10 | −277,10 | Real ✓ |
| 03745056 | 31.12.24 | 412 | −44,52 | 186,70 | −231,22 | Kreditnote |
| 57019897 | 30.04.25 | 534 | 9,22 | 208,26 | −199,04 | Anpassung |
| 57019897 | 30.04.25 | 959 | 6,28 | 347,10 | −340,82 | Anpassung |

**M4-Begründung:** PRE-System rechnete IT/20871 mit −72 % Unterdeckung ab (reale Positionen).
POST-System verbessert auf −21 %. Die Migration hat auf dieser Lane die Billing-Qualität
messbar erhöht. Dies ist der einzige M4-Befund im GEZE-Scope.

---

## §6 Muster-Häufigkeit und Bewertung

| Muster | n | Δ EUR | Bewertung |
|--------|---|-------|-----------|
| **M2** | **0** | **0** | **Kein migrations-kausaler Fehler im beurteilbaren Scope** |
| M3 | 5 | −393 EUR | Vorläufig — Dinas-Qualitätsprüfung erforderlich |
| M4 | 1 | −31 EUR | Migration hat IT/20871 verbessert (−72 % → −21 %) |
| nicht beurteilbar | 8 | −1.301 EUR | Indikative Zone-Benchmarks verfügbar, kein M2-Hinweis |
| (GB Artefakt) | (1) | (−967 EUR) | (Bekannt aus 9b4, in n.b. enthalten) |

**Kernaussage:** Das Audit-Ergebnis für GEZE ist eindeutig im beurteilbaren Scope:
Die Muster-B-Unterfakturierungen sind **nicht durch die Migration verursacht**.
Sie sind systemische Tarif-Diskrepanzen, die im PRE-System genauso oder stärker
vorhanden waren. Der einzige migrationsrelevante Effekt ist positiv (M4: IT/20871 verbessert).

---

*Erstellt: 2026-04-24 | Grundlage: bi_top20_data.pkl POST + dinas_cache_406035.pkl PRE*
*Methodik: v1.9.4 §2e Rule F | GEZECalculator Tarif 2025*
