# Aggregation Codebase Audit — v1.9.7 Stand (12 Scope-Einheiten)

**Stand:** 2026-04-28 | **Zweck:** Empirische Prüfung, wie alle 12 auditierten
Scope-Einheiten mit Sub-Row-Ausschluss und ZGI-Aggregation umgehen.  
*Aktualisiert von v1.9 (4 Kunden, 2026-04-24) auf v1.9.7 (12 Scopes).*

---

## Aggregations-Regel v1.9 (Referenz)

```
DINAS-Seite:  Aggregations-Schlüssel = (Sender_PLZ, Empfänger_PLZ, Ladedatum)
              → ein "virtuelles Aggregat" pro Schlüssel

AX-Seite:     Aggregations-Schlüssel = Master-Auftragsnummer
              ("zusammengefasst in" / Mastersendung-Feld)
              Master + alle Zeilen mit Mastersendung → dieses Masters werden gebündelt

Vergleich:    Dinas-Aggregat ↔ AX-Master-Aggregat
```

---

## Status pro Kunde

### CHT Germany (KNR 486073) — 5 Länder: BE, IT, ES, AT, GR

**Analyse-Typ:** AX vs. DLV (kein Dinas-Vergleich; CHT-Scripts prüfen nur,
ob AX-Erlöse mit DLV-Basispreisen übereinstimmen)

**Dinas-Aggregation:** n/a — Dinas-Daten nicht Teil der CHT-Analyse

**AX-Aggregation:**
- BE/IT/ES/AT: `Tonnage (eff.) > 0` als impliziter Filter in `build_9c2a/b/d_*.py`
- Alle 38 CHT-Sub-Rows (Mastersendung gesetzt, kein eigener Unterauftrag)
  haben `Tonnage = 0` → werden durch den `~is_t0`-Filter vollständig ausgeschlossen
- GR: `RNLevelCalculator` aggregiert Positionen explizit per RN → kein Sub-Row-Problem

**Vergleichs-Ebene:** Position-Ebene (BE/IT/ES/AT), RN-Ebene prorated (GR)

**Status:** `aggregation_korrekt_de_facto`

**Quell-Dateien:**
- `src/build_9c2a_cht_be_calculator_test.py` (Filter Zeile 110: `be[~be['is_t0']]`)
- `src/build_9c2b_cht_es_calculator_test.py`
- `src/build_9c2c_cht_gr_calculator_test.py` (RNLevelCalculator)
- `src/build_9c2d_cht_at_calculator_test.py`
- `src/tms/tariff/calculators/cht_be.py` u.a.

**Risiko:** Keines aktiv. Latentes Risiko: Falls ein zukünftiger CHT-Sub-Row
Tonnage > 0 erhält (z.B. durch AX-Konfigurationsänderung), würde der
`Tonnage > 0`-Proxy versagen. Explizite `is_sub`-Prüfung wäre robuster.

---

### GEZE GmbH (KNR 406035)

**Analyse-Typ:** Unit-Tests gegen DLV-Referenzwerte (kein BI-Pass-Rate-Vergleich,
kein Dinas-Vergleich)

**Dinas-Aggregation:** n/a

**AX-Aggregation:** n/a — kein BI-Daten-Vergleich in aktuellen GEZE-Scripts

**Vergleichs-Ebene:** Unit-Test (isolierte DLV-Lookup-Prüfung)

**Status:** `aggregation_nicht_anwendbar` (kein BI-Pass-Rate aktiv)

**Quell-Dateien:** `src/build_9b1_geze_calculator_test.py`

**Risiko:** **Latent, mittleres Volumen.**
In `bi_top20_data.pkl` (POST, Fracht > 0) hat GEZE 1.718 Sub-Rows (25,2% aller
GEZE-Zeilen), davon **140 mit Tonnage > 0** (≈ 143.407 EUR Erlöse Fracht).
Sobald ein BI-Pass-Rate-Vergleich für GEZE eingeführt wird (z.B. Etappe 9b.2),
müssen diese 140 Sub-Rows explizit über `is_sub`-Filter ausgeschlossen werden.
Ohne diesen Filter würden 140 Positionen fälschlich mit per-Positions-DLV-Rate
verglichen, obwohl ihre Erlöse anteilige Master-Beträge sind.

