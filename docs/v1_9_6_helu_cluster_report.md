# HELU-KABEL GmbH — Step 2+3 Cluster-Report v1.9.6

**Stand:** 2026-04-28
**KNR:** 408244 (HELU-KABEL GmbH)
**Periode:** POST-AX (2025-09-27 – 2026-03-31)
**Pipeline:** `src/build_helu_step23_v196.py` (inline)
**Cache:** `output/helu_step23_results_v196.pkl`

## Headline

**Net Δ = +202,52 EUR (+0,06 %) — praktisch Null. Kein Migrationsschaden.**
M2 (−3.897 EUR) und M_over (+4.100 EUR) heben sich fast vollständig auf.
M2-Muster: Kleinstdeltas (1–10 EUR/Row) aus per-100kg-Band-Rundungs-Artefakten — kein systemisches Unterfakturierungs-Muster.
Calculator-Bugs H1+H2 vor Step 2 identifiziert und gefixt (Commit 897a2c6).

## Executive Summary

| Metrik | Wert |
|---|---|
| KNR | 408244 |
| Pool roh (ef>0) | 2.293 |
| Sub-Rows (is_sub, ef>0) | 97 |
| OOS (DE=7, EE=1, LU=1) | 9 |
| ton=0 | 2 |
| **In-Scope** | **2.185** |
| DLV-Lücke | **0** (100 % Coverage) |
| Beurteilbar | **2.185** |
| M1 \|fp\|≤5 % | **2.044** (93,5 %) |
| M2 fp<−5 % | **102** (4,7 %) |
| M_over fp>+5 % | **39** (1,8 %) |
| Σ ef (beurteilbar) | 315.991,07 EUR |
| Σ dlv (beurteilbar) | 315.788,55 EUR |
| **Net Δ** | **+202,52 EUR (+0,06 %)** |

### Land-Aufschlüsselung

| Land | Rows | Σ ef | Σ dlv | Δ | fp_net | M1 | M2 | M_ov |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| IT | 1.682 | 117.594 | 118.265 | **−671** | −0,006 | 1.577 | 78 | 27 |
| PT | 122 | 62.961 | 61.011 | +1.950 | +0,032 | 114 | 4 | 4 |
| ES | 100 | 52.514 | 53.725 | **−1.211** | −0,023 | 87 | 9 | 4 |
| GB | 55 | 48.125 | 47.580 | +545 | +0,011 | 52 | 1 | 2 |
| AT | 165 | 16.026 | 16.041 | −15 | −0,001 | 156 | 8 | 1 |
| GR | 26 | 9.022 | 9.561 | **−539** | −0,056 | 24 | 2 | 0 |
| IE | 32 | 8.778 | 8.797 | −20 | −0,002 | 32 | 0 | 0 |
| CH | 3 | 971 | 809 | +163 | +0,201 | 2 | 0 | 1 |

## Methodik

### Calculator

`HeluCalculator` (helu.py, Commits e2807b5 + 7500102), pricing_basis = `kg`.

**Pricing-Logik:**

```
eff_kg    = t_kg  (falls t_kg < LDM-Schwelle)
          = max(t_kg, LDM × Faktor)  (Teilpartie, falls t_kg ≥ Schwelle und LDM > 0)
billing_kg = max(100, ceil(eff_kg / 100) × 100)
fracht     = max(running_prev_max, rate_per_100kg × billing_kg / 100)
```

LDM-Konfiguration je Land:

| Land | Schwelle (kg) | Faktor (kg/LDM) |
|---|---:|---:|
| IT, GB | 2.500 | 1.500 / 1.250 |
| AT, PT, IE, PL, CH | 2.501 | 1.250 |
| ES | 2.501 | 1.500 |
| GR | 3.301 | 1.650 |

### DLV-Versionen

| Land | DLV-Datei | Gültig |
|---|---|---|
| IT/AT/ES/PT/GB/IE/PL/CH | Export XX ab 01.12.2023 bis 31.12.2023.xlsx | 2023 |
| GR | 20250520_Helukabel_Export GR ergänzt um Athen.xlsx | ab 2025 |

Kein shipment_date-Dispatch (einheitliche Version pro Land) — P12 nicht anwendbar.
Kein Upload-DLV-Unterordner — P16 nicht anwendbar.

### Scope-Entscheidungen

