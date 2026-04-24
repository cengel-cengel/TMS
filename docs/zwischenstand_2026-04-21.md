# Zwischenstand — TMS Migration Audit
**Stand:** 2026-04-21 | **Branch:** `claude/audit-billing-migration-wfgWR` | **Methodik:** v1.8.2

---

## Management-Zusammenfassung

| Kunde | KNR(s) | Status | Etappe | Delta / Befund | Retroaktiv-Risiko |
|---|---|---|---|---|---|
| EBM-Papst Mulfingen | 410844 | Abgeschlossen | 9a.4 | +41.283 EUR (Floater) | niedrig |
| GEZE GmbH | 406035 | Abgeschlossen | 9b.4 | +51.187 EUR (Floater); 12 Muster-B offen | offen |
| Fischerwerke GmbH | 409480 | Zwischenstand | 9a.3.2 | Muster-A +3.057 EUR; Muster-B −4.825 EUR | mittel |
| Sika-Gruppe | 491063/511241/527406 | Abgeschlossen | 8i | 8 Unterfakturierung-Familien, 7 Coverage-Gaps | **HOCH** |
| CHT Germany GmbH | 486073 | Abgeschlossen | 9c.2d | 5 Länder, alle ≥93.3 % | niedrig |
| HERMA GmbH | 423650 | Nicht gestartet | — | Früh-Indikator: −167 kEUR (nicht DLV-validiert — siehe §6) | offen |

**Wesentliche Querschnittsbefunde:**
- Muster-A (+7 % ERKA-Index): bestätigt für Fischerwerke (Mrz 2026) und EBM-Papst (Jan 2026) — systemübergreifend, kundenseitig terminiert. Klärung mit ERKA noch offen.
- Muster-B (Unterfakturierung): belegt bei Fischerwerke (IE/ES/BE/IT-Copiano/GR/GB), Sika (2 Familien AX < DLV, 4 Familien Dinas < AX < DLV). EBM-Papst: 1 Zeile (−100 EUR).
- CHT: 5 Länder kalkulatorisch validiert; DLV-Version-Gap in pre_dlv_2026-Zeilen konsistent (~−2 % bis −2.9 %) — Typ-B-Befund (informativ).
- Sika Re-Run: höchste Priorität vor Onboarding neuer Kunden.
- HERMA: Im Rahmen der Früh-Analysen wurde eine nominale Dinas-AX-Differenz von −167 kEUR identifiziert. Diese Zahl ist nicht DLV-validiert und enthält potenziell methodische Artefakte (rn_level_adjustment, Floater, billing_scope), die bei einem vollständigen Calculator-Build herausgefiltert werden. Die endgültige Zahl wird nach Abschluss des HERMA-Rollouts bekannt sein. **Keine operative Verwendung dieser Zahl bis DLV-Validierung abgeschlossen.**

---

## §1 EBM-Papst Mulfingen (KNR 410844)

**Billing-Basis:** LDM → Palletspaces (`ceil(LDM / 0.4)`), flat per Sendung; Toll separat
**DLV:** `20251010-DLV` (Phase in_dlv_2025), `20260301-DLV` (Phase in_dlv_2026)
**Abgeschlossene Etappen:** 9a.4.1–9a.4.2 | **Report:** `docs/9a43_report.md`

### Scope-Kaskade

| Phase | Zeilen | EUR-Volumen |
|---|---|---|
| pre_dlv (vor 10.10.2025) | 9 | 25.423 EUR — exkl. vom Check |
| in_dlv_2025 | 330 | ~430 kEUR |
| in_dlv_2026 | 9 | — |
| **Calculator OK** | **339** | — |

### Befunde

| Muster | Treffer | EUR-Summe | Lanes |
|---|---|---|---|
| Muster-A (+7 % floater_pct) | 50 Zeilen | —[^1] | IE/PL/EE/SK/HR — Jan 2026 |
| Muster-B (Unterfakturierung) | 1 Zeile | −100,40 EUR | EE Lehmja |
| **Gesamt-Delta** | **339 Zeilen** | **+41.283 EUR** | Alle in_dlv-Zeilen |

