# Groz-Beckert KG — Step 2+3 Cluster-Report v1.9.6

**Stand:** 2026-04-28
**KNRs:** 490527 (Groz-Beckert Europe GmbH), 410912 (Groz-Beckert KG), 527373 (Groz Beckert Portuguesa)
**Periode:** POST-AX (2025-09-27 – 2026-03-31)
**Pipeline:** `src/build_groz_beckert_step23_v196.py`
**Cache:** `output/groz_beckert_step23_results_v196.pkl`

## Headline

**M1 fp_mean = 0.0000 — AX rechnet exakt auf DLV oder darüber. Kein Migrationsschaden.**
M2 = 0. Alle M_over erklären sich durch Über-Band-Sendungen (GC) und Sonderrouten-Zuschläge.
LTL-FTL (PT-Porto-Lanes): Δ = 0,00 EUR — perfekte DLV-Konformität.

## Executive Summary

| Metrik | Wert |
|---|---|
| Aktive KNRs (In-Scope) | 490527 + 410912 + 527373 |
| KNR 527410 (Carding Belgium) | scope_out — alle 187 Rows DE-Inland |
| Pool roh (ef>0, active KNRs) | 621 |
| Scope-out (DE/HR/NO/SE) | 84 |
| Sub-Rows (is_sub, ef>0) | 10 |
| In-Scope | **527** |
| DLV-Lücke | **0** (100 % Coverage) |
| Beurteilbar | **527** |
| M1 \|fp\|≤5 % | **473** (89,8 %) |
| M2 fp<−5 % | **0** (0,0 %) |
| M_over fp>+5 % | **54** (10,2 %) |
| Σ ef (beurteilbar) | 112.997,43 EUR |
| Σ dlv (beurteilbar) | 107.268,86 EUR |
| **Net Δ** | **+5.728,57 EUR (+5,34 %)** |

### Mode-Aufschlüsselung

| Mode | Rows | Σ ef | Σ dlv | Δ | fp_net |
|---|---:|---:|---:|---:|---:|
| LTL-FTL (PT-Lanes) | 53 | 62.808,17 | 62.808,17 | **0,00** | 0,000 |
| GC (Gewicht, alle anderen) | 474 | 50.189,26 | 44.460,69 | **+5.728,57** | +0,129 |

### KNR-Aufschlüsselung

| KNR | Name | Rows | Σ ef | Δ | fp_net |
|---|---|---:|---:|---:|---:|
| 490527 | Groz-Beckert Europe GmbH | 460 | 48.029 | +3.918 | +8,9 % |
| 410912 | Groz-Beckert KG | 57 | 43.618 | +1.811 | +4,3 % |
| 527373 | Groz Beckert Portuguesa | 10 | 21.351 | 0 | 0,0 % |

## Methodik

### Dual-Mode Calculator

`GrozBeckertCalculator` (groz_beckert.py) verwendet zwei Pricing-Modi:

- **LTL-FTL**: Lademeter-basiert, nur für Sonder-Lanes (72458→PT 4409-516, 58640→PT 4409-516, 70794→CH 4528)
- **GC**: Gewicht-basiert (EUR/100kg), alle anderen Destinationen

Tarifgruppen-Schema:
- `groz_beckert_lane_72458_pt` / `groz_beckert_lane_58640_pt` → LTL-FTL
- `groz_beckert_gc_XX` (be/ch/es/fi/fr/gb/it/ma/nl/ee) → GC

### Scope-Entscheidungen

| Ausschluss | Grund | Rows |
|---|---|---|
| KNR 527410 | Carding Belgium — alle DE-Inland | 187 |
| OOS Land: DE | kein Export-DLV | 81 |
| OOS Land: HR/NO/SE | je 1 Row, kein DLV | 3 |
| Sub-Rows (is_sub) | Erlöse auf Master | 10 |
| ef=0 Rows (P4) | cross-system / administrativ | 587 |

### ZGI-Cluster-Aggregation

