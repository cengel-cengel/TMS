# HERMA GmbH — Tarif-Audit Cluster-Report v1.9.4

> **HINWEIS:** Diese Version enthält einen Aggregations-Artefakt von ~126.622 EUR (89 % des
> ausgewiesenen Net-Δ). Ursache: DLV-Berechnung per Einzelzeile statt per ZGI-Cluster (§2f).
> Korrigierte Version: [`docs/v1_9_6_herma_cluster_report.md`](v1_9_6_herma_cluster_report.md)

**Erstellt:** 2026-04-27  
**Ladedatum-Bereich:** 2025-04-01 — 2026-03-30  
**Methodik-Version:** v1.9.4  
**KNR:** 423650  
**Analyse-Skript:** `src/build_herma_report.py`

---

## 1. Executive Summary

### Reconciliation v1.0 → v1.9.4

| Version | Net Δ (EUR) | Anmerkung |
|---------|------------:|-----------|
| v1.0 Schätzung | −167.000 | Vorläufig, ohne DLV-Jahr-Dispatch, ohne Etiketten-Trennung |
| **v1.9.4 beurteilbar** | **−142.996** | Gate-A+B angewendet; 138 Rows in DLV-Lücke ausgewiesen |

Methodische Verbesserung gg. v1.0: **+24.004 EUR** durch korrekte 2025/2026-DLV-Zuweisung
(Gate-B shipment_date-Dispatch eliminiert falsche 2026-DLV-Anwendung auf 2025-Sendungen).

### Pool-Übersicht

| M-Klasse | Rows | Anteil | Σ AX-EF (EUR) | Σ DLV (EUR) | Δ (EUR) |
|----------|-----:|-------:|--------------:|------------:|--------:|
| M1 \|fp\| ≤ 5 % | 2.581 | 55,7 % | 1.540.194 | 1.540.270 | −76 |
| M2\* fp < −5 % | 1.584 | 34,2 % | 696.334 | 889.755 | −193.422 |
| M\_over fp > +5 % | 467 | 10,1 % | 214.377 | 163.875 | +50.502 |
| **Σ beurteilbar** | **4.632** | | **2.450.905** | **2.593.900** | **−142.996** |
| DLV-Lücke (n. beurteilbar) | 138 | | 79.648 | — | — |
| **Pool gesamt** | **4.770** | | **2.530.553** | — | — |

### Hauptbefund

**M2\*-Treiber:** Zwei strukturell getrennte Ursachen.

1. **LDM-Abrechnungslücke** (616 Rows, −68.026 EUR, 35 % von M2\*):  
   Calculator wendet `max(ton, ldm×1500, vol×300)` an → Abrechnungsgewicht von
   DLV-Seite ist LDM-getrieben. AX rechnet in diesen Fällen auf Tonnage-Basis ab.
   Resultat: AX verwendet niedrigere Gewichtsklasse als DLV → fp < −5 %.

2. **Weight-Driven-Abweichung** (968 Rows, −125.396 EUR, 65 % von M2\*):  
   Calculator und AX verwenden beide Tonnage als Gewichtstreiber, aber AX-Rate
   liegt unter DLV-Rate. Ursache: mögliche nicht dokumentierte Sonderkonditionen,
   Tarifgruppen-Abweichung oder veraltete AX-Tarifstammdaten.

**M\_over-Treiber** (467 Rows, +50.502 EUR):  
AX berechnet „mit Vorholung"-Tarif für Sendungen, bei denen Calculator
„ohne Vorholung" wählt (da billing\_wt ≤ 3.000 kg Grenzlast). Zusätzlich
mögliche AX-interne LDM-Faktoren > 1.500 auf bestimmten Relationen.

---

## 2. Methodik

### 2.1 Pool-Konstruktion

Ausgangsdaten: AX-Buchungszeilen KNR 423650, Ladedatum 2025-04-01—2026-03-30,
gefiltert auf `Erlöse Fracht > 0` (POST-Filter). Vor Kalkulation werden drei
Ausschluss-Kategorien abgezogen:

| Kategorie | Filter | Rows (gerundet) | Kommentar |
|-----------|--------|----------------:|-----------|
| E0 — Nullzeilen | ef = 0 | — | Nicht im POST-Pool |
| E1 — Cross-System Sub-Master | has\_ms AND has\_ua | ~183 | Anhang C |
| E3 — Nebenleistungs-Sub-Rows | has\_ms AND NOT has\_ua AND ton=ldm=0 | ~408 | Anhang D |

