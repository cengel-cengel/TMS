# 9b.4 — GEZE GmbH: Phasen-Rollout Findings Report

**Etappe:** 9b.3 → 9b.4  
**Erstellt:** 2026-04-20  
**Branch:** `claude/audit-billing-migration-wfgWR`  
**Commit-Basis:** 49c1eb7 (9b.3) + afb8356 (Methodik v1.4)

---

## §1 Executive Summary

Die GEZE-Analyse (KNR 406035, POST-Periode, RN > 5, Erlöse Fracht > 0) ergibt:

- **Gesamt-Delta:** +51.187 EUR (Ist > DLV-Basispreis) — plankonform durch Diesel-/CHF-Floater
- **Muster-A:** **0 Treffer** — kein systemischer 7 %-ERKA-Indexaufschlag in keiner Lane
- **Muster-B:** **13 Kandidaten** mit delta_raw < −10 EUR identifiziert; nach
  Artefakt-Prüfung **1 Aggregationsartefakt** (GB/WS13 8SY, n_pos=27),
  **12 unvalidiert, manuell zu prüfen**
- **CHF-Floater:** Korrekt in `Erlöse Fracht` eingerechnet; 51/95 CH-Gruppen im
  Neutralband, 3 Gruppen mit aktivem Floater (CHF/EUR 0,908–0,957)
- **Gate-1:** Aktiv — 25,5 % Tonnage=0 (1.109/4.349) überschreitet 20 %-Schwelle

---

## §2 Methodik-Referenz

| Parameter | Wert |
|---|---|
| Customer | GEZE GmbH (KNR 406035) |
| Periode | POST (Leistungsdatum ab AX-Live) |
| Filter | RN > 5, Erlöse Fracht > 0, DLV-Land, Tonnage > 0 |
| Aggregationsebene | Sendungs-Gruppe: Rechnungsnummer × Empfänger Land × PLZ-norm |
| aggregation_key_source | `mastersendung` (kein Ausgangsbordero-Key) |
| DLV-Datei | `20250305_Geze_Export_incl.*.xlsx`, Sheet "Exporttarife" |
| DLV-Gültigkeit | 2025-01-01 – 2025-12-31 (kein 2026-DLV; 2025-Fallback aktiv) |
| Maut | In `basispreis` inkludiert → toll = 0 |
| Diesel | Separat in `Erlöse Diesel`; nicht in `floater_pct` |
| Muster-A-Schwelle | `abs(floater_pct − 0,07) < 0,0015` |
| Muster-B-Schwelle | `delta_raw < −10 EUR` |
| Methodik-Version | v1.4 (`afb8356`) |

---

## §3 Gesamt-Befund: Soll vs Ist

### Phasen-Verteilung (1.098 Sendungs-Gruppen aus 3.120 Positionen)

| Phase | Gruppen | Anteil | Erlöse Fracht |
|---|---|---|---|
| `in_dlv_2025` | 773 | 70,4 % | 187.791 EUR |
| `in_dlv_2025_fallback` | 325 | 29,6 % | 73.095 EUR |

Kein `pre_dlv`, kein `unknown` — vollständige DLV-Abdeckung der beurteilbaren Gruppen.

### Delta-Übersicht per Lane

| Land | n Grp | n Pos | DLV-Soll € | Ist € | Delta € | fp_mean | Muster-A | Muster-B |
|---|---|---|---|---|---|---|---|---|
| AT | 163 | 338 | 18.247,91 | 22.825,03 | +4.577,12 | +0,168 | 0 | 2 |
| CH | 95 | 612 | 15.523,83 | 21.494,54 | +5.970,71 | +0,289 | 0 | 0 |
| ES | 245 | 341 | 30.310,06 | 33.883,39 | +3.573,33 | +0,077 | 0 | 2 |
| FR | 149 | 590 | 67.477,55 | 78.858,95 | +11.381,39 | +0,136 | 0 | 4 |
| GB | 8 | 591 | 27.050,08 | 46.337,82 | +19.287,74 | +0,710 | 0 | 1 |
| IE | 4 | 5 | 2.392,35 | 2.405,21 | +12,86 | +0,003 | 0 | 0 |
| IT | 363 | 552 | 41.402,67 | 46.976,57 | +5.573,90 | +0,089 | 0 | 4 |
| PT | 71 | 91 | 7.294,85 | 8.104,58 | +809,73 | +0,134 | 0 | 0 |
| **Gesamt** | **1.098** | **3.120** | **209.699,30** | **260.886,08** | **+51.186,78** | | **0** | **13** |

