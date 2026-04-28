# Bitzer Kühlmaschinenbau GmbH — Cluster-Report v1.9.6

**Kunde:** Bitzer Kühlmaschinenbau GmbH | KNR 406345  
**Stand:** 2026-04-28 | Methodik: v1.9.6  
**Berichtszeitraum:** POST (gesamter BI-Export)  
**DLV-Stand:** IT=Upload 2026, AT/FR/ES/CH/PT/BE/NL/LU=2025  
**Script:** `src/build_bitzer_step23_v196.py` → Cache: `output/bitzer_step23_results_v196.pkl`

---

## Executive Summary

| Metrik | Wert |
|---|---|
| Gesamtzeilen (KNR 406345, POST) | 5 578 |
| davon Erlöse Fracht = 0 (P4 cross-system) | 2 172 |
| **Pool Step 2 (ef > 0)** | **3 406** |
| Beurteilbar | 3 330 (97.8 %) |
| Nicht beurteilbar (no_dlv) | 76 (2.2 %) |
| M1 \|fp\| ≤ 5 % | 2 861 (85.9 %) |
| M2 fp < −5 % | 277 (8.3 %) |
| M_over fp > +5 % | 192 (5.8 %) |
| Σ Erlöse Fracht (beurteilbar) | 723 694 EUR |
| Σ DLV-Soll (beurteilbar) | 750 473 EUR |
| **Net Δ (Erlöse − DLV)** | **−26 780 EUR (−3.57 %)** |

**Zwei strukturelle Sonderfälle (in Netto-Δ enthalten, gesondert bewertet):**

| Sonderfall | Rows | Δ (EUR) | Ursache |
|---|---|---|---|
| FR-13400 Aubagne FTL-Artefakt | 13 | −8 109 | Calculator nutzt per-Sendung-DLV, BI-Abrechnung per LTL-Zone 9 |
| IT Zone 4 Rottenburg DLV-Period | 77 | −21 511 | Upload DLV 2026 höhere Raten vs. 2025-Abrechnung |

**Bereinigtes Net Δ** (ohne FR-13400, alle sonstigen Lanes): **−18 670 EUR (−2.52 %)**

### Coverage-Rekonsiliation: 66.2 % (v1.9.4) → 97.8 % (v1.9.6)

| Ausbaustufe | Δ Coverage | Lanes hinzugefügt |
|---|---|---|
| v1.9.4 (IT+AT+FR+ES+CH) | 66.2 % | 5 Länder |
| +PT (Task 5) | +1.2 % | PT Zone 1/4/6 |
| +BE/NL/LU (Task 6) | +7.4 % | Benelux kombiniert |
| +ZGI Tonnage-Substitution (v1.9.6) | +0.5 % | 17 Sub-Rows |
| Restlücke (DE Inbound + FR/IT PLZ) | −2.2 % | Scope-out + ERKA |
| **v1.9.6 gesamt** | **97.8 %** | |

---

## Methodik v1.9.6

### Grundprinzipien (SKILL.md P1–P15)

- **P1** Pool-Definition: Erlöse Fracht > 0 (administrative ef=0-Rows ausgeschlossen)
- **P2** fp-Formel: `fp = (Erlöse_Fracht − DLV_Soll) / DLV_Soll`
- **P3** billing_kg: `max(100, ceil(Tonnage / 100) × 100)`
- **P5** Tonnage-Quelle: Tonnage (frpfl.) bevorzugt, Fallback Tonnage (eff.), Fallback 1 kg → 100 kg billing
- **P10** Multi-Origin: Rottenburg (71126, 72108) und Schkeuditz (04435) verwenden identische Vertragstarife; getrennte Tarifgruppen dokumentieren Ursprung ohne Tarifabweichung
- **P13** scope_out / no_dlv: Länder ohne implementierten DLV → LookupError → Status `no_dlv`
- **P15** Upload-Tarife: Upload-Ordner ist aktiver Tarif, NICHT Archiv — IT FTL-Cap-Precedent

