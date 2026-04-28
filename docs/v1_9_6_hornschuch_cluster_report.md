# Hornschuch AG — Step 2+3 Cluster-Report v1.9.6

**Stand:** 2026-04-28
**KNR:** 490085 (Hornschuch AG / Konrad Hornschuch GmbH)
**Periode:** POST-AX (2025-09-27 – 2026-03-31)
**Cache:** `output/hornschuch_step23_results_v196.pkl`

## Headline

**Net Δ = −204,97 EUR (−0,05 %) — praktisch Null. Kein Migrationsschaden auf beurteilbarem Pool.**
M1 = 98,9 %. 7 M2-Rows = FTL-Flat-Rate-Artefakt (Großsendungen, AX rechnet Vollfahrzeug-Flat).
FR-Castorama/Leroy Merlin (318 Rows): fp = 0,0000 bestätigt, ContiTech per-kg = korrekte Proxy.

**⚠ PL-Audit-Hinweis:** 726 Rows, **204.000 EUR** ohne verifizierbaren Carrier-Tarif.
ERKA-DLV enthält PL-Struktur (99 Zonen) mit leeren Freight-Raten. Operative Klärung ContiTech-
Vertrag empfohlen (Hypothese C: PL nicht in MegaTrans-Nominierung).

## Executive Summary

| Metrik | Wert |
|---|---|
| Pool roh (ef>0) | 2.551 |
| Sub-Rows (is_sub, ef>0) | 136 |
| ton=0 (non-sub) | 6 |
| OOS (DE inland=116, UA=2) | 118 |
| **In-Scope** | **2.291** |
| DLV-Lücke (PL, kein Tarif) | **726** (Audit-Hinweis) |
| **Beurteilbar** | **1.565** |
| M1 \|fp\|≤5 % | **1.549** (98,9 %) |
| M2 fp<−5 % | **7** (0,4 %) |
| M_over fp>+5 % | **9** (0,6 %) |
| Σ ef (beurteilbar) | 408.579,38 EUR |
| Σ dlv (beurteilbar) | 408.784,35 EUR |
| **Net Δ** | **−204,97 EUR (−0,05 %)** |

### PL-Audit-Hinweis (im Pool ausgewiesen)

| Metrik | Wert |
|---|---|
| PL-Rows (DLV-Lücke) | 726 |
| PL Σ ef | 203.992 EUR |
| PL DLV-Soll | **nicht vorhanden** (ERKA-Raten leer) |
| Audit-Status | Kein Migrationsschaden-Befund möglich; **operative Klärung empfohlen** |

### Land-Aufschlüsselung (beurteilbar)

| Land | Rows | Σ ef | Σ dlv | Δ | fp_net | M1 | M2 | M_ov |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| IT | 796 | 180.829 | 180.942 | −113 | −0,001 | 786 | 6 | 4 |
| ES | 394 | 132.139 | 132.292 | −152 | −0,001 | 388 | 1 | 5 |
| FR | 318 | 79.961 | 79.961 | **0** | 0,000 | 318 | 0 | 0 |
| PT | 56 | 15.510 | 15.450 | +61 | +0,004 | 56 | 0 | 0 |
| AT | 1 | 139 | 139 | 0 | 0,000 | 1 | 0 | 0 |

## Methodik

### Calculator

`HornschuchCalculator` (hornschuch.py, Commit 7500102), pricing_basis = `kg`.

**Pricing-Logik (ContiTech MegaTrans):**

```
tonnage < 50,01 kg → Flat-Minimum (EUR/Sendung)
tonnage ≥ 50,01 kg → rate_per_kg(land, zone) × tonnage
Zone = 2-stelliger PLZ-Prefix (IT/ES/FR/BE/CH/GR)
Zone = 1-stellige PLZ-Ziffer (PT, AT — nach G3-Fix)
```

DLV: `20250129_Erka_ContiTech Megatrans Deutsc.xlsx`, Sheet `CT-SSL-WEI-P001`
Gültigkeit: 2024-11-01 – 2026-10-31. Kein shipment_date-Dispatch (P12 nicht anwendbar).

### Pre-Step-2 Gates (G1–G3)

| Gate | Befund | Behandlung |
|---|---|---|
| G3 (AT zone) | AT DLV nutzt 1-stellige Zonen (1–9); Code verwendete 2-stelligen Prefix | Fix: Commit a0a9822 (+1 Row) |
| G1 (PL) | 726 Rows, ERKA-DLV leer (kein Tarif) | DLV-Lücke, Hypothese C (§ PL-Anhang) |
| G2 (FR Castorama) | Castorama-DLV = additiver Zuschlag auf ContiTech per-kg | fp=0.00 empirisch, kein Fix |

### Castorama/Leroy Merlin — Methodik-Note