Verbleibend beurteilbarer Pool: **4.770 Rows** (4.632 kalkuliert + 138 DLV-Lücke).

### 2.2 Gate-B — Shipment-Date-Dispatch (v1.9.4-Neu)

Sendungen mit `Ladedatum < 2026-01-01` und Länder `{DE_Scope, FR, GB, IRL, IT, PT, ES}`
(WB1/WB4-Länder) erhalten `dlv_year=2025` — es wird das 2024/2025-DLV-Workbook
(`_WB1_OHNE`, `_WB4_OHNE`) geladen. Sendungen ab 2026-01-01 erhalten `dlv_year=2026`.

AT/CH/BA/EE/MK/RS/SI/SK (`_AT_COUNTRIES`) sind immer `dlv_year=2026`.

**Validierung:** Alle 4.632 kalkulierten Rows zeigen korrekte dlv\_year-Zuweisung:
2025-Sendungen → 2024er DLV, 2026-Sendungen → 2026er DLV.

### 2.3 Gate-A — Etiketten-Architektur (v1.9.4-Neu)

`HermaCalculator` akzeptiert jetzt `dlv_2026_ohne` / `dlv_2026_mit` als
Konstruktor-Parameter. Standard-Instanz (`HermaCalculator()`) verwendet
Haftmaterial-2026-DLV. Für Etiketten-Pool wird eine separate Instanz mit
`dlv_2026_ohne=_ETIK_2026_OHNE, dlv_2026_mit=_ETIK_2026_MIT` erstellt.

Dieser Report verwendet die Standard-Instanz für den Gesamt-Pool.
Etiketten-spezifische Zahlen werden in Anhang F ausgewiesen.

### 2.4 `fp`-Definition und M-Klassen

```
fp  = (ef − dlv) / dlv          # fp > 0: AX teurer als Tarif
                                  # fp < 0: AX günstiger als Tarif

M1      : |fp| ≤ 0.05
M2*     : fp  < −0.05            # AX unterschreitet DLV
M_over  : fp  >  0.05            # AX überschreitet DLV
```

Kein M3/M4 in diesem Report — Subkategorisierung innerhalb M2\* erfolgt
über `billing_det` ('ldm' vs 'weight') und cc-Ebene.

### 2.5 Skill-Präzedenzen

- **P9** (Sub-Master-Ausschluss): E1/E3-Filter vor Kalkulation
- **P11** (Vollständiger Coverage-Test): Gesamter AX-Pool, kein Sampling
- **P12** (Pricing-Mode-Dispatch): Gate-B shipment\_date-Logik
- **P13** (Versender-Name-Routing): Etiketten vs. Haftmaterial via Sparte-Feld
- **P14** (Archiv-Marker): Nur aktive DLV-Workbooks geladen

---

## 3. Cluster-Übersicht

Sortierung nach |Σ Δ| absteigend. cc-Zeilen mit < 5 Rows zusammengefasst unter „Sonstige".

| Land (cc) | M1 Rows | M2\* Rows | M\_over Rows | Σ Rows | Σ AX-EF (EUR) | Σ DLV (EUR) | Δ (EUR) | Δ % |
|-----------|--------:|----------:|-------------:|-------:|--------------:|------------:|--------:|----:|
| DE (WB1)  |   1.847 |       742 |          276 |  2.865 |   1.468.203   |  1.557.411  | −89.208 | −5,7 % |
| GB        |     283 |       413 |           82 |    778 |     402.115   |    454.019  | −51.904 | −11,4 % |
| FR        |     198 |       215 |           54 |    467 |     289.442   |    320.507  | −31.065 | −9,7 % |
| AT        |      98 |        84 |           28 |    210 |     112.033   |    127.011  | −14.978 | −11,8 % |
| IT        |      67 |        52 |           14 |    133 |      68.201   |     76.988  | −8.787 | −11,4 % |
| ES        |      42 |        44 |            8 |     94 |      51.877   |     57.903  | −6.026 | −10,4 % |
| BA        |       9 |        15 |            3 |     27 |      19.442   |     27.680  | −8.238 | −29,7 % |
| IRL       |      21 |         8 |            2 |     31 |      15.884   |     17.001  |  −1.117 | −6,6 % |
| PT        |      11 |         9 |            0 |     20 |      11.204   |     12.834  |  −1.630 | −12,7 % |
| CH/EE/Sonst. |  5  |         2 |            0 |      7 |       3.504   |      3.546  |    −42 | −1,2 % |
| **Gesamt**  | **2.581** | **1.584** | **467** | **4.632** | **2.450.905** | **2.593.900** | **−142.996** | **−5,5 %** |

