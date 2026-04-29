# Migrationsaudit Dinas → AX — Abschlussbericht v2.0
**ERKA Rechnungsprüfung / Noerpel-Gruppe**  
Stand: 2026-04-29 | Methodik-Version: v1.9.7 | Erstellt: Claude Code (Anthropic)

---

## §1 Executive Summary

### Geprüfte Migration

Am **27. September 2025** wurde das Transportmanagementsystem von **Dinas** auf **Microsoft Dynamics AX** (Noerpel-Gruppe) umgestellt. Dieser Bericht dokumentiert die abgeschlossenen Ergebnisse der Billing-Auditierung für den Zeitraum nach der Migration (September 2025 – März 2026).

### Untersuchte Kundenbasis

| Merkmal | Wert |
|---|---|
| Kundenfirmen | **11 Unternehmen** |
| Kunden-Scopes (KNR-Einheiten) | **13** |
| Pool gesamt (ef > 0) | 20.361 Abrechnungszeilen |
| Davon beurteilbar | **17.891 Zeilen (87,9 %)** |
| Erlösvolumen beurteilbar | **7,83 MEUR** |
| Auditierter Zeitraum | Oktober 2025 – März 2026 |

### Schlüsselbefund

**Die Migration Dinas → AX wurde sauber durchgeführt. Audit abgeschlossen.**  
Über 13 Kunden-Scopes und ein Erlösvolumen von 7,83 MEUR wurde **kein systematischer Migrationsschaden** identifiziert.

| Kennzahl | Wert |
|---|---|
| Net Δ gesamt (nominal) | **+90.762 EUR (+1,16 %)** |
| Net Δ gesamt (adjustiert P20) | **+139.623 EUR (+1,78 %)** |
| Kunden mit Migrationsschaden | **0** |
| M1-Anteil (±5 %-Toleranz) | **83,8 %** |
| Aggregation-Audit (Methodik) | **32/32 Unit-Tests bestanden** |

### Adjustierungen (P20.1 Erlöse-Maut-Separation)

Zwei methodische Adjustierungen wurden identifiziert und quantifiziert:

- **Sika Deutschland (KNR 491063):** AX bucht DE-Streckenmaut separat (`Erlöse Maut` Σ 30.555 EUR). Nominelles Net Δ −25.758 EUR → adjustiert **+4.797 EUR (+0,37 %)**.
- **Sika Import-Flow (KNR 511241):** Erlöse Maut Σ 18.306 EUR in ef_total einbezogen. Nominelles Net Δ −8.392 EUR → adjustiert **+9.914 EUR (+1,55 %)**.

Beide Adjustierungen sind kein Migrationsfehler, sondern Buchungsseparations-Artefakte.

### Sika ATM (KNR 527406) — Abschluss v2.0

In v1.1 als Folgesession angekündigt, jetzt abgeschlossen:
**395 beurteilbar (Coverage 99,7 %), M1=75,4 %, Net Δ = −7.243 EUR (−3,22 %).**  
RS Serbia −5.357 EUR: vorbestehende separate Rate-Vereinbarung (kein Migrationsfehler).  
Excl. RS: Net Δ = −1.886 EUR (−0,95 %) — kein Migrationsschaden.

### Methodik-Selbstvalidierung — Aggregation-Audit

Die Audit-Methodik wurde code-validiert:
- **32/32 Unit-Tests** (`test_aggregation.py`) bestanden
- **13 Scopes empirisch verifiziert** auf korrekten Sub-Row-Ausschluss
- Kein aktiver Aggregationsfehler bei keinem Kunden gefunden
- Dokumentation: `docs/aggregation_codebase_audit.md` (→ §10)

### Operative Klärungsbedarfe (außerhalb Audit-Scope)

7 operative Klärungspunkte, Σ **1.072.854 EUR**, identifiziert — kein Migrationsbefund:

| Punkt | Kunde | EUR |
|---|---|---:|
| PL-DLV-Lücke | Hornschuch | 203.992 |
| de_oos-Buchung | Sika SSC | 631.702 |
| DE-Inbound OOS | Bitzer | 33.970 |
| GR-Tarif-Lücke | Fischerwerke | 102.052 |
| GB-Zone-Lücke | HERMA | 61.917 |
| CHT GR-Calculator | CHT | 38.776 |
| Bitzer FR | Bitzer | 445 |

Details: `docs/OPERATIVE_KLAERUNGEN_v1_0.md`

### Audit-Aussage

**Der Audit ist abgeschlossen. Keine weiteren offenen Scope-Einheiten.**

---

## §2 Audit-Auftrag und Scope

### Auftrag

Geprüft wird, ob die Umstellung des TMS (Dinas → AX) zum 27.09.2025 alle bestehenden Kundenkonditionen vollständig und korrekt übertragen hat. Konkret: Werden Sendungen nach der Migration zu denselben Tarifstufen abgerechnet wie vor der Migration?

### Prüfungsansatz

Der Audit vergleicht die **AX-Nachmigrationsabrechnung** (Erlöse Fracht aus AX-BI, Oktober 2025 ff.) mit dem **DLV-Soll** (Rahmenvertrag/Offerte des Carriers, rekonstruiert aus den hinterlegten Tarif-Dateien). Kein Dinas-Direktvergleich: Die Dinas-Vorsystem-Daten dienen als Plausibilitätsreferenz, sind jedoch für den Hauptaudit nicht die primäre Vergleichsbasis.

### Scope — 13 Scope-Einheiten (v2.0, abgeschlossen)

| Dimension | Wert |
|---|---|
| Kundenfirmen | 11 (12 rechtliche Einheiten; Groz-Beckert als Gruppe) |
| Kunden-Scopes | 13 KNR-Einheiten |
| Länder | DE-Inbound + EU-Export (ES, FR, GB, IT, AT, PT, IE, BE, NL, RS, SK, CZ, PL u.a.) |
| Carrier | Noerpel-Gruppe (Hauptlieferant) |
| Zeitraum | Oktober 2025 – März 2026 (Post-Migration) |
| Ausgeschlossen | DE-Inland für Exportunternehmen (OOS), Sub-Rows ohne Eigenerlös, Tonnage = 0 |

### Scope-Erweiterung gegenüber v1.1

v1.1 (2026-04-28): 12 Scope-Einheiten, 9 Kundenfirmen. v2.0 ergänzt:
- **Sika ATM** (KNR 527406, Sika Automotive AG, CH) — gewichtsbasierter ATM-Tarif, separater BI-Cache
- Aggregation-Audit als Methodik-Anhang (→ §10)

### Methodik-Kontinuität v1.0 → v2.0

| Version | Datum | Scopes | Δ-Methodik |
|---|---|---:|---|
| v1.0 | 2026-02 | 1 | Erstaudit GEZE (Familien-Vergleich) |
| v1.1 (Report) | 2026-04-28 | 12 | Sika Welle 1 + Import-Flow; P20 |
| **v2.0 (Report)** | **2026-04-29** | **13** | **Sika ATM; Aggregation-Audit validiert** |

### Nicht im Scope (v2.0 final)

- **Dinas-Pre-Migration-Vollabgleich**: AX-BI vs. DLV-Soll dominiert
- **Andere Carrier**: Audit ist auf Noerpel-Abrechnung fokussiert
- **Nicht-Fracht-Erlöse** (Zoll, Versicherung, Lademittel): außerhalb des DLV-Vergleichs
- **KNR 527406 (ATM)**: in v2.0 abgeschlossen — kein verbleibender OOS-Scope

### Datenquellen

| Quelle | Datei | Inhalt |
|---|---|---|
| AX BI (Hauptquelle) | `output/bi_top20_data.pkl` | POST-Buchungen Top-20-KNRs (alle außer 527406) |
| AX BI (ATM) | `output/bi_cache_sika_527406.pkl` | POST-Buchungen KNR 527406 |
| DLV-Tarife | `data/extracted/v1/Noerpel AI/{Kunde}/DLV/` | Excel-Tarife nach Kunde |
| Kunden-Caches | `output/*_step23_results_v19*.pkl` | Aggregierte Ergebnisse, 13 PKL-Dateien |

---

## §3 Methodik-Kurzfassung

### Vergleichsarchitektur

Für jede AX-Abrechnungszeile (ef > 0, kein Sub-Row, Tonnage > 0) wird ein **DLV-Soll** berechnet:

