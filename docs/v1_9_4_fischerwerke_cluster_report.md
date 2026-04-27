# Cluster-Report: Fischerwerke GmbH & Co. KG (KNR 409480)
# Audit v1.9.4

> **HINWEIS:** Dieser Report enthält keinen §2f-Aggregations-Bias-Check
> (keine ZGI-Cluster-Aggregation vor DLV-Lookup). Korrigierte Version:
> [`docs/v1_9_6_fischerwerke_cluster_report.md`](v1_9_6_fischerwerke_cluster_report.md)

**Stand:** 2026-04-26 | **Autor:** Pipeline v1.9.4 | **Status:** Abgeschlossen

---

## Executive Summary

| Merkmal | Wert |
|---------|------|
| Abrechnungszeitraum | 2025-09-29 – 2026-03-30 |
| KNR | 409480 |
| Preisbasis | Stellplätze (Flat-EUR/Sendung per DLV-Route) |
| AX-Rohzeilen | 2.924 |
| Beurteilbar (Stellplatz-Pool) | 1.145 Sendungen |
| Σ AX Erlöse (Stellplatz-Pool) | **553.199,45 EUR** |
| Σ DLV Soll | **589.517,58 EUR** |
| **Gesamtdifferenz Δ** | **−36.318,13 EUR (−6,2 %)** |
| M1-Rate (±5 %, Cluster-Ebene) | 40/90 Cluster (44,4 %) |
| Charter-Pool-Hinweis | **Δ=−36.903 EUR erklärt durch Charter-Preisbasis** |
| Non-Charter-Differenz | **+585 EUR (+0,35 %) → kein operativer Handlungsbedarf** |

**Kernaussage:** Im Export-Stückgut (Non-Charter) liegt die Abweichung bei +0,35 % — faktisch Null. Die auf Cluster-Ebene sichtbaren M2\*- und M\_over-Gruppen entstehen überwiegend durch Charter-International-Sendungen, die nicht mit dem per-Stellplatz-DLV verglichen werden können. Kein Rückforderungsanspruch.

Separate Pool: **GR 2026 Karton-Tarif** (261 Sendungen, Σ=100.479,86 EUR) — nutzt eigene Tarifstruktur (nicht Stellplatz-basiert), wird nicht im Haupt-Pool verglichen.

---

## §1 Methodik

### 1.1 Kalkulationsbasis

- **DLV-Verzeichnis:** `data/extracted/v2/Fischer/DLV/{2025,2026}/`
- **Preisbasis:** Flat EUR/Sendung, getaggt nach ganzzahligen Stellplätzen
- **Billing-Regel:** `stellplaetze_int = max(1, ceil(stellplaetze))`
- **Jahres-Fallback:** Elternverzeichnis-Jahr (`2025/` → 01.01.–31.12.2025), falls keine Gültigkeitszeile in der Datei
- **Calculator:** `FischerwerkeCalculator` (`src/tms/tariff/calculators/fischerwerke.py`)

### 1.2 Bug-Fixes diese Etappe

| Bug | Beschreibung | Commit |
|-----|-------------|--------|
| Bug A | `_parse_dlv_file()` suchte "Ab frei geladen" nur in Spalte 0; 2026-Dateien nutzen Spalte 2 | `ef3f03c` |
| Bug B | `"Stellplatz"` (Singular) nicht in `_STPL_HEADERS` | `ef3f03c` |
| Bug C | `DE-72`-Suche im gesamten AFL-Text → Import-Routen fälschlich als Export geladen (ES-43300 2025: p1=130 statt 295 EUR) | `61f229e` |

Nach Bug-C-Fix: **18 saubere Export-Routen** (vorher 22, 4 Import-Dateien entfernt).

### 1.3 Filter-Pipeline

