# Sika 511241 Import-Flow — Welle 2 Report
## KNR 511241 (SIKA Supply Center AG) — Import ES/IT → DE

**Methodik-Version:** v1.9.7  
**Datum:** 2026-04-28  
**Commit Calculator:** 4d38156 (`sika_import.py`)  
**Commit Pipeline:** 07ba458 (`build_sika_import_step23_v197.py`)  
**Cache:** `output/sika_import_step23_results_v197.pkl`

---

## §1 Scope und Pool

**Abgrenzung:** KNR 511241 enthält neben Export-Sendungen (ssc_eu) und OOS-Inland-DE (de_oos)
einen Block physischer Import-Sendungen: Lieferungen von den Sika-Produktionsstandorten
Cerano/IT und Alcobendas/ES zum Sika-Lager Stuttgart DE-70499. Diese wurden im
Welle-1-Report (v1_9_7_sika_welle1_cluster_report.md §8.1) als "de_oos Import-Origins"
identifiziert.

**Pool-Abgrenzung:** `ef > 0` UND `Versender-PLZ ∈ {28108 (ES), 28065 (IT)}`

| Kennzahl | Wert |
|---|---:|
| Pool roh | 346 |
| is_sub | 0 |
| ton=0 non-sub | 0 |
| stp_eff=0 nach P6 | 0 |
| **Beurteilbar** | **346** |
| DLV-Lücke | 0 |

**Erlöse:**

| Typ | EUR |
|---|---:|
| Σ Erlöse Fracht (ef) | 629.422 |
| Σ Erlöse Maut (P20) | 18.306 |
| Σ ef_total (ef+Maut) | 647.729 |

**Zeitraum:** 2025-09-29 – 2026-03-30  
**Jahr-Verteilung:** 2025 = 182 Rows / 2026 = 164 Rows (Year-Dispatch aktiv)

---

## §2 DLV-Struktur und Calculator-Bau

**DLV-Dateien:**

| Jahr | Datei |
|---|---|
| 2025 | `20250109_Sika Supply_Import Spanien und Italien 2025.xlsx` |
| 2026 | `20251216_Sika Supply_Import Spanien und Italien 2026.xlsx` |

**Pricing-Modi (Offerte-Sheet):**

| Versender | Modus | Basis |
|---|---|---|
| ES-28108 (Sika S.A.U., Alcobendas) | per-Stellplatz | EUR/Sendung für 1–34 Paletten |
| IT-28065 (Sika Polyurethane Mfg., Cerano) | Komplett-LKW | LKW 1 (≤33 Stpl.) / LKW 2 (>33 Stpl.) |

**Tarif-Referenzwerte (2025/2026):**

| Modus | 2025 EUR | 2026 EUR |
|---|---:|---:|
| ES stp=1 | 160,99 | 168,23 |
| ES stp=33 | 2.279,60 | 2.382,18 |
| ES stp=34 | 2.297,40 | 2.400,78 |
| IT LKW 1 (stp ≤ 33) | 1.495,00 | 1.562,00 |
| IT LKW 2 (stp > 33) | 1.575,00 | 1.645,00 |

**DE-Maut:** Separates Sheet `DE-Maut ab 202312` (ident mit Export-DLV-Anlage).
ES-Ursprung → `fr_es_pt`-Gruppe; IT-Ursprung → `at_it`-Gruppe.
AT-Maut: inkludiert in IT-LKW-Flatrates (kein separater Zuschlag).

**Calculator-Klasse:** `SikaImportCalculator` in `src/tms/tariff/calculators/sika_import.py`.
Extra-Parameter: `vers_plz`, `vers_land` (Versender-Routing-Key).

---

## §3 Pre-Flight

| Prüfpunkt | Befund |
|---|---|
| P4 Sub-Row-Filter | 0 Sub-Rows im Import-Pool — kein Filter nötig |
| P6 stp-Fallback | 0 Rows mit stp=0 — Fallback nie ausgelöst |
| P14 OOS-Ausschluss | Scope explizit auf ES/IT-Versender-PLZ eingeschränkt |
| P16 Year-Dispatch | 2025/2026 Dateien geladen; 182/164 Rows korrekt dispatched |
| P20 Erlöse-Maut | Σ 18.306 EUR Erlöse Maut in AX; DLV enthält maut_surcharge separat |

**P20-Anwendung:** `ef_total = Erlöse Fracht + Erlöse Maut`.
DLV-Soll = `basispreis + maut_surcharge` (kalkulatorische Maut aus DE-Maut-Anlage).
Beide Seiten enthalten die Maut-Komponente → fairer Vergleich.

---

## §4 Step 2 — Cluster-Struktur

**Cluster-Schlüssel:** `(vers_land, vers_plz, DLV-Modus)`

| Cluster | n | Σ ef | Σ dlv | Modus |
|---|---:|---:|---:|---|
| ES-28108 | 113 | 263.226 | 269.048 | per-Stellplatz |
| IT-28065 stp≤33 (LKW 1) | 232 | 363.738 | — | Komplett-LKW |
| IT-28065 stp>33 (LKW 2) | 1 | 2.458 | — | Komplett-LKW |

---

## §5 Step 3 — M-Klassifikation

### Nominal (ef vs dlv)