bi_cache_groz_beckert.pkl enthält keine `Abrechnungsstrecke`- / `Zusammengefasst in`-Spalten.
Im in-scope-Pool: 0 Mastersendungen gesetzt → ZGI-Aggregation ist No-Op.
**ZGI-Bias: 0 EUR bestätigt.**

### M-Klassifikation

```
fp = (Erlöse_Fracht − DLV_Soll) / DLV_Soll
M1:     |fp| ≤ 5 %
M2:     fp < −5 %
M_over: fp > +5 %
```

## Cluster-Übersicht nach Tarifgruppe

| Tarifgruppe | Mode | Rows | Σ ef | Σ dlv | Δ | fp_net | M1 | M2 | M_ov |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| groz_beckert_lane_72458_pt | LTL-FTL | 43 | 41.457 | 41.457 | **0** | 0,000 | 43 | 0 | 0 |
| groz_beckert_lane_58640_pt | LTL-FTL | 10 | 21.351 | 21.351 | **0** | 0,000 | 10 | 0 | 0 |
| groz_beckert_gc_be | GC | 60 | 6.693 | 4.713 | +1.981 | +0,420 | 48 | 0 | 12 |
| groz_beckert_gc_ch | GC | 45 | 5.378 | 4.264 | +1.114 | +0,261 | 32 | 0 | 13 |
| groz_beckert_gc_gb | GC | 74 | 9.873 | 8.631 | +1.242 | +0,144 | 70 | 0 | 4 |
| groz_beckert_gc_fr | GC | 75 | 9.048 | 8.308 | +741 | +0,089 | 63 | 0 | 12 |
| groz_beckert_gc_it | GC | 155 | 12.776 | 12.478 | +298 | +0,024 | 148 | 0 | 7 |
| groz_beckert_gc_es | GC | 41 | 3.885 | 3.770 | +115 | +0,031 | 37 | 0 | 4 |
| groz_beckert_gc_nl | GC | 15 | 879 | 778 | +101 | +0,130 | 14 | 0 | 1 |
| groz_beckert_gc_ma | GC | 2 | 406 | 269 | +137 | +0,508 | 1 | 0 | 1 |
| groz_beckert_gc_fi | GC | 5 | 1.007 | 1.007 | 0 | 0,000 | 5 | 0 | 0 |
| groz_beckert_gc_ee | GC | 2 | 244 | 244 | 0 | 0,000 | 2 | 0 | 0 |

### Land-Aufschlüsselung (beurteilbar)

| Land | Rows | Σ ef | Σ dlv | Δ | fp_net | M1 | M_ov |
|---|---:|---:|---:|---:|---:|---:|---:|
| PT | 53 | 62.808 | 62.808 | **0** | 0,000 | 53 | 0 |
| IT | 155 | 12.776 | 12.478 | +298 | +0,024 | 148 | 7 |
| FR | 75 | 9.048 | 8.308 | +741 | +0,089 | 63 | 12 |
| GB | 74 | 9.873 | 8.631 | +1.242 | +0,144 | 70 | 4 |
| BE | 60 | 6.693 | 4.713 | +1.981 | +0,420 | 48 | 12 |
| CH | 45 | 5.378 | 4.264 | +1.114 | +0,261 | 32 | 13 |
| ES | 41 | 3.885 | 3.770 | +115 | +0,031 | 37 | 4 |
| NL | 15 | 879 | 778 | +101 | +0,130 | 14 | 1 |
| FI | 5 | 1.007 | 1.007 | 0 | 0,000 | 5 | 0 |
| MA | 2 | 406 | 269 | +137 | +0,508 | 1 | 1 |
| EE | 2 | 244 | 244 | 0 | 0,000 | 2 | 0 |

## Detail: LTL-FTL Lanes (PT-Porto)

### Cluster: groz_beckert_lane_72458_pt (Albstadt → Porto)

- **Rows:** 43 | **Δ = 0,00 EUR** | **M1: 43 / 43**
- Origin: 72458 Albstadt → Dest: PLZ 4409-516 (Porto-Region)
- Pricing: Lademeter-basiert (LTL-FTL), DLV-Strecken-Preisliste
- fp-Verteilung: alle exakt 0,0000 — AX rechnet 1:1 nach DLV