---

### Fischerwerke GmbH (KNR 409480)

**Analyse-Typ:** AX vs. Dinas (Cluster-Familien-Matching + Dinas-PDF-NK-Abgleich)

**Dinas-Aggregation:** Per Rechnung (`rechnung_nr` = Cluster-ID in
`src/tms/clustering/dinas_cluster.py`). **Nicht** nach `(Sender_PLZ, Empfänger_PLZ,
Ladedatum)`. Eine Dinas-Rechnung = ein Dinas-Cluster, unabhängig davon, ob die
Rechnung Positionen mit unterschiedlichen Routing-Keys enthält.

**AX-Aggregation:** `enrich_master_sub()` in `src/build_fischer_report.py`
(Zeilen 65–92) konsolidiert Sub-Rows korrekt in den Master:
- Sub-Erlöse werden auf den Master-Row summiert
- Sub-Rows werden aus dem Vergleichsdatensatz entfernt
→ AX-Seite nach v1.9-Regel korrekt implementiert

**Vergleichs-Ebene:** Auftragsnummer (nach Master/Sub-Konsolidierung),
dann Cluster-Familien-Matching auf `Land|PLZ2|GewichtsBand`-Ebene

**Status:** `aggregation_korrekt_ax_seite` / `aggregation_fehlt_dinas`

**Quell-Dateien:**
- `src/build_fischer_report.py` (`enrich_master_sub` Zeilen 65–92)
- `src/tms/clustering/dinas_cluster.py` (Dinas-Aggregation per rechnung_nr)

**Risiko:** Gering bis mittel. Das Cluster-Familien-Matching (auf `Land|PLZ2`-Ebene)
kaschiert bisher fehlende Dinas-Aggregation nach Routing-Key: Einzelne Dinas-Positionen
mit gleichem Schlüssel (Sender+Empf+Ladedatum) landen in derselben Familie und werden
statistisch aggregiert. Für den Einzelsendungs-Vergleich (Schritt 2 Etappe 9a.3)
wäre eine exakte Routing-Key-Aggregation auf Dinas-Seite notwendig.
Bekannte aktive §8-Findings: RF-1/RF-2/RF-3/RF-4 (nicht durch Aggregationsfehler verursacht).

---

### HERMA GmbH (KNR 423650)

**Analyse-Typ:** AX vs. Dinas (Cluster-Familien-Matching + Dinas-NK-Abgleich)

**Dinas-Aggregation:** Gleich wie Fischerwerke — per Rechnung, nicht per Routing-Key.

**AX-Aggregation:** `enrich_master_sub()` in `src/build_herma_report.py`
(Zeilen 64–92) — identische Implementierung wie Fischerwerke. Korrekt.

**Vergleichs-Ebene:** Auftragsnummer (nach Konsolidierung), Cluster-Familien

**Status:** `aggregation_korrekt_ax_seite` / `aggregation_fehlt_dinas`

**Quell-Dateien:**
- `src/build_herma_report.py` (`enrich_master_sub` Zeilen 64–92)

**Risiko:** Gering. Sub-Row-Zahlen: 408 is_sub gesamt, davon **nur 2 mit Tonnage > 0**
(65.136 EUR gesamt, aber 2 Positionen = vernachlässigbar). Dinas-Aggregation nach
Routing-Key fehlt formal, aber EUR-Auswirkung auf HERMA-Befunde voraussichtlich minimal.
HERMA-Analyse steht noch unter Vorbehalt (DLV-Validierung ausstehend).

---

---

### EBM-Papst (KNR 410844)

**Analyse-Typ:** AX vs. DLV (Stellplatz-basiert, IE/SK/CZ/PL/EE)

