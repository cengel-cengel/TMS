# Konsolidierte Audit-Lage v1.9.7 — 12 Kunden / 13 Scope-Einheiten

**Stand:** 2026-04-29 (Update Sika ATM 527406 v1.9.7: 2026-04-29)  
**Methodik-Basis:** v1.9.7 (ZGI-Cluster-Aggregation §2f; AX POST × DLV-Soll; Erlöse-Maut-Trennung §15)  
**Periode:** POST-AX (2025-09-27 – 2026-03-31)

---

## 1. Konsolidierte Tabelle

| Kunde | KNR | Calculator (Commit) | Cache-Datei | Pool roh | Beurteilbar | Coverage | M1 | M2* | M_over | Σ ef (EUR) | Net Δ (EUR) | Net Δ % | Headline |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| GEZE GmbH | 406035 | geze.py (dd3d558) | geze_step23_results_v196.pkl | 2.917 | 2.759 | 94,6 % | 2.550 | 132 | 77 | 391.904 | +4.138 | +1,07 % | kein Schaden |
| EBM-Papst | 410844 | ebm.py (7500102) | ebm_step23_results_v196.pkl | 353 | 308 | 87,3 % | 285 | 1 | 22 | 480.133 | +3.514 | +0,74 % | kein Schaden |
| Fischerwerke | 409480 | fischerwerke.py (61f229e) | fischerwerke_step23_results_v196.pkl | 1.173 | 839 | 71,5 % | 321 | 107 | 411 | 537.574 | +106.811 | +24,80 % | Charter-Artefakt¹ |
| HERMA GmbH | 423650 | herma.py (c26dbe1) | herma_step23_results_v196.pkl | 3.781 | 3.642 | 96,3 % | 2.842 | 384 | 416 | 2.428.736 | −16.374 | −0,67 % | kein Schaden |
| CHT Germany | 486073 | cht.py (22f0b83) | cht_step23_results_v196.pkl | 702 | 554 | 78,9 % | 539 | 0 | 15 | 257.594 | −668 | −0,26 % | kein Schaden |
| Bitzer | 406345 | bitzer.py (93dc7c1) | bitzer_step23_results_v196_postfix.pkl | 3.406 | 3.330 | 97,8 % | 2.868 | 206 | 256 | 723.694 | +26.407 | +3,79 % | kein Schaden² |
| Groz-Beckert | 490527/410912/527373 | groz_beckert.py (7500102) | groz_beckert_step23_results_v196.pkl | 621 | 527 | 84,9 % | 473 | 0 | 54 | 112.997 | +5.729 | +5,07 % | kein Schaden³ |
| HELU-KABEL | 408244 | helu.py (897a2c6) | helu_step23_results_v196.pkl | 2.293 | 2.185 | 95,3 % | 2.044 | 102 | 39 | 315.991 | +203 | +0,06 % | kein Schaden |
| Hornschuch AG | 490085 | hornschuch.py (a0a9822) | hornschuch_step23_results_v196.pkl | 2.551 | 1.565 | 61,4 % | 1.549 | 7 | 9 | 408.579 | −205 | −0,05 % | kein Schaden⁴ |
| **Sika DE** | **491063** | **sika_de.py** | **sika_welle1_step23_results_v197.pkl** | **1.822** | **1.379** | **75,7 %** | **887** | **293** | **199** | **1.278.459** | **−25.758** | **−1,97 %** | **kein Schaden⁵** |
| **Sika SSC** | **511241** | **ssc.py** | **sika_welle1_step23_results_v197.pkl** | *(geteilt)* | **62** | — | **43** | **0** | **19** | **43.358** | **+2.600** | **+6,38 %** | **kein Schaden⁶** |
| **Sika Import** | **511241** | **sika_import.py (4d38156)** | **sika_import_step23_results_v197.pkl** | **346** | **346** | **100 %** | **278** | **9** | **59** | **629.422** | **+9.915** | **+1,55 %** | **kein Schaden⁷** |
| **Sika ATM** | **527406** | **sika_atm.py (f005e63)** | **sika_atm_step23_results_v197.pkl** | **396** | **395** | **99,7 %** | **298** | **92** | **5** | **217.470** | **−7.243** | **−3,22 %** | **kein Schaden⁸** |