[^1]: Muster-A EUR-Summe ist im Gesamt-Delta (+41.283 EUR) enthalten; keine separate Isolation erhoben.

**Muster-A-Detail:** floater_pct = 0.07000 ± 0.0015 auf allen 5 Lanes, ausschließlich Januar 2026. Identisches Muster wie Fischerwerke (dort Mrz 2026) — bestätigt ERKA-Index als systemübergreifende Vereinbarung.

**Altzahl-Revision:** 9a.1.b hatte −18.517 EUR gemeldet. Drei Ursachen: Eircode-Matching-Lücke (IE), fehlende Floater-Modellierung, fehlende Phasen-Trennung. Korrekte Zahl: +41.283 EUR (keine Unterfakturierung in beurteilbaren Zeilen).

**Retroaktiv-Risiko:** niedrig.

**Offene Punkte:** ERKA-Indexschreiben Jan 2026 anfordern. Keine blockierenden §8-Fälle.

---

## §2 GEZE GmbH (KNR 406035)

**Billing-Basis:** Weight (Tonnage eff. in kg), per 100 kg Schritte; Maut/Mobility-Package inklusiv
**DLV:** `20250305_Geze_Export_incl.*.xlsx` — 2025-Fallback aktiv (kein 2026-DLV)
**Abgeschlossene Etappen:** 9b.3–9b.4 | **Report:** `docs/9b4_geze_report.md`

### Scope-Kaskade

| Phase | Gruppen | Positionen | Erlöse Fracht |
|---|---|---|---|
| in_dlv_2025 | 773 | — | 187.791 EUR |
| in_dlv_2025_fallback | 325 | — | 73.095 EUR |
| **Gesamt beurteilbar** | **1.098** | **3.120** | **260.886 EUR** |
| Tonnage=0 (Gate-1) | 1.109 / 4.349 pos | 25,5 % | — |

Gate-1 aktiv: 25,5 % Tonnage=0 überschreitet 20 %-Schwelle. Kein DLV-Check auf diesen Zeilen.

### Befunde nach Land

| Land | Gruppen | DLV-Soll | Ist | Delta | Muster-A | Muster-B |
|---|---|---|---|---|---|---|
| AT | 163 | 18.248 EUR | 22.825 EUR | +4.577 EUR | 0 | 2 |
| CH | 95 | 15.524 EUR | 21.495 EUR | +5.971 EUR | 0 | 0 |
| ES | 245 | 30.310 EUR | 33.883 EUR | +3.573 EUR | 0 | 2 |
| FR | 149 | 67.478 EUR | 78.859 EUR | +11.381 EUR | 0 | 4 |
| GB | 8 | 27.050 EUR | 46.338 EUR | +19.288 EUR | 0 | 1 |
| IE | 4 | 2.392 EUR | 2.405 EUR | +13 EUR | 0 | 0 |
| IT | 363 | 41.403 EUR | 46.977 EUR | +5.574 EUR | 0 | 4 |
| PT | 71 | 7.295 EUR | 8.105 EUR | +810 EUR | 0 | 0 |
| **Gesamt** | **1.098** | **209.699 EUR** | **260.886 EUR** | **+51.187 EUR** | **0** | **13** |

**Muster-A:** 0 Treffer — GEZE weist keinen systemischen ERKA-Indexaufschlag auf. Negativer Befund schärft das Bild: Muster-A ist kundenseitig aktiviert (EBM Jan 2026, Fischerwerke Mrz 2026), nicht verfrachterspezifisch.

**Muster-B:** 13 Kandidaten (delta_raw < −10 EUR). Nach Artefakt-Prüfung: 1 Aggregationsartefakt (GB/WS13 8SY, n_pos=27), 12 Kandidaten manuell zu prüfen (kein abgeschlossener Befund).

**CHF-Floater:** korrekt in Erlöse Fracht eingerechnet; 51/95 CH-Gruppen im Neutralband, 3 Gruppen mit aktivem Floater (CHF/EUR 0,908–0,957).

**Retroaktiv-Risiko:** offen — 12 Muster-B-Kandidaten unvalidiert, kein abgeschlossener Klärungsstatus.