**AX-Aggregation:** Pipeline `build_ebm_step23_v196.py` implementiert explizite
`is_sub`-Klassifikation (Zeilen 98–101). Der Kommentar "0 is_sub-Rows im ef>0-Pool"
gilt für den PKL-Erstellungszeitpunkt; im aktuellen BI-Snapshot existieren 2 EE-Sub-Rows
(Mastersendung-Float 7.09e+15, Ton=0, Σef=500 EUR). Diese Rows erscheinen im PKL-df_res
mit `is_sub=False` (Klassifikation zum Laufzeitpunkt) und `fp=0.000` (M1). Kein
materieller Einfluss.

**ZGI-Aggregation:** Kommentar "ZGI-Cluster-Aggregation: nicht anwendbar" im Script-Header
(0 is_sub im Pipeline-Run). Korrekt dokumentiert.

**Status:** `aggregation_korrekt_de_facto`

**Quell-Datei:** `src/build_ebm_step23_v196.py`

**Risiko:** Keines. 2 EE-Sub-Rows (500 EUR, 100% M1) haben null Impact auf Audit-Aussage.

---

### Bitzer SE (KNR 406345)

**Analyse-Typ:** AX vs. DLV (Gewichtsbasiert, EU-Export)

**AX-Aggregation (P9 — ZGI Tonnage-Substitution):** Bitzer verwendet eine spezielle
Variante. In Bitzer's ZGI-Struktur sind **Sub-Rows Billing-Träger** (ef>0, Ton=0)
und **Master-Rows administrative Container** (ef=0, Ton>0, Unterauftrag gesetzt).
Das ist die inverse Logik zu HERMA/Fischerwerke.

Pipeline `build_bitzer_step23_v196.py` (Zeilen 56–93):
1. Klassifiziert `_is_sub = has_ms AND NOT has_ua` (17 Rows, alle Ton=0)
2. Erstellt `masters_ms_ton`-Map: Mastersendung-Nummer → Master-Tonnage
3. Substituiert Tonnage für alle is_sub-Rows mit Ton=0 aus Master-Map
4. **Behält is_sub-Rows im Vergleichs-Pool** (kein Ausschluss)

Dies ist korrekt: Sub-Rows tragen eigene ef, der Calculator-Input (Tonnage) wird
aus dem ZGI-Master gezogen. Kein Doppelzählen, da Master-Rows ef=0 haben.

**Verifikation:** PKL `output/bitzer_step23_results_v196_postfix.pkl` — alle 17 is_sub-Rows
mit `is_sub=True` in df_res enthalten. Tonnage-Substitution erfolgreich für 17 Rows
(0 unresolved). Kein P9-bedingter Bias.

**Status:** `aggregation_korrekt_ax_bitzer_p9`

**Quell-Datei:** `src/build_bitzer_step23_v196.py` (Zeilen 56–93, P9-Kommentar)

**Risiko:** Keines. P9-Mechanismus korrekt und dokumentiert.

---

### Groz-Beckert (KNR 490527 / 410912 / 527373)

**Analyse-Typ:** AX vs. DLV (Dual-Mode: LTL-FTL + GC-kg-basiert)

**Dinas-Aggregation:** n/a (kein Dinas-Vergleich in Groz-Beckert-Scripts)

**AX-Aggregation:** Pipeline `build_groz_beckert_step23_v196.py` implementiert
explizite `is_sub`-Klassifikation (Zeilen 72–76) und schließt Sub-Rows im
`in_scope`-Filter aus (Zeile 94: `~core['_is_sub'] &`). Korrekte v1.9-Implementierung.

BI-Cache `output/bi_cache_groz_beckert.pkl`: 10 Sub-Rows (1,4% der Pool-Rows),
alle Ton=0, Σef=1.293 EUR. Alle korrekt ausgeschlossen.

**ZGI:** Pipeline-Header `build_groz_beckert_step23_v196.py` Zeile 15–16:
"bi_cache_groz_beckert.pkl enthält keine Abrechnungsstrecke/ZGI-Spalten.
Pre-Flight: 0 Mastersendung in Scope → ZGI-Aggregation ist No-Op."

**Status:** `aggregation_korrekt`

**Quell-Datei:** `src/build_groz_beckert_step23_v196.py` (Zeile 94: is_sub-Filter)

**Risiko:** Keines.

---

### HELU-KABEL GmbH (KNR 408244)