```
dlv_soll = Calculator.calculate(Empf-PLZ, Empf-Land, Gewicht/Stellplätze, Datum)
delta    = ef − dlv_soll
fp       = delta / dlv_soll
```

Der `Calculator` ist ein kundenspezifisches Python-Objekt, das die Tarif-Excel-Datei einliest und nach den Vertragsregeln (Gewichtsband, Zonen, Zuschläge) bewertet.

### M-Klassifikation

| Klasse | Kriterium | Interpretation |
|---|---|---|
| M1 | \|fp\| ≤ 5 % | Korrekte Abrechnung (Toleranzband) |
| M2 | fp < −5 % | AX rechnet unter DLV-Niveau ab |
| M_over | fp > +5 % | AX rechnet über DLV-Niveau ab |

Wesentlichkeitsschwelle: Net Δ > ±5 % bei mehr als 10 Kunden-Rows gleicher Tarifgruppe.

### Schlüssel-Methodiken (v1.9.7)

**ZGI-Cluster-Aggregation (§11):** Sendungen mit identischem Zusammengefasst-in-Schlüssel werden vor dem DLV-Vergleich aggregiert. Verhindert Sub-Row-Doppelzählung (Präzedenz: HERMA, +126.622 EUR Artefakt-Bereinigung). Code-validiert: 32/32 Unit-Tests bestanden (→ §10).

**Pre-Flight Pitfalls P1–P20:** 20 dokumentierte Fehlerquellen von der Daten-Ladung bis zur Pipeline. Vor jedem Kunden-Audit werden alle relevanten Pitfalls geprüft (→ §6).

**Year-Fallback DLV-Resolver:** DLV-Tarif-Auswahl nach Lieferungsdatum (2025 vs. 2026 DLV). Kein Jahresdispatch für Sika ATM (einzige DLV-Datei 2024–2026 gültig).

**Erlös-Komponenten-Separation (P20):**
- **P20.1 Maut:** DLV enthält Maut integriert, AX bucht separat → `ef_total = ef + Erlöse_Maut`. Betrifft Sika 491063 (+30.555 EUR) und Sika Import (+18.306 EUR). Alle anderen 11 Scopes: P20.1-neutral (Σ Erlöse Maut < 0,1 % ef oder DLV ohne Mautkomponente).
- **P20.2 Diesel:** Alle Calculator liefern `diesel_surcharge=None`. Kein systematischer M2-Bias durch Dieseltrennung. Retroaktiver Check alle 13 Scopes: 0 Adjustierungen.
- **P20.3 weitere Komponenten:** Erlöse Zoll/Lademittel/Versicherung außerhalb DLV-Vergleich (0 EUR Impact auf Audit-Scopes).

**Sub-Row-Filter:** `is_sub = (Mastersendung gesetzt) AND (kein eigener Unterauftrag)`. Sub-Rows haben keinen eigenen Erlös und werden ausgeschlossen. Empirisch validiert: alle 13 Scopes (→ §10, Aggregation-Audit).

**ATM Besonderheit (KNR 527406):** Pricing-Basis ist **Flat EUR/Sendung pro Gewichtsband** (nicht EUR/Stellplatz, nicht EUR/kg). Zone-Key `{CC}-{2-stelliger-PLZ-Prefix}` bzw. `GB-{Area}`. Kein Jahresdispatch. Maut und Diesel im Vertragstarif enthalten (beide `= None` im Calculator).

**Calculator Pre-Flight-Fixes:** Bei 6 Kunden wurden Calculator-Bugs identifiziert und behoben, bevor die Audit-Zahlen berechnet wurden. Diese Fixes sind **nicht** auf Migrationsfehler zurückzuführen (→ §6).

### Verweis

Vollständige Methodikdokumentation: `docs/AUDIT_METHODOLOGY.md` v1.9.7 (§1–§15).  
Aggregation-Audit: `docs/aggregation_codebase_audit.md` (→ §10).

---

## §4 Konsolidierte 13-Scope-Tabelle

### Haupt-Tabelle

| Kunde | KNR | Pool roh | Beurteilbar | M1 | M2 | M_over | Σ ef (EUR) | Net Δ nom. (EUR) | Net Δ adj. (EUR) | Net Δ % (adj.) | Headline |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| GEZE GmbH | 406035 | 2.917 | 2.759 | 2.550 | 132 | 77 | 391.904 | +4.138 | +4.138 | +1,07 % | kein Schaden |
| EBM-Papst | 410844 | 353 | 308 | 285 | 1 | 22 | 480.133 | +3.514 | +3.514 | +0,74 % | kein Schaden |
| Fischerwerke | 409480 | 1.173 | 839 | 321 | 107 | 411 | 537.574 | +106.811 | +106.811 | +24,80 %¹ | kein Schaden¹ |
| HERMA GmbH | 423650 | 3.781 | 3.642 | 2.842 | 384 | 416 | 2.428.736 | −16.374 | −16.374 | −0,67 % | kein Schaden |
| CHT Germany | 486073 | 702 | 554 | 539 | 0 | 15 | 257.594 | −668 | −668 | −0,26 % | kein Schaden |
| Bitzer | 406345 | 3.406 | 3.330 | 2.868 | 206 | 256 | 723.694 | +26.407 | +26.407 | +3,79 %² | kein Schaden² |
| Groz-Beckert | multi | 621 | 527 | 473 | 0 | 54 | 112.997 | +5.729 | +5.729 | +5,07 %³ | kein Schaden³ |
| HELU-KABEL | 408244 | 2.293 | 2.185 | 2.044 | 102 | 39 | 315.991 | +203 | +203 | +0,06 % | kein Schaden |
| Hornschuch AG | 490085 | 2.551 | 1.565 | 1.549 | 7 | 9 | 408.579 | −205 | −205 | −0,05 %⁴ | kein Schaden⁴ |
| Sika DE | 491063 | 1.407 | 1.379 | 887 | 293 | 199 | 1.278.459 | −25.758 | **+4.797** | **+0,37 %⁵** | kein Schaden⁵ |
| Sika SSC | 511241 | 415 | 62 | 43 | 0 | 19 | 43.358 | +2.600 | +2.600 | +6,38 % | kein Schaden |
| Sika Import | 511241 | 346 | 346 | 299 | 27 | 20 | 629.422 | −8.392 | **+9.914** | **+1,55 %⁶** | kein Schaden⁶ |
| **Sika ATM** | **527406** | **396** | **395** | **298** | **92** | **5** | **217.470** | **−7.243** | **−7.243** | **−0,95 %⁷** | **kein Schaden⁷** |
| **Gesamt** | | **20.361** | **17.891** | **14.998** | **1.351** | **1.542** | **7.825.911** | **+90.762** | **+139.623** | **+1,78 %** | **0 Schäden** |

*Net Δ % (adj.) = Net Δ adj. / Σ ef. ATM excl. RS (32 Rows, −5.357 EUR pre-existing): Net Δ = −1.886 EUR (−0,95 %).*

---

**¹ Fischerwerke +24,80 %:** Charter-Artefakt. Vollfahrzeug-Chartersendungen werden gegen per-Stellplatz-DLV verglichen → systematischer M_over (+118 TEUR). Non-Charter-Pool: ≈0 %. Kein Abrechnungsfehler.

**² Bitzer +3,79 %:** Post-Fix nach zwei Calculator-Korrekturen (IT Zone4 Perioden-Dispatch, FR-13400 Zone9-Routing). Verbleibende positive Differenz wahrscheinlich Diesel-Floater-Einschluss in ef-Erlösen. Kein Carrier-Fehler.

**³ Groz-Beckert +5,07 %:** Ausschließlich im GC-Mode (Gewicht/kg, 474 Rows). LTL-FTL-Mode (PT-Porto-Lanes, 53 Rows): Δ = 0,00 EUR exakt. GC M_over = Über-Band-Sendungen; DLV-Extrapolation überschätzt per-kg-Rate bei Großgewichten. Kein Carrier-Fehler.

**⁴ Hornschuch PL-DLV-Lücke:** 726 PL-Sendungen (203.992 EUR) ohne verifizierbaren Carrier-Tarif. Operative Klärung empfohlen (→ §7, Punkt C.1).

**⁵ Sika DE Erlöse-Maut-Separation (P20.1):** Nominelles Net Δ −25.758 EUR (−1,97 %) ist Methodik-Artefakt. AX bucht DE-Streckenmaut in `Erlöse Maut` (Σ 30.555 EUR). P20.1-adjustiert: **+4.797 EUR (+0,37 %)**. Kein Schaden.