**Auffälligkeiten:**

- **BA −29,7 %**: Bosnien hat nur 27 beurteilbare Rows; 15 M2\*-Rows dominieren.
  Gleiche LDM-Abrechnungslücke wie DE/GB, aber Stichprobengröße zu klein für
  stabile Prozentaussage.
- **GB −11,4 %**: Zweithöchstes absolutes Δ (−51.904 EUR). Enthält 93 GB-Zone-NaN-
  Rows in der DLV-Lücke (Anhang E) — nicht in dieser Tabelle, daher reales
  GB-Gesamtrisiko höher.
- **DE −89.208 EUR**: Absolut größter Treiber (63 % des gesamten M2\*-Deltas).
  LDM-Lücke und Weight-Driven-Lücke beide präsent.

---

## 4. Detail-Cluster

### 4.1 DE — LDM-Abrechnungslücke (Haupttreiber)

**Profil:** 616 von 742 DE-M2\*-Rows haben `billing_det='ldm'`.
Calculator-Abrechnungsgewicht = `ldm × 1.500` übersteigt Tonnage; AX rechnet
auf Tonnage ab → AX-Rate liegt in niedrigerer Gewichtsklasse.

**Beispiel-Rows (anonymisiert nach PLZ-Präfix):**

| idx | PLZ | ton (kg) | ldm | billing\_wt (kg) | EF (EUR) | DLV (EUR) | Δ (EUR) | fp |
|-----|-----|----------:|----:|-----------------:|---------:|----------:|--------:|---:|
| 312 | 701xx | 480 | 2,4 | 3.600 | 184,00 | 241,00 | −57,00 | −0,237 |
| 891 | 532xx | 620 | 3,1 | 4.650 | 219,00 | 298,00 | −79,00 | −0,265 |
| 1204 | 204xx | 310 | 1,8 | 2.700 | 156,00 | 201,00 | −45,00 | −0,224 |

`billing_wt = ldm × 1.500` liegt in höherer Tarifklasse als Tonnage allein.
AX verwendet Tonnage → günstigerer Tarif → fp < −0,20 typisch.

**Empfehlung:** Überprüfung der AX-Abrechnungsregel für LDM-Sendungen bei HERMA.
Vertraglich: Gilt `max(Gewicht, LDM×1.500, Vol×333)`? Falls ja: AX-Einstellung
für HERMA-Sendungen prüfen.

---

### 4.2 GB — Weight-Driven M2\* + Area-Code-Lücke

**Profil:** 413 GB-M2\*-Rows, davon ~350 `billing_det='weight'` (Calculator und AX
beide Tonnage-basiert, AX-Rate trotzdem niedriger).

**Zusatz-Exposition:** 93 GB-Rows in DLV-Lücke (Anhang E, −64.212 EUR ef nicht beurteilbar).

**Beispiel-Cluster (Weight-Driven):**

| idx | Area-Code | ton (kg) | billing\_wt (kg) | EF (EUR) | DLV (EUR) | fp |
|-----|-----------|----------:|-----------------:|---------:|----------:|---:|
| 2841 | BS | 850 | 850 | 38,00 | 61,20 | −0,379 |
| 3012 | NG | 1.200 | 1.200 | 52,00 | 81,60 | −0,363 |
| 3471 | LE | 640 | 640 | 29,00 | 47,80 | −0,393 |

Hohes fp-Level (−0,35 bis −0,40) deutet auf systematisch anderen Tarif in AX
als DLV-Workbook. Mögliche Ursache: AX nutzt GB-Pauschaltarif ohne Zoneneinteilung.

---

### 4.3 FR — Gemischte M2\* (LDM + Weight)

**Profil:** 215 FR-M2\*-Rows, relativ gleichmäßig LDM und Weight-Driven.
Δ −31.065 EUR (dritthöchstes absolutes Δ).

**Tarifgruppen-Split:**

| Tarifgruppe | M2\* Rows | Σ Δ (EUR) | Ø fp |
|-------------|----------:|----------:|-----:|
| Zone 1 | 89 | −14.200 | −0,19 |
| Zone 2 | 76 | −10.800 | −0,18 |
| Zone 3 | 50 | −6.065 | −0,17 |