Der positive Gesamt-Delta (+51.187 EUR) entspricht einem durchschnittlichen
`floater_pct` von +12,9 % über alle Gruppen — plankonform als Diesel-/CHF-Floater.

---

## §4 Muster-A: Kein Treffer

**Ergebnis: 0 Gruppen** mit `abs(floater_pct − 0,07) < 0,0015`.

GEZE weist keinen systemischen 7 %-ERKA-Indexaufschlag auf, wie er bei EBM-Papst
(Jan 2026) und Fischerwerke (März 2026) dokumentiert wurde. Dies ist ein
**negativer Befund im Sinne der Audit-Methodik** — er schärft das Bild des
kunden-spezifischen Roll-outs:

| Kunde | ERKA-Aktivierungsmonat | n Treffer |
|---|---|---|
| EBM-Papst | Januar 2026 | 50 |
| Fischerwerke | März 2026 | ~31 |
| **GEZE** | **nicht nachweisbar** | **0** |

Mögliche Erklärungen: GEZE hat noch keine ERKA-Vereinbarung, oder das Roll-out-
Datum liegt außerhalb der vorliegenden POST-Daten (nach April 2026).

---

## §5 Muster-B: 13 Kandidaten

### 5.1 Übersicht

| RN | Land | PLZ | Zone | Phase | n_pos | Tonnage | Billing kg | Ist € | Soll € | Delta € | fp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2560101 | AT | 5300 | 5 | in_dlv_2025 | 5 | 508 | 600 | 101,93 | 140,64 | −38,71 | −0,275 |
| 2563945 | AT | 8055 | 7 | in_dlv_2025 | 4 | 908 | 1.000 | 213,03 | 265,50 | −52,47 | −0,198 |
| 2563945 | FR | 40000 | 6 | in_dlv_2025 | 2 | 1.157 | 1.200 | 603,00 | 629,40 | −26,40 | −0,042 |
| 2573273 | ES | 36400 | 5 | in_dlv_2025 | 2 | 125 | 200 | 107,54 | 137,28 | −29,74 | −0,217 |
| 2573273 | ES | 38639 | 7 | in_dlv_2025 | 1 | 8 | 100 | 24,02 | 165,61 | −141,59 | −0,855 |
| 2578458 | GB | WS13 8SY | 1 | in_dlv_2025 | **27** | 7.528 | 7.600 | 1.479,91 | 2.447,20 | **−967,29** | −0,395 |
| 2582348 | IT | 10070 | 3 | fallback | 1 | 37 | 100 | 35,95 | 53,87 | −17,92 | −0,333 |
| 2582348 | IT | 16138 | 3 | fallback | 5 | 590 | 600 | 222,54 | 253,38 | −30,84 | −0,122 |
| 2582348 | IT | 16152 | 3 | fallback | 1 | 46 | 100 | 27,32 | 53,87 | −26,55 | −0,493 |
| 2586869 | FR | 81000 | 6 | fallback | 1 | 1.633 | 1.700 | 808,44 | 891,65 | −83,21 | −0,093 |
| 4251011138 | FR | 57600 | 3 | in_dlv_2025 | 1 | 60 | 100 | 29,46 | 75,70 | −46,24 | −0,611 |
| 4251011138 | FR | 59273 | 4 | in_dlv_2025 | 4 | 10.319 | 10.400 | 2.348,90 | 2.560,48 | **−211,58** | −0,083 |
| 4251017635 | IT | 10070 | 3 | fallback | 1 | 19 | 100 | 17,92 | 53,87 | −35,95 | −0,667 |

**Gesamt-Erwartungsverlust (13 Kandidaten):** −1.709,26 EUR

### 5.2 Aggregationsartefakt: GB/WS13 8SY

**RN 2578458 / GB Zone 1 / PLZ WS13 8SY** — n_pos=27, delta=−967 EUR.

Diese Gruppe bündelt 27 Positionen mit insgesamt 7.528 kg auf derselben Rechnung
an dieselbe Lieferadresse (WS13 8SY = Lichfield, GB Zone 1). Der Calculator
berechnet auf der aggregierten Tonnage von 7.600 billing_kg einen Soll-Basispreis
von 2.447 EUR; tatsächlich wurden nur 1.480 EUR als `Erlöse Fracht` verbucht.

**Aggregationsartefakt-Indizien:**
- n_pos = 27 (deutlich über Normalbereich 1–5)
- Ohne Ausgangsbordero-Abgleich unklar, ob es 1 konsolidierte Sendung oder
  27 Einzelsendungen sind