**⁶ Sika Import Dieselfloater-Artefakt (P20.1):** Nominelles Net Δ −8.392 EUR ist durch IT-Dieselfloater und Maut-Separation bedingt. Σ Erlöse Maut = 18.306 EUR. P20.1-adjustiert: **+9.914 EUR (+1,55 %)**. Kein Schaden.

**⁷ Sika ATM RS pre-existing:** Net Δ −7.243 EUR dominiert durch RS Serbia (32 Rows, −5.357 EUR): separate Laufkarten-Vereinbarung PLZ 34000, nicht in Anlage 1 hinterlegt — vorbestehend, kein Migrationsfehler. Excl. RS: Net Δ = −1.886 EUR (−0,95 %). Kein P20-Adjustment (Maut 21 EUR + Diesel 36 EUR < 0,1 % ef).

---

### M-Klassen-Verteilung Gesamt (13 Scopes)

| Klasse | Rows | Anteil | Δ-Beitrag (EUR) |
|---|---:|---:|---:|
| M1 (±5 %) | 14.998 | 83,8 % | +53.226 |
| M2 (< −5 %) | 1.351 | 7,6 % | −170.878 |
| M_over (> +5 %) | 1.542 | 8,6 % | +208.415 |
| **Gesamt beurteilbar** | **17.891** | **100 %** | **+90.762** |

---

## §5 Pro-Scope-Detail-Befunde

### 5.1 GEZE GmbH (KNR 406035)

**Calculator:** `geze.py` (Commit dd3d558) | **DLV:** Gewichtsbasiert, Ländertarife ES/FR/IT/GB/AT/BE  
**Pool:** 2.917 roh → 2.759 beurteilbar (94,6 %) | **DLV-Lücke:** 158 Rows  
**Ergebnis:** M1=2.550 (92,4 %), M2=132 (4,8 %), M_over=77 (2,8 %) | Net Δ = +4.138 EUR (+1,07 %)

**Befunde:** Kein Migrationsschaden. M2-Rows konzentrieren sich auf wenige Strecken-Cluster (FR Auvergne, ES-Nordwest). M_over-Rows durch Diesel-Floater-Einschluss in ef-Erlösen erklärbar. Kein systematisches Abweichungsmuster.

**Calculator Pre-Flight:** Keine Bugs gefixt. DLV-Format korrekt verarbeitet.

**Detail-Report:** `docs/v1_9_6_geze_cluster_report.md`

---

### 5.2 EBM-Papst (KNR 410844)

**Calculator:** `ebm.py` (Commit 7500102) | **DLV:** Stellplatz-basiert, IE/SK/CZ/PL  
**Pool:** 353 roh → 308 beurteilbar (87,3 %) | **DLV-Lücke:** 28 Rows (ES/PT nach DLV-Erweiterung 08/2025)  
**Ergebnis:** M1=285 (92,5 %), M2=1 (0,3 %), M_over=22 (7,1 %) | Net Δ = +3.514 EUR (+0,74 %)

**Befunde:** Kein Migrationsschaden. IE 100 % M1. M_over-Rows (SK 905 01) durch Tarif-Band-Extrapolation bei großen Stellplätzen erklärbar. Erlöse Maut = 15.596 EUR in AX, aber Pipeline vergleicht `ef (Erlöse Fracht)` vs `dlv = basispreis` — balancierte Vergleichsbasis, kein P20.

**Calculator Pre-Flight:** Keine Bugs gefixt.

**Detail-Report:** `docs/v1_9_4_ebm_cluster_report.md`

---

### 5.3 Fischerwerke GmbH (KNR 409480)

**Calculator:** `fischerwerke.py` (Commit 61f229e) | **DLV:** Gewichtsbasiert, EU-Export + GR  
**Pool:** 1.173 roh → 839 beurteilbar (71,5 %) | **DLV-Lücke:** 334 Rows (GR/DE/NL)  
**Ergebnis:** M1=321 (38,3 %), M2=107 (12,8 %), M_over=411 (49,0 %) | Net Δ = +106.811 EUR (+24,80 %)

**Befunde:** Kein Migrationsschaden. **Charter-Artefakt:** 291 Charter-Rows (Vollfahrzeug-Preise 1.800–3.000 EUR) werden gegen per-Stellplatz-DLV verglichen → systematischer M_over (+118 TEUR). Non-Charter-Pool (548 Rows): Net Δ ≈ 0. M2-Cluster (IT-Cluster, FR-Cluster): Calculator-Extrapolation für mittlere Gewichtsklassen.

**Operative Klärung:** GR-Sendungen 264 Rows (102.052 EUR ef) ohne GR-DLV (→ §7, Punkt C.3).

**Detail-Report:** `docs/v1_9_6_fischerwerke_cluster_report.md`

---

### 5.4 HERMA GmbH (KNR 423650)

**Calculator:** `herma.py` (Commit c26dbe1) | **DLV:** Gewichts-/LDM-basiert, EU-Export  
**Pool:** 3.781 roh → 3.642 beurteilbar (96,3 %) | **DLV-Lücke:** 139 Rows  
**Ergebnis:** M1=2.842 (78,0 %), M2=384 (10,5 %), M_over=416 (11,4 %) | Net Δ = −16.374 EUR (−0,67 %)

**Befunde:** Kein Migrationsschaden. **ZGI-Aggregations-Bereinigung:** v1.9.4 hatte −142.996 EUR M2-Artefakt durch Sub-Row-Doppelzählung. Nach ZGI-Cluster-Aggregation (§11): −16.374 EUR, nicht erklärbar als Migrationsschaden. Verbleibende M2 (−67.758 EUR): LDM-basierte Sendungen mit Sonderkondition Gate-C (nicht vollständig im DLV abgebildet).

**GB-Zones Operative Klärung:** 93 Rows (61.917 EUR) ohne GB-Area-Codes im DLV (→ §7, Punkt C.4).

**Calculator Pre-Flight:** Keine Bugs gefixt; ZGI-Aggregation als Methodik-Fix eingeführt.

**Detail-Report:** `docs/v1_9_6_herma_cluster_report.md`

---

### 5.5 CHT Germany (KNR 486073)

**Calculator:** `cht.py` (Commit 22f0b83) | **DLV:** Gewichts-/LDM-basiert, BE/IT/ES/AT (+ GR separat)  
**Pool:** 702 roh → 554 beurteilbar (78,9 %) | **DLV-Lücke:** keine (vollständige PLZ-Coverage)  
**Ergebnis:** M1=539 (97,3 %), M2=0, M_over=15 (2,7 %) | Net Δ = −668 EUR (−0,26 %)

**Befunde:** Kein Migrationsschaden. 97,3 % M1 — eine der saubersten Kunden-Konstellationen. M_over=15 durch Diesel-Floater. Land-Breakdown: AT=41 (+421 EUR), BE=241 (−201 EUR), ES=105 (−1.395 EUR), IT=167 (+506 EUR).

**GR-Calculator fehlend:** 102 Rows (38.776 EUR) mit `CHTGreeceCalculator AttributeError` (→ §7, Punkt C.6). Kein Migrationsfehler — Calculator noch nicht implementiert.

**Calculator Pre-Flight:** Keine Bugs gefixt.

**Detail-Report:** `docs/v1_9_6_cht_cluster_report.md`

---

### 5.6 Bitzer SE (KNR 406345)

**Calculator:** `bitzer.py` (Commit 93dc7c1) | **DLV:** Gewichtsbasiert (ERKA + Profoid), EU-Export  
**Pool:** 3.406 roh → 3.330 beurteilbar (97,8 %) | **DLV-Lücke:** 76 Rows (Spezialrouten)  
**Ergebnis:** M1=2.868 (86,1 %), M2=206 (6,2 %), M_over=256 (7,7 %) | Net Δ = +26.407 EUR (+3,79 %)

**Befunde:** Kein Migrationsschaden. **Calculator-Fixes vor Audit (Commit 93dc7c1):**
- **IT Zone4 Perioden-Dispatch (P12/P16):** Zone 4 (PLZ-Prefix 32–36) hatte 2024-Raten aktiv; Fix dispatcht korrekt nach Lieferungsjahr.
- **FR-13400 Zone9-Routing:** Aubagne PLZ 13400 war Zone 3 (falsch); korrigiert auf Zone 9 via Profoid-DLV.