**Offene Punkte:** Manuelle Prüfung der 12 Muster-B-Kandidaten. 2026-DLV bei GEZE anfordern (aktuell 2025-Fallback).

**Offene Audit-Komponente (v1.9-Findings):** Dinas-AX-Vergleich auf Basis der Aggregations-Regel (§2e) wurde für GEZE noch nicht durchgeführt. Empirische Validierung zeigt 8,54 % des Dinas-Gesamt-Volumens (4.242 EUR) in 15 Multi-Group-Rechnungen, die bei einer Aggregations-korrekten Prüfung methodisch ausgewertet werden müssen. Status: offene Audit-Komponente.

---

## §3 Fischerwerke GmbH (KNR 409480)

**Billing-Basis:** Stellplätze (Flat-Rate per Sendung), Lookup-Tabelle per Route
**DLV:** Per-Route-Dateien; IT/BE/DK/IE/ES 2026-DLV vorhanden; GR/GB 2026-DLV fehlt
**Etappen-Status:** 9a.3.1–9a.3.2 abgeschlossen, **4 Rückfragen (RFs) offen** — kein Final-Report
**Report:** `docs/fischerwerke_findings_interim.md`

### Scope-Kaskade

| Lane | DLV-Gültigkeitsfenster | n in_dlv | Beurteilbar |
|---|---|---|---|
| IT-Padova | 01.01–31.12.2026 | 89 | ja |
| IT-Copiano | 12.01–31.12.2026 | 41 | ja |
| BE-Willebroek | 01.01–31.12.2026 | 14 | ja |
| DK-Koge | 01.01–31.12.2026 | 56 | ja |
| IE-Dublin | 01.01–31.12.2026 | 35 | ja |
| ES-MontRoig | 01.01–31.12.2026 | 99 | ja |
| GR-Athen | 01.05–31.12.2025 | 245 | 2025-DLV nur |
| GB-Wallingford | 01.05–31.12.2025 | 39 | 2025-DLV nur |
| **GR 2026** | — | **360** | **UNBEURTEILBAR** (kein 2026-Stückgut-DLV) |
| **GB 2026** | — | — | **UNBEURTEILBAR** (kein 2026-DLV) |
| IT-Verona | — | 21 | UNBEURTEILBAR (DLV-Zuordnung offen) |

GR 2026: 360 Zeilen, 167.638 EUR ohne Referenz-Tarif.

### Befunde

| Muster | Lanes | Treffer | EUR-Summe |
|---|---|---|---|
| Muster-A (+7 %) | IT-Padova/Copiano, BE, DK, IE, ES | 62 Zeilen | +3.057 EUR |
| Muster-B (Unter) | IT-Copiano | 3 Zeilen | −339 EUR |
| Muster-B | BE-Willebroek | 2 Zeilen | −240 EUR |
| Muster-B | IE-Dublin | 2 Zeilen | −759 EUR |
| Muster-B | ES-MontRoig | 3 Zeilen | −532 EUR |
| Muster-B | GR-Athen (2025) | 21 Zeilen | −920 EUR |
| Muster-B | GB-Wallingford (2025) | 10 Zeilen | −2.035 EUR ⚠️ |
| **Muster-B Gesamt** | | **41 Zeilen** | **−4.825 EUR** |

**Muster-A-Detail:** Alle 6 aktuellen 2026-Lanes betroffen, synchron ab ca. März 2026. Ratio-Streuung < 0.00002 Std.abw. — kein Zufall. Höchstwahrscheinlich nicht archiviertes ERKA-Indexschreiben (RF-1 offen).

**GB-Wallingford Warnung:** Größtes Muster-B-Volumen (−2.035 EUR). Kein 2026-DLV identifiziert; 2025-DLV war bis 31.12.2025 gültig.

### Offene Rückfragen

| RF | Inhalt | Blocker für |
|---|---|---|
| RF-1 | ERKA-Indexschreiben: Muster-A als dokumentierte Erhöhung oder Fehler? | Final-Report |
| RF-2 | GB-Wallingford 2026-DLV vorhanden? | GB in_dlv_2026-Check |
| RF-3 | GR-Stückgut 2026-DLV vorhanden? | GR in_dlv_2026-Check (167 kEUR offen) |
| RF-4 | IT-Verona: Padova-DLV oder separate Vereinbarung? | IT-Verona-Check |