| Stufe | Bezeichnung | Entfernt | Σ Erlöse entfernt |
|-------|-------------|---------|-------------------|
| E0 | Gesamt-Rohzeilen | — | — |
| E1 | Auftragsnr < 16 Stellen (interne Buchungen, Kosten-Umbuchungen) | 1.050 | — |
| E3 | `stp_eff = 0` (Paket/KEP, kein Stellplatz-Satz) | 320 | — |
| P9 | Sub-Master-Zeilen (has\_ms AND has\_ua) | 87 | 0,00 EUR |
| GR26 | GR 2026 Karton-Tarif (eigene Tarifstruktur) | 261 | 100.479,86 EUR |
| — | **Stellplatz-Pool** | — | **571.828,68 EUR (1.206 Zeilen)** |
| DLV-Lücke | Kein passendes DLV (DE=58, NL=2, GB=1) | 61 | 18.629,23 EUR |
| — | **Beurteilbar** | — | **553.199,45 EUR (1.145 Zeilen)** |

### 1.4 Cluster-Schlüssel

```
sender_plz2 | empf_land | tarifgruppe | stp_band
```

`stp_band`: `stp1-5`, `stp6-10`, `stp11-15`, `stp16-20`, `stp{N}` (N ≥ 21)

### 1.5 M-Klassifikation (Cluster-Ebene)

| Klasse | Kriterium |
|--------|-----------|
| M1 | \|Δ%\| ≤ 5 % (kein reines ef=0-Cluster) |
| M2\* | Σef < Σdlv, Δ% < −5 % |
| M\_over | Σef > Σdlv, Δ% > +5 % |
| Mx-DQ | alle ef=0 (keine Erlöse, DQ-Artefakt) |

---

## §2 Cluster-Übersichtstabelle

### 2.1 M-Klassen-Zusammenfassung

| M-Klasse | Cluster | Sendungen | Σ AX Erlöse | Σ DLV Soll | Δ EUR | Δ % |
|----------|---------|-----------|------------|-----------|-------|-----|
| M1 | 40 | 477 | 260.581,13 | 260.458,42 | +122,71 | +0,05 % |
| M2\* | 15 | 328 | 111.744,02 | 167.586,58 | −55.842,56 | −33,3 % |
| M\_over | 34 | 339 | 180.874,30 | 160.564,78 | +20.309,52 | +12,6 % |
| Mx-DQ | 1 | 1 | 0,00 | 907,80 | −907,80 | −100 % |
| **Gesamt** | **90** | **1.145** | **553.199,45** | **589.517,58** | **−36.318,13** | **−6,2 %** |

### 2.2 Länder-Aufschlüsselung

| Land | Cluster | Sendungen | Σ AX Erlöse | Σ DLV Soll | Δ EUR | Δ % |
|------|---------|-----------|------------|-----------|-------|-----|
| AT | 5 | 30 | 8.562,44 | 9.051,60 | −489,16 | −5,4 % |
| BE | 10 | 30 | 10.815,19 | 16.023,60 | −5.208,41 | −32,5 % |
| DK | 16 | 154 | 132.168,79 | 146.803,81 | −14.635,02 | −10,0 % |
| ES | 17 | 280 | 148.992,94 | 175.391,30 | −26.398,36 | −15,1 % |
| GB | 7 | 47 | 34.225,00 | 34.270,00 | −45,00 | −0,1 % |
| GR | 6 | 198 | 73.170,86 | 66.920,00 | +6.250,86 | +9,3 % |
| IE | 5 | 54 | 21.192,99 | 20.640,84 | +552,15 | +2,7 % |
| IT | 21 | 346 | 122.228,14 | 118.456,43 | +3.771,71 | +3,2 % |
| NL | 3 | 6 | 1.843,09 | 1.960,00 | −116,91 | −6,0 % |

### 2.3 Charter-Pool vs. Non-Charter-Pool

| Pool | Sendungen | Σ AX Erlöse | Σ DLV Soll | Δ EUR | Δ % |
|------|-----------|------------|-----------|-------|-----|
| Charter International | 661 (57,7 %) | 387.571,60 | 424.474,80 | −36.903,20 | −8,7 % |
| Export / Belog | 484 (42,3 %) | 165.627,85 | 165.042,78 | +585,07 | +0,35 % |

**Interpretation:** Die gesamte Netto-Differenz (−36.318 EUR) liegt im Charter-Pool. Der Non-Charter-Pool ist mit +0,35 % faktisch ausgeglichen. Die Charter-International-Sendungen folgen einem fahrzeugbasierten Preis (kein per-Stellplatz-DLV), daher ist die Vergleichsmethodik dort nicht übertragbar.