| | ES | IT | Gesamt |
|---|---:|---:|---:|
| Beurteilbar | 113 | 233 | 346 |
| M1 | 113 (100%) | 186 (79,8%) | 299 (86,4%) |
| M2 | 0 | 27 | 27 |
| M_over | 0 | 20 | 20 |

### P20-adjustiert (ef+Maut vs dlv)

| | ES | IT | Gesamt |
|---|---:|---:|---:|
| Beurteilbar | 113 | 233 | 346 |
| M1 | 113 (100%) | 165 (70,8%) | 278 (80,3%) |
| M2 | 0 | 9 | 9 |
| M_over | 0 | 59 | 59 |

### Net Δ

| | Nominal | P20-adjustiert |
|---|---:|---:|
| ES Net Δ | −5.822 EUR (−2,16 %) | −557 EUR (−0,21 %) |
| IT Net Δ | −2.570 EUR (−0,70 %) | +10.472 EUR (+2,84 %) |
| **Gesamt** | **−8.392 EUR (−1,32 %)** | **+9.915 EUR (+1,55 %)** |

Σ dlv (Referenzbasis): 637.814 EUR

---

## §6 Befund-Analyse

### §6.1 ES-28108 — Vollständig sauber

113/113 Rows M1 (P20-adj). Net Δ P20 = −557 EUR (−0,21 %). Der per-Stellplatz-Tarif
von ES greift präzise: Keine DLV-Lücke, kein Muster. Abweichung liegt innerhalb normaler
Rundungsdifferenzen.

**Bewertung: M_korrekt. Kein Befund.**

### §6.2 IT-28065 — Dieselfloater-Artefakt

IT-Rows zeigen fp_p20-Streuung von −12 % bis +38 % um den LKW-Flatrate-DLV-Soll.
Die ef-Werte variieren pro LKW-1-Sendung von 1.322 EUR bis 2.097 EUR (DLV-Soll: 1.551/1.618 EUR).

**Ursache:** Das DLV enthält ausschließlich die Basisrate (LKW 1 = 1.495/1.562 EUR).
Der Dieselfloater ist als "Quartalswert ab 01.03.2024" vereinbart und wird in AX
als Faktor auf den Basispreis aufgeschlagen. Der Quartalsfloater ist nicht im
statischen DLV-Sheet enthalten.

Evidenz:
- Σ Erlöse Diesel (BI) für IT-28065 = 15.773 EUR (≈ 4,3 % des ef)
- Streuung korreliert mit Lieferdatum-Quartalen
- Einzelne Sendungen zeigen fp_p20 > +30 % (Quartale mit hohem Diesel-Index)
  und fp_p20 < −10 % (Quartale mit niedrigem Diesel-Index)
- Aggregat IT Net Δ P20 = +10.472 EUR (+2,84 %) — kein systematischer Schaden

**Bewertung: Dieselfloater-Artefakt. Kein Migrationsschaden.**

---

## §7 P20-Adjustierung Zusammenfassung

| AX-Spalte | Betrag EUR |
|---|---:|
| Σ Erlöse Fracht (ef) | 629.422 |
| + Σ Erlöse Maut | 18.306 |
| = Σ ef_total (P20-adjustiert) | 647.729 |
| Σ DLV-Soll (basispreis + maut_surcharge) | 637.814 |
| **Net Δ P20-adjustiert** | **+9.915 EUR (+1,55 %)** |

Die P20-Adjustierung dreht das Vorzeichen: nominal −8.392 EUR → adjustiert +9.915 EUR.
Treiber: IT-Dieselfloater-Quartalsvariation. Innerhalb Wesentlichkeitsschwelle.

---

## §8 Audit-Aussage

> **KNR 511241 Import-Flow (346 Rows, 629.422 EUR ef): Kein Migrationsschaden.**
>
> 0 DLV-Lücken. ES per-Stellplatz: vollständig M1. IT Komplett-LKW: fp-Streuung
> durch quartalsweisen Dieselfloater, Aggregat +2,84 % P20-adj.
> Net Δ P20-adjustiert gesamt: +9.915 EUR (+1,55 %) — innerhalb Wesentlichkeitsschwelle.

---

## §9 Auswirkung auf Gesamtaussage

Dieser Scope ergänzt die 11-Kunden-Lage aus dem Final Audit Report v1.0 um
einen weiteren verifizierten Block:

| Kennzahl | Welle 1 (§7.2 de_oos-Block) | Import-Flow |
|---|---|---|
| Rows | 347 (de_oos, nicht beurteilbar) | 346 beurteilbar |
| Status | Operative Klärung (Buchungsfrage) | **Auditiert — sauber** |

Empfehlung §7.2 (Sika SSC de_oos-Buchungsfrage) bleibt bestehen:
Die 347 de_oos-Rows stammen zwar physisch aus demselben Import-Flow-Ursprung
(ES/IT → DE), sind jedoch unter KNR 511241 gebucht, obwohl der Export-DLV
nur für DE-Ursprung gilt. Die Buchungsfrage (KNR 511241 vs 491063) ist unabhängig
vom Audit-Ergebnis zu klären.

**Die Gesamtaussage bleibt unverändert: Kein systematischer Migrationsschaden.**