**¹ Fischerwerke:** Net Δ +106.811 EUR ist ein Methodik-Artefakt. Charter-Sendungen
(Vollfahrzeug-Preis) werden gegen per-Stellplatz-DLV verglichen → systematischer M_over
(+118 TEUR). Non-Charter-Pool: ~+135 EUR (~0 %). Keine operativen Beanstandungen.

**² Bitzer (post-fix):** Zwei Calculator-Bugs gefixt (IT Zone4 Perioden-Dispatch P16;
FR-13400 Zone9-Routing). Vor Fix: Net Δ −26.780 EUR (−3,57 %). Die +3,79 % nach Fix
deuten auf Diesel-Floater-Einschluss in ef-Erlösen hin (offene Prüfung).

**³ Groz-Beckert:** Net Δ +5.729 EUR ausschließlich im GC-Mode (Gewicht/kg, 474 Rows).
LTL-FTL-Mode (PT-Porto-Lanes, 53 Rows): Δ = 0,00 EUR exakt. GC M_over = Über-Band-
Sendungen; DLV-Soll überschätzt per-kg-Extrapolation. Kein Carrier-Fehler.
Coverage 84,9 % = 527/621 (94 Rows DE/HR/NO/SE OOS + 10 Sub-Rows).

**⁴ Hornschuch AG (PL-Lücke):** 726 PL-Rows (203.992 EUR) ohne verifizierbaren
Carrier-Tarif (ERKA-DLV: 99 PL-Zonen, alle Raten leer). Coverage 61,4 % auf
Pool roh; auf In-Scope (2.291 Rows) = 68,3 %. Operative Klärung ContiTech-
Vertrags-Scope PL empfohlen (Hypothese C: PL nicht in MegaTrans-Nominierung).

**⁵ Sika DE (Erlöse-Maut-Separation):** Nominelles Net Δ −25.758 EUR (−1,97 %) ist
vollständig ein Methodik-Artefakt. AX bucht DE-Streckenmaut separat in `Erlöse Maut`
(Σ 30.555 EUR); Pipeline verwendet nur `Erlöse Fracht`. DLV-Soll enthält `basispreis +
de_maut`. Adjustiertes Net Δ = **+4.797 EUR (+0,37 %)** — kein Migrationsschaden.
M2=293 (21,2 %): davon 107 Extreme-M2 (fp < −50 %) durch Kleinstsendungen mit
fractional AX-Rates; 186 Moderate-M2 durch Maut-Separation-Bias.

**⁶ Sika SSC (M_over-Cluster):** AX rechnet für 19 SSC-Export-Sendungen (30,6 %) über
DLV-Niveau ab. Positives Net Δ = kein Noerpel-Schaden. OOS-Block de_oos
(347 Rows, 632 TEUR) außerhalb Export-DLV-Scope; operative Klärung Buchungszugehörigkeit
empfohlen. KNR 527406 ATM: abgeschlossen (s. ⁸).

**⁷ Sika Import-Flow (Dieselfloater-Artefakt):** 346 Rows sind physische Import-Sendungen
von IT-28065 (Cerano) und ES-28108 (Alcobendas) nach DE-70499 (Stuttgart). Es gelten
gesonderte Import-DLV-Dateien (2025/2026). P20-Adjustierung: Σ 18.306 EUR Erlöse Maut
in ef_total einbezogen. Net Δ P20-adj = +9.915 EUR (+1,55 %). IT M_over (59 Rows):
Quartalsdieselfloater variiert AX-ef über/unter LKW-Flatrate; Aggregat innerhalb
Wesentlichkeitsschwelle. ES: 113/113 M1 (100 %), Net Δ P20 = −557 EUR (−0,21 %).
Kein Migrationsschaden. Report: `docs/v1_9_7_sika_511241_import_report.md`.

**⁸ Sika ATM (RS pre-existing, kein Migrationsfehler):** 395 beurteilbar (Coverage 99,7 %).
Net Δ −7.243 EUR (−3,22 %) dominiert durch RS Serbia (32 Rows, −5.357 EUR, −20,52 %):
separate Laufkarten-Vereinbarung für PLZ 34000 Kragujevac, nicht in Anlage 1 hinterlegt;
14 M2-Rows weichen systematisch unter DLV-Satz ab (vorbestehend, kein Migrationsfehler).
Excl. RS: Net Δ −1.886 EUR (−0,95 %) — innerhalb Wesentlichkeitsschwelle. P20: keine
Adjustment (Maut 21 EUR + Diesel 36 EUR < 0,1 % ef). IT 85025 M_over (2 Rows, +3.611 EUR):
Abrechnungsgrundlage Stellplatz vs. Gewicht operative Prüfung. ES 28041 (1 Row, +1.270 EUR):
Spot-Rate Hypothese. PT: 100 % M1, Net Δ = 0 EUR exakt. Calculator-Bugs: keine.
Report: `docs/v1_9_7_sika_atm_cluster_report.md`.