**Retroaktiv-Risiko:** mittel — Muster-B belastbar (unabhängig von RF-1); GR 2026 ohne Referenz-Tarif (167 kEUR).

---

## §4 Sika-Gruppe (KNR 491063 / 511241 / 527406)

**Billing-Basis:** Stellplätze (sika_de_stellplatz, ssc_stellplatz, sika_atm_ch)
**Abgeschlossene Etappe:** 8i | **Report:** `docs/sika_findings_summary.md`

### Scope-Kaskade

| Kennzahl | Wert |
|---|---|
| Familien gesamt (eindeutige Route-Tarif-Kombinationen) | 81 |
| Bilateral vergleichbar (Dinas + AX vorhanden) | 25 |
| Orphan Dinas (nur Dinas vorhanden) | 25 |
| Orphan AX (nur AX vorhanden) | 31 |
| Familien mit Unterfakturierung (AX < Dinas-Niveau) | **8** |
| Familien ohne AX-Abrechnung (Coverage-Gaps) | **7** |
| Dinas-Fracht gesamt (historisch) | 2.605.231 EUR |
| AX-Fracht gesamt (POST-Periode, bisher) | 719.426 EUR |

### Unterfakturierung: 8 Familien

| # | Route | Δ AX–Dinas (%) | Muster |
|---|---|---|---|
| 1 | SSC Stuttgart → PLZ-38 (DE) | −52,7 % | A — AX < DLV (echter Fehler) |
| 2 | SSC Stuttgart → PLZ-47 (DE) | −9,1 % | A — AX < DLV (echter Fehler) |
| 3 | Sika DE → Dublin (IE) | −25,4 % | B — DLV ≤ AX < Dinas |
| 4 | SSC → Dublin (IE) | −10,5 % | B — DLV ≤ AX < Dinas |
| 5 | Sika DE → Luxemburg | −7,1 % | B — DLV ≤ AX < Dinas |
| 6 | Sika DE → PLZ-38 (DE) | −81,7 % | C — Dinas-Anomalie (hohe PRE-Basis) |
| 7 | Sika DE → PLZ-47 (DE) | −58,3 % | C — Dinas-Anomalie |
| 8 | SSC Inbound PLZ-28 → Stuttgart | −23,8 % | D — Inbound; kein DLV-Soll |

**Muster-A (AX < DLV):** Familien 1+2 — sofortiger Handlungsbedarf, rückwirkend ab Migrationsdatum.

**Coverage-Gaps:** 7 Familien, davon 3 genuine ATM-CH-Gaps (FR/IT-Zielgebiete) mit nachgewiesener Sendungsaktivität im POST-Tagesbericht.

**Retroaktiv-Risiko:** HOCH — echte Unterfakturierung (Muster A) belegt; Coverage-Gaps mit POST-Aktivität.

**Nächste Schritte:** Sika Re-Run mit aktualisierter Methodik (v1.8.1); Validierung Familien 1+2 gegen aktuelles DLV; ATM-CH-Gaps manuell klären.

---

## §5 CHT Germany GmbH (KNR 486073)

**Billing-Basis:** Weight (Tonnage eff. in kg); AT: Flat per Band; IT/BE/ES/GR: per 100 kg Schritte
**Abgeschlossene Etappen:** 9c.1 (IT), 9c.2a (BE), 9c.2b (ES), 9c.2c (GR), 9c.2d (AT)
**Methodik:** billing_scope = "position" für alle 5 Länder | kg_rounding_rule: §2c v1.8.1

### Scope-Kaskade (alle 5 Länder)