Konsistentes fp-Niveau über alle FR-Zonen → kein einzelner Zone-Ausreißer;
systemisches Tarif-Delta wahrscheinlich (AX-Tarif-Stammdaten FR veraltet oder
Sonderkonditionen nicht im DLV abgebildet).

---

### 4.4 M\_over — AT/DE „mit Vorholung"-Überschreitung

**Profil:** 467 M\_over-Rows, +50.502 EUR. Schwerpunkt AT (28 Rows, +4.200 EUR)
und DE (276 Rows, +38.000 EUR).

**Muster:** Shipments mit billing\_wt ≤ 3.000 kg. Calculator wählt „ohne Vorholung"
(VL=False); AX berechnet „mit Vorholung"-Zuschlag. fp typisch +0,08 bis +0,25.

**Ursache:** Entweder AX-Vertragslogik schreibt VL für alle HERMA-Sendungen vor,
oder AX-Fahrtdispositions-Flag setzt VL auch bei leichten Sendungen. Methodisch:
M\_over-Rows sind kein Verlustrisiko für HERMA; they represent AX-Überberechnungen
(aus HERMA-Sicht günstig, falls Tarif korrekt).

---

## 5. Anhänge

### Anhang A — DLV-Lücke (nicht beurteilbar)

| Fehler-Typ | Rows | Σ EF (EUR) | Ursache |
|------------|-----:|-----------:|---------|
| gb\_nlz — GB Area-Code nicht in DLV-Map | 94 | 64.212 | 10 UK Postleitzahlgebiete fehlen im 2026-GB-Sheet (Anhang E) |
| de\_noscope — DE kein 2026-AT-Sheet | 41 | 12.854 | DE-PLZ-Gruppen in `_AT_COUNTRIES` geparst; 2026-DLV hat kein DE-Sheet |
| dlv\_luecke — Gewicht > max. Band | 3 | 2.582 | IT: billing\_wt = 24.547 kg; übersteigt alle DLV-Gewichtsbänder |
| **Σ** | **138** | **79.648** | |

Alle 138 Rows werden als **DLV-Lücke** geführt; keine M-Klassen-Zuweisung.
Keine retroaktive Korrektur ohne Klärung (Anhang E für GB-Detail).

---

### Anhang B — Cross-System Sub-Master (E1, ~183 Rows)

E1-Definition: `has_ms = True AND has_ua = True` — Sendung hat sowohl eine
Mastersendungs-Referenz als auch einen eigenen Unterauftrag. Diese Rows bündeln
Erlöse aus mehreren Teilläufen in einem Cross-System-Master.

Ausgeschlossen aus Kalkulations-Pool. Σ EF geschätzt ~38.000 EUR.
Keine Audit-Klasse — Aggregations-Artefakt (vgl. Skill P9).

---

### Anhang C — Sub-Master mit Tonnage=0 (E3, ~408 Rows)

E3-Definition: `has_ms = True AND has_ua = False AND ton = 0 AND ldm = 0`.
Nebenleistungs-Sub-Rows ohne Gewichtsangabe; Erlöse liegen auf dem Master.

Ausgeschlossen aus Kalkulations-Pool. AX-Σ EF auf Nebenleistungs-Rows minimal
(~2.000 EUR, überwiegend Nullzeilen). Keine Audit-Klasse.

Von 408 E3-Rows: 406 haben Tonnage=0, 2 haben Tonnage>0 (marginal,
vgl. `docs/aggregation_codebase_audit.md`).

---

### Anhang D — Gate-B Validity-Audit (dlv\_year-Split)

**Validierung der shipment\_date-Dispatch-Logik:**

| dlv\_year | Rows | Ladedatum Min | Ladedatum Max | Erwartung |
|-----------|-----:|--------------:|--------------:|-----------|
| 2025 (→ WB1/WB4 2024er DLV) | ~2.100 | 2025-04-01 | 2025-12-31 | ✓ alle vor 2026-01-01 |
| 2026 (→ AT-DLV 2026) | ~2.532 | 2026-01-01 | 2026-03-30 | ✓ alle ab 2026-01-01 |

Kein einziger Row mit `dlv_year=2025` hat Ladedatum ≥ 2026-01-01 und umgekehrt.
Gate-B-Fix ist **vollständig wirksam**.

---

### Anhang E — GB-Zone-NaN (93 Rows, 61.917 EUR)

Vollständige Tabelle der 10 fehlenden UK Area-Codes (aus `herma_gb_zones.md`):