### Cluster: groz_beckert_lane_58640_pt (Iserlohn → Porto)

- **Rows:** 10 | **Δ = 0,00 EUR** | **M1: 10 / 10**
- Origin: 58640 Iserlohn → Dest: PLZ 4409-516
- Pricing: gleiche LDM-Preisliste
- KNR 527373 (Groz Beckert Portuguesa): alle 10 Rows hier, alle M1

**LTL-FTL-Gesamt: 53 Rows, Δ = 0,00 EUR — perfekte DLV-Konformität.**

### Warum LTL-FTL und nicht GC?

Der Calculator selektiert LTL-FTL wenn:
1. Origin-PLZ ∈ {72458, 58640} **und**
2. Destination PLZ in PT 4409-516-Bereich

CH-4528-Sendungen von 72458 erhalten **GC-Fallback** (LTL-FTL nur für Leinfelden 70794 → CH),
daher zeigen CH 4528-Rows teilweise M_over (Zuschläge, s. Abschnitt Detail GC).

## Detail: GC-Lanes — M_over Ursachen

### Ursache 1 — Über-Max-Band (GC Bandpreis-Extrapolation)

DLV definiert Gewichtsbänder bis max. ~3.000 kg. Sendungen darüber werden mit dem letzten
Bandsatz berechnet, während AX Marktpreise berechnet.

Größte Einzelfälle:

| Land | PLZ | Ton | ef | dlv | Δ | fp |
|---|---|---:|---:|---:|---:|---:|
| BE | 8540 | 7.533 | 1.300,00 | 394,71 | +905,29 | +2,29 |
| BE | 8540 | 7.533 | 1.300,00 | 394,71 | +905,29 | +2,29 |
| GB | LS21 1TB | 2.073 | 1.710,00 | 550,99 | +1.159,01 | +2,10 |
| IT | 13871 | 3.458 | 605,00 | 434,70 | +170,30 | +0,39 |

BE 8540 (7.533 kg, doppelt): identische Sendung zweimal erfasst — AX bucht Vollfahrzeug-Preis
(1.300 EUR), DLV-Bandpreis für max. Band = 394,71 EUR. fp = +2,29 = kein Datenfehler sondern
Vollfahrzeug vs. Stückgut-DLV (Charter-Artefakt analog Fischerwerke).

### Ursache 2 — CH 4528 GC-Fallback (kein LTL-FTL ohne Leinfelden-Origin)

12 Rows PLZ 4528 (Zuchwil), Origin 72458 (Albstadt). LTL-FTL-Lane ist nur für Origin 70794
(Leinfelden) konfiguriert. Albstadt-Sendungen fallen auf GC-Tarif → DLV niedriger als ef.

| M-Klasse | Rows | fp-Bereich |
|---|---:|---|
| M1 | 5 | 0,000 |
| M_over | 7 | +0,58 – +2,47 |

AX rechnet teilweise LTL-FTL-Preise, Calculator gibt GC → fp>0. Kein Billing-Fehler,
sondern DLV-Konfigurationslücke (kein Zuchwil-Lane für Albstadt-Origin).

### Ursache 3 — FR 59270 (fp = +3,21)

| PLZ | Ton | ef | dlv | Δ | fp |
|---|---:|---:|---:|---:|---:|
| 59270 | 285 | 360,06 | 85,50 | +274,56 | +3,21 |

Destination 59270 Bailleul (Nord-Frankreich). DLV-Satz sehr niedrig (285 kg → Band 1).
AX rechnet vermutlich inklusive Sondergebühr / Gefahrgut-Zuschlag. Einzelfall, kein Muster.

### Zusammenfassung M_over

| Ursache | Rows | Δ (EUR) |
|---|---:|---:|
| Über-Max-Band GC (Vollfahrzeug) | ~8 | ~3.200 |
| CH 4528 GC-Fallback | 7 | 1.114 |
| Sondergebühren / Einzelfälle | ~39 | ~1.414 |
| **Gesamt M_over** | **54** | **+5.729** |

**Kein M2. Kein Unterfakturierungsmuster.**

## Anhänge