- Bei 27 Einzelsendungen à ~279 kg wäre DLV-Soll: 27 × max(83,29; 50,05×3) =
  27 × 150,15 = 4.054 EUR → Ist noch stärker unter DLV-Soll
- Bei 1 konsolidierten Sendung: 2.447 EUR Soll, 1.480 EUR Ist → echte
  Unterfakturierung möglich

**Bewertung:** Als **"Aggregationsartefakt — Sendungs-Aggregation erforderlich"**
kennzeichnen. Nicht als bestätigte Unterfakturierung werten bis Ausgangsbordero-
Abgleich vorliegt. Methodik §2a angewendet.

### 5.3 Schwerpunktfälle (unvalidiert, pending Sendungs-Aggregation)

**FR/59273 Zone 4 (RN 4251011138), delta=−211,58 EUR:**
- n_pos=4, Tonnage 10.319 kg, billing_kg=10.400
- Basispreis 2.560 EUR (DLV FR Zone 4 Hochgewicht), Ist 2.349 EUR
- fp=−0,083 (−8,3 % unter DLV-Base)
- Gleiche RN hat auch FR/57600 Zone 3 Muster-B (delta=−46, fp=−0,611)
- Hypothese: Falsche Zone-Zuordnung oder abweichender Tarif für schwere Sendungen

**ES/38639 Zone 7 (RN 2573273), delta=−141,59 EUR:**
- n_pos=1, Tonnage 7,9 kg, billing_kg=100
- Basispreis 165,61 EUR (ES Zone 7 = Las Palmas, Minimum), Ist 24,02 EUR
- fp=−0,855 (nur 14,5 % des DLV-Minimums bezahlt)
- Hypothese: Zone-7-Minimum nicht angewendet, stattdessen Inlandsrate
  oder Fehltarif gebucht

**AT/8055 Zone 7 (RN 2563945), delta=−52,47 EUR:**
- n_pos=4, Tonnage 908 kg, billing_kg=1.000
- AT Zone 7 (PLZ 80-89 = Graz-Umgebung), rate≤1000=26,55
- Soll: max(min,26,55×10)=265,50 EUR; Ist: 213,03 EUR
- fp=−0,198 (konsistente Unterdeckung)

**FR/81000 Zone 6 Fallback (RN 2586869), delta=−83,21 EUR:**
- Fallback-Phase (in_dlv_2025_fallback), 1 Position, 1.633 kg
- Fällt unter 2025-DLV-Fallback (kein 2026-DLV); Unterdeckung −9,3 %

### 5.4 Kleinfälle mit Minimum-Floor-Verdacht

Vier Fälle mit fp deutlich unter −0,3 und n_pos=1, billing_kg=100:
- IT/10070 (RN 2582348): Ist 35,95 vs Soll 53,87 → fp=−0,333
- IT/16152 (RN 2582348): Ist 27,32 vs Soll 53,87 → fp=−0,493
- FR/57600 (RN 4251011138): Ist 29,46 vs Soll 75,70 → fp=−0,611
- IT/10070 (RN 4251017635): Ist 17,92 vs Soll 53,87 → fp=−0,667

**Hypothese:** In diesen Gruppen wurde das DLV-Minimum nicht angewendet — stattdessen
ein linearer Rate×billing_kg-Betrag ohne Minimum-Floor gebucht. Indiz: Die
erwarteten Basispreise entsprechen jeweils dem Minimum-Floor (53,87 EUR = IT Zone 3
Minimum; 75,70 EUR = FR Zone 3 Minimum), während die Ist-Werte darunterliegen.

---

## §6 CHF-Floater: Band-Zuordnung

### Ergebnis (95 CH-Gruppen, 612 CH-Positionen)

| CHF-Band (CHF/EUR) | Typ | n Gruppen | Bedeutung |
|---|---|---|---|
| 1,0210 – 1,0747 | sg | 51 | Neutralband — kein CHF-Aufschlag |
| 0,9470 – 0,9567 | sg | 1 | CHF-Floater aktiv (~0,95-Niveau) |
| 0,9372 – 0,9469 | sg | 1 | CHF-Floater aktiv (~0,94-Niveau) |
| 0,9078 – 0,9175 | sg | 1 | CHF-Floater aktiv (~0,91-Niveau) |
| kein Match | — | 41 | Diesel-Überlagerung oder Mischperioden |

**fp-Statistik CH:** mean=+0,289 / p25=0,000 / p50=0,000 / p75=+0,443 / std=0,432