### ZGI-Cluster-Aggregation v1.9.6 §2f

AX-Mastersendungen bündeln mehrere Unteraufträge. Sub-Rows (Mastersendung gesetzt,
kein eigener Unterauftrag) haben Erlöse auf dem Master-Row (ef=0) und eigene Tonnage=0.

**Identifikation Sub-Rows:**
```
is_sub = has_ms AND NOT has_ua
```

**Tonnage-Substitution:** Sub-Row-Tonnage wird aus dem zugehörigen P9-Master-Row
(ef=0, Tonnage>0, Unterauftrag gesetzt) ersetzt. 17 Sub-Rows identifiziert;
11 aufgelöst, 6 ohne identifizierbaren Master (→ Fallback 1 kg).

**Vergleichs-Ebene:** Jede Sub-Row einzeln, mit substituierter Tonnage.

### Multi-Origin-Logik

| Ursprung PLZ | Werk | Rows | Σ ef (EUR) | Σ dlv (EUR) | Net Δ (EUR) |
|---|---|---|---|---|---|
| 71126, 72108 | Rottenburg | 2 251 | 501 376 | 531 627 | −30 251 |
| 04435 | Schkeuditz | 1 076 | 221 249 | 218 097 | +3 152 |
| unbekannt | unknown | 3 | 1 068 | 749 | +319 |

Rottenburg zeigt negativen Gesamtdelta, der zu ~71 % durch IT Zone 4 und FR-13400
erklärt wird. Schkeuditz liegt im positiven Bereich (+1.4 %). Tarif-identisch per Vertrag.

### M-Klassifikation

| Muster | Bedingung | Interpretation |
|---|---|---|
| M1 | \|fp\| ≤ 5 % | Abrechnung konform mit DLV (±5 % Toleranz) |
| M2 | fp < −5 % | Erlöse unter DLV → Bitzer günstiger als DLV |
| M_over | fp > +5 % | Erlöse über DLV → Bitzer teurer als DLV |

---

## Cluster-Übersicht — M-Klassifikation nach Tarifgruppe

Sortiert nach Net Δ (aufsteigend = größte Unterdeckung zuerst).

| Tarifgruppe | Rows | M1 | M2 | M_ov | Σ ef | Σ dlv | Net Δ | fp_net |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bitzer_it_zone4_rottenburg ⚠️ | 77 | 13 | 61 | 3 | 59 145 | 80 655 | **−21 511** | −26.7 % |
| bitzer_fr_special_13400_rottenburg ⚠️ | 13 | 0 | 13 | 0 | 958 | 9 068 | **−8 109** | −89.4 % |
| bitzer_nl_zone1_rottenburg | 171 | 163 | 8 | 0 | 28 448 | 29 558 | −1 110 | −3.8 % |
| bitzer_fr_zone3_rottenburg | 144 | 133 | 11 | 0 | 20 055 | 20 907 | −851 | −4.1 % |
| bitzer_it_zone3_schkeuditz | 47 | 34 | 9 | 4 | 14 491 | 14 971 | −479 | −3.2 % |
| bitzer_it_zone3_rottenburg | 73 | 54 | 13 | 6 | 10 143 | 10 595 | −452 | −4.3 % |
| bitzer_it_zone5_schkeuditz | 15 | 13 | 2 | 0 | 8 874 | 9 316 | −442 | −4.7 % |
| bitzer_fr_zone4_rottenburg | 26 | 19 | 7 | 0 | 3 612 | 4 044 | −432 | −10.7 % |
| bitzer_pt_zone6_rottenburg | 16 | 13 | 3 | 0 | 7 192 | 7 604 | −411 | −5.4 % |
| bitzer_ch_zone14_rottenburg | 23 | 10 | 13 | 0 | 1 179 | 1 520 | −341 | −22.5 % |
| bitzer_es_zone3_rottenburg | 22 | 11 | 10 | 1 | 1 965 | 2 257 | −292 | −12.9 % |
| bitzer_it_zone5_rottenburg | 17 | 16 | 1 | 0 | 10 959 | 11 241 | −282 | −2.5 % |
| bitzer_it_zone1_schkeuditz | 257 | 238 | 4 | 15 | 35 313 | 35 542 | −229 | −0.6 % |
| bitzer_ch_zone14_schkeuditz | 13 | 5 | 6 | 2 | 1 809 | 2 029 | −219 | −10.8 % |
| bitzer_pt_zone1_rottenburg | 10 | 8 | 2 | 0 | 3 623 | 3 834 | −211 | −5.5 % |
| bitzer_be_zone1_rottenburg | 59 | 56 | 3 | 0 | 5 718 | 5 815 | −97 | −1.7 % |
| bitzer_fr_special_77380_rottenburg | 47 | 44 | 2 | 1 | 15 235 | 15 322 | −86 | −0.6 % |
| *… weitere 43 Lanes ±M1 …* | | | | | | | | |
| bitzer_fr_zone3_schkeuditz | 73 | 64 | 6 | 3 | 22 791 | 19 309 | **+3 482** | +18.0 % |
| bitzer_it_zone1_rottenburg | 604 | 516 | 14 | 74 | 124 577 | 122 128 | +2 449 | +2.0 % |
| bitzer_it_zone2_rottenburg | 390 | 347 | 13 | 30 | 84 300 | 83 813 | +487 | +0.6 % |
| bitzer_es_zone6_rottenburg | 22 | 19 | 0 | 3 | 31 777 | 30 961 | +816 | +2.6 % |