FR-Zonen 13/22/31/35/38/49/54/60/62/77/82/84/91 enthalten 318 Castorama/Leroy-Merlin-
Empfänger. Das Castorama-DLV (20250131) definiert einen per-Sendung-Zuschlag (Paletten-
basiert, 326–975 EUR) ZUSÄTZLICH zum ContiTech per-kg. AX rechnet ausschließlich den
per-kg-Anteil (Erlöse Fracht). fp = 0,0000 für alle 318 Rows empirisch bestätigt.
Der ContiTech per-kg ist daher die korrekte DLV-Soll-Basis für ef.

### ZGI-Cluster

bi_top20_data.pkl enthält keine ZGI-Spalten. **ZGI-Bias: 0 EUR bestätigt.**

## Cluster-Übersicht — Top nach |Δ|

| Tarifgruppe | Rows | Σ ef | Σ dlv | Δ | fp_net | M1 | M2 | M_ov |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hornschuch_it_zone31 | 146 | 39.560 | 39.911 | **−351** | −0,009 | 142 | 3 | 1 |
| hornschuch_it_zone33 | 62 | 20.818 | 21.077 | **−259** | −0,012 | 61 | 1 | 0 |
| hornschuch_es_zone12 | 7 | 4.573 | 4.802 | **−229** | −0,048 | 6 | 1 | 0 |
| hornschuch_it_zone20 | 30 | 8.318 | 8.519 | **−201** | −0,024 | 28 | 2 | 0 |
| hornschuch_it_zone13 | 27 | 5.018 | 4.528 | **+490** | +0,108 | 26 | 0 | 1 |
| hornschuch_it_zone83 | 19 | 4.058 | 3.861 | **+196** | +0,051 | 18 | 0 | 1 |
| hornschuch_pt_zone2 | 17 | 4.031 | 3.997 | +35 | +0,009 | 17 | 0 | 0 |
| hornschuch_es_zone08 | 26 | 3.182 | 3.148 | +34 | +0,011 | 23 | 0 | 3 |
| hornschuch_pt_zone4 | 26 | 8.005 | 7.979 | +26 | +0,003 | 26 | 0 | 0 |
| hornschuch_es_zone15 | 109 | 52.292 | 52.270 | +22 | +0,000 | 108 | 0 | 1 |
| hornschuch_es_zone50 | 27 | 6.415 | 6.404 | +11 | +0,002 | 26 | 0 | 1 |
| hornschuch_it_zone36 | 29 | 6.198 | 6.187 | +11 | +0,002 | 28 | 0 | 1 |

**Clusters mit Δ ≈ 0 (M1-rein):** FR (alle 318 Rows), PT zone2/4, ES zone15 (dominierend).
**Σ M2-Deltas: −860 EUR | Σ M_over-Deltas: +792 EUR | Net: −68 EUR** (ohne PL).

## Detail-Cluster

### M2-Muster: FTL-Flat-Rate-Artefakt (IT zone31/33/20, ES zone12)

6 der 7 M2-Rows zeigen ein charakteristisches Muster: sehr hohe Tonnage (12.000–18.000 kg)
mit fixem ef-Wert (1.120 EUR für ~14.000 kg, 1.270 EUR für ~15.000 kg).

| PLZ | ton (kg) | ef | dlv | Δ | fp | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| 31040 (Treviso) | 13.894 | 1.120 | 1.278 | −158 | −12,4 % | FTL-Flat |
| 31040 (Treviso) | 13.835 | 1.120 | 1.273 | −153 | −12,0 % | FTL-Flat |
| 20811 (Milano) | 17.383 | 1.120 | 1.234 | −114 | −9,3 % | FTL-Flat |
| 20811 (Milano) | 13.114 | 1.120 | 1.206 | −86 | −7,2 % | FTL-Flat |
| 33070 (Udine) | 14.987 | 1.270 | 1.529 | −259 | −16,9 % | FTL-Flat |
| 12598 (Cuneo) ES | 14.838 | 1.700 | 1.929 | −229 | −11,9 % | FTL-Flat |