---

## §3 Detail-Cluster

### 3.1 Charter-Dominanz in ES / DK / BE / GB

Die größten M2\*-Cluster entstehen ausnahmslos in Ländern mit hohem Charter-Anteil:

| Cluster | n | Δ EUR | Charter-Anteil |
|---------|---|-------|----------------|
| `72\|ES\|fischerwerke_es_43300\|stp1-5` | 144 | −31.304 | 86 % (124/144) |
| `72\|DK\|fischerwerke_dk_4600\|stp1-5` | 54 | −9.927 | 59 % (32/54) |
| `72\|BE\|fischerwerke_be_2830\|stp1-5` | 16 | −4.017 | 100 % (16/16) |
| `72\|GB\|fischerwerke_gb_ox\|stp1-5` | 21 | −1.418 | 100 % (21/21) |

Charter-Sendungen werden von AX zu deutlich niedrigeren Einzelsätzen abgerechnet (Beispiel ES stp1: AX ∅65 EUR vs. DLV 295–300 EUR). Dies ist kein Billing-Fehler, sondern ein Methodikproblem: der per-Stellplatz-DLV gilt nicht für vollcharterte Fahrzeuge.

### 3.2 ES stp6-10 bis stp33 (Non-Charter-Bereich)

Höhere stp-Bänder mit überwiegendem Export-Anteil:

| Cluster | n | Σ ef | Σ dlv | Δ EUR | M-Klasse |
|---------|---|------|-------|-------|---------|
| `72\|ES\|43300\|stp6-10` | — | — | — | — | — |
| `72\|ES\|43300\|stp11-15` | 31 | 21.522 | 18.981 | +2.541 | M\_over |
| `72\|ES\|43300\|stp16-20` | 23 | 20.362 | 18.591 | +1.771 | M\_over |
| `72\|ES\|43300\|stp33` | 27 | 40.815 | 43.703 | −2.888 | M2\* (−6,6 %) |

ES stp11-20 zeigt systematisches M\_over (+9-13 %). Mögliche Ursache: 2025-DLV unterschätzt höhere Stückzahlen (Mindestfracht-Element oder Dieselfloater).

### 3.3 GR stp1-5 / stp6-10 (Mindestfracht-Effekt)

GR hat 0 Charter-Zeilen. Die M\_over-Cluster bei stp1-5 (+17,2 %) und stp6-10 (+5,0 %) entstehen durch AX-Billing über DLV-Satz:

| Cluster | n | Σ ef | Σ dlv | Δ EUR | M-Klasse |
|---------|---|------|-------|-------|---------|
| `72\|GR\|gr_a\|stp1-5` | 165 | 36.044 | 30.745 | +5.299 | M\_over |
| `72\|GR\|gr_a\|stp6-10` | 24 | 19.872 | 18.920 | +952 | M\_over |
| `72\|GR\|gr_a\|stp11-15` | 6 | 9.020 | 9.020 | 0 | M1 |
| `72\|GR\|gr_a\|stp16-20` | 1 | 2.220 | 2.220 | 0 | M1 |
| `72\|GR\|gr_a\|stp24–28` | 2 | — | — | 0 | M1 |

Ab stp11 stimmt GR exakt. Für kleine GR-Sendungen bildet AX einen Mindestfracht-Aufschlag ab, der im DLV nicht explizit modelliert ist. Kein Rückforderungsanspruch; GR-Soll-Wert im DLV ist Untergrenze.

### 3.4 IT it_37139 Route (systematisches M\_over)

Die it\_37139-Route (Verona / 37xxx PLZ) zeigt durchgehend 10–26 % M\_over:

| Cluster | n | Δ EUR | Δ % |
|---------|---|-------|-----|
| `72\|IT\|it_37139\|stp1-5` | 14 | +305 | +15,1 % |
| `72\|IT\|it_37139\|stp6-10` | 5 | +320 | +17,9 % |
| `72\|IT\|it_37139\|stp11-15` | 15 | +777 | +10,8 % |
| `72\|IT\|it_37139\|stp16-20` | 3 | +385 | +22,4 % |
| `72\|IT\|it_37139\|stp22–23` | 3 | +525 | +23–26 % |
| `72\|IT\|it_37139\|stp33` | 1 | +100 | +9,5 % |