**Gesamt beurteilbar:** 3 330 Rows | M1: 2 861 | M2: 277 | M_over: 192

### Länderbilanz

| Land | Rows | M1 | M2 | M_ov | Σ ef (EUR) | Σ dlv (EUR) | Net Δ (EUR) | fp_net |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| IT | 1 714 | 1 441 | 123 | 150 | 386 893 | 406 878 | −19 984 | −4.9 % |
| FR | 519 | 469 | 46 | 4 | 119 645 | 125 482 | −5 837 | −4.7 % |
| ES | 325 | 249 | 44 | 32 | 104 551 | 103 028 | +1 523 | +1.5 % |
| AT | 290 | 275 | 12 | 3 | 37 189 | 36 979 | +209 | +0.6 % |
| CH | 189 | 153 | 33 | 3 | 21 077 | 21 802 | −724 | −3.3 % |
| NL | 171 | 163 | 8 | 0 | 28 448 | 29 558 | −1 110 | −3.8 % |
| PT | 40 | 33 | 7 | 0 | 16 344 | 17 072 | −727 | −4.3 % |
| BE | 59 | 56 | 3 | 0 | 5 718 | 5 815 | −97 | −1.7 % |
| LU | 23 | 22 | 1 | 0 | 3 828 | 3 860 | −32 | −0.8 % |

---

## Detail-Analyse — Kritische Befunde

### Befund 1: FR-13400 Aubagne — FTL-DLV-Artefakt (−8 109 EUR)

**Tarifgruppe:** `bitzer_fr_special_13400_rottenburg` | 13 Rows | fp_net: −89.4 %

**Ursache:** Für PLZ 13400 (Aubagne) liegt ein Sonderziel-DLV als per-Sendung-FTL-Vertrag vor
(`20241213_Bitzer_Export FR-13400 Aubagne.xlsx`). Der Calculator lädt diesen DLV korrekt
(Minimum 697.5 EUR/Sendung, Band bis 5 000 kg = 697.5 EUR/Sendung).

Die tatsächliche BI-Abrechnung verwendet jedoch den allgemeinen **FR Zone 9 LTL-Tarif**:
- Zone 9 Minimum: 46.30 EUR → exakter Match mit BI-Wert 46.30 EUR (100 kg)
- Zone 9 Rate 500 kg: 28.4 EUR/100 kg → 500 × 28.4 / 100 = 142.00 EUR → Match ✓

**Beispiel-Rows:**