| Land | Etappe | n gesamt | n in_dlv | n Haupt-Test | Match-Rate | Status |
|---|---|---|---|---|---|---|
| IT | 9c.1 | 158 | 68 | 63 (excl. 5 §8) | **100,0 %** | ✓ BESTANDEN |
| BE | 9c.2a | 258 | 121 | 65 (excl. 111 rn_adj, split, §8) | **100,0 %** | ✓ BESTANDEN |
| ES | 9c.2b | 114 | 50 | 30 (excl. 30 rn_adj, 4 split, 16 §8) | **93,3 %** | ✓ BESTANDEN |
| GR | 9c.2c | 102 | 45 | 45 (excl. 50 rn_adj) | **97,8 %** | ✓ BESTANDEN |
| AT | 9c.2d | 36 | 13 | 13 (kein rn_adj) | **100,0 %** | ✓ BESTANDEN |

Erfolgskriterium ≥90 %: alle 5 Länder bestanden.

### §8-Findings Matrix

| Land | §8-Typ | Beschreibung |
|---|---|---|
| IT | Typ B | 5 Ausreißer-Zeilen in in_dlv_2026 — unbekannte Tarifkonstellation |
| BE | Typ B | 111 rn_adj (bidirektionale Faktoren −2,9 % bis +3,0 %); Split-Positionen |
| ES | Typ B | 16 §8-Ausreißer; 4 Split-Positionen; rn_adj-Faktor ≈ −1,94–1,96 % |
| GR | Typ B | 50 rn_adj; Faktor ≈ −2,43 % (konsistent, DLV-Version-Gap) |
| AT | — | 0 §8-Fälle; 23 pre_dlv_2026 (Faktor ≈ −1,96 %, Typ B informativ) |

**DLV-Version-Gap:** Alle pre_dlv_2026-Zeilen zeigen konsistenten negativen Versatz gegenüber 2026-DLV (IT: nicht erhoben; BE: ~−2,9 %; ES: ~−1,96 %; GR: ~−2,43 %; AT: ~−1,96 %). Klassifiziert als Typ B (informativ) — kein 2025-DLV extrahiert.

**BE rn_adj bidirektional:** Einzige Ausnahme zur sonst konsistent negativen rn_adj-Richtung. RN 924081 (+2,96 %) und RN 924102 (+0,50 %), RN 924234 (+0,42 %) zeigen positive Faktoren — möglicherweise nachrechnungs-bedingte AX-Korrekturen. Klärungsfrage Typ A (Operations).

**AT Spezifika (9c.2d):**
- billing_scope = "position" (Flat per Band, nicht per-100-kg)
- kg_rounding_rule = "actual_kg_fracht_only" (§2c v1.8.1)
- Maut: ceil(actual_kg/100)×100; AT-Maut in Fracht inklusiv
- Diesel: not_contracted — 36/36 Zeilen Erlöse_Diesel = 0 bestätigt
- Maut-Delta max = 0.0000 EUR (exakt)

**Retroaktiv-Risiko:** niedrig — alle 5 Länder ≥90 %; Abweichungen methodisch klassifiziert.

---

## §6 Nicht-bearbeitete Kunden (Top-20)

Die folgenden Kunden haben noch keinen abgeschlossenen Audit-Durchlauf. Kein Calculator-Check, keine DLV-Validierung, keine belastbaren Befunde.

### HERMA GmbH (KNR 423650) — Früh-Indikator vorhanden

**Status:** Nicht gestartet (kein Etappen-Report, kein Calculator-Build auf Positions-Ebene)
**Billing-Basis:** Weight (max(Tonnage, LDM×ldm_factor, Vol×vol_factor)), Flat per Sendung
**DLV:** BiddingMatrix 2023–2026 (Haftmaterial/Etiketten, mit/ohne Vorholung); Infrastruktur: `src/tms/tariff/calculators/herma.py` vorhanden
**Früh-Indikator:** Dinas-AX-Effektivpreisvergleich via `build_herma_report.py` zeigt 73 Cluster mit |ΔEff| > 5 %, nominale Differenz −167.554 EUR.

> **⚠ VORBEHALT:** Diese Zahl ist **nicht DLV-validiert**. Sie enthält potenziell
> methodische Artefakte (rn_level_adjustment, Muster-A-Floater, Sonder-PLZ-Pattern,
> billing_scope-Artefakte), die bei einem ordnungsgemäßen Calculator-Build
> herausgefiltert werden würden. **Keine operative Verwendung dieser Zahl in
> 9c.4 oder Etappe 10 bis DLV-Validierung abgeschlossen.**