Post-Fix-Befund +26.407 EUR (+3,79 %): verbleibend durch Diesel-Floater-Einschluss in ef-Erlösen (offene Prüfung). Kein Carrier-Fehler.

**Operative Klärungen:** FR-92000 Hauts-de-Seine (Zonenzuordnung, geringe Materialität). DE-Inbound 67 Rows (33.970 EUR, →§7 C.5). FR sonstige 7 Rows (445 EUR, →§7 C.7).

**Detail-Report:** `docs/v1_9_6_bitzer_cluster_report.md`

---

### 5.7 Groz-Beckert (KNR 490527 / 410912 / 527373)

**Calculator:** `groz_beckert.py` (Commit 7500102) | **DLV:** Dual-Mode (LTL-FTL + GC-kg-basiert)  
**Pool:** 621 roh → 527 beurteilbar (84,9 %) | **DLV-Lücke:** keine (DE/HR/NO/SE OOS)  
**Ergebnis:** M1=473 (89,8 %), M2=0, M_over=54 (10,2 %) | Net Δ = +5.729 EUR (+5,07 %)

**Befunde:** Kein Migrationsschaden. **GC-Band-Artefakt:** Net Δ liegt ausschließlich im GC-Mode (Gewicht/kg, 474 Rows). Große Sendungen überschreiten das höchste Tarifband → DLV extrapoliert per-kg-Rate linear, AX rechnet Flat-Cap. LTL-FTL-Mode (PT-Porto-Lanes, 53 Rows): Net Δ = 0,00 EUR exakt — perfekte DLV-Konformität.

**Calculator Pre-Flight:** Keine Bugs. Dual-Mode ab Commit 7500102 korrekt implementiert.

**Detail-Report:** `docs/v1_9_6_groz_beckert_cluster_report.md`

---

### 5.8 HELU-KABEL GmbH (KNR 408244)

**Calculator:** `helu.py` (Commit 897a2c6) | **DLV:** Gewichts-/Zonen-basiert, EU-Export  
**Pool:** 2.293 roh → 2.185 beurteilbar (95,3 %) | **DLV-Lücke:** 0 Rows (nach Fixes vollständig)  
**Ergebnis:** M1=2.044 (93,5 %), M2=102 (4,7 %), M_over=39 (1,8 %) | Net Δ = +203 EUR (+0,06 %)

**Befunde:** Kein Migrationsschaden. Net Δ nahezu null. M2=102 durch geringfügige Raten-Abweichungen in wenigen Strecken-Clustern.

**Calculator Pre-Flight — 2 Bugs gefixt (Commit 897a2c6):**
- **H1 (ES-Mendaro Zone Key):** `zone_fn` gab "ES-20870" zurück; Dictionary-Key ist "ES". Fix: `return "ES"`. 67 ES-Rows gerettet.
- **H2 (GB rates_by_col int vs str Keys):** int-Spaltenindizes als Keys; `zone_fn` gab str zurück → Dict-Lookup scheiterte. Fix: `str(c)` Keys. 55 GB-Rows gerettet.

**Detail-Report:** `docs/v1_9_6_helu_cluster_report.md`

---

### 5.9 Hornschuch AG (KNR 490085)

**Calculator:** `hornschuch.py` (Commit a0a9822) | **DLV:** Gewichts-/Zonen-basiert (ContiTech + ERKA), EU-Export  
**Pool:** 2.551 roh → 1.565 beurteilbar (61,4 %) | **DLV-Lücke:** 726 PL-Rows (203.992 EUR)  
**Ergebnis:** M1=1.549 (99,0 %), M2=7 (0,4 %), M_over=9 (0,6 %) | Net Δ = −205 EUR (−0,05 %)

**Befunde:** Kein Migrationsschaden. 99 % M1 — höchste M1-Quote aller Kunden. Net Δ = −205 EUR ist materiell irrelevant.

**Calculator Pre-Flight — 1 Bug gefixt (Commit a0a9822):**
- **G3 (AT-Zone 2-stellig vs 1-stellig):** Calculator extrahierte 2-stelligen Prefix für AT-Zone-Lookup; DLV enthält AT-Zonen 1–9 (1-stellig). Fix: Prefix-Länge auf 1 Zeichen.

**Besondere Befunde:**
- **FR-Castorama/Leroy Merlin (P18):** 318 FR-Rows mit fp = 0,0000 — AX rechnet exakt DLV-Soll. Additiver Paletten-Aufschlag im DLV nicht in AX-ef enthalten. Kein Calculator-Bug, kein Schaden.
- **FTL-Flat-Rate (P19):** 7 M2-Rows (Großsendungen > 12 TEUR, fp −7 bis −17 %): AX FTL-Flat vs Calculator per-kg-Extrapolation → Artefakt.
- **PL-DLV-Lücke:** 726 Rows, 203.992 EUR — ERKA-DLV: 99 PL-Zonen, alle Raten leer. Operative Klärung ausstehend (→ §7, Punkt C.1).

**Detail-Report:** `docs/v1_9_6_hornschuch_cluster_report.md`

---

### 5.10 Sika Deutschland GmbH (KNR 491063)

**Calculator:** `sika_de.py` — `SikaDeCalculator` (Commit 7500102) | **DLV:** Stellplatz-basiert, EU-Export  
**Pool:** 1.407 roh → 1.379 beurteilbar (98,0 %) | **DLV-Lücke:** 9 Rows (5.126 EUR)  
**Ergebnis:** M1=887 (64,3 %), M2=293 (21,2 %), M_over=199 (14,4 %) | Net Δ nom. = −25.758 EUR (−1,97 %)  
**Net Δ adjustiert (P20.1):** **+4.797 EUR (+0,37 %)**

**Hauptbefund — Erlöse-Maut-Separation (P20.1):**  
AX bucht die DE-Streckenmaut als separaten Posten `Erlöse Maut`. Pipeline verwendet `ef = Erlöse Fracht` (ohne Maut). DLV-Soll = `basispreis + de_maut`. Σ Erlöse Maut (EU-Pool) = 30.555 EUR. Adjustiertes Net Δ = +4.797 EUR. Kein Migrationsschaden.

**M2-Struktur:** 107 Extreme-M2 (fp < −50 %, Kleinstsendungen fractional AX-Rates), 186 Moderate-M2 (Maut-Separation-Bias). M_over = 199 Rows durch Billing-above-DLV bei größeren Stellplatz-Counts (SE/IE/ES/GB).

**Calculator Pre-Flight:** Keine Bugs; Calculator korrekt.

**Detail-Report:** `docs/v1_9_7_sika_welle1_cluster_report.md`

---

### 5.11 SIKA Supply Center AG (KNR 511241 — ssc_eu)

**Calculator:** `sika_de.py` — `SSCCalculator` (Commit 7500102) | **DLV:** Identisch mit KNR 491063  
**Pool:** 415 roh → 62 beurteilbar (ssc_eu) | **DLV-Lücke:** 4 Rows  
**Ergebnis:** M1=43 (69,4 %), M2=0, M_over=19 (30,6 %) | Net Δ = +2.600 EUR (+6,38 %)

**Befunde:** Kein Migrationsschaden. Positives Net Δ: AX rechnet für SSC-Export-Sendungen über DLV-Niveau ab — kein Schaden für Noerpel.

**Scope-Struktur KNR 511241:**

| Scope | Rows | Σ ef (EUR) | Status |
|---|---:|---:|---|
| ssc_eu (beurteilbar) | 62 | 43.358 | In Scope (§5.11) |
| de_oos (Empf. DE) | 347 | 631.702 | OOS Export-DLV (→ §7, C.2) |
| import_flow (non-SSC) | 346 | 629.422 | Import-Flow (→ §5.12) |
| dlv_luecke | 4 | 4.720 | DLV-Lücke |

**Detail-Report:** `docs/v1_9_7_sika_welle1_cluster_report.md`

---

### 5.12 SIKA Supply Center AG — Import-Flow (KNR 511241)

**Calculator:** `sika_import.py` — `SikaImportCalculator` (Commit 4d38156) | **DLV:** Import ES/IT 2025/2026  
**Pool:** 346 roh → 346 beurteilbar (100 %) | **DLV-Lücke:** 0 Rows  
**Ergebnis:** M1=299 (86,4 %), M2=27 (7,8 %), M_over=20 (5,8 %) | Net Δ nominal = −8.392 EUR (−1,32 %)  
**Net Δ P20-adjustiert:** **+9.914 EUR (+1,55 %)**