---

## 2. Methodik-Anmerkungen

### EBM — v1.9.6 Re-Run (2026-04-28)

EBM v1.9.6 Pipeline (`build_ebm_step23_v196.py`) läuft durch, Ergebnis in
`output/ebm_step23_results_v196.pkl`. ZGI-Aggregations-Bias: **0 EUR bestätigt**
(0 Sub-Rows im ef>0-Pool, keine Abrechnungsstrecke/ZGI-Spalten in bi_top20_data.pkl).

Pool-Details v1.9.6 vs. v1.9.4:

| Metrik | v1.9.4 | v1.9.6 | Δ |
|---|---:|---:|---|
| Rohzeilen | 456 | 456 | = |
| Pool (ef>0, nach E1/E3) | 365 | 353 | −12 ³ |
| Scope-out (DE/GB/RS) | 20 | 17 | −3 |
| DLV-Lücke | 49 | 28 | −21 ⁴ |
| Beurteilbar | 296 | 308 | +12 |
| Net Δ | +3.208 EUR (+0,75 %) | +3.514 EUR (+0,74 %) | +306 EUR |

**³** v1.9.4 startete von allen 456 Rows und filterte E1 (cross-system). v1.9.6 filtert
ef>0 zuerst (356) und dann E3 (stp_eff=0): 353. Die 86 cross-system Rows haben alle ef=0.

**⁴** v1.9.4 hatte ES/PT als out-of-scope (kein DLV); v1.9.6 hält ES/PT in-scope
(EBM hat seit 2025-08-19 PT_ES-DLV), ES/PT-Rows gehen in DLV-Lücke wenn PLZ nicht
im DLV. M_over-Anstieg (+7→+22) liegt daran, dass SK 905 01 Rows (die in v1.9.4
Mx-DQ waren) jetzt als M_over klassifiziert werden (kein Mx-Kategoriefilter in v1.9.6).

**Audit-Aussage bleibt**: kein Migrationsschaden. IE 100 % M1. Net Δ +0,74 % unter
Wesentlichkeitsschwelle. EBM-Report v1.9.4: `docs/v1_9_4_ebm_cluster_report.md`.

### Groz-Beckert — Dual-Mode Calculator (LTL-FTL + GC)

Groz-Beckert KG (KNR 410912) + Groz-Beckert Europe GmbH (KNR 490527) +
Groz Beckert Portuguesa (KNR 527373). KNR 527410 (Carding Belgium):
scope_out — alle 187 Rows DE-Inland.

Pipeline: `src/build_groz_beckert_step23_v196.py` (Commit 481681f).
Net Δ +5.728,57 EUR liegt ausschließlich im GC-Mode (Gewicht/kg, 474 Rows).
LTL-FTL-Mode (PT-Porto-Lanes, 53 Rows): Δ = 0,00 EUR — perfekte DLV-Konformität.
Calculator-Bugs: keine (dual-mode ab 7500102 korrekt).

### HELU-KABEL — Methodik-Note Calculator-Fixes H1+H2

Pipeline: `src/build_helu_step23_v196.py` (Commit 5338f72). Vor Step 2 wurden
zwei Calculator-Bugs gefixt (Commit 897a2c6):
- **H1 (ES-Mendaro zone key):** `_load_es_mendaro` `zone_fn` gab "ES-20870" zurück;
  `_parse_vertical`-Regex extrahiert Key "ES" → Dict-Lookup scheiterte. Fix: `return "ES"`.
- **H2 (GB rates_by_col int vs str keys):** `rates_by_col` hatte int-Spalten-Indizes als Keys,
  `zone_fn` gab `str(col)` zurück → `dict.get("1")` auf int-Key-Dict → None. Fix: `str(c)` Keys.
67 ES-Rows und 55 GB-Rows waren betroffen; nach Fix 100 % Coverage (0 DLV-Lücke).