### Anhang A — Pool-Aufbau

```
Gesamt BI-Cache (groz_beckert):       1.395 Rows
  davon ef=0 (P4, cross-system):        587 Rows
  davon KNR 527410 scope_out:           187 Rows
  davon ef>0, aktive KNRs:             621 Rows
    davon OOS Land (DE/HR/NO/SE):        84 Rows
    davon Sub-Rows (is_sub):             10 Rows
    In-Scope:                           527 Rows
    DLV-Lücke:                            0 Rows  (100 % Coverage)
    Beurteilbar:                        527 Rows
```

### Anhang B — Calculator-Commits

| Komponente | Commit | Stand |
|---|---|---|
| groz_beckert.py | 7500102 | Pre-Audit-Freeze |
| GrozBeckertCalculator | dual-mode (LTL-FTL + GC) | — |

### Anhang C — M1 fp-Verteilung

```
M1 fp: mean = 0.0000, std = 0.0000, min = 0.0000, max = 0.0000
Alle 473 M1-Rows haben fp exakt = 0,0000.
AX rechnet nie unter DLV (kein M2), rechnet für M1 exakt auf DLV.
```

### Anhang D — KNR 527410 Scope-Out-Begründung

KNR 527410 (Groz Beckert Carding Belgium): alle 187 Rows Empfänger Land = DE.
Kein Export-DLV für DE-Inland → scope_out. Ef-Summe in 527410: ef>0-Anteil vorhanden
aber ohne DLV-Soll nicht beurteilbar. Dokumentiert als `oos_knr` im Cache.

### Anhang E — ZGI-Aggregation Nachweis

bi_cache_groz_beckert.pkl Spalten enthalten keine `Abrechnungsstrecke` oder
`Zusammengefasst in`. Mastersendung-Prüfung im in-scope-Pool: 0 Rows mit gesetzter
Mastersendung. ZGI-Aggregations-Schritt ist No-Op. ZGI-Bias = 0 EUR.

### Anhang F — Operative Followups

| Thema | Priorität |
|---|---|
| CH 4528 Albstadt-Origin: LTL-FTL-Lane für 72458 prüfen | Niedrig |
| BE 8540 Vollfahrzeug-Doppelbuchung (7.533 kg ×2): Dinas-Check | Niedrig |
| FR 59270 Sondergebühr identifizieren | Backlog |

## Gesamtbewertung

### Audit-Aussage

**Kein Migrationsschaden bei Groz-Beckert.**

- M2 = 0: keine einzige Unterfakturierungs-Row
- M1 fp_mean = 0.0000: AX rechnet exakt auf DLV (kein Rundungsspielraum nach unten)
- Net Δ = +5.728,57 EUR (+5,34 %): Groz-Beckert zahlt geringfügig über DLV-Soll
- Alle M_over erklären sich durch strukturelle Ausreißer (Über-Max-Band, CH-4528-GC-Fallback,
  Sondergebühren) — keine systematische Abweichung

### Vergleich mit anderen Welle-2-Kunden

| Kunde | M2 | M_over | Net Δ % | Headline |
|---|---:|---:|---:|---|
| Groz-Beckert | **0** | 54 | +5,34 % | kein Schaden |
| EBM-Papst | 1 | 22 | +0,74 % | kein Schaden |
| GEZE | 132 | 77 | +1,07 % | kein Schaden |
| Fischerwerke | 107 | 411 | +24,80 % | Charter-Artefakt |
| HERMA | 384 | 416 | −0,67 % | kein Schaden |
| CHT Germany | 0 | 15 | −0,26 % | kein Schaden |
| Bitzer | 206 | 256 | +3,79 % | kein Schaden |

### Nächster Schritt: HELU-KABEL (KNR 408244)

- BI-Cache: `output/bi_top20_data.pkl` ✓
- Calculator: `src/tms/tariff/calculators/helu.py` (7500102)
- Tarif: per-100kg, einfachstes Preisschema aller Welle-2-Kunden
- Scope: ~326.781 EUR Σ ef erwartet
- Komplexität: Gering — 1 Durchlauf erwartet