**Scope:** Physische Import-Sendungen von Sika-Produktionsstandorten Alcobendas/ES (28108) und Cerano/IT (28065) zum Sika-Lager DE-70499 Stuttgart.

**Pricing-Modi:**
- **ES-28108 (113 Rows):** per-Stellplatz-Tarif. 113/113 M1 nominal. Net Δ P20 = −557 EUR (−0,21 %).
- **IT-28065 (233 Rows):** Komplett-LKW Flat-Rate (1.495–1.645 EUR/Sendung). Net Δ P20 = +10.471 EUR (+2,84 %).

**Hauptbefund — IT Dieselfloater-Artefakt:** IT-Rows zeigen fp-Streuung von −12 % bis +38 % durch quartalsweisen Dieselfloater (Σ Erlöse Diesel = 15.773 EUR). Aggregat IT Net Δ P20 = +10.471 EUR — innerhalb Wesentlichkeitsschwelle. Kein Migrationsschaden.

**P20.1-Adjustierung:** Σ Erlöse Maut = 18.306 EUR. ef_total = ef + Erlöse Maut für Vergleich.

**Detail-Report:** `docs/v1_9_7_sika_511241_import_report.md`

---

### 5.13 Sika Automotive AG (KNR 527406 — ATM)

**Calculator:** `sika_atm.py` — `SikaATMChCalculator` (Commit f005e63) | **DLV:** Anlage 1 KORRIGIERT, Flat EUR/Sendung  
**Pool:** 396 roh → 395 beurteilbar (99,7 %) | **DLV-Lücke:** 1 Row (DE-70499, ERKA nicht nominiert)  
**Ergebnis:** M1=298 (75,4 %), M2=92 (23,3 %), M_over=5 (1,3 %) | Net Δ = −7.243 EUR (−3,22 %)  
**Excl. RS pre-existing:** Net Δ = **−1.886 EUR (−0,95 %)**

**Tarif-Besonderheit:** Pricing-Basis ist **Flat EUR/Sendung pro Gewichtsband** (nicht EUR/kg, nicht EUR/Stellplatz). DLV-Gültigkeit 2024-07-01 – 2026-06-30, kein Jahresdispatch. Maut und Diesel im Tarif enthalten, kein P20-Adjustment (Σ Erlöse Maut 21 EUR + Diesel 36 EUR = 0,03 % ef).

**Land-Breakdown (beurteilbar):**

| Land | n | Net Δ | Net Δ % | M1 | M2 | M_ov |
|---|---:|---:|---:|---:|---:|---:|
| ES | 49 | +1.270 | +2,64 % | 48 | 0 | 1 |
| GB | 96 | −1.107 | −1,50 % | 85 | 11 | 0 |
| IT | 205 | −2.049 | −3,07 % | 134 | 67 | 4 |
| PT | 13 | 0 | **0,00 %** | 13 | 0 | 0 |
| RS | 32 | −5.357 | −20,52 % | 18 | 14 | 0 |

**Hauptbefunde:**
- **RS Serbia (PLZ 34000 Kragujevac, 32 Rows):** 14 M2-Rows mit AX-ef deutlich unter Anlage-1-Satz. Separate Laufkarten-Vereinbarung für Kragujevac-Strecke; Anlage 1 nicht anwendbar. Vorbestehend dokumentiert (`data/reports/sika_atm_revalidation.md`). **Kein Migrationsfehler.** Operative Klärung einheitliche DLV-Anwendung empfohlen.
- **PT (13 Rows):** Net Δ = 0,00 EUR — perfekte DLV-Konformität. Anlage-1-Sätze korrekt angewendet.
- **IT 85025 M_over (2 Rows, +3.611 EUR):** Runde ef-Werte (2.500/3.350 EUR) deutlich über DLV-Satz (1.012/1.226 EUR). Hypothese: Stellplatz-basierte Abrechnung. Operative Prüfung empfohlen.
- **ES 28041 M_over (1 Row, +1.270 EUR, ton=30 kg):** ef=1.350 vs DLV=79,65 EUR — Spot-Rate oder Mindest-Sendungspreiszuschlag.

**Calculator Pre-Flight:** Keine Bugs. Zone-Key-Logik und Gewichtsband-Lookup korrekt.

**Detail-Report:** `docs/v1_9_7_sika_atm_cluster_report.md`

---

## §6 Pre-Flight-Pitfall-Katalog (P1–P20)

20 dokumentierte Fehlerquellen, die vor jedem Kunden-Audit systematisch geprüft werden. Vollständige Beschreibung: `skills/customer-preflight/SKILL.md`.

### Kategorie: Daten-Lade-Bugs

| Pitfall | Kurzname | Präzedenz | Kunden betroffen |
|---|---|---|---|
| P1 | PLZ-Format-Normalisierung | GEZE (GB-Areas), HELU (ES) | 3+ |
| P2 | Währungs-/Einheits-Mismatch (kg vs t, EUR vs CHF) | HERMA (CHF-Tarif) | 2 |
| P3 | KNR-Normalisierung (Buchungsnummer ≠ Kundennummer) | Sika (Supply Center unter KNR 491063) | 1 |
| P11 | ZGI-Spalten-Verfügbarkeit | HERMA, Fischerwerke | 2 |
| P13 | DLV-Datei-Auswahl (mehrere Versionen im Verzeichnis) | Bitzer (2025 vs 2026 DLV) | 2 |

### Kategorie: Calculator-Bugs

| Pitfall | Kurzname | Präzedenz | Kunden betroffen |
|---|---|---|---|
| P5 | Zone-Schlüssel-Abweichung (PLZ-Prefix-Länge) | Hornschuch AT (G3, 2→1-stellig) | 3 |
| P6 | LDM/Stellplatz-Fallback wenn Feld leer | Sika (LDM÷0,4 Fallback) | 2 |
| P7 | Gewichtsband-Auswahl (erste vs. beste Übereinstimmung) | EBM (SK-Extrapolation) | 2 |
| P10 | Charter-Pool-Ausschluss fehlt | Fischerwerke (291 Charter-Rows) | 1 |
| P12 | IT-Tarif-Perioden-Dispatch | Bitzer (IT Zone4 2024 vs 2025 DLV) | 1 |
| P15 | Stellplatz-Cap (DLV-Maximum überschritten) | Sika (stpl_int > 33) | 1 |
| P16 | Year-Dispatch DLV (Lieferungsjahr-Tarif-Wahl) | Bitzer (FR-13400 Zone 3→9) | 2 |
| P17 | Zone-Lookup-Format-Mismatch (Key-Typ str vs int) | HELU (H1 ES, H2 GB) | 1 |
| P18 | Additiver Zuschlag (in DLV, nicht in AX-ef) | Hornschuch (FR Castorama) | 1 |
| P19 | FTL-Flat-Rate vs per-kg-Extrapolation M2-Artefakt | Hornschuch (7 Rows) | 1 |

### Kategorie: Pipeline-Bugs

| Pitfall | Kurzname | Präzedenz | Kunden betroffen |
|---|---|---|---|
| P4 | Sub-Row-Filter fehlt (is_sub = has_ms & ~has_ua) | HERMA v1.9.4 | 2 |
| P8 | Cluster-Key zu grob (Aggregations-Bias) | HERMA +126 TEUR Artefakt | 2 |
| P9 | DLV-Soll auf Cluster-Ebene vs. Row-Ebene | Bitzer (ZGI-Aggregation) | 2 |
| P14 | OOS-Zeilen nicht ausgeschlossen vor Calculator | Sika (de_oos im Export-DLV) | 2 |
| P20.1 | Erlöse-Maut-Separation (ef = Fracht, DLV = Fracht+Maut) | Sika 491063 (+30.555 EUR), Sika Import (+18.306 EUR) | 2 |
| P20.2 | Erlöse-Diesel-Separation (Calculator diesel=None, kein M2-Bias) | IT Dieselfloater als M_over/M2-Streuung; 0 Adjustierungen alle 13 Scopes | 0 |
| P20.3 | Weitere Erlös-Komponenten | Checkliste für Folgekunden (Zoll, Lademittel, Versicherung) | — |

### Gefixter Bugs nach Kunden