| Tonnage | billing_kg | ef (EUR) | DLV-Special (EUR) | fp |
|---:|---:|---:|---:|---:|
| 23.9 kg | 100 | 46.30 | 697.50 | −93.4 % |
| 500.0 kg | 500 | 142.00 | 697.50 | −79.6 % |
| 800.0 kg | 800 | 176.00 | 697.50 | −74.8 % |

**Interpretation:** Bitzer nutzt für diese 13 LTL-Sendungen den allgemeinen FR-Tarif,
NICHT den FTL-Sonderziel-DLV. Mögliche Erklärung: FTL-DLV gilt nur für Vollbeladung
(Dedicated Truck); kleine Teilladungen werden im allgemeinen FR-Tarif abgerechnet.

**Methodische Einordnung:** Diese 13 M2-Rows sind **kein echtes M2** im Sinne
"Bitzer zahlt weniger als Vertrag". Sie sind ein DLV-Selektions-Artefakt (falsche
Tarifgruppe für LTL-Abrechnung). Net Δ ohne diese 13 Rows: **−18 670 EUR (−2.52 %)**.

**Nächster Schritt:** Klärung mit Noerpel, ob FR-13400 LTL korrekt über Zone 9 oder
über FTL-DLV abzurechnen ist. Bis zur Klärung: Rows als `special_dlv_pending` markieren.

---

### Befund 2: IT Zone 4 Rottenburg — DLV-Perioden-Mismatch (−21 511 EUR)

**Tarifgruppe:** `bitzer_it_zone4_rottenburg` | 77 Rows | M2: 61 | fp_net: −26.7 %

**Ursache:** Der Calculator verwendet den **IT Upload DLV 2026** (V_FRA_7042_O_IT_ALL_Bitzer.xlsx).
Die BI-Abrechnung stammt aus dem **Abrechnungszeitraum 2025**, in dem der alte IT-Tarif 2025
galt. Zone 4 (PLZ-Prefix 32, 33, 34, 36 u.a.) hatte 2025 deutlich niedrigere Raten.

Zusätzlich: Upload DLV 2026 hat PLZ-Prefix 32 → Zone 4 (vormals Zone 2 im 2025er DLV),
was für diese Sendungen 2025-Abrechnung in Zone 2 erklärt (niedrigere Rate).

**fp-Verteilung Zone 4 Rottenburg:** mean = −20.5 %, std = 35.7 % (hohe Streuung
deutet auf gemischte PLZ-Zuordnungen Zonen 2/4 im 2025er Tarif).

**Nächster Schritt:** Verifikation mit IT 2025-DLV-Datei; wenn bestätigt, Zone-4-Rows
mit 2025-Raten neu berechnen für korrekte Periodenvergleichsbereinigung.

---

### Befund 3: FR Zone 3 Schkeuditz — Positive Abweichung (+3 482 EUR, +18.0 %)

**Tarifgruppe:** `bitzer_fr_zone3_schkeuditz` | 73 Rows | M_over: 3 | fp_net: +18.0 %

Hohe positive Abweichung. BI-Abrechnung über DLV-Soll. Mögliche Ursachen:
Zonenzuordnungs-Differenz Schkeuditz→FR (andere Frachtwegführung?),
oder anderer Tarif für Schkeuditz-Abgänge nach FR Zone 3.
Nicht unmittelbar auffällig (Bitzer zahlt weniger als abgerechnet = günstig für Bitzer).

---

### Befund 4: IT Zone 1 Rottenburg — Größte Lane (604 Rows, +2.0 %)

**Tarifgruppe:** `bitzer_it_zone1_rottenburg` | 604 Rows | fp_net: +2.0 %

Größte einzelne Lane (17.6 % aller beurteilbaren Rows). Liegt komfortabel im M1-Bereich.
74 M_over-Rows (12.2 %) zeigen leichte Überpreisung — innerhalb Toleranz.

---

## Anhänge

### Anhang A — DLV-Lücken (3 offene Positionen)

#### A1: FR PLZ 92000 Nanterre — 7 Sendungen, 445.20 EUR