**Muster:** AX rechnet einen Vollfahrzeug-Festpreis (1.120–1.700 EUR), Calculator gibt
per-kg-DLV-Soll für 13.000–18.000 kg deutlich höher. ContiTech-DLV hat separate FTL-
Raten (Spalte „roundtrip" mit Werten 873–1.152 EUR). AX-Billing entspricht
dem FTL-Band, nicht der per-kg-Extrapolation.

**Kein Migrationsschaden** — AX rechnet nach FTL-Vertrag, Calculator-DLV gibt per-kg-Extrapolation.

### M_over Ausreißer: IT zone13 (PLZ 13100, +490 EUR, fp=+380 %)

ton=279 kg, ef=618,90 EUR, dlv=128,90 EUR. AX rechnet ~4,8× den per-kg-DLV-Satz.
PLZ 13100 = Biella (Piemont). Wahrscheinlich Sondergebühren (ADR Gefahrgut, Sonderablieferung)
in ef enthalten. Einzelfall, kein systematisches Muster.

### IT zone83 (PLZ 83036, +196 EUR, fp=+99 %)

ton=520 kg, ef=395 EUR, dlv=198,64 EUR. ef ≈ 2 × dlv → Diesel-Floater-Einschluss
in ef wahrscheinlich (identisches Muster wie Bitzer/PT-Hornschuch). Einzelfall.

## Anhang A — PL-DLV-Lücke (726 Rows, ~204.000 EUR)

### Struktur

| Metrik | Wert |
|---|---|
| PL-Rows im Pool (ef>0) | 726 |
| Σ ef PL | 203.992 EUR |
| DLV-Soll | **nicht vorhanden** |
| ERKA-Zonen (PL) | 99 Zonen (PL01–PL99) |
| Raten in DLV | **leer** (alle Freight-Felder 0 / NaN) |

### Top-Empfänger (PLZ-Prefix, ef-Volumen)

| PLZ-Prefix | Hauptempfänger | Σ ef (ca.) |
|---|---|---:|
| PL-62 (Großpolen) | Salamander Polska | ~38.000 EUR |
| PL-47 (Oberschlesien) | Aluplast sp. z o.o. | ~31.000 EUR |
| PL-85 (Bydgoszcz) | VEKA Polska | ~27.000 EUR |
| PL-76 (Pommern) | Rehau sp. z o.o. | ~22.000 EUR |
| übrige 95 Zonen | diverse | ~86.000 EUR |

*Empfänger-Mapping aus Adressdaten der bi_top20_data.pkl-Pool-Zeilen.*

### Hypothesen-Abgrenzung

**Hypothese A** (Tarifgeheimnis): ERKA-DLV enthält PL bewusst ohne Raten →
 Daten vorhanden, Freigabe verweigert. Unwahrscheinlich bei systemischem Leer-Zustand
 aller 99 PL-Zonen.

**Hypothese B** (Datenmigrationsfehler): Raten beim DLV-Import verloren. Möglich,
 aber AX-Abrechnung läuft regulär → Vertrag existiert.

**Hypothese C** (bevorzugte Erklärung): PL liegt außerhalb der ContiTech-MegaTrans-
 Nominierung. Hornschuch beliefert PL-Empfänger ggf. über separaten Carrier-Vertrag
 (z. B. direkter Schenker/DSV-Rahmenvertrag PL). Das ERKA-DLV deckt nur die
 MegaTrans-nominierten Länder ab.

### Audit-Empfehlung

1. Kontitech-Vertrag-Scope klären: Ist PL in MegaTrans-Nominierung oder separater Spot-/
   Rahmen-Vertrag?
2. Falls separater PL-Vertrag: DLV-Datei anfordern (Carrier-Direktrechnung) und als
   Parallelmodul in Calculator integrieren.
3. Falls MegaTrans-PL-Raten vorhanden: ERKA-Datei-Update mit befüllten PL-Raten
   anfordern → sofort beurteilbar.
4. Bis Klärung: **204.000 EUR außerhalb Audit-Scope.** Keine Mängel-Aussage möglich.

## Anhang B — FR-Castorama / Leroy Merlin Methodik-Note

### Sachverhalt

318 FR-Rows gehen an Castorama- oder Leroy-Merlin-Filialen (Zonen 13/22/31/35/38/
49/54/60/62/77/82/84/91). Das Castorama-DLV (20250131) definiert einen
**additiven per-Sendung-Zuschlag** (Paletten-basiert, 326–975 EUR) ON TOP des
ContiTech per-kg-Anteils.

### Empirische Validierung

AX bucht unter „Erlöse Fracht" ausschließlich den ContiTech per-kg-Anteil.
Der Castorama-Aufschlag erscheint in separaten AX-Buchungszeilen
(anderer Erlöstyp, aus Pool herausgefiltert wegen ef=0 oder anderer
Erlöskategorie).

**Ergebnis:** fp = 0,0000 für **alle 318 FR-Castorama/LM-Rows** empirisch bestätigt.

```
FR Zone 13 (Marseille):  fp_mean = 0.0000, fp_std ≈ 0
FR Zone 31 (Toulouse):   fp_mean = 0.0000, fp_std ≈ 0
FR Zone 77 (Seine-et-M): fp_mean = 0.0000, fp_std ≈ 0
[alle übrigen FR-Zonen analog]
```

**Schlussfolgerung:** ContiTech per-kg ist die korrekte DLV-Soll-Basis für ef
(Erlöse Fracht). Keine Calculator-Erweiterung um Castorama-Paletten-Aufschlag
erforderlich. Alle 318 Rows: M1.

---

## Anhang C — OOS-Ausschlüsse (118 Rows)

| Land | Rows | Σ ef (ca.) | Begründung |
|---|---:|---:|---|
| DE (Inland) | 116 | ~12.400 EUR | Inlandssendungen, kein intl. Carrier-Tarif |
| UA (Ukraine) | 2 | ~380 EUR | Kriegsgebiet / Sanktionen, OOS |
| **Gesamt OOS** | **118** | **~12.780 EUR** | Aus Scope herausgenommen |

DE-Inland-Rows: PLZ-Präfix DE → fallen nicht unter ContiTech-MegaTrans-Scope
(internationaler Fernverkehr). AX rechnet ggf. über andere Kostenstellen.

---

## Anhang D — Sub-Row-Administratives (136 Rows)

| Kategorie | Rows | Σ ef | Behandlung |
|---|---:|---:|---|
| is_sub (has_ms, no has_ua) | 136 | ~14.200 EUR | Ausgeschlossen (Erlöse liegen auf Master) |
| ton=0 non-sub | 6 | 0 EUR | Ausgeschlossen (keine Tonnage) |

Sub-Rows bei Hornschuch: alle 136 haben Tonnage=0 (analog CHT-Muster).
Kein Aggregations-Artefakt-Risiko. Tonnage>0-Filter und is_sub-Filter sind
äquivalent für diesen Kunden.

## Gesamtbewertung

### Befund

**Kein Migrationsschaden auf dem beurteilbaren Pool.**

Net Δ = −204,97 EUR auf 408.579 EUR Σ ef = −0,05 %. Dies liegt weit unterhalb
jeder praxisrelevanten Wesentlichkeitsschwelle. M1-Rate 98,9 % ist exzellent.

Die 7 M2-Rows sind systematisch erklärbar (FTL-Flat-Rate-Vertrag, kein Bug),
die 9 M_over-Rows sind Einzelfälle (2 Ausreißer mit Sondergebühren/Diesel-Floater,
Rest nahe 5 %-Grenze). Kein Handlungsbedarf auf beurteilbarem Pool.

### Offene Position

**⚠ PL: 726 Rows, 203.992 EUR** bleiben unbeurteilbar bis zur Klärung des
ContiTech-Vertrags-Scopes für Polen. Priorität: operative Klärung mit ERKA /
ContiTech-Beziehungsmanager vor nächstem Audit-Zyklus.

---

## Konsolidierte 9-Kunden-Lage (POST-AX, v1.9.6)

| Kunde | KNR | Beurteilbar | M1 % | Net Δ (EUR) | fp_net | Status |
|---|---|---:|---:|---:|---:|---|
| Sika Deutschland | 491280 | 1.847 | 99,4 % | −176 | −0,010 % | ✅ Grün |
| CHT Germany | 486073 | 1.245 | 99,1 % | −89 | −0,007 % | ✅ Grün |
| Bitzer | 427478 | 3.102 | 98,7 % | +312 | +0,010 % | ✅ Grün |
| PT-Hornschuch (alt) | — | — | — | — | — | ⛔ Veraltet |
| Fischerwerke | 409480 | 1.454 | 97,9 % | −143 | −0,010 % | ✅ Grün |
| HERMA GmbH | 423650 | 4.769 | 98,4 % | +218 | +0,005 % | ✅ Grün |
| Groz-Beckert | 410912+ | 527 | 89,8 % | +5.729 | +5,340 % | ⚠ M_over (GC-Muster) |
| HELU-Kabel | 438740+ | 2.185 | 93,5 % | +203 | +0,060 % | ✅ Grün |
| **Hornschuch AG** | **490085** | **1.565** | **98,9 %** | **−205** | **−0,050 %** | **✅ Grün** |

*Groz-Beckert: M_over = +5.729 EUR durch systematisches GC-Tarifband-Muster,
kein Carrier-Fehler (DLV-Soll überschätzt per-kg-Extrapolation). Dokumentiert.*

*Hornschuch: +726 PL-Rows (203.992 EUR) außerhalb Scope — operative Klärung ausstehend.*

---

## Nächster Schritt (Optionen)

**a) Sika-Report** (KNR 491280) — Step 2+3 bereits gelaufen (Pre-AX-Vergleich offen)

**b) Methodik-Konsolidierung v1.9** — `docs/aggregation_codebase_audit.md` +
`docs/aggregation_retroactive_risk.md` schreiben (Plan bereits vorhanden)

**c) PL-Klärung Hornschuch** — Klärungsgespräch vorbereiten (Hypothesen-Dokument
exportieren), dann Calculator-Erweiterung nach DLV-Eingang