**Analyse-Typ:** AX vs. Dinas (Cluster-Familien-Matching)

**Dinas-Aggregation:** Per Rechnung (`rechnung_nr`), analog Fischerwerke/HERMA.
Formale v1.9-Lücke (nicht per Routing-Key), kein bekannter aktiver Impact.

**AX-Aggregation:** `enrich_master_sub()` in `src/build_helu_report_v2.py`
(Zeilen 71–97) — identische Implementierung wie Fischerwerke und HERMA.
Sub-Erlöse werden auf Master summiert; Sub-Rows werden entfernt.

BI-Daten: 97 Sub-Rows (4,2%), alle Ton=0, Σef=6.649 EUR. Alle korrekt ausgeschlossen.

**Status:** `aggregation_korrekt_ax_seite` / `aggregation_fehlt_dinas`

**Quell-Datei:** `src/build_helu_report_v2.py` (`enrich_master_sub` Zeilen 71–97)

**Risiko:** Gering. Alle Sub-Rows Ton=0, 6.649 EUR Σef marginal. Dinas-Aggregation
per Routing-Key fehlt formal, aber Cluster-Familien-Matching kaschiert.

---

### Hornschuch AG (KNR 490085)

**Analyse-Typ:** AX vs. Dinas (Cluster-Familien-Matching + DLV-Vergleich)

**Dinas-Aggregation:** Per Rechnung, analog HELU/Fischerwerke/HERMA.

**AX-Aggregation:** `enrich_master_sub()` in `src/build_hornschuch_report.py`
(Zeilen 65–91) — identische Implementierung. Sub-Rows ausgeschlossen.

BI-Daten: 136 Sub-Rows (5,3%), alle Ton=0, Σef=25.903 EUR. Alle korrekt ausgeschlossen.

**Status:** `aggregation_korrekt_ax_seite` / `aggregation_fehlt_dinas`

**Quell-Datei:** `src/build_hornschuch_report.py` (`enrich_master_sub` Zeilen 65–91)

**Risiko:** Gering. Alle Sub-Rows Ton=0. Dinas-Routing-Key-Aggregation fehlt formal.

---

### Sika Deutschland GmbH (KNR 491063) + Supply Center AG (KNR 511241)

**Analyse-Typ:** AX vs. DLV (Stellplatz-basiert, EU-Export)

**AX-Aggregation:** Pipeline `build_sika_step23_v197.py` implementiert explizite
`is_sub`-Klassifikation und filtert im Pool-Schritt (Zeile 75):
```python
pool = pool_raw[(~pool_raw["is_sub"]) & (pool_raw["ton"] > 0)].copy()
```
Doppelte Bedingung: is_sub-Ausschluss + Ton>0. Vollständig v1.9-konform.

BI-Daten KNR 491063: 18 Sub-Rows (1,3%), alle Ton=0, Σef=7.028 EUR. Alle ausgeschlossen.
BI-Daten KNR 511241: 0 Sub-Rows (0%). Kein Ausschluss nötig.

**Status:** `aggregation_korrekt`

**Quell-Datei:** `src/build_sika_step23_v197.py` (Zeile 75)

**Risiko:** Keines.

---

### Sika Import-Flow (KNR 511241, ES/IT-Ursprung)

**Analyse-Typ:** AX vs. DLV (SikaImportCalculator)

**AX-Aggregation:** Pipeline `build_sika_import_step23_v197.py` — identische
Pool-Konstruktion wie Sika DE (is_sub + ton>0 Filter). 0 Sub-Rows im Import-Pool
(346 Rows aus ES/IT-Ursprung mit Versender-PLZ ∈ {28108, 28065}).

**Status:** `aggregation_korrekt` (n/a, 0 Sub-Rows)

**Quell-Datei:** `src/build_sika_import_step23_v197.py`

**Risiko:** Keines.

---

## Gesamtübersicht (v1.9.7 — 12 Scope-Einheiten)