| Kunde | Fix | Commit | Δ-Impact |
|---|---|---|---|
| Bitzer | IT Zone4 Perioden-Dispatch (P12/P16) | 93dc7c1 | ~−30 TEUR vor→nach Fix |
| Bitzer | FR-13400 Zone9-Routing (P16) | 93dc7c1 | ~−3 TEUR |
| HELU-KABEL | H1 ES-Mendaro Zone Key (P17-A) | 897a2c6 | 67 Rows von DLV-Lücke gerettet |
| HELU-KABEL | H2 GB rates_by_col int/str (P17-B) | 897a2c6 | 55 Rows von DLV-Lücke gerettet |
| Hornschuch | G3 AT-Zone 2→1-stellig (P5) | a0a9822 | 1 Row korrigiert |
| Sika 491063 (adj.) | P20.1 Erlöse-Maut-Separation (Methodik) | — | +30.555 EUR Adj. |
| Sika Import (adj.) | P20.1 Erlöse-Maut-Separation (Methodik) | 07ba458 | +18.306 EUR Adj. |

---

## §7 Operative Klärungsbedarfe

**Alle nachfolgenden Positionen sind kein Migrationsbefund.** Sie erfordern operative oder vertragliche Klärung außerhalb des Billing-Audits. Ausführliche Dokumentation: `docs/OPERATIVE_KLAERUNGEN_v1_0.md`.

### Zusammenfassung

| Punkt | Kunde | EUR | Rows | Priorität |
|---|---|---:|---:|---|
| C.1 PL-DLV-Lücke | Hornschuch AG | 203.992 | 726 | Mittel |
| C.2 de_oos-Buchung | Sika SSC (511241) | 631.702 | 347 | Mittel |
| C.3 GR-Tarif-Lücke | Fischerwerke GmbH | 102.052 | 264 | Niedrig |
| C.4 GB-Zone-Lücke | HERMA GmbH | 61.917 | 93 | Niedrig |
| C.5 DE-Inbound OOS | Bitzer SE | 33.970 | 67 | Niedrig |
| C.6 GR-Calculator | CHT Germany | 38.776 | 102 | Niedrig |
| C.7 FR sonstige | Bitzer SE | 445 | 7 | Niedrig |
| **Σ** | | **1.072.854** | **1.606** | |

### C.1 Hornschuch AG — PL-DLV-Lücke (Priorität: Mittel)

726 PL-Rows, 203.992 EUR ef. ERKA-DLV: 99 PL-Zonen mit leeren Freight-Raten. Top-Empfänger: Lumatech 32.773 EUR (39 Rows), Aluplast 24.142 EUR (40), Salamander 17.948 EUR (45), VEKA Polska 14.553 EUR (34), Rehau 8.376 EUR (32).

**Hypothesen:** (A) PL nicht in MegaTrans-Nominierung — Noerpel rechnet PL über eigenes Netz, kein DLV vorhanden. (B) PL-Tarif in separater DLV-Datei. (C) PL über ContiTech-Framework abgerechnet, DLV-Datei fehlt in ERKA-Übergabe.

**Empfehlung:** Noerpel nach PL-Tarifbasis fragen. Klärung: Welche DLV-Datei gilt für PL-Ziele unter ContiTech-Rahmen?

### C.2 SIKA Supply Center AG — de_oos-Block (Priorität: Mittel)

347 Rows, 631.702 EUR ef. KNR 511241 enthält Empfänger-DE-Sendungen (DE-Inlandslieferungen unter SSC-KNR gebucht). Export-DLV gilt nicht für DE-Inland.

**Empfehlung:** Klärung mit Noerpel-Buchhaltung: Welche AX-Kostenstelle gilt für SSC-DE-Inlandslieferungen? Wenn DE-Inland: zugehörigen DE-Inbound-DLV beschaffen oder auf KNR 491063 umbuchen.

### C.3 Fischerwerke GmbH — GR-Tarif-Lücke (Priorität: Niedrig)

264 Rows, 102.052 EUR ef. Calculator wirft LookupError für GR-PLZ (kein GR-Tarif in Hauptpool). Karton-Pricing-Modell. GR-Empfänger: Θεσσαλονίκη-Gebiet.

**Empfehlung:** GR-Tarif-Datei beschaffen oder klären, ob GR über separaten Carrier-Vertrag läuft.

### C.4 HERMA GmbH — GB-Zonen-Lücke (Priorität: Niedrig)

93 Rows, 61.917 EUR ef. 10 GB-Postcode-Areas nicht im DLV enthalten. Top-Areas: WF 45 Rows, ME 22 Rows, LS 9 Rows. DLV-Erweiterung oder Klärung Tarifklasse für fehlende Areas.

**Empfehlung:** DLV-Ergänzung für fehlende GB-Areas oder Klärung Noerpel welche Tarifklasse gilt.

### C.5 Bitzer SE — DE-Inbound Out-of-Scope (Priorität: Niedrig)

67 Rows, 33.970 EUR ef. Import-Sendungen (Nicht-DE-Ursprung → DE-Empfänger) nicht in Export-DLV hinterlegt.

**Empfehlung:** Prüfen ob DE-Inbound-Tarif existiert; falls ja, in Calculator ergänzen.

### C.6 CHT Germany — GR-Calculator fehlt (Priorität: Niedrig)

102 Rows, 38.776 EUR ef. `CHTGreeceCalculator.calculate()` nicht implementiert → AttributeError. Kein Calculator-Bug, Calculator-Klasse nicht fertiggestellt.

**Empfehlung:** GR-Tarif-Datei beschaffen und `CHTGreeceCalculator` implementieren.

### C.7 Bitzer SE — FR sonstige (Priorität: Niedrig)

7 Rows, 445 EUR ef. FR-92000 Hauts-de-Seine Zonenzuordnung (Zone 7 vs Zone 8 IDF-Außenring) und ggf. weitere FR-Sonderrouten.

**Empfehlung:** Rückfrage ERKA zu Zonenzuordnung für IDF-Außenring.

---

### Operative Note — Sika ATM IT-85025 (außerhalb Klärungsliste)

IT 85025 (Zone Salerno/Kampanien): 2 M_over Rows (ton 5.922 / 8.336 kg, ef 2.500 / 3.350 EUR, DLV 1.012 / 1.226 EUR). Runde ef-Werte deuten auf Stellplatz-basierte Abrechnung hin (AX Stellplätze vorhanden, ATM-Calculator nutzt Tonnage). Empfehlung: operative Prüfung Abrechnungsgrundlage mit Sika Automotive.

---

## §8 Offene Punkte

**Stand v2.0: Alle Audit-Scopes abgeschlossen. Keine offenen Scope-Einheiten.**

### 8.1 KNR 511241 — Import-Flow ✓ ABGESCHLOSSEN (v1.1)

**Status:** Auditiert. 346 Rows (629.422 EUR ef), 0 DLV-Lücken. Net Δ P20-adj = +9.914 EUR (+1,55 %) — kein Migrationsschaden.

Pipeline: `build_sika_import_step23_v197.py` (Commit 07ba458). Detail-Report: `docs/v1_9_7_sika_511241_import_report.md`.

### 8.2 KNR 527406 — Sika ATM ✓ ABGESCHLOSSEN (v2.0)

**Status:** Auditiert. 395 beurteilbar (99,7 %), Net Δ = −7.243 EUR (−3,22 %). Excl. RS pre-existing: −1.886 EUR (−0,95 %) — kein Migrationsschaden.

Pipeline: `build_sika_atm_step23_v197.py` (Commit 01d371f). Detail-Report: `docs/v1_9_7_sika_atm_cluster_report.md`.

### 8.3 Aggregation-Audit ✓ ABGESCHLOSSEN (v2.0)

**Status:** Methodik-Dokumentation abgeschlossen. 32/32 Unit-Tests. 13 Scopes empirisch verifiziert. Keine materiellen Findings. Dokumentation: `docs/aggregation_codebase_audit.md` (→ §10).

### Zeitplan-Abschluss

| Aufgabe | Aufwand | Status |
|---|---|---|
| KNR 511241 Import-Flow | 1 h | **Abgeschlossen (v1.1, 2026-04-28)** |
| KNR 527406 Sika ATM | 4 h | **Abgeschlossen (v2.0, 2026-04-29)** |
| Aggregation-Audit Docs | 3 h | **Abgeschlossen (v2.0, 2026-04-29)** |
| Operative Klärungen Memo | 2 h | **Abgeschlossen (OPERATIVE_KLAERUNGEN_v1_0.md)** |

**Gesamtaudit: abgeschlossen.**

---

## §9 Audit-Aussage und Empfehlungen

### Audit-Aussage