**Interpretation:**
- Die Bimodalität (p25/p50=0,000 vs. p75=+0,443) entspricht dem erwarteten Profil:
  Neutralband-Gruppen haben fp≈0 (Maut-inklusive DLV-Base, kein CHF-Aufschlag),
  Aktiv-Band-Gruppen haben fp im Bereich der jeweiligen Stückgut-Fraktion.
- 41 ungematchte CH-Gruppen: `Erlöse Fracht` enthält hier vermutlich einen
  kombinierten Diesel+CHF-Anteil (beide in derselben Spalte, nicht getrennt
  ausgewiesen). Alternativ: Abrechnungszeitraum überlappt Bandwechsel.
- **Positive Bestätigung (§7-Konsequenz):** ERKA hat den CHF-Floater korrekt
  eingerechnet. Der `_parse_chf_floater`-Bug (9b.1, Commit dd3d558) betraf nur
  den Validator, nicht die Produktionsabrechnung.

---

## §7 Saubere Lanes: Kurz-Bericht

### IE — Near-Perfect Match (fp_mean=+0,003)

4 Gruppen aus 5 Positionen, 4 Destinationen (D02, D22, A92, D4K).
`Erlöse Fracht` stimmt auf +0,3 % mit DLV-Basispreis überein. Das bestätigt:
- IE Zone 1 (alle IE = Zone 1, Minimum 106,65 EUR)
- Formel `billing_kg = max(100, ceil(t/100)×100)` korrekt angewendet
- Maut-Inkludierung korrekt (kein extra Maut-Zuschlag erwartet, keiner vorhanden)

IE ist der methodische Anker-Test für die GEZE-Kalkulation.

### PT — Stabiler Floater (+0,134)

71 Gruppen, 91 Positionen, 4 Zonen, kein Muster-B, fp_mean=+0,134 (±0,306).
Konsistent mit Diesel-Floater-Niveau Q1 2025. Keine Auffälligkeiten.

### IT — Überwiegend korrekt (+0,089)

363 Gruppen, 552 Positionen, 6 Zonen. 4 Muster-B-Kandidaten (davon 3 auf RN 2582348
und 1 auf RN 4251017635) mit Minimum-Floor-Verdacht. IT insgesamt gesund.

---

## §8 Offene Klärungsfragen

| Nr | Frage | Priorität |
|---|---|---|
| 8.1 | GB/WS13 8SY (RN 2578458): Ausgangsbordero-Abgleich — 1 Sendung oder 27 Einzelsendungen? | Hoch |
| 8.2 | FR/59273 (RN 4251011138) und FR/57600 (gleiche RN): Welcher Tarif wurde tatsächlich für 10.319 kg FR Zone 4 angesetzt? | Hoch |
| 8.3 | ES/38639 Zone 7 (RN 2573273): Wurde Las-Palmas-Minimum korrekt geprüft? | Mittel |
| 8.4 | Minimum-Floor-Fälle (4× billing_kg=100, fp < −0,3): Systemisches Problem oder Einzelfall-Fehleingaben? | Mittel |
| 8.5 | GEZE Sendungs-Aggregation: Ab wann ist ein `Ausgangsbordero`-Key aus den BI-Daten extrahierbar, um Positions-Aggregation zu ersetzen? (§2a Methodik) | Mittel |
| 8.6 | Warum hat GEZE 25,5 % Tonnage=0-Zeilen? Ist das ein AX-Export-Artefakt oder ein Billing-Daten-Problem? | Mittel |
| 8.7 | 41 CH-Gruppen ohne Band-Match: Enthält `Erlöse Fracht` für diese Gruppen sowohl Diesel- als auch CHF-Anteil (keine Trennung)? | Niedrig |
| 8.8 | Kein Muster-A bei GEZE: Liegt das Roll-out-Datum des ERKA-Aufschlags nach April 2026, oder hat GEZE keine ERKA-Vereinbarung? | Niedrig |

---

## §9 Zusammenfassung Handlungsbedarf

| Maßnahme | Zuständig | Basis |
|---|---|---|
| Ausgangsbordero-Abgleich GB/WS13 8SY | ERKA/IT | Klärungsfrage 8.1 |
| Tarifprüfung FR Zone 4 bei >10.000 kg (RN 4251011138) | ERKA Billing | Klärungsfrage 8.2 |
| Minimum-Floor-Eskalation 4 Kleinfälle | ERKA Billing | Klärungsfrage 8.4 |
| Tonnage=0-Ursache (1.109 Zeilen) | ERKA IT / AX-Team | Klärungsfrage 8.6 |
| Sendungs-Aggregation vorbereiten | Audit (nächste Etappe) | §2a Methodik |