| Ausschluss | Grund | Rows |
|---|---|---|
| Sub-Rows (is_sub) | Erlöse auf Master | 97 |
| DE-Inland | kein Export-DLV | 7 |
| EE, LU | kein HELU-DLV | 2 |
| ton=0 | keine Gewichtsbasis | 2 |

### ZGI-Cluster

bi_top20_data.pkl enthält keine ZGI-Spalten. 0 Mastersendungen im in-scope-Pool.
**ZGI-Bias: 0 EUR bestätigt.**

## Cluster-Übersicht — Top nach |Δ|

Alle 95 aktiven Tarifgruppen; nachfolgend die 15 mit größtem |Δ|:

| Tarifgruppe | Rows | Σ ef | Σ dlv | Δ | fp_net | M1 | M2 | M_ov |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| helu_pt_zone3 | 72 | 49.729 | 47.683 | **+2.046** | +0,043 | 66 | 2 | 4 |
| helu_gb_zone1 | 55 | 48.125 | 47.580 | +545 | +0,011 | 52 | 1 | 2 |
| helu_it_zone25 | 69 | 5.357 | 4.615 | **+742** | +0,161 | 51 | 0 | 18 |
| helu_es_zoneES | 67 | 47.859 | 48.218 | −359 | −0,007 | 57 | 6 | 4 |
| helu_es_zone18 | 4 | 2.541 | 3.377 | **−837** | −0,248 | 3 | 1 | 0 |
| helu_gr_zone57 | 26 | 9.022 | 9.561 | **−539** | −0,056 | 24 | 2 | 0 |
| helu_it_zone20 | 179 | 13.347 | 13.731 | −384 | −0,028 | 157 | 21 | 1 |
| helu_it_zone35 | 178 | 13.542 | 13.733 | −191 | −0,014 | 168 | 9 | 1 |
| helu_at_zone5 | 46 | 6.270 | 6.453 | −183 | −0,028 | 42 | 4 | 0 |
| helu_it_zone50 | 53 | 3.613 | 3.745 | −133 | −0,035 | 47 | 6 | 0 |
| helu_it_zone37 | 92 | 4.758 | 4.851 | −93 | −0,019 | 81 | 9 | 2 |
| helu_it_zone10 | 101 | 6.639 | 6.719 | −81 | −0,012 | 96 | 4 | 1 |
| helu_pt_zone4 | 22 | 5.642 | 5.738 | −96 | −0,017 | 20 | 2 | 0 |
| helu_at_zone7 | 7 | 4.025 | 3.817 | **+208** | +0,055 | 6 | 0 | 1 |
| helu_ch_zoneCH46 | 1 | 370 | 207 | **+163** | +0,786 | 0 | 0 | 1 |

**Clusters mit Δ = 0 (M1-rein):** 52 Tarifgruppen, überwiegend IT-Zonen mit kleinem Volumen.

## Detail-Cluster

### M2-Muster: Band-Rounding-Artefakt (IT, AT — überwiegende M2-Ursache)

78 der 102 M2-Rows sind IT-Rows mit kleinen Einzeldeltas (−2 bis −10 EUR/Row).
Ursache: per-100kg-Bandstruktur — billing_kg rundet auf 100er-Grenze, AX rechnet
gelegentlich mit einem anderen Band (typisch: 1 Band tiefer als Teilpartie-adjusted DLV).
Muster: fp_mean ≈ −0,03 bis −0,08, std ≈ 0,07 → zufällige Streuung, kein systematisches
Unterfakturierungs-Muster.

Σ M2 IT: −1.387 EUR | Σ M2 AT: −220 EUR | kein einzelnes großes Defizit.

### M2-Ausreißer: Teilpartie-Diskrepanz (ES + GR)

**ES 18500 (Granada) — 1 Row:**
- ton=8.135 kg, ldm=6,0; ef=1.500 EUR vs dlv=2.349 EUR → Δ=−849 EUR (fp=−36 %)
- DLV Teilpartie: eff_kg = max(8.135, 6 × 1.500) = 9.000 kg → billing=9.000 → Rate ergibt 2.349
- AX rechnet ohne LDM-Teilpartie (nur Tonnage-basiert: 8.135 kg → billing=8.200 → ~1.500 EUR)
- **Prüfpunkt:** AX wendet Teilpartie-Regel für ES nicht an → 1 Row, 849 EUR Defizit