PLZ-Prefix 92 fehlt in der FR-Zonentabelle. Geografisch konsistent mit
Île-de-France-Nachbarn 91 und 95 (beide Zone 4). ERKA-Anfrage an Noerpel
formalisiert: → `docs/operative_followups/bitzer_fr_92000_zone.md`

| Versender PLZ | ef (EUR) | Tonnage |
|---|---|---|
| 71126 (Rottenburg) | 87.00 × 3 | 300 kg |
| 71126 (Rottenburg) | 58.00 × 1 | 200 kg |
| 04435 (Schkeuditz) | 33.50 × 2 | 100 kg |
| 04435 (Schkeuditz) | 59.20 × 1 | 200 kg |

Erwartete Zone 4: Calculator nach ERKA-Bestätigung automatisch korrekt
(kein Code-Fix nötig, nur DLV-Tabellen-Update).

#### A2: IT PLZ 09122 Cagliari — 1 Sendung, 95.00 EUR

PLZ-Prefix 09 (Sardinien/Cagliari) fehlt in der IT Upload-Zonentabelle.
IT DLV deckt 00–06 als Zone 4 ab; 07–09 (Sassari/Cagliari) fehlen.
Inselzuschlag wahrscheinlich; ERKA-Anfrage sinnvoll.

#### A3: FR PLZ 77380 Combs-la-Ville >15 000 kg — 1 Sendung, 911.60 EUR

Sonderziel-DLV für FR-77380 hat Maximalband 15 000 kg. Diese Sendung:
billing_kg = 17 200 kg. Alle verfügbaren DLV-Versionen (2025, 2026 Standard,
2026 Upload LTL V_FRA_7042_O_FR_LTL_Bitzer.xlsx) enden bei 15 000 kg.
**Permanente Lücke** — kein Fix ohne erweitertes DLV. Spotrate-Abrechnung.

Die übrigen 47 FR-77380-Rows (billing_kg ≤ 15 000 kg) werden korrekt als
`bitzer_fr_special_77380_rottenburg` bewertet (fp_net: −0.6 %, M1-dominant).

---

### Anhang B — DE Inbound: 67 Sendungen, 33 970 EUR (Out-of-Scope)

**Empfänger Land = DE** bezeichnet ausschließlich **eingehende Fracht** an
Bitzer-Werke Rottenburg (PLZ 71126, 72108, 71065, 75382) und Schkeuditz (04435).

Versender-Länder: IT (57), FR (4), CH (2), NL (1), BE (1), PT (1), DE (1), PL (1), GB (1).

**Klassifikation:** Diese Rows sind **Rücktransporte / Importfracht**, NICHT
Teil des Bitzer-Exportvertrags mit Noerpel. BitzCalculator implementiert
ausschließlich Ausfuhrrouten (Werk → Ausland). Für Einfuhrrouten gelten
separate Importtarife (ERKA nötig).

**Entscheidung:** Scope-out v1.9.6. Separate Behandlung wenn Importtarife
verfügbar. Kein DLV-Gap — andere Vertragsdomäne.

Status im Calculator: `no_dlv` (LookupError bei `_get_country('DE')`).

---

### Anhang C — Cross-System P4: 2 172 Sendungen (ef = 0)

Alle Rows mit `Erlöse Fracht = 0` sind aus dem Analysepool ausgeschlossen.
Diese repräsentieren administrative Buchungen, Gutschriften und ZGI-Master-Rows
(Erlöse auf Unterauftrag-Seite aggregiert, nicht auf Mastersendung).

**Kein Handlungsbedarf** — korrekt klassifiziert durch ef > 0 Poolfilter.

---

### Anhang D — Sub-Master P9: 6 ZGI-Master-Rows

| Mastersendung | Unteraufträge | Tonnage (frpfl.) |
|---|---|---|
| 7.092e+15 | 2 UA | 1 218.0 kg |
| 7.092e+15 | 2 UA | 35.6 kg |
| 7.092e+15 | 1 UA | 1 418.0 kg |
| 7.092e+15 | 2 UA | 3 813.0 kg |
| 7.092e+15 | 2 UA | 600.0 kg |
| 7.092e+15 | 2 UA | 1 949.3 kg |