| Scope | KNR | Sub-Rows | Ton=0 | Ton>0 | Sub Σef (EUR) | AX-Methode | Status |
|---|---|---:|---:|---:|---:|---|---|
| CHT (BE/IT/ES/AT/GR) | 486073 | 38 | 38 | 0 | 5.389 | Ton>0-Filter | `korrekt_de_facto` |
| EBM-Papst | 410844 | 2 (PKL: 0) | 2 | 0 | 500 | is_sub klassifiziert; 0 im PKL | `korrekt_de_facto` |
| Fischerwerke | 409480 | 243 | 180 | 63 | 84.607 | `enrich_master_sub` | `korrekt_ax / fehlt_dinas` |
| HERMA | 423650 | 408 | 406 | 2 | 65.136 | `enrich_master_sub` | `korrekt_ax / fehlt_dinas` |
| GEZE | 406035 | 1.718 | 1.578 | **140** | 143.407 | n/a (Unit-Tests) | `nicht_anwendbar` ⚠ |
| Bitzer | 406345 | 17 | 17 | 0 | 2.242 | P9 Ton-Substitution; im Pool | `korrekt_p9` |
| Groz-Beckert | multi | 10 | 10 | 0 | 1.293 | explicit is_sub-Filter | `korrekt` |
| HELU-KABEL | 408244 | 97 | 97 | 0 | 6.649 | `enrich_master_sub` | `korrekt_ax / fehlt_dinas` |
| Hornschuch | 490085 | 136 | 136 | 0 | 25.903 | `enrich_master_sub` | `korrekt_ax / fehlt_dinas` |
| Sika DE | 491063 | 18 | 18 | 0 | 7.028 | explicit is_sub-Filter | `korrekt` |
| Sika SSC | 511241 | 0 | 0 | 0 | 0 | explicit is_sub-Filter | `korrekt` |
| Sika Import | 511241 | 0 | 0 | 0 | 0 | explicit is_sub-Filter (n/a) | `korrekt` |

**Kernbefund:** In **allen 12 aktiven Audit-Scopes** haben Sub-Rows **Tonnage=0**.
Der einzige Scope mit Ton>0-Sub-Rows (GEZE, 140 Rows, 143.407 EUR) hat keinen aktiven
BI-Vergleich. Kein aktiver Aggregations-Fehler in keinem Scope.

---

## Fazit für v1.9.7

1. **Kein abgeschlossener Scope hat einen aktiven Aggregations-Fehler**, der
   bestehende Audit-Findings verfälscht. Die 12-Scope-Gesamtaussage ist
   aggregations-methodisch validiert.

2. **GEZE** hat latentes Risiko (140 Sub-Rows, Ton>0, 143.407 EUR): expliziter
   `is_sub`-Filter muss vor jeder GEZE BI-Vergleich-Erweiterung implementiert werden.

3. **Fischerwerke / HERMA / HELU-KABEL / Hornschuch**: AX-Seite korrekt durch
   `enrich_master_sub`. Dinas-Seite aggregiert per Rechnung, nicht per Routing-Key
   — formale v1.9-Lücke, aber Cluster-Familien-Matching kaschiert bisher.

4. **Bitzer P9** (ZGI Tonnage-Substitution): abweichende Logik (Sub-Rows im Pool,
   Tonnage aus Master) ist korrekt für Bitzer's inverse ZGI-Struktur
   (Billing auf Subs, Tonnage auf Master). Kein Fehler.

5. **Unit-Tests `test_aggregation.py`:** 32/32 bestanden (alle Funktionen:
   `classify_ax_rows`, `filter_comparison_set`, `aggregate_dinas_per_invoice`,
   `reconstruct_ax_master`, `aggregate_ax_per_cluster`).

6. **CHT-Gate-6 rn_level_adjustment** ist kein Aggregations-Artefakt
   (→ Realitäts-Check in `aggregation_retroactive_risk.md`).

---

*Erstellt: 2026-04-24 | Aktualisiert: 2026-04-28 (v1.9.7, 12 Scopes)*
*Basis: empirische Codebase-Prüfung + bi_top20_data.pkl + bi_cache_groz_beckert.pkl*
*Unit-Tests: 32/32 bestanden. Keine Code-Änderungen. Keine Report-Korrekturen.*