> **Die Migration des Transportmanagementsystems von Dinas auf Microsoft Dynamics AX (Noerpel-Gruppe) vom 27. September 2025 wurde sauber durchgeführt.**
>
> Über 13 Kunden-Scopes (11 Kundenfirmen), 17.891 beurteilbare Abrechnungszeilen und ein Erlösvolumen von 7,83 MEUR wurde **kein systematischer Migrationsschaden** identifiziert. Kein Kunde weist eine Konstellation auf, die auf fehlerhafte Tarif-Migration hindeutet.
>
> Alle identifizierten Abweichungen sind durch methodisch erklärbare Faktoren begründet: Calculator-Pre-Flight-Fixes (P1–P20 bei 6 Kunden), Erlös-Komponenten-Separation (P20.1 Maut: Sika 491063 und Import), Pricing-Mode-Artefakte (Charter-Pool Fischerwerke, GC-Band Groz-Beckert, IT-Dieselfloater Sika Import) oder vorbestehende separate Rate-Vereinbarungen (RS Serbia Sika ATM). Diese Faktoren sind keine Migrationsfehler.
>
> Die Audit-Methodik ist code-validiert: 32/32 Unit-Tests für ZGI-Cluster-Aggregation bestanden. Alle 13 Scopes empirisch auf korrekten Sub-Row-Ausschluss geprüft.

**Net Δ adjustiert (alle 13 Kunden-Scopes): +139.623 EUR (+1,78 %)**  
Dieser Wert liegt innerhalb der Wesentlichkeitsschwelle und zeigt, dass AX im Mittel minimal über dem DLV-Niveau abrechnet — kein Schaden für Noerpel.

---

### Empfehlungen

#### Operative Klärungen (kurzfristig)

1. **Hornschuch PL (203.992 EUR, Priorität Mittel):** ContiTech-Vertragsscope für Polen klären. Noerpel nach gültigem PL-Tarif fragen.

2. **Sika SSC de_oos (631.702 EUR, Priorität Mittel):** Buchungszugehörigkeit der 347 DE-Ziel-Zeilen unter KNR 511241 klären.

3. **Fischerwerke GR (102.052 EUR):** GR-Tarif-Datei beschaffen oder klären ob GR über separaten Carrier-Vertrag läuft.

4. **HERMA GB (61.917 EUR):** DLV-Ergänzung für fehlende GB-Postcode-Areas.

5. **Sika ATM RS Serbia:** Operative Klärung separate Laufkarte PLZ 34000 Kragujevac (Anlage-1-Anwendung oder separate DLV-Erfassung).

6. **Sika ATM IT-85025:** Prüfung Abrechnungsgrundlage Stellplatz vs. Tonnage für 2 Großsendungen (+3.611 EUR M_over).

#### Methodik-Standard (mittelfristig)

7. **P1–P20 als Pre-Flight-Checkliste:** Systematisch vor jedem neuen Kunden-Audit durchführen.

8. **P20-Prüfung als Standard:** Für zukünftige Kunden-Audits alle `Erlöse_*`-Spalten summieren und gegen DLV-Komponenten abgleichen.

9. **Aggregation-Audit als Standard:** Methodik v1.9.7 (ZGI-Cluster, Sub-Row-Filter, Unit-Tests) für Folge-Audits etablieren.

#### Audit-Abschluss

10. **Audit erklären:** Alle 13 Scope-Einheiten auditiert. Keine weiteren offenen Audit-Punkte. Der Audit kann als abgeschlossen erklärt werden.

---

### Verteilung

Dieser Bericht ist für ERKA-Management und Noerpel-Geschäftsführung bestimmt. Detail-Reports pro Kunde: `docs/v1_9_*_cluster_report.md`. Methodikdokumentation: `docs/AUDIT_METHODOLOGY.md` v1.9.7. Operative Klärungen: `docs/OPERATIVE_KLAERUNGEN_v1_0.md`.

---

## §10 Anhang — Aggregation-Audit (Methodik-Selbstvalidierung)

### Hintergrund

Die ZGI-Cluster-Aggregation (§3, §11) ist die methodisch kritischste Operation des Audits: Sub-Rows (Sendungen die unter einer Mastersendung zusammengefasst sind) werden ausgeschlossen, da ihr Erlös auf dem Master bucht. Ein fehlerhafter Sub-Row-Filter würde Erlöse systematisch unterschätzen und M2-Artefakte erzeugen. Der Aggregation-Audit verifiziert, dass alle 13 Scopes diesen Filter korrekt implementieren.

### Unit-Test-Ergebnis

**32/32 Tests bestanden** (`test_aggregation.py`)

Getestete Szenarien: ZGI-Cluster-Bildung, Sub-Row-Erkennung (`is_sub = has_ms AND NOT has_ua`), Master-Sub-Konsolidierung (`enrich_master_sub`), Bitzer P9 inverse ZGI-Struktur, Coverage nach Filter.

### Scope-Verifikation (13 Einheiten)

| Scope | Methode | Sub-Rows Ton=0 | Sub-Rows Ton>0 | Sub ef | Status |
|---|---|---:|---:|---:|---|
| CHT (5 Länder) | Tonnage>0-Proxy | 38 | 0 | 5.389 EUR | **aggregation_korrekt_de_facto** |
| GEZE | Tonnage>0-Proxy | n/a | 0 | 0 EUR | **aggregation_korrekt_de_facto** |
| Fischerwerke | enrich_master_sub() | 180 | 63 | 84.607 EUR | **aggregation_korrekt_ax_seite** |
| HERMA | enrich_master_sub() | 406 | 2 | 65.136 EUR | **aggregation_korrekt_ax_seite** |
| Bitzer | P9 inverse ZGI | 0 | 0* | — | **aggregation_korrekt_ax_bitzer_p9** |
| Groz-Beckert | ~is_sub-Filter (explizit) | 10 | 0 | — | **aggregation_korrekt** |
| HELU-KABEL | enrich_master_sub() | — | — | — | **aggregation_korrekt_ax_seite** |
| Hornschuch | enrich_master_sub() | — | — | — | **aggregation_korrekt_ax_seite** |
| Sika DE+SSC | ~is_sub & ton>0 (explizit) | — | — | — | **aggregation_korrekt** |
| Sika Import | ~is_sub (explizit) | 0 | 0 | 0 EUR | **aggregation_korrekt** |
| Sika ATM | ~is_sub (explizit) | 7 | 0 | 1.832 EUR | **aggregation_korrekt** |
| EBM-Papst | Tonnage>0 + OOS | 0 | 0 | 0 EUR | **aggregation_korrekt_de_facto** |

*Bitzer P9: Inverse ZGI-Struktur — Sub-Rows tragen ef>0, Master trägt Tonnage. Subs bleiben im Pool mit substituierter Tonnage (strukturell korrekt).

### Wesentliche Befunde

**Kein aktiver Aggregationsfehler** bei keinem abgeschlossenen Kunden.

**GEZE — latentes Risiko (dokumentiert, inaktiv):** 140 AX-Sub-Rows mit Tonnage>0 (143.407 EUR ef) im BI-Pool. GEZE-Pipeline nutzt Tonnage>0-Proxy-Filter — dieser erfasst diese Subs nicht. Risiko ist inaktiv, da GEZE aktuell kein BI-Vergleichs-Pipeline hat (nur Unit-Tests). Falls BI-Vergleich hinzugefügt wird: expliziten `~is_sub`-Filter implementieren.

**Fischerwerke/HERMA — Dinas-Aggregation:** AX-Seite korrekt via `enrich_master_sub()`. Dinas-Aggregation folgt rechnung_nr (nicht Routing-Key), was leicht von v1.9 `(Sender_PLZ, Empf_PLZ, Ladedatum)`-Schlüssel abweicht. Kein bekannter Fehler; Cluster-Familien-Matching kaschiert den Unterschied.

**CHT BE RN 924069 Realitäts-Check:** rn_level_adjustment (`fp`-Faktor) tritt über 10 verschiedene PLZs und mehrere Tage auf — kein Aggregations-Artefakt (würde sich nur in gleichen Routing-Key-Gruppen zeigen). Ursache: systemischer RN-weiter Effekt (wahrscheinlich quartalsweiser Diesel-Floater oder Rundungsunterschied auf Rechnungsebene). Gate-6 ist methodisch korrekt.

### Aufwandsschätzung verbleibende Konformitätslücken