**Nächste Schritte:** Vollständiger Calculator-Build analog zu CHT/EBM/GEZE; DLV-Parsing für FR/43 und PT/20 priorisieren.

---

### Weitere Kunden (kein Früh-Indikator)

| Kunde | KNR | Billing-Basis (erwartet) | DLV / Infrastruktur | Priorität |
|---|---|---|---|---|
| Bitzer Kühlmaschinenbau | nicht erhoben | Weight (kg) | nicht erhoben | Welle 1 |
| Groz-Beckert | nicht erhoben | Weight (kg) | nicht erhoben | Welle 1 |
| HELU-Kabel | nicht erhoben | Weight (kg) | `calculators/helu.py` vorhanden | Welle 2 |
| Hornschuch | nicht erhoben | Weight (kg) | `calculators/hornschuch.py` vorhanden | Welle 2 |

Weitere Kunden im Top-20-Inventar: KNRs und Billing-Basis nicht erhoben.

---

## §7 Querschnitt-Analysen

### §7A Methodik-Entwicklung

| Version | Datum | Wesentliche Änderungen |
|---|---|---|
| v1.0–v1.3 | vor 2026-04 | Grundgerüst: Phasen-Logik, Muster-A/B-Definition |
| v1.4 | 2026-04-18 | §2 GEZE-DLV-Format; Aggregationsebene Sendungs-Gruppe |
| v1.5 | 2026-04-18 | §3 Muster-A-Formel mit Diesel-Separation; §7 EBM-Diesel-Retroaktiv |
| v1.6a | 2026-04-19 | §1 pre_dlv_2026-Phase; Fallback-Phase präzisiert |
| v1.6b | 2026-04-19 | §2a diesel_mode/maut_mode pro (kunde,land); §7 EBM-Präzision |
| v1.6.1 | 2026-04-19 | §2a Einzelfall-all_in-Ausnahme |
| v1.7 | 2026-04-19 | §6b RN-Level-Faktor-Detection (Gate 6) |
| v1.7.1 | 2026-04-20 | §3a Sonder-PLZ-Aufschlag + AX-Raten-Präzision |
| v1.7.2 | 2026-04-20 | §6c AX-Raten-Präzisions-Check + Zeitbezug-Befund |
| v1.8 | 2026-04-20 | §2b billing_scope-Tabelle; §6a–§6c RN-Level-Calculator-Pipeline |
| v1.8.1 | 2026-04-21 | §2c kg_rounding_rule; AT Strukturbefund; Flat-Rate-Dokumentation |
| v1.8.2 | 2026-04-21 | §9a Multi-Agent-Workflow-Regeln; Ground-Truth-Pflicht; Halluzinierungsincident dokumentiert |

**Aktuelle Version:** v1.8.2 (`88f9591`)

### §7B Cross-Customer Pattern-Aggregation

**Muster-A (+7 % ERKA-Index):**
- EBM-Papst: aktiviert Jan 2026 (50 Zeilen, 5 Lanes)
- Fischerwerke: aktiviert Mrz 2026 (62 Zeilen, 6 Lanes)
- GEZE: nicht aktiviert (0 Treffer) — negativer Befund bestätigt Kundenselektion
- Schlussfolgerung: Muster-A ist eine kundenseitig terminierte Vereinbarung, nicht eine verfrachterspezifische Änderung. Klärung mit ERKA (Indexschreiben anfordern) ausstehend.

**Muster-B (Unterfakturierung):**
- Fischerwerke: 41 Zeilen, −4.825 EUR (IE/ES/BE/IT-Copiano/GR/GB)
- EBM-Papst: 1 Zeile, −100,40 EUR (EE Lehmja)
- Sika: 8 Familien, davon 2 mit AX < DLV (echter Fehler)
- HERMA: 73 Cluster, nominale Differenz −167 kEUR — **nicht DLV-validiert**, nicht als Muster-B zu werten bis Calculator-Build abgeschlossen (siehe §6)