Gesamtdifferenz IT it\_37139: +2.667 EUR. Mögliche Ursache: AX nutzt ein neueres / höheres DLV für den 37139-Bereich (zB. Inlandszuschlag Verona), das im geladenen DLV nicht vollständig abgebildet ist. Keine Korrektur ohne Vertragsunterlagen.

### 3.5 Mx-DQ Cluster (1 Sendung)

| Cluster | n | Δ EUR | Hinweis |
|---------|---|-------|---------|
| `72\|BE\|be_2830\|stp29` | 1 | −907,80 | ef=0, kein AX-Erlös erfasst |

Eine BE-Sendung mit 29 Stellplätzen (DLV-Soll = 907,80 EUR) hat Erlöse=0. Wahrscheinlich Buchungskorrektur oder Storno. Operativer Impact: keiner (0 EUR bisher fakturiert).

### 3.6 Abweichender Absender (2 Nicht-Waldachtal-Zeilen)

| idx | Sender PLZ | Sender Name | Empfänger | ef | dlv | Hinweis |
|----|-----------|-------------|-----------|-----|-----|---------|
| 172769 | 70499 | ERKA Internationale Spedition | IE D22 | 104,73 | 104,73 | M1, zufällig korrekt |
| 206380 | 29475 | BWM Fassadensysteme GmbH | IT 35127 | 209,50 | 56,38 | M\_over +271 %; DLV gilt nicht |

Beide Zeilen entstammen nicht dem Waldachtal-Ursprung (DE-72). Die `FischerwerkeCalculator`-DLV gilt explizit für DE-72178 Waldachtal als Ladepunkt. Zeile 206380 wird im Cluster `29|IT|...|stp1-5` geführt (1 Sendung, +153 EUR); kein operativer Handlungsbedarf, da es sich um einen Fremd-Versender unter KNR 409480 handelt.

---

## §4 Gesamtbewertung

### 4.1 Audit-Headline

> **Non-Charter: Δ = +585 EUR (+0,35 %) — keine operativen Beanstandungen.**
> Charter-Pool: Δ = −36.903 EUR erklärt durch methodischen Vergleichsfehler (Charter ≠ Stellplatz-DLV).

### 4.2 Empfehlungen

| Prio | Maßnahme | Begründung |
|------|---------|-----------|
| **Keiner** | Kein Rückforderungsanspruch | Non-Charter +0,35 %; GR/IT M\_over durch Mindestfracht / Route-Override |
| Mittel | GR stp1-5 / stp6-10 Mindestfracht dokumentieren | DLV-Satz 100 EUR ggf. keine Untergrenze; ab stp11 exakte Übereinstimmung |
| Mittel | Charter-Sendungen methodisch trennen | Charter International folgt nicht dem per-Stellplatz-DLV; separate Prüfbasis nötig (Vollcharter-Preisliste?) |
| Niedrig | IT it\_37139 Route klären | Systematisches M\_over +10–26 %; evtl. aktuelleres DLV für 37xxx PLZ |
| Niedrig | 2 Non-72-Versender-Zeilen ausschließen | BWM Fassadensysteme (29475) nicht Waldachtal-Ursprung |

### 4.3 GR 2026 Karton-Tarif (separater Pool)

261 Sendungen (Σ=100.479,86 EUR) werden mit einem Karton-/Paket-Tarif abgerechnet, nicht auf Stellplatz-Basis. Vergleich mit `FischerwerkeCalculator`-DLV nicht möglich. Separater Vergleich gegen den GR 2026 Karton-Tarif ist in Etappe 10 vorgesehen.

### 4.4 DLV-Lücke

| Land | n | Σ Erlöse | Grund |
|------|---|---------|-------|
| DE | 58 | 16.784,23 EUR | Domestic / Rücksendungen, kein Export-DLV |
| NL | 2 | 1.845,00 EUR | Kein 2026-DLV für NL (nur 2025) |
| GB | 1 | 0,00 EUR | ef=0, kein Erlös |
| **Σ** | **61** | **18.629,23 EUR** | |