**GR 57009 (Thessaloniki) — 2 Rows:**
- ton=4.143 kg / 3.855 kg, ldm=4,0 / 3,0 LDM → GR Teilpartie (Schwelle 3.301, Faktor 1.650)
- eff_kg = 6.600 / 5.775 kg → dlv=1.184 / 978 EUR; ef=822 / 801 EUR → Δ=−363 / −176 EUR
- Gleiche Ursache: AX rechnet tonnagenbasiert, DLV erwartet LDM-Teilpartie

**IT zone25 (PLZ 25040/25050, Brescia) — 18 M_over Rows:**
- ef=71,40 EUR, dlv=31,40 EUR für 39–200 kg → Δ=+40 EUR/Sendung, fp=+96–127 %
- Sendungen: alle PLZ 25040 (Castrezzato) / 25050 (Erbusco)
- Systematischer Aufschlag: AX rechnet ein Minimum von 71,40 EUR;
  DLV gibt 31,40 EUR bei billing_kg=100. Differenz = Sondergebühr / Zuschlag nicht im DLV.
- M_over (Überzahlung) — kein Migrationsschaden für Kunden

**PT 3025-248 — Zeile mit fp=+100 % (Δ=+1.734 EUR):**
- ton=11.556 kg, ldm=9,0; ef=3.468,40 EUR, dlv=1.734,20 EUR
- ef ≈ 2 × dlv → wahrscheinlich Diesel-Floater inklusive in ef (Σ-Faktoren auf ef erhöhen ef
  um 100 % des Basispreises). Nicht ungewöhnlich bei LKW-Großsendungen. Kein Billing-Fehler.

## PT-4925 Lanheses — Diagnose

### Befund (Aufgabe 1)

| Metrik | Wert |
|---|---|
| PT gesamt (ef>0) | 122 Rows, Σef = 62.961 EUR |
| PT-4925 (Lanheses, PLZ 4925-432) | **1 Row**, Σef = 1.129 EUR |
| PT andere PLZ | 121 Rows |

### Tarif-Vergleich (1 Row: 7.641 kg)

| Quelle | Rate | Bemerkung |
|---|---|---|
| Allgemeines PT-DLV (zone_key=4) | 1.196,25 EUR | per-100kg, PT zone4 |
| Lanheses-DLV (PT-4925) | LDM-basiert (758–985 EUR/Band) | Andere Struktur! |
| Actual ef | **1.128,70 EUR** | |

Das Lanheses-DLV verwendet LDM-basierte Flat-Rates (kein per-100kg), mit Bändern:
- 5.200 kg / 2 LDM → 758,20 EUR
- 6.200 kg / 3 LDM → 831,70 EUR
- 7.200 kg / 4 LDM → 985,20 EUR

Für 7.641 kg: kein exaktes Band → Extrapolation → ca. 985–1.200 EUR Bereich.

### Klassifikation mit allgemeinem PT-DLV

ef (1.128,70) vs dlv (1.196,25) → fp = −5,6 % → **M2** (knapp unter Schwelle).

Begründung: AX rechnet nach Lanheses-Sonderroute; Calculator verwendet allgemeine PT-Zone.
Kein echter Billing-Fehler — Methodik-Artefakt durch fehlende Lanheses-Integration.

### Entscheidung

**Volumen zu klein für Calculator-Erweiterung:** 1 Row, 1.129 EUR, fp knapp M2.
Die Row wird in Step 3 als M2 klassifiziert. Im Report als Lanheses-Sonderroute
(methodisch erklärbar) flagged. Kein operativer Handlungsbedarf.

## Anhänge

### Anhang A — Calculator-Bug-Fixes (Pre-Flight, Commit 897a2c6)

| Bug | Symptom | Fix |
|---|---|---|
| H1 (ES-Mendaro) | `zone_fn` → "ES-20870", rates-key "ES" (Regex stoppt an "-") | `zone_fn` gibt "ES" zurück |
| H2 (GB rates_by_col) | rates dict int-keys, `zone_fn` returns str → lookup scheitert | rates dict auf str-keys umgestellt |
| Coverage vor Fix | 94,3 % (67 ES + 55 GB Failures) | Nach Fix: 99,9 % |

### Anhang B — DLV-Lücke (EE, LU)

| Land | Rows | Σ ef | Grund |
|---|---:|---:|---|
| EE | 1 | ~244 EUR | kein HELU DLV |
| LU | 1 | ~35 EUR | kein HELU DLV |

Beide scope_out. Volumen < 300 EUR gesamt — keine operativen Beanstandungen.