**DLV-Version-Gap (CHT, alle Länder):**
- pre_dlv_2026-Zeilen zeigen konsistenten negativen Versatz ~−2 % bis −2.9 %
- Ursache: fehlendes 2025-DLV; 2026-DLV-Raten liegen höher
- Klassifiziert als Typ-B-Befund (informativ, kein Handlungsbedarf)
- Nicht zu verwechseln mit Unterfakturierung

### §7C Retroaktiv-Risiko-Matrix

| Kunde | Risiko | Begründung |
|---|---|---|
| Sika-Gruppe | **HOCH** | AX < DLV belegt (Familien 1+2); Coverage-Gaps mit POST-Aktivität |
| Fischerwerke | mittel | Muster-B belastbar; GR 2026 ohne Referenz (167 kEUR offen) |
| HERMA | offen | Früh-Indikator −167 kEUR nominal, **nicht DLV-validiert** — kein belastbares Risiko-Rating möglich |
| GEZE | offen | 12 Muster-B-Kandidaten unvalidiert |
| EBM-Papst | niedrig | 1 Muster-B-Zeile; positiver Gesamt-Delta |
| CHT | niedrig | Alle 5 Länder ≥90 %; Abweichungen methodisch klassifiziert |

### §7D Direkter Schaden (Muster-B, quantifiziert)

| Kunde | EUR-Summe | Basis | Konfidenz |
|---|---|---|---|
| Fischerwerke | −4.825 EUR | 41 Zeilen in_dlv, belastbar | hoch |
| Sika (Muster A, AX<DLV) | nicht isoliert erhoben | 2 Familien × POST-Periode | mittel |
| EBM-Papst | −100 EUR | 1 Zeile | hoch |
| HERMA | nicht verwendet | Dinas-Vergleich, nicht DLV-validiert — gesperrt bis Calculator-Build | — |
| **Quantifiziert gesamt** | **−4.925 EUR (excl. HERMA/Sika)** | | |

---

## §8 Prognose und Empfehlungen

### §8A Prognose Audit-Completion

| Kunde | Verbleibende Arbeit | Aufwand-Schätzung |
|---|---|---|
| Sika Re-Run | v1.8.1-Methodik; ATM-CH-Gaps | 1–2 Sessions |
| Fischerwerke Final | RF-1/2/3/4 klären; dann Final-Report | nach RFs: 1 Session |
| GEZE Muster-B | 12 Kandidaten manuell prüfen | 0,5–1 Session |
| HERMA Calculator | DLV-Parser; Calculator-Build; Integration Test | 2–3 Sessions |
| Bitzer/Groz-Beckert | Vollständiger Durchlauf (Welle 1) | je 2–3 Sessions |

### §8B Empfehlungen (priorisiert)

1. **Sika Re-Run sofort** — HOCH-Risiko; Familien 1+2 (AX < DLV) erfordern Sofortkorrektur in AX.
2. **ERKA-Indexschreiben anfordern** — RF-1 (Fischerwerke) und EBM-Papst betroffen; klärt ob Muster-A archiviert oder unabgestimmt.
3. **GB/GR-DLVs 2026 für Fischerwerke** — 167 kEUR GR-Volumen ohne Referenz-Tarif.
4. **HERMA Calculator-Build** — Größtes unquantifiziertes Risiko (−167 kEUR Früh-Indikator).
5. **Bitzer/Groz-Beckert onboarden** — Welle 1 abschließen.

### §8C QA-Hinweis

Bei Verwendung von Read-only-Agenten (Explore) für die Extraktion von Build-Script-Ausgaben: diese Agenten können Python nicht ausführen und produzieren plausibel wirkende aber falsche Zahlen (dokumentiert in `docs/qa_agent_hallucination_2026-04-21.md`). Alle Zahlenwerte in diesem Dokument wurden ausschließlich aus direkten `python src/build_9c*.py`-Ausgaben entnommen.

---

*Erstellt: 2026-04-21 | Zuletzt aktualisiert: 2026-04-21 | Script-Basis: build_9c*, build_herma_report.py | Methodik: v1.8.2*
*Branch: `claude/audit-billing-migration-wfgWR` | Commit-Basis: `8c12df2`*