### Hornschuch AG — PL-DLV-Lücke + AT-Zone-Fix G3

Pipeline: `src/build_hornschuch_step23_v196.py`. Vor Step 2 wurde Bug G3 gefixt
(Commit a0a9822): AT-Zone-Funktion nutzte 2-stelligen PLZ-Prefix, DLV hat AT-Zonen
1–9 (1-stellig) → 1 Row korrigiert.

FR-Castorama/Leroy Merlin (318 Rows): Castorama-DLV definiert additiven
per-Sendung-Zuschlag ON TOP des ContiTech per-kg. AX bucht nur ContiTech per-kg
in Erlöse Fracht. fp = 0,0000 für alle 318 FR-Rows empirisch bestätigt.

PL-Lücke: 726 Rows / 203.992 EUR. ERKA-DLV enthält 99 PL-Zonen mit leeren
Freight-Raten → kein DLV-Soll berechenbar. Operative Klärung ausstehend.

### Sika Deutschland GmbH (KNR 491063) — Erlöse-Maut-Trennung

Pipeline: `src/build_sika_step23_v197.py`. DLV: Noerpel SIKA Stellplatzofferte 2025/2026.
Erlöse-Maut-Trennung: AX bucht `Erlöse Fracht` (base) und `Erlöse Maut` (surcharge) getrennt.
Calculator `SikaDeCalculator` + `SSCCalculator` aus `sika_de.py` (Commit 7500102).
KNR 491063 und 511241 in gemeinsamer Pkl: `sika_welle1_step23_results_v197.pkl`.

Kein Calculator-Bug. M2=293 erklärt durch:
- Erlöse-Maut-Separation-Bias (primär, ~30.555 EUR)
- Kleinstsendungen fractional rates (107 Extreme-M2-Rows, fp < −50 %)

Adjustiertes Net Δ: +4.797 EUR (+0,37 %). KNR 527406 (ATM): Welle 2.

### Sika 511241 Import-Flow — Separate Scope-Einheit

Pipeline: `src/build_sika_import_step23_v197.py` (Commit 07ba458).  
Calculator: `SikaImportCalculator` in `src/tms/tariff/calculators/sika_import.py` (Commit 4d38156).  
DLV: `Import Spanien und Italien 2025/2026` — ES per-Stellplatz; IT LKW-Flatrate.

Pricing-Modi: ES-28108 → per-Stellplatz (1–34 Paletten); IT-28065 → Komplett-LKW
(LKW 1 ≤ 33 Stpl., LKW 2 > 33 Stpl.). DE-Maut: aus DE-Maut-Anlage (gleiche Datei
wie Export-DLV). AT-Maut: inkludiert in IT-Flatrates.

P20-Adjustierung: ef_total = Erlöse Fracht + Erlöse Maut (18.306 EUR gesamt).
Net Δ P20-adj = +9.915 EUR (+1,55 %); IT M_over durch Quartalsdieselfloater.
Report: `docs/v1_9_7_sika_511241_import_report.md`.

---

### CHT Germany — 4 Länder im Aggregat

CHT-Pkl enthält alle beurteilbaren CHT-Länder (BE, IT, ES, AT) in einer Datei.
Land-Breakdown (rdf, 554 Rows):

| Land | n | Σ ef | Σ dlv | Net Δ |
|---|---:|---:|---:|---:|
| AT | 41 | 16.983 | 16.562 | +422 |
| BE | 241 | 42.490 | 42.690 | −201 |
| ES | 105 | 124.484 | 125.879 | −1.395 |
| IT | 167 | 73.638 | 73.132 | +506 |
| **Σ** | **554** | **257.594** | **258.262** | **−668** |

CHT GR (separater Report/Script): nicht in bi_top20_data.pkl; separat in
`src/build_9c2c_cht_gr_calculator_test.py` mittels RNLevelCalculator — kein
Step-2+3-Pool.

### HERMA — M2*-Reduktion durch Cluster-Aggregation

v1.9.4 wies −142.996 EUR M2* aus (Weight-Driver-Artefakt). v1.9.6 nach
ZGI-Aggregation: −67.758 EUR M2*. Verbleibend nach Cluster-Fix: Net Δ −16.374 EUR.
Nicht auf Migrationsschaden zurückführbar.

---

## 3. Offene Operative Followups