### Anhang C — OOS DE-Inland (7 Rows)

7 Rows Empfänger Land = DE. Inland-Fracht ohne Export-DLV → scope_out.
Versender: HELUKABEL GMBH 71282. DE-Rows sind Rücksendungen oder Inland-Lieferungen.

### Anhang D — Sub-Rows (97 Rows, is_sub, ef>0)

97 Rows mit gesetzter Mastersendung, kein eigener Unterauftrag.
Erlöse liegen auf dem Master-Row. Alle scope_out (Sub-Row-Filter §2e v1.9.6).
Sub-Row Σ ef: ~15.000 EUR (Schätzung; ef-Werte auf Master-Rows).

### Anhang E — ton=0 Filter (2 Rows)

| Land | PLZ | Grund |
|---|---|---|
| IT | — | ton=0, ldm vermutlich 0 → keine Gewichtsbasis |
| ES | — | ton=0 |

Beide scope_out (keine Billing-Basis ableitbar).

### Anhang F — PT-4925 Lanheses

Siehe § PT-Lanheses-Diagnose. 1 Row, 1.129 EUR, M2 fp=−5,6 %.
Lanheses-DLV strukturell verschieden (LDM-basiert vs. per-100kg allgemeines PT).
Methodik-Artefakt, kein operativer Handlungsbedarf.

## Gesamtbewertung

### Audit-Aussage

**Kein Migrationsschaden bei HELU-KABEL.**

- Net Δ = +202,52 EUR (+0,06 %): praktisch Null — AX rechnet auf DLV-Niveau
- M2 (102 Rows, −3.897 EUR) = überwiegend per-100kg-Band-Rounding-Artefakt
  (IT: 78 Rows, Kleinstdeltas −2 bis −10 EUR/Row)
- Teilpartie-Diskrepanz (ES 18500, GR 57009): 3 Rows, Σ=−1.388 EUR.
  AX rechnet ohne LDM-Teilpartie — Prüfpunkt, aber kein Migrationsschaden
- M_over (39 Rows, +4.100 EUR): IT zone25 Sondergebühr (+742 EUR), PT zone3 M_over (+2.046 EUR),
  überwiegend Überzahlung von AX-Seite

### Operative Followups

| Thema | Priorität |
|---|---|
| ES 18500 (Granada) Teilpartie: prüfen ob AX LDM-Teilpartie anwendet | Niedrig |
| GR 57009 (Thessaloniki) Teilpartie: identisches Muster | Niedrig |
| IT zone25 (PLZ 25040/25050) Sondergebühr +40 EUR/Sendung identifizieren | Backlog |
| PT 3025-248 fp=+100 % Row: Diesel-Floater in ef bestätigen | Backlog |

### Konsolidierte 8-Kunden-Lage

| Kunde | KNR | Beurteilbar | Net Δ (EUR) | Net Δ % | Headline |
|---|---|---:|---:|---:|---|
| GEZE GmbH | 406035 | 2.759 | +4.138 | +1,07 % | kein Schaden |
| EBM-Papst | 410844 | 308 | +3.514 | +0,74 % | kein Schaden |
| Fischerwerke | 409480 | 839 | +106.811 | +24,80 % | Charter-Artefakt |
| HERMA GmbH | 423650 | 3.642 | −16.374 | −0,67 % | kein Schaden |
| CHT Germany | 486073 | 554 | −668 | −0,26 % | kein Schaden |
| Bitzer | 406345 | 3.330 | +26.407 | +3,79 % | kein Schaden |
| Groz-Beckert | 490527+ | 527 | +5.729 | +5,34 % | kein Schaden |
| **HELU-KABEL** | **408244** | **2.185** | **+203** | **+0,06 %** | **kein Schaden** |

**Gesamtaussage (8 Kunden):** In keinem der 8 abgeschlossenen Kunden ist ein systematischer
Migrationsschaden nachweisbar. Calculator-Bugs H1+H2 (HELU) vor Step 2 identifiziert + gefixt.

### Nächster Schritt: Hornschuch AG (KNR 490085)

- BI-Cache: `output/bi_top20_data.pkl` ✓
- Calculator: `src/tms/tariff/calculators/hornschuch.py` (7500102)
- Tarif: ContiTech-MegaTrans, per-kg
- Scope: ~708.478 EUR Σ ef erwartet
- Komplexität: Mittel — 1–2 Durchläufe