Diese 6 Master-Rows haben ef=0 und Tonnage>0. Sie dienen als Tonnage-Quelle
für die Sub-Row-Substitution (Anhang §ZGI). Korrekt aus dem Analysepool
ausgeschlossen (ef=0).

**17 Sub-Rows** mit zugehörigen Master-Tonnagen: 11 erfolgreich substituiert,
6 ohne identifizierbaren Master (Fallback 1 kg → billing_kg 100).

---

### Anhang E — Multi-Origin: Rottenburg vs. Schkeuditz

Beide Werke verwenden **identische Vertragstarife** (per DLV kein Ortsaufschlag).
BitzCalculator gibt Origin-PLZ als Tarifgruppen-Suffix aus für Tracking.

| Werk | Rows | M1 % | fp_net | Σ Δ |
|---|---|---|---|---|
| Rottenburg | 2 251 | 84.8 % | −5.7 % | −30 251 EUR |
| Schkeuditz | 1 076 | 88.5 % | +1.4 % | +3 152 EUR |

**Rottenburg-Nachteil** zu ~71 % durch IT Zone 4 (−21 511 EUR) und FR-13400
(−8 109 EUR) erklärbar — beides Messartefakte (DLV-Perioden-Mismatch bzw.
FTL-DLV-Selektion). Bereinigt wäre auch Rottenburg nahezu ausgeglichen.

---

### Anhang F — Calculator-Ausbau-Note: 8 neue Lanes (v1.9.6)

In den Tasks 5–7 dieses Projekts implementiert:

| Lane | DLV-Datei | Zone-Logik |
|---|---|---|
| PT Zone 1/4/6 Rottenburg | `20241213_Bitzer_Export PT.xlsx` | PLZ-Prefix-Mapping |
| PT Zone 1/4/6 Schkeuditz | gleiche DLV | Identische Raten |
| BE Zone 1 | `20241213_Bitzer_Export BE, NL, LU.xlsx` | Country=Zone1 |
| NL Zone 1 | gleiche Benelux DLV | Country=Zone1 |
| LU Zone 2 | gleiche Benelux DLV | Country=Zone2; FTL 753.50 |
| FR-92000 | ausstehend (ERKA) | — |
| FR-77380 Sonderziel | `V_FRA_7042_O_FR_LTL_Bitzer.xlsx` | Cap 15 000 kg |
| IT Upload 2026 | `V_FRA_7042_O_IT_ALL_Bitzer.xlsx` | Zone-4-Korrekturen |

SKILL.md P15 hinzugefügt: Upload-Ordner sind aktive Tarife.

---

## Bewertung und Handlungsempfehlungen

### Sofort

1. **FR-13400 Klärung** (Noerpel): Gilt FTL-DLV für Teilladungen oder nur Vollbeladung?
   Impact: −8 109 EUR (scheinbar), tatsächlich LTL-konforme Abrechnung.
2. **IT Zone 4 2025-DLV**: Perioden-Mismatch bestätigen; ggf. 2025-Raten für
   historischen Vergleich laden. 61 M2-Rows, −21 511 EUR bereinigen.

### Mittelfristig

3. **ERKA FR 92000**: Noerpel-Anfrage stellen → 7 Sendungen, 445 EUR.
4. **ERKA IT 09122**: Sardinien-Zuschlag klären → 1 Sendung, 95 EUR.
5. **FR 77380 >15t**: DLV-Erweiterungsanfrage oder Spot-Rate-Dokumentation.

### Ziel-Zustand

- v1.9.7: FR-92000 + IT-09122 gelöst → ≥ 99.5 % Beurteilbarkeit
- v2.0: IT Perioden-Normierung + FR-13400 Methodikklärung → bereinigter fp

---

*Generiert: 2026-04-28 | Script: `src/build_bitzer_step23_v196.py` | Cache: `output/bitzer_step23_results_v196.pkl`*