| Followup | Datei | Priorität |
|---|---|---|
| Bitzer FR-13400 Aubagne: ERKA-Rückfrage Zone 9 vs. Profoid-DLV | `docs/operative_followups/bitzer_fr_13400_aubagne_tarifwahl.md` | Mittel |
| Bitzer FR-92000 Hauts-de-Seine: Zonenzuordnung PLZ 92xxx | `docs/operative_followups/bitzer_fr_92000_zone.md` | Niedrig |
| HERMA GB-Zones: 10 fehlende UK Area-Codes | `docs/operative_followups/herma_gb_zones.md` | Niedrig |
| EBM SK/1380: Calculator _lookup() first-match-wins (Backlog) | `docs/backlog/calculator_known_issues.md` | Backlog |

---

## 4. Sika-Status — v1.9.7 ABGESCHLOSSEN (KNR 491063 + 511241)

Report: `docs/v1_9_7_sika_welle1_cluster_report.md`  
Pipeline: `src/build_sika_step23_v197.py` | PKL: `output/sika_welle1_step23_results_v197.pkl`  
KNR 527406 (ATM): separates BI-Loading erforderlich → Welle 2.

### Voruntersuchung (Etappe 8i, 2026-04-19)

Methodik v1.0 (Familien-Vergleich Dinas PRE × AX POST, nicht v1.9.6).
Report: `docs/sika_findings_summary.md`.

Wesentliche Befunde:
- 8 Familien mit Unterfakturierung, davon 2 Muster-A (AX < DLV < Dinas) → sofortiger Prüfbedarf
- 3 ATM-CH-Gaps (KNR 527406, FR/IT-Routen, 55.520 EUR hist. Volumen, POST-Aktivität bestätigt)
- Serbien (RS/34104): DLV-Satz +25 % über Dinas-Ist → DLV-Konfigurationsprüfung nötig

### v1.9.6-Status-Audit

```
Sika Status-Audit — 2026-04-28
──────────────────────────────────────────────

KNR 491063 (Sika Deutschland GmbH / CH AG):
  BI-Daten (bi_top20_data.pkl): 1.407 Rows ef>0, Σef = 1.290.687 EUR
  Dinas-Cache:          dinas_cache_491063.pkl  (942 KB) ✓
  Calculator:           sika_de.py — Commit 7500102
                        shipment_date-Dispatch 2025/2026 vorhanden ✓
  v1.9.6 Step23-Script: FEHLT
  v1.9.6 Pkl:           FEHLT
  ZGI-Aggregation:      noch nicht implementiert für Sika
  Status:               BLOCKIERT — kein v1.9.6 Step23 Pipeline-Script

KNR 511241 (SIKA SUPPLY CENTER AG):
  BI-Daten (bi_top20_data.pkl): 415 Rows ef>0, Σef = 681.512 EUR
  Dinas-Cache:          dinas_cache_ssc_511241.pkl  (217 KB) ✓
  Calculator:           ssc.py → SSCCalculator aus sika_de.py ✓
  v1.9.6 Step23-Script: FEHLT (kann mit KNR 491063 gemeinsam gebaut werden)
  v1.9.6 Pkl:           FEHLT
  Status:               BLOCKIERT — kein v1.9.6 Step23 Pipeline-Script

KNR 527406 (Sika ATM CH / Automotive):
  BI-Daten (bi_top20_data.pkl): 0 Rows — KNR NICHT in TOP-20-Datei
  Separate BI-Cache:    bi_cache_sika_527406.pkl  (517 KB) ✓
                        bi_cache_sika_atm_de.pkl  (664 KB) ✓
  Dinas-Cache:          dinas_cache_491063.pkl (geteilt mit KNR 491063)
  Calculator:           sika_atm.py — Commit f005e63
  v1.9.6 Step23-Script: FEHLT
  v1.9.6 Pkl:           FEHLT
  ATM-CH Stp:           NaN in Dinas (gewichtsbasiert, EUR/100kg) — kein
                        Stellplatz-Vergleich möglich; separates DLV nötig
  Status:               BLOCKIERT — nicht in bi_top20, separates BI-Loading
                        nötig + kein v1.9.6 Step23 Script

──────────────────────────────────────────────
Empfehlung Reihenfolge:
  Sika-Re-Run VOR Groz-Beckert: NEIN
  Begruendung:
    (a) Sika benötigt neues v1.9.6 Pipeline-Script für zwei KNRs gleichzeitig
        (491063 + 511241) — Bauaufwand ~2 h.
    (b) KNR 527406 (ATM) ist nicht in bi_top20 → separates BI-Loading;
        stp=NaN schränkt Vergleichbarkeit ein.
    (c) Die kritischen Sika-Befunde (Muster A: 2 Familien AX<DLV) sind bereits
        bekannt und in sika_findings_summary.md dokumentiert. Eine v1.9.6-
        Neuanalyse bestätigt diese, löst sie aber nicht.
    → Sika-Re-Run nach Groz-Beckert + HELU + Hornschuch (Welle 2 fertig),
      dann als eigenständige Etappe.
──────────────────────────────────────────────
```