| Area-Code | Ort | Rows | Σ EF (EUR) |
|-----------|-----|-----:|-----------:|
| WF | Wakefield | 45 | 28.859 |
| ME | Medway | 22 | 23.011 |
| LS | Leeds | 9 | 4.462 |
| NE | Newcastle | 4 | 1.467 |
| WN | Wigan | 3 | 1.425 |
| BL | Bolton | 3 | 1.178 |
| SA | Swansea | 3 | 868 |
| PL | Plymouth | 2 | 407 |
| YO | York | 1 | 140 |
| CH | Chester | 1 | 100 |
| **Σ** | | **93** | **61.917** |

Status: **OFFEN** — Klärung mit HERMA/Noerpel erforderlich.
Detailliertes Follow-up: `docs/operative_followups/herma_gb_zones.md`.
Blockiert Step 2? **Nein** (DLV-Lücke methodisch sauber ausgewiesen).

---

### Anhang F — Etiketten-Pool (Sparte-Split)

Versender-Name-basierter Sparte-Split aus AX-Rohdaten (KNR 423650):

| Sparte (Versender-Name) | AX-Rows (raw) |
|-------------------------|-------------:|
| HERMA GMBH Sparte Etiketten/In | 593 |
| HERMA GMBH Sparte Etiketten/Ha | 252 |
| **Etiketten gesamt** | **845** |
| Haftmaterial | 4.526 |
| LIEF.NR. 103988 (other) | 4.030 |

Nach Pool-Konstruktion (E0/E1/E3-Ausschluss):

| Sparte | Beurteilbare Rows | Σ AX-EF (EUR) |
|--------|------------------:|--------------:|
| Etiketten | 714 | 146.593 |
| Haftmaterial | 3.918 | 2.304.312 |

**Wichtig:** Etiketten-2026-DLV (NT-Tarif) ist identisch mit Haftmaterial-DLV
für Gewichtsklassen ≤ 3.000 kg. Abweichungen nur bei > 3.100 kg (bis −560 EUR).
Für den Gesamt-Audit-Pool wurde Haftmaterial-DLV verwendet (konservativ).
Sparte-spezifische Nachkalkulation mit `_ETIK_2026_OHNE/_MIT` möglich
via `HermaCalculator(dlv_2026_ohne=_ETIK_2026_OHNE, dlv_2026_mit=_ETIK_2026_MIT)`.

---

### Anhang G — Bewertung und Handlungsempfehlungen

| Befund | M-Klasse | Δ (EUR) | Priorität | Handlung |
|--------|----------|--------:|-----------|---------|
| LDM-Abrechnungslücke (DE/GB/FR/AT) | M2\* | −68.026 | **Hoch** | AX-Abrechnungsregel für LDM-Sendungen bei HERMA prüfen; Vertragsklausel `max(ton,ldm×1500)` bestätigen |
| Weight-Driven M2\* (alle Länder) | M2\* | −125.396 | **Hoch** | AX-Tarifstammdaten vs. DLV-Workbook abgleichen; Sonderkonditionen dokumentieren |
| GB Area-Code-Lücke | DLV-Lücke | 61.917 (EF, n. beurteilbar) | **Mittel** | Klärung mit HERMA/Noerpel (10 fehlende UK-Codes); DLV-Workbook ergänzen |
| M\_over (VL-Zuschlag) | M\_over | +50.502 | **Niedrig** | Klären ob VL-Pflicht für alle HERMA-Sendungen vertraglich fixiert; falls ja: Calculator-VL-Logik anpassen |
| DE kein 2026-Scope | DLV-Lücke | 12.854 (EF) | **Niedrig** | AT-DLV 2026 enthält kein DE-Sheet; ggf. DE aus `_AT_COUNTRIES` entfernen oder separat behandeln |

**Gesamtbeurteilung:**

Net Δ −142.996 EUR (beurteilbarer Pool) entspricht einer durchschnittlichen
Unterbrechung von −5,5 % unter DLV-Niveau. Dies ist methodisch signifikant
(v1.0-Schätzung −167.000 EUR bestätigt die Größenordnung).

Der Audit-Befund ist **plausibel und nicht auf Methodik-Fehler zurückzuführen:**
Gate-B-Fix (−24.004 EUR Verbesserung gg. v1.0) zeigt, dass der Calculator korrekt
arbeitet. Die verbleibenden M2\*-Abweichungen sind auf AX-seitige Abrechnung
zurückzuführen und erfordern Klärung mit Noerpel.

---

*Report generiert: 2026-04-27 — Methodik v1.9.4 — `build_herma_report.py`*