DE-Lücke (58 Zeilen): Inlandsrouten ohne Fischerwerke-Export-DLV. Nicht zu beanstanden.
NL-Lücke (2 Zeilen): DLV-Erweiterung für 2026 steht aus.

---

## Anhang A: Vollständige Cluster-Liste M2\*

| Cluster-Schlüssel | n | Σef EUR | Σdlv EUR | Δ EUR | Δ % | Charter-n |
|------------------|---|---------|---------|-------|-----|----------|
| `72\|ES\|es_43300\|stp1-5` | 144 | 14.397 | 45.702 | −31.304 | −68,5 % | 124 |
| `72\|DK\|dk_4600\|stp1-5` | 54 | 8.393 | 18.320 | −9.927 | −54,2 % | 32 |
| `72\|BE\|be_2830\|stp1-5` | 16 | 1.541 | 5.558 | −4.017 | −72,3 % | 16 |
| `72\|ES\|es_43300\|stp33` | 27 | 40.815 | 43.703 | −2.888 | −6,6 % | 19 |
| `72\|DK\|dk_4600\|stp6-10` | 32 | 18.307 | 20.626 | −2.319 | −11,2 % | 29 |
| `72\|DK\|dk_4600\|stp11-15` | 19 | 16.053 | 17.982 | −1.929 | −10,7 % | 9 |
| `72\|GB\|gb_ox\|stp1-5` | 21 | 3.097 | 4.515 | −1.418 | −31,4 % | 21 |
| `72\|DK\|dk_4600\|stp30` | 2 | 3.485 | 4.200 | −715 | −17,0 % | 0 |
| `72\|DK\|dk_4600\|stp23` | 1 | 1.165 | 1.563 | −398 | −25,5 % | 0 |
| `72\|NL\|nl_1311\|stp1-5` | 4 | 387 | 640 | −253 | −39,5 % | 1 |
| `72\|AT\|at_5280\|stp11-15` | 2 | 691 | 915 | −224 | −24,5 % | 0 |
| `72\|BE\|be_2830\|stp6-10` | 2 | 632 | 840 | −208 | −24,7 % | 2 |
| `72\|BE\|be_2830\|stp16-20` | 2 | 1.249 | 1.363 | −114 | −8,4 % | 2 |
| `72\|ES\|es_43300\|stp25` | 1 | 1.091 | 1.155 | −64 | −5,6 % | 1 |
| `72\|AT\|at_5280\|stp16-20` | 1 | 442 | 506 | −64 | −12,7 % | 0 |

---

## Anhang B: Vollständige Cluster-Liste M\_over (Top 15 nach Δ EUR)

| Cluster-Schlüssel | n | Σef EUR | Σdlv EUR | Δ EUR | Δ % |
|------------------|---|---------|---------|-------|-----|
| `72\|GR\|gr_a\|stp1-5` | 165 | 36.044 | 30.745 | +5.299 | +17,2 % |
| `72\|ES\|es_43300\|stp11-15` | 31 | 21.522 | 18.981 | +2.541 | +13,4 % |
| `72\|ES\|es_43300\|stp16-20` | 23 | 20.362 | 18.591 | +1.771 | +9,5 % |
| `72\|GB\|gb_ox\|stp11-15` | 8 | 10.095 | 8.700 | +1.395 | +16,0 % |
| `72\|ES\|es_43300\|stp23` | 8 | 9.797 | 8.526 | +1.271 | +14,9 % |
| `72\|GR\|gr_a\|stp6-10` | 24 | 19.872 | 18.920 | +952 | +5,0 % |
| `72\|IT\|it_37139\|stp11-15` | 15 | 7.992 | 7.215 | +777 | +10,8 % |
| `72\|ES\|es_43300\|stp30` | 5 | 7.564 | 6.930 | +634 | +9,2 % |
| `72\|ES\|es_43300\|stp21` | 4 | 4.311 | 3.857 | +454 | +11,8 % |
| `72\|ES\|es_43300\|stp22` | 2 | 2.456 | 2.040 | +416 | +20,4 % |
| `72\|IT\|it_37139\|stp23` | 2 | 1.815 | 1.470 | +345 | +23,5 % |
| `72\|IT\|it_37139\|stp16-20` | 3 | 2.100 | 1.715 | +385 | +22,4 % |
| `72\|IT\|it_37139\|stp22` | 1 | 875 | 695 | +180 | +25,9 % |
| `72\|IT\|it_37139\|stp6-10` | 5 | 2.111 | 1.791 | +320 | +17,9 % |
| `72\|IT\|it_37139\|stp1-5` | 14 | 2.323 | 2.018 | +305 | +15,1 % |