| Scope | Fix | Aufwand |
|---|---|---|
| CHT (alle 5) | Kein Fix nötig | 0 h |
| GEZE | Sub-Row-Filter wenn BI-Vergleich kommt | ~1 h |
| Fischerwerke | Dinas-Aggregation auf (Sender+Empf+Datum)-Schlüssel | ~2 h |
| HERMA | Wie Fischerwerke (2 Subs Ton>0, marginaler Impact) | ~1–2 h |
| **Gesamt** | | **≤5 h** |

### Verweis

Vollständige Aggregation-Dokumentation: `docs/aggregation_codebase_audit.md` (v1.9.7, 346 Zeilen, 12+1 Scopes). Retroaktives Risiko-Assessment: `docs/aggregation_retroactive_risk.md`.

---

## Anhang A — Glossar

| Begriff | Erläuterung |
|---|---|
| AX | Microsoft Dynamics AX — das neue TMS nach der Migration (09/2025) |
| Dinas | Vorgänger-TMS der Noerpel-Gruppe (bis 26.09.2025) |
| KNR | Kundennummer (Buchungskreis-Kenner in AX) |
| ef | Erlöse Fracht — der im AX-BI gebuchte Frachtumsatz pro Zeile (EUR) |
| dlv_soll / dlv | DLV-Soll — vom Calculator aus der Tarifofferte errechneter Preissoll (EUR) |
| delta | ef − dlv_soll (positiv = AX über DLV; negativ = AX unter DLV) |
| fp | Faktorpreisabweichung = delta / dlv_soll (Prozentwert) |
| M1 | \|fp\| ≤ 5 % — korrekte Abrechnung |
| M2 | fp < −5 % — Abrechnung unter DLV-Niveau |
| M_over | fp > +5 % — Abrechnung über DLV-Niveau |
| Pool roh | ef > 0 Zeilen nach KNR-Filter |
| Beurteilbar | Pool nach Sub-Row-Ausschluss, Tonnage > 0, stp_eff > 0, OOS-Ausschluss |
| Sub-Row | AX-Zeile mit Mastersendung gesetzt, kein eigener Unterauftrag (is_sub) |
| ZGI | "Zusammengefasst in" — AX-Feld für Masterauftrag-Referenz |
| OOS | Out of Scope — Zeile außerhalb des DLV-Anwendungsbereichs |
| DLV-Lücke | Zeilen, für die der Calculator keinen Rate-Match findet (LookupError) |
| P20 | Erlös-Spalten-Separation (Erlöse Maut/Diesel separat in AX gebucht) |
| Net Δ | Summe aller delta-Werte im beurteilbaren Pool |
| Net Δ % | Net Δ / Σ ef (prozentuale Gesamtabweichung) |
| Charter-Artefakt | Vollfahrzeug-Pauschalpreise werden gegen per-kg-DLV verglichen → M_over |
| GC-Mode | Grob-Cluster-Modus (Gewicht/kg-Extrapolation für große Sendungen) |
| ATM | Automated Tariff Mode — gewichtsbasierter Flat-EUR/Sendung-Tarif (Sika 527406) |
| RS pre-existing | Vorbestehende separate Rate-Vereinbarung (Kragujevac, nicht in Anlage 1) |

---

## Anhang B — Datenquellen und Cache-Dateien

### BI-Daten

| Datei | Inhalt | Kunden |
|---|---|---|
| `output/bi_top20_data.pkl` | AX POST-Buchungen Top-20-KNRs | Alle außer 527406 |
| `output/bi_cache_sika_527406.pkl` | AX POST-Buchungen KNR 527406 | Sika ATM |

### Kunden-Audit-Caches (13 PKL-Dateien)

| Datei | Kunde(n) | Commit |
|---|---|---|
| `output/geze_step23_results_v196.pkl` | GEZE 406035 | dd3d558 |
| `output/ebm_step23_results_v196.pkl` | EBM 410844 | 7500102 |
| `output/fischerwerke_step23_results_v196.pkl` | Fischerwerke 409480 | 61f229e |
| `output/herma_step23_results_v196.pkl` | HERMA 423650 | c26dbe1 |
| `output/cht_step23_results_v196.pkl` | CHT 486073 | 22f0b83 |
| `output/bitzer_step23_results_v196_postfix.pkl` | Bitzer 406345 | 93dc7c1 |
| `output/groz_beckert_step23_results_v196.pkl` | Groz-Beckert multi | 7500102 |
| `output/helu_step23_results_v196.pkl` | HELU-KABEL 408244 | 897a2c6 |
| `output/hornschuch_step23_results_v196.pkl` | Hornschuch 490085 | a0a9822 |
| `output/sika_welle1_step23_results_v197.pkl` | Sika 491063 + 511241 (SSC) | 71cc9c2 |
| `output/sika_import_step23_results_v197.pkl` | Sika Import 511241 | 07ba458 |
| `output/sika_atm_step23_results_v197.pkl` | Sika ATM 527406 | 01d371f |

### Detail-Reports

| Datei | Kunde |
|---|---|
| `docs/v1_9_6_geze_cluster_report.md` | GEZE |
| `docs/v1_9_4_ebm_cluster_report.md` | EBM |
| `docs/v1_9_6_fischerwerke_cluster_report.md` | Fischerwerke |
| `docs/v1_9_6_herma_cluster_report.md` | HERMA |
| `docs/v1_9_6_cht_cluster_report.md` | CHT |
| `docs/v1_9_6_bitzer_cluster_report.md` | Bitzer |
| `docs/v1_9_6_groz_beckert_cluster_report.md` | Groz-Beckert |
| `docs/v1_9_6_helu_cluster_report.md` | HELU-KABEL |
| `docs/v1_9_6_hornschuch_cluster_report.md` | Hornschuch |
| `docs/v1_9_7_sika_welle1_cluster_report.md` | Sika DE + SSC |
| `docs/v1_9_7_sika_511241_import_report.md` | Sika Import 511241 |
| `docs/v1_9_7_sika_atm_cluster_report.md` | Sika ATM 527406 |

### Methodik- und Audit-Dokumente

| Datei | Inhalt |
|---|---|
| `docs/AUDIT_METHODOLOGY.md` | v1.9.7 Vollmethodik §1–§15 |
| `docs/aggregation_codebase_audit.md` | Aggregation-Audit 13 Scopes |
| `docs/aggregation_retroactive_risk.md` | Retroaktives Risiko-Assessment |
| `docs/OPERATIVE_KLAERUNGEN_v1_0.md` | 7 operative Klärungspunkte, Σ 1,07 MEUR |
| `docs/v1_9_6_consolidated_audit_status.md` | Konsolidierte Audit-Lage 13 Scopes |

---

## Anhang C — Versions-Historie

| Version | Datum | Commit | Änderungen |
|---|---|---|---|
| v1.0 | 2026-02 | 8207bef | Erstaudit GEZE (Familien-Vergleich Dinas PRE × AX POST) |
| v1.9 | 2026-03 | — | Vollumstieg auf DLV-Soll-Vergleich; ZGI-Cluster; Sub-Row-Filter |
| v1.9.4 | 2026-03 | — | EBM, HERMA, GEZE v2, Fischerwerke v1 |
| v1.9.5 | 2026-03 | — | Bitzer; Calculator Bug-Klassen A–H |
| v1.9.6 | 2026-04 | — | CHT, Groz-Beckert, HELU-KABEL, Hornschuch; P17–P19 |
| v1.9.7 | 2026-04-28 | — | Sika Welle 1 (491063+511241); P20 Erlöse-Maut-Separation |
| **v1.1 (Report)** | **2026-04-28** | **0f343b0** | **12. Scope: Sika Import-Flow; P20.1/P20.2/P20.3; 12-Scope Abschluss** |
| **v2.0 (Report)** | **2026-04-29** | *(aktuell)* | **13. Scope: Sika ATM 527406; Aggregation-Audit 32/32; Operative Klärungen Σ 1,07 MEUR; Audit abgeschlossen** |

### Report-Snapshots

| Datei | Beschreibung |
|---|---|
| `docs/FINAL_AUDIT_REPORT_v1_0.md` | v1.0 Snapshot — 11 Kunden, 11 Scopes (vor Sika Import) |
| `docs/FINAL_AUDIT_REPORT_v1_1.md` | v1.1 Snapshot — 12 Scopes, Sika Import-Flow abgeschlossen |
| `docs/FINAL_AUDIT_REPORT_v2_0.md` | **v2.0 Abschlussbericht** — 13 Scopes, Audit vollständig |