---

## 5. Welle-2-Status

### Welle-2-Kunden — Abgeschlossen

| Kunde | KNR | Commit | Net Δ | Status |
|---|---|---|---:|---|
| Groz-Beckert | 490527/410912/527373 | 481681f | +5.729 EUR | ✅ Abgeschlossen |
| HELU-KABEL | 408244 | 5338f72 | +203 EUR | ✅ Abgeschlossen |
| Hornschuch AG | 490085 | 9ad8c85 | −205 EUR | ✅ Abgeschlossen (PL-Lücke offen) |

### Verbleibend

| Kunde | KNR | Σ ef (EUR) | Status |
|---|---|---:|---|
| Sika DE+SSC | 491063+511241 | 1.321.817 | ✅ Abgeschlossen (v1.9.7, 2026-04-28) |
| **Sika Import-Flow** | **511241** | **629.422** | **✅ Abgeschlossen (v1.9.7, 2026-04-28)** |
| Sika ATM | 527406 | — | BLOCKIERT — separates BI-Loading, gewichtsbasiert |

```
Nächster Schritt (Optionen):
  (a) Sika ATM (KNR 527406) — bi_cache_sika_527406.pkl laden + sika_atm.py Calculator
  (b) Aggregation-Audit Docs — aggregation_codebase_audit.md + retroactive_risk.md
  (c) Hornschuch PL-Klärung — Klärungsgespräch ContiTech vorbereiten
```

---

## 6. Gesamtbild — Audit-Aussage (12 abgeschlossene Scope-Einheiten / 11 Kunden)

| Metrik | Wert |
|---|---|
| Scope-Einheiten abgeschlossen | 12 (11 Kunden + Sika Import-Flow) |
| Kunden (eindeutig) | 11 (GEZE, EBM, Fischerwerke, HERMA, CHT, Bitzer, Groz-Beckert, HELU, Hornschuch, Sika DE, Sika SSC+Import) |
| Σ ef beurteilbar | ~7.608.000 EUR |
| Net Δ gesamt nominell (alle 12) | ~+116.312 EUR (+1,5 %) |
| Kunden mit Migrationsschaden | **0** |
| Kunden mit operativem Handlungsbedarf | **4** (HERMA M2* −16 TEUR; Bitzer Diesel-Floater; Hornschuch PL-Lücke 204 TEUR; Sika SSC de_oos-Klärung 632 TEUR) |
| Calculator-Bugs identifiziert + gefixt | **8** (P10 Fischerwerke; P12+P13+P16 HERMA/Bitzer; H1 Bitzer FR-13400; H1+H2 HELU; G3 Hornschuch AT) |

**Gesamtaussage:**  
In keiner der 12 abgeschlossenen Scope-Einheiten ist ein systematischer Migrationsschaden
(AX < DLV über multiple Lanes) nachweisbar. Alle M2-Cluster erklären sich durch
Calculator-Artefakte (Upload-DLV-Zonen, Charter-Pool, Weight-Driver-Bandeffekt,
FTL-Flat-Rate, Erlöse-Maut-Trennung, Dieselfloater-Quartalsvariation) oder randständige
Einzelfälle. Die Migration hat in keinem Fall zu struktureller Unterfakturierung geführt.

Sika DE nominelles Net Δ −25.758 EUR (−1,97 %): vollständig Erlöse-Maut-Separation-
Artefakt — adjustiert +4.797 EUR (+0,37 %). Sika Import-Flow Net Δ P20-adj +9.915 EUR
(+1,55 %): IT-Dieselfloater-Quartalsvariation. Hornschuch PL (726 Rows, 204 TEUR):
außerhalb Audit-Scope bis zur operativen Klärung des ContiTech-Vertrags-Scopes.