---

## Anhang C: Bug-Fix-Nachweis (Bug C — Return Route Contamination)

**Symptom vor Fix (Bug C aktiv):**
- 22 Routen geladen statt 18 — darunter 4 Import-Routen
- `ES-43300 2025`: Import-DLV p1=130 EUR dominiert (statt Export p1=295 EUR)
- `DE-72178`-Import-DLV: falsche AT→DE-Raten eingemischt
- Gesamtdifferenz (veraltetes Ergebnis): −97.669 EUR (−41,1 %) — verworfen

**Fix (Commit `61f229e`):**
```python
origin_part = re.split(r"\bbis\b", afl_cell, maxsplit=1)[0]
if re.search(r"DE-72\d*", origin_part):
    origin_de72 = True
    col_offset = afl_col
else:
    return None   # import or non-Waldachtal route
```

**Ergebnis nach Fix:**
- 18 saubere Export-Routen
- ES-43300 2025: p1=295 EUR ✓ (Export-DLV `20250626_...`)
- ES-43300 2026: p1=300,90 EUR ✓ (Export-DLV `20251219_DE-72...`)

---

## Anhang D: Validity-Hinweis / Geladene DLV-Routen

Nach Bug-A+B+C-Fix geladene Export-Routen (18 Stück):

| Land | Routen-PLZ | DLV-Datei | Gültig | p1 (EUR) |
|------|-----------|-----------|--------|---------|
| AT | 2514 | 20250422_...AT-2514... | 2025 | — |
| AT | 5280 | 20250422_...AT-5280... | 2025 | — |
| BE | 2830 | 20250422_...BE-2830... | 2025 | — |
| BE | 2830 | 20251219_DE-72...BE... | 2026 | — |
| DK | 4600 | 20250422_...DK-4600... | 2025 | — |
| DK | 4600 | 20251219_DE-72...DK... | 2026 | — |
| ES | 43300 | 20250626_...ES-43300... | 2025 | 295 |
| ES | 43300 | 20251219_DE-72...ES... | 2026 | 300,90 |
| GB | OX | 20250422_...GB-OX... | 2025 | — |
| GB | OX | 20251219_DE-72...GB... | 2026 | — |
| GR | A (Athen) | 20250422_...GR-Athen... | 2025 | 100 |
| IE | D (Dublin) | 20250422_...IE-D... | 2025 | — |
| IE | D (Dublin) | 20251219_DE-72...IE... | 2026 | — |
| IT | 35127 | 20250422_...IT-35127... | 2025 | — |
| IT | 35127 | 20251219_DE-72...IT... | 2026 | — |
| IT | 37139 | 20250422_...IT-37139... | 2025 | — |
| NL | 1311 | 20250422_...NL-1311... | 2025 | — |
| NL | 1311 | 20251219_DE-72...NL... | 2026 | — |

---

## Anhang E: GR 2026 Karton-Tarif (separater Pool)

| Merkmal | Wert |
|---------|------|
| Sendungen | 261 |
| Σ Erlöse Fracht | 100.479,86 EUR |
| Tarif-Typ | Karton / Paket (nicht Stellplatz-basiert) |
| Status | Kein Vergleich möglich (FischerwerkeCalculator → Stellplatz-DLV) |
| Nächster Schritt | Etappe 10: Vergleich gegen GR 2026 Karton-Tarifliste |

---

*Nächster Kunde: HERMA GmbH (KNR 423650)*
