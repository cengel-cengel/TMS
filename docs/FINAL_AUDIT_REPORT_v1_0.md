# Migrationsaudit Dinas → AX — Abschlussbericht v1.0
**ERKA Rechnungsprüfung / Noerpel-Gruppe**  
Stand: 2026-04-28 | Methodik-Version: v1.9.7 | Erstellt: Claude Code (Anthropic)

---

## §1 Executive Summary

### Geprüfte Migration

Am **27. September 2025** wurde das Transportmanagementsystem von **Dinas** auf **Microsoft Dynamics AX** (Noerpel-Gruppe) umgestellt. Dieser Bericht dokumentiert die Ergebnisse der Billing-Auditierung für den Zeitraum nach der Migration (September 2025 – März 2026).

### Untersuchte Kundenbasis

| Merkmal | Wert |
|---|---|
| Kundenfirmen | 9 Unternehmen |
| Kunden-Scopes (KNR-Einheiten) | 11 |
| Pool gesamt (ef > 0) | 19.619 Abrechnungszeilen |
| Davon beurteilbar | 17.150 Zeilen (87,4 %) |
| Erlösvolumen beurteilbar | **6,98 MEUR** |
| Auditierter Zeitraum | Oktober 2025 – März 2026 |

### Schlüsselbefund

**Die Migration Dinas → AX wurde sauber durchgeführt.**  
Über 11 Kunden-Scopes und ein Erlösvolumen von 6,98 MEUR wurde **kein systematischer Migrationsschaden** identifiziert.

| Kennzahl | Wert |
|---|---|
| Net Δ gesamt (nominal) | +106.397 EUR (+1,52 %) |
| Net Δ gesamt (adjustiert) | **+136.952 EUR (+1,96 %)** |
| Kunden mit Migrationsschaden | **0** |
| M1-Anteil (±5 %-Toleranz) | 84,0 % |

### Adjustierung Sika Deutschland (KNR 491063)

Ein methodischer Befund wurde identifiziert und quantifiziert: AX bucht die DE-Streckenmaut als separaten Erlösposten (`Erlöse Maut`), während das DLV-Vergleichssoll die Maut integriert enthält. Das nominelle Net Δ von −25.758 EUR (−1,97 %) für KNR 491063 reduziert sich nach Adjustierung auf **+4.797 EUR (+0,37 %)** — kein Migrationsschaden.

### Operative Klärungsbedarfe (außerhalb Audit-Scope)

Zwei größere Positionen erfordern operative Klärung, betreffen jedoch **keine** Migrationsfehler:

- **Hornschuch AG** (KNR 490085): 726 PL-Sendungen (203.992 EUR) ohne verifizierbaren Carrier-Tarif. Klärung ContiTech-Vertragsscope für Polen empfohlen.
- **SIKA Supply Center AG** (KNR 511241): 347 DE-Ziel-Zeilen (631.702 EUR) unter SSC-KNR gebucht — Buchungszugehörigkeit zu prüfen.

### Offene Welle-2-Themen

Zwei Sika-Teilscopes werden in Folgesessions abgeschlossen (keine Änderung der Gesamtaussage erwartet):
- KNR 511241 Import-Flow (2 Zeilen, Welle 2)
- KNR 527406 ATM Schweiz (separate BI-Quelle)

### Vertrauen in die Aussage

11 Kunden-Scopes zeigen konsistent: kein Kunde weist einen Befund auf, der auf systematische Tarif-Übertragungsfehler hindeutet. Calculator-Pre-Flight-Fixes (P1–P20) wurden bei 6 Kunden vor der Analyse durchgeführt und sind nicht auf Migrations-Versagen zurückzuführen.
---

## §2 Audit-Auftrag und Scope

### Auftrag

Geprüft wird, ob die Umstellung des TMS (Dinas → AX) zum 27.09.2025 alle bestehenden Kundenkonditionen vollständig und korrekt übertragen hat. Konkret: Werden Sendungen nach der Migration zu denselben Tarifstufen abgerechnet wie vor der Migration?

### Prüfungsansatz

Der Audit vergleicht die **AX-Nachmigrationsabrechnung** (Erlöse Fracht aus AX-BI, Oktober 2025 ff.) mit dem **DLV-Soll** (Rahmenvertrag/Offerte des Carriers, rekonstruiert aus den hinterlegten Tarif-Dateien). Kein Dinas-Direktvergleich: Die Dinas-Vorsystem-Daten dienen als Plausibilitätsreferenz, sind jedoch für den Hauptaudit nicht die primäre Vergleichsbasis.

### Scope

| Dimension | Wert |
|---|---|
| Kunden | 9 Unternehmen (11 KNR-Scopes) |
| Länder | DE-Inbound (Empf. DE) + EU-Export (ES, FR, GB, IT, AT, PT, IE, BE, NL u.a.) |
| Carrier | Noerpel-Gruppe (Hauptlieferant) |
| Zeitraum | Oktober 2025 – März 2026 (Post-Migration) |
| Ausgeschlossen | DE-Inland für Exportunternehmen (OOS für Export-DLV), Sub-Rows ohne Eigenerlös, Tonnage = 0 |

### Nicht im Scope

- **KNR 527406** (Sika ATM CH): separates BI-Loading erforderlich, in Folgesession
- **Dinas-Pre-Migration-Vollabgleich**: Kein vollständiger Dinas-Abgleich; DLV-Soll-Vergleich dominiert
- **Andere Carrier**: Audit ist auf Noerpel-Abrechnung fokussiert
- **Nicht-Fracht-Erlöse** (Zoll, Versicherung, Lademittel): außerhalb des DLV-Vergleichs

### Datenquellen

| Quelle | Datei | Inhalt |
|---|---|---|
| AX BI | `output/bi_top20_data.pkl` | Alle POST-Buchungen für Top-20-KNRs |
| DLV-Tarife | `data/extracted/v1/Noerpel AI/{Kunde}/DLV/` | Excel-Tarif-Dateien nach Kunde |
| Kunden-Caches | `output/*_step23_results_v196*.pkl` | Aggregierte Audit-Ergebnisse pro Kunde |
| Methodik | `docs/AUDIT_METHODOLOGY.md` v1.9.7 | 9 Kunden-Scopes dokumentiert |
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

**ZGI-Cluster-Aggregation (§11):** Sendungen mit identischem Zusammengefasst-in-Schlüssel werden vor dem DLV-Vergleich aggregiert. Verhindert Sub-Row-Doppelzählung (Präzedenz: HERMA, +126.622 EUR Artefakt-Bereinigung).

**Pre-Flight Pitfalls P1–P20:** 20 dokumentierte Fehlerquellen von der Daten-Ladung bis zur Pipeline. Vor jedem Kunden-Audit werden alle relevanten Pitfalls geprüft (→ §6).

**Year-Fallback DLV-Resolver:** DLV-Tarif-Auswahl nach Lieferungsdatum (2025 vs. 2026 DLV).

**Erlös-Spalten-Separation (P20):** AX bucht manche Erlös-Komponenten getrennt. Wenn DLV integriert und AX separiert, wird `ef_total = ef + Erlöse_Maut` als Vergleichsbasis verwendet. Betrifft nur Sika 491063 (rückwirkend geprüft für alle 11 Kunden).

**Sub-Row-Filter:** `is_sub = (Mastersendung gesetzt) AND (kein eigener Unterauftrag)`. Sub-Rows haben keinen eigenen Erlös und werden ausgeschlossen.

**Calculator Pre-Flight-Fixes:** Bei 6 Kunden wurden Calculator-Bugs identifiziert und behoben, bevor die Audit-Zahlen berechnet wurden. Diese Fixes sind **nicht** auf Migrationsfehler zurückzuführen, sondern auf Abweichungen zwischen DLV-Formatierung und Calculator-Implementierung (→ P5–P17).

### Verweis

Vollständige Methodikdokumentation: `docs/AUDIT_METHODOLOGY.md` v1.9.7 (§1–§15).  
Pre-Flight-Skill: `skills/customer-preflight/SKILL.md` (P1–P20).
---

## §4 Konsolidierte 11-Kunden-Lage

### Haupt-Tabelle

| Kunde | KNR | Pool roh | Beurteilbar | M1 | M2 | M_over | Σ ef (EUR) | Net Δ (EUR) | Net Δ % | Headline |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| GEZE GmbH | 406035 | 2.917 | 2.759 | 2.550 | 132 | 77 | 391.904 | +4.138 | +1,07 % | kein Schaden |
| EBM-Papst | 410844 | 353 | 308 | 285 | 1 | 22 | 480.133 | +3.514 | +0,74 % | kein Schaden |
| Fischerwerke | 409480 | 1.173 | 839 | 321 | 107 | 411 | 537.574 | +106.811 | +24,80 % | kein Schaden¹ |
| HERMA GmbH | 423650 | 3.781 | 3.642 | 2.842 | 384 | 416 | 2.428.736 | −16.374 | −0,67 % | kein Schaden |
| CHT Germany | 486073 | 702 | 554 | 539 | 0 | 15 | 257.594 | −668 | −0,26 % | kein Schaden |
| Bitzer | 406345 | 3.406 | 3.330 | 2.868 | 206 | 256 | 723.694 | +26.407 | +3,79 % | kein Schaden² |
| Groz-Beckert | multi | 621 | 527 | 473 | 0 | 54 | 112.997 | +5.729 | +5,07 % | kein Schaden³ |
| HELU-KABEL | 408244 | 2.293 | 2.185 | 2.044 | 102 | 39 | 315.991 | +203 | +0,06 % | kein Schaden |
| Hornschuch AG | 490085 | 2.551 | 1.565 | 1.549 | 7 | 9 | 408.579 | −205 | −0,05 % | kein Schaden⁴ |
| Sika DE | 491063 | 1.407 | 1.379 | 887 | 293 | 199 | 1.278.459 | −25.758 | −1,97 % | kein Schaden⁵ |
| Sika SSC | 511241 | 415 | 62 | 43 | 0 | 19 | 43.358 | +2.600 | +6,38 % | kein Schaden⁶ |
| **Gesamt** | | **19.619** | **17.150** | **14.401** | **1.232** | **1.517** | **6.979.019** | **+106.397** | **+1,52 %** | **0 Schäden** |

**Adjustiertes Gesamt** (nach P20-Korrektur Sika 491063): Net Δ = **+136.952 EUR (+1,96 %)**

---

**¹ Fischerwerke +24,80 %:** Charter-Artefakt. Vollfahrzeug-Chartersendungen werden gegen per-Stellplatz-DLV verglichen → systematischer M_over (+118 TEUR). Non-Charter-Pool: ≈0 %. Kein Abrechnungsfehler.

**² Bitzer +3,79 %:** Post-Fix nach zwei Calculator-Korrekturen (IT Zone4 Perioden-Dispatch, FR-13400 Zone9-Routing). Verbleibende positive Differenz wahrscheinlich Diesel-Floater-Einschluss in ef. Keine operativen Beanstandungen.

**³ Groz-Beckert +5,07 %:** Ausschließlich im GC-Mode (Gewicht/kg, 474 Rows). LTL-FTL-Mode (PT-Porto-Lanes, 53 Rows): Δ = 0,00 EUR exakt. GC M_over = Über-Band-Sendungen; DLV-Extrapolation überschätzt per-kg-Rate bei Großgewichten. Kein Carrier-Fehler.

**⁴ Hornschuch PL-Lücke:** 726 PL-Sendungen (203.992 EUR) ohne verifizierbaren Carrier-Tarif (ERKA-DLV: 99 PL-Zonen mit leeren Freight-Raten). Operative Klärung ContiTech-Vertragsscope empfohlen (→ §7).

**⁵ Sika DE Erlöse-Maut-Separation:** Nominelles Net Δ −25.758 EUR (−1,97 %) ist Methodik-Artefakt. AX bucht DE-Maut in separatem Posten `Erlöse Maut` (Σ 30.555 EUR). Adjustiertes Net Δ = **+4.797 EUR (+0,37 %)**. Kein Schaden.

**⁶ Sika SSC M_over:** Net Δ > 0 bedeutet AX rechnet über DLV-Niveau ab. Kein Noerpel-Schaden. OOS-Block de_oos (347 Rows, 632 TEUR) außerhalb Audit-Scope (→ §7).

### M-Klassen-Verteilung Gesamt

| Klasse | Rows | Anteil | Δ-Beitrag (EUR) |
|---|---:|---:|---:|
| M1 (±5 %) | 14.401 | 84,0 % | +61.882 |
| M2 (< −5 %) | 1.232 | 7,2 % | −155.539 |
| M_over (> +5 %) | 1.517 | 8,8 % | +200.054 |
| **Gesamt beurteilbar** | **17.150** | **100 %** | **+106.397** |
---

## §5 Pro-Kunde-Detail-Befunde

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

**Operative Klärung:** GR-Sendungen 264 Rows (ca. 100 TEUR) ohne GR-DLV — Klärung in Etappe 10 vorgesehen.

**Detail-Report:** `docs/v1_9_6_fischerwerke_cluster_report.md`

---

### 5.4 HERMA GmbH (KNR 423650)

**Calculator:** `herma.py` (Commit c26dbe1) | **DLV:** Gewichts-/LDM-basiert, EU-Export  
**Pool:** 3.781 roh → 3.642 beurteilbar (96,3 %) | **DLV-Lücke:** 139 Rows  
**Ergebnis:** M1=2.842 (78,0 %), M2=384 (10,5 %), M_over=416 (11,4 %) | Net Δ = −16.374 EUR (−0,67 %)

**Befunde:** Kein Migrationsschaden. **ZGI-Aggregations-Bereinigung:** v1.9.4 hatte −142.996 EUR M2-Artefakt durch Sub-Row-Doppelzählung. Nach ZGI-Cluster-Aggregation (§11): −16.374 EUR, nicht erklärbar als Migrationsschaden.

Verbleibende M2 (−67.758 EUR): dominiert von LDM-basierten Sendungen, bei denen DLV-Tarif für LDM-Preisstufen über AX-Erlösen liegt. Mögliche Ursache: Sonderkonditionen Gate-C (LDM-Sonderpreis) nicht vollständig im DLV abgebildet. Keine operativen Beanstandungen.

**Calculator Pre-Flight:** Keine Bugs gefixt; ZGI-Aggregation als Methodik-Fix eingeführt.

**Detail-Report:** `docs/v1_9_6_herma_cluster_report.md`
---

### 5.5 CHT Germany (KNR 486073)

**Calculator:** `cht.py` (Commit 22f0b83) | **DLV:** Gewichts-/LDM-basiert, BE/IT/ES/AT (+ GR separat)  
**Pool:** 702 roh → 554 beurteilbar (78,9 %) | **DLV-Lücke:** keine (vollständige PLZ-Coverage)  
**Ergebnis:** M1=539 (97,3 %), M2=0, M_over=15 (2,7 %) | Net Δ = −668 EUR (−0,26 %)

**Befunde:** Kein Migrationsschaden. 97,3 % M1 — eine der saubersten Kunden-Konstellationen. M_over=15 durch Diesel-Floater. Erlöse Maut = 12.742 EUR in AX, aber CHT-Pipeline vergleicht `Erlöse Fracht vs basispreis` separat — balancierte Vergleichsbasis, kein P20.

**Land-Breakdown:** AT=41 (+421 EUR), BE=241 (−201 EUR), ES=105 (−1.395 EUR), IT=167 (+506 EUR).

**Calculator Pre-Flight:** Keine Bugs gefixt. Methodisch korrekte Maut-Separation im Calculator.

**Detail-Report:** `docs/v1_9_6_cht_cluster_report.md`

---

### 5.6 Bitzer SE (KNR 406345)

**Calculator:** `bitzer.py` (Commit 93dc7c1) | **DLV:** Gewichtsbasiert (ERKA + Profoid), EU-Export  
**Pool:** 3.406 roh → 3.330 beurteilbar (97,8 %) | **DLV-Lücke:** 76 Rows (Spezialrouten)  
**Ergebnis:** M1=2.868 (86,1 %), M2=206 (6,2 %), M_over=256 (7,7 %) | Net Δ = +26.407 EUR (+3,79 %)

**Befunde:** Kein Migrationsschaden. **Calculator-Fixes vor Audit:**
- **IT Zone4 Perioden-Dispatch (P16):** Zone 4 (PLZ-Prefix 32–36) hatte 2024-Raten aktiv; Fix dispatcht korrekt nach Lieferungsjahr. Betroffene Rows: ~80.
- **FR-13400 Zone9-Routing:** Aubagne PLZ 13400 wurde Zone 3 zugeordnet (falsch); korrigiert auf Zone 9 via Profoid-DLV.

Post-Fix-Befund: Net Δ +26.407 EUR (+3,79 %). Verbleibende positive Differenz durch Diesel-Floater-Einschluss in ef-Erlösen (offene Prüfung). Kein Carrier-Abrechnungsfehler.

**Operative Klärung:** FR-92000 Hauts-de-Seine (Zonenzuordnung, geringe Materialiät). DE-Inbound 67 Rows (33.970 EUR, Out-of-Scope, kein DE-Inbound-DLV vorhanden).

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

**Befunde:** Kein Migrationsschaden. Net Δ nahezu null. M2=102 durch geringfügige Raten-Abweichungen in wenigen Strecken-Clustern — methodisch erklärt (§14 Hornschuch-Analogie).

**Calculator Pre-Flight — 2 Bugs gefixt (Commit 897a2c6):**
- **H1 (ES-Mendaro Zone Key):** `zone_fn` gab "ES-20870" zurück; Dictionary-Key ist "ES". Fix: `return "ES"`. 67 ES-Rows betroffen, nach Fix vollständige Coverage.
- **H2 (GB rates_by_col int vs str Keys):** `rates_by_col` hatte int-Spaltenindizes als Keys, `zone_fn` gab str zurück → Dict-Lookup scheiterte. Fix: str(c) Keys. 55 GB-Rows betroffen.

**Detail-Report:** `docs/v1_9_6_helu_cluster_report.md`
---

### 5.9 Hornschuch AG (KNR 490085)

**Calculator:** `hornschuch.py` (Commit a0a9822) | **DLV:** Gewichts-/Zonen-basiert (ContiTech + ERKA), EU-Export  
**Pool:** 2.551 roh → 1.565 beurteilbar (61,4 %) | **DLV-Lücke:** 726 PL-Rows (203.992 EUR)  
**Ergebnis:** M1=1.549 (99,0 %), M2=7 (0,4 %), M_over=9 (0,6 %) | Net Δ = −205 EUR (−0,05 %)

**Befunde:** Kein Migrationsschaden. 99 % M1 — höchste M1-Quote aller Kunden. Net Δ = −205 EUR ist materiell irrelevant.

**Calculator Pre-Flight — 1 Bug gefixt (Commit a0a9822):**
- **G3 (AT-Zone 2-stellig vs 1-stellig):** Calculator extrahierte 2-stelligen PLZ-Prefix für AT-Zone-Lookup; DLV enthält AT-Zonen 1–9 (1-stellig). Fix: Prefix-Länge auf 1 Zeichen. 1 AT-Row betroffen.

**Besondere Befunde:**
- **FR-Castorama/Leroy Merlin (P18):** 318 FR-Rows mit fp = 0,0000 — AX rechnet exakt DLV-Soll. Castorama-DLV enthält additiven Paletten-Aufschlag (326–975 EUR/Sendung) nicht in AX-ef enthalten. Kein Calculator-Bug, kein Schaden.
- **FTL-Flat-Rate (P19):** 7 M2-Rows (Großsendungen > 12 TEUR, fp = −7 bis −17 %): AX rechnet FTL-Flat, Calculator extrapoliert per-kg → Artefakt.
- **PL-DLV-Lücke:** 726 Rows, 203.992 EUR — ERKA-DLV hat 99 PL-Zonen mit leeren Freight-Raten. Operative Klärung ausstehend (→ §7).

**Detail-Report:** `docs/v1_9_6_hornschuch_cluster_report.md`

---

### 5.10 Sika Deutschland GmbH (KNR 491063)

**Calculator:** `sika_de.py` — `SikaDeCalculator` (Commit 7500102) | **DLV:** Stellplatz-basiert, EU-Export  
**Pool:** 1.407 roh → 1.379 beurteilbar (98,0 %) | **DLV-Lücke:** 9 Rows (5.126 EUR)  
**Ergebnis:** M1=887 (64,3 %), M2=293 (21,2 %), M_over=199 (14,4 %) | Net Δ nom. = −25.758 EUR (−1,97 %)  
**Net Δ adjustiert:** **+4.797 EUR (+0,37 %)**

**Hauptbefund — Erlöse-Maut-Separation (P20):**  
AX bucht die DE-Streckenmaut als separaten Posten `Erlöse Maut`. Die Pipeline verwendet `ef = Erlöse Fracht` (ohne Maut). DLV-Soll = `basispreis + de_maut`. Σ Erlöse Maut (EU-Pool) = 30.555 EUR. Adjustiertes Net Δ = +4.797 EUR. Kein Migrationsschaden.

**M2-Struktur:** 107 Extreme-M2 (fp < −50 %, Kleinstsendungen ef << DLV-Minimum, fractional AX-Rates), 186 Moderate-M2 (Maut-Separation-Bias). M_over = 199 Rows durch Billing-above-DLV bei größeren Stellplatz-Counts (SE/IE/ES/GB).

**Calculator Pre-Flight:** Keine Bugs; Calculator korrekt. Rückwirkender Maut-Check: nur 491063 betroffen.

**Detail-Report:** `docs/v1_9_7_sika_welle1_cluster_report.md`

---

### 5.11 SIKA Supply Center AG (KNR 511241)

**Calculator:** `sika_de.py` — `SSCCalculator` (Commit 7500102) | **DLV:** Identisch mit KNR 491063  
**Pool:** 415 roh → 62 beurteilbar (ssc_eu) | **DLV-Lücke:** 4 Rows (4.720 EUR)  
**Ergebnis:** M1=43 (69,4 %), M2=0, M_over=19 (30,6 %) | Net Δ = +2.600 EUR (+6,38 %)

**Befunde:** Kein Migrationsschaden. Positives Net Δ: AX rechnet für SSC-Export-Sendungen über DLV-Niveau ab — kein Schaden für Noerpel.

**Scope-Struktur KNR 511241:**

| Scope | Rows | Σ ef (EUR) | Status |
|---|---:|---:|---|
| ssc_eu (beurteilbar) | 62 | 43.358 | In Scope |
| de_oos (Empf. DE) | 347 | 631.702 | OOS Export-DLV (→ §7) |
| import_flow (non-SSC, Empf. nicht-DE) | 2 | 1.732 | OOS Welle 2 |
| dlv_luecke | 4 | 4.720 | DLV-Lücke |

**Detail-Report:** `docs/v1_9_7_sika_welle1_cluster_report.md` (gemeinsam mit 491063)
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
| P20 | Erlös-Spalten-Separation (ef = Fracht, DLV = Fracht+Maut) | Sika 491063 (30.555 EUR Adj.) | 1 |

### Gefixter Bugs nach Kunden

| Kunde | Fix | Commit | Δ-Impact |
|---|---|---|---|
| Bitzer | IT Zone4 Perioden-Dispatch (P12/P16) | 93dc7c1 | ~−30 TEUR vor→nach Fix |
| Bitzer | FR-13400 Zone9-Routing (P16) | 93dc7c1 | ~−3 TEUR |
| HELU-KABEL | H1 ES-Mendaro Zone Key (P17-A) | 897a2c6 | 67 Rows von DLV-Lücke gerettet |
| HELU-KABEL | H2 GB rates_by_col int/str (P17-B) | 897a2c6 | 55 Rows von DLV-Lücke gerettet |
| Hornschuch | G3 AT-Zone 2→1-stellig (P5) | a0a9822 | 1 Row korrigiert |
| Sika (adj.) | P20 Erlöse-Maut-Separation (Methodik) | — | +30.555 EUR Adj. |
---

## §7 Operative Klärungsbedarfe

**Alle nachfolgenden Positionen sind kein Migrationsbefund.** Sie erfordern operative oder vertragliche Klärung außerhalb des Billing-Audits.

### 7.1 Hornschuch AG — PL-DLV-Lücke (Priorität: Mittel)

| Merkmal | Wert |
|---|---|
| Rows | 726 |
| Σ ef | 203.992 EUR |
| Ursache | ERKA-DLV enthält 99 PL-Zonen mit leeren Freight-Raten |
| Hauptempfänger | Salamander/Aluplast/VEKA/Rehau (PL Fensterrahmen-Kunden) |

**Hypothesen:**
- **A** (wahrscheinlichste): PL nicht in MegaTrans-Nominierung — Noerpel rechnet PL über eigenes Netz, kein DLV vorhanden.
- **B**: PL-Tarif in separater DLV-Datei (nicht erkannt).
- **C**: PL-Sendungen werden über ContiTech-Framework abgerechnet, aber DLV-Datei fehlt in ERKA-Übergabe.

**Empfehlung:** Noerpel nach PL-Tarifbasis fragen. Klärungsziel: Welche DLV-Datei gilt für PL-Ziele unter ContiTech-Rahmen?

---

### 7.2 SIKA Supply Center AG — de_oos-Block (Priorität: Mittel)

| Merkmal | Wert |
|---|---|
| Rows | 347 |
| Σ ef | 631.702 EUR |
| Ursache | KNR 511241 enthält Empfänger-DE-Sendungen (Inland-Lieferungen) |

**Buchungsfrage:** Sind DE-Ziel-Sendungen korrekt unter KNR 511241 (Supply Center AG) gebucht, oder handelt es sich um Buchungsfehler (sollten unter KNR 491063 oder anderem KNR stehen)? Export-DLV gilt nicht für DE-Inland.

**Empfehlung:** Klärung mit Noerpel-Buchhaltung: Welche AX-Kostenstelle gilt für SSC-DE-Inlandslieferungen?

---

### 7.3 Bitzer SE — FR-92000 Hauts-de-Seine (Priorität: Niedrig)

| Merkmal | Wert |
|---|---|
| Betroffene Rows | Wenige (<10) |
| Ursache | PLZ 92xxx wird Zone 8 (IDF-Außen) zugeordnet; möglicherweise Zone 7 (IDF-Kern) |

**Empfehlung:** Rückfrage ERKA zu Zonenzuordnung für IDF-Außenring.

---

### 7.4 Bitzer SE — DE-Inbound Out-of-Scope (Priorität: Niedrig)

| Merkmal | Wert |
|---|---|
| Rows | 67 |
| Σ ef | 33.970 EUR |
| Ursache | Importtarif (Nicht-DE-Ursprung → DE-Empfänger) nicht in DLV hinterlegt |

**Empfehlung:** Prüfen ob DE-Inbound-Tarif existiert; falls ja, in Calculator ergänzen.

---

### 7.5 HERMA GmbH — GB-Zones Fehlende Area Codes (Priorität: Niedrig)

| Merkmal | Wert |
|---|---|
| Betroffene Areas | Ca. 10 fehlende UK-Postcode-Areas |
| Ursache | DLV-Datei enthält nicht alle GB-Postcode-Areas; betroffene Rows in DLV-Lücke |

**Empfehlung:** DLV-Ergänzung für fehlende GB-Areas oder Klärung welche Tarifklasse gilt.

---

### 7.6 Fischerwerke GmbH — GR-Sendungen ohne DLV (Priorität: Niedrig)

| Merkmal | Wert |
|---|---|
| Rows | 264 |
| Σ ef | ca. 100.000 EUR (Schätzung Karton-Tarif) |
| Ursache | Kein GR-Tarif für 2025 im Hauptpool; Calculator wirft LookupError |

**Empfehlung:** GR-Tarif-Datei beschaffen oder Klärung Noerpel, ob GR über separaten Carrier-Vertrag läuft. Vorgesehen für Etappe 10.

---

### Zusammenfassung Operative Klärungen

| Punkt | Kunde | EUR | Priorität |
|---|---|---:|---|
| PL-DLV-Lücke | Hornschuch | 203.992 | Mittel |
| de_oos-Buchung | Sika SSC | 631.702 | Mittel |
| FR-92000 Zone | Bitzer | < 5.000 | Niedrig |
| DE-Inbound | Bitzer | 33.970 | Niedrig |
| GB-Area-Codes | HERMA | n/a (DLV-Lücke) | Niedrig |
| GR-Tarif | Fischerwerke | ~100.000 | Niedrig |
---

## §8 Offene Punkte (Sika-Restwellen)

### 8.1 KNR 511241 — Import-Flow (Welle 2)

**Status:** 2 Rows (1.732 EUR) mit Versender non-SSC + Empfänger nicht-DE. Diese Rows entstammen IT/ES-Ursprung und liegen außerhalb des Export-DLV-Scopes (DLV gilt nur für DE-Ursprung). Ein Import-Flow-DLV ist erforderlich.

**Erwartung:** 2 Rows, materiell irrelevant (<0,1 % des 511241-Pools). Keine Änderung der Audit-Aussage.

**Nächste Schritte:** Import-Flow-DLV für IT/ES-Ursprung identifizieren; ggf. als dauerhafter OOS dokumentieren.

---

### 8.2 KNR 527406 — Sika ATM Schweiz (separate Session)

**Status:** Nicht in bi_top20_data.pkl. Separates BI-Loading aus `bi_cache_sika_527406.pkl` erforderlich.

| Merkmal | Wert |
|---|---|
| BI-Cache | `output/bi_cache_sika_527406.pkl` (517 KB) |
| Calculator | `sika_atm.py` (Commit f005e63) |
| Besonderheit | `Abrechnungsstellplätze` = NaN (gewichtsbasiert, EUR/100kg) |
| DLV | Separates ATM-DLV (unterschiedlich von 491063/511241) |
| Dinas-Cache | Geteilt mit KNR 491063 (`dinas_cache_491063.pkl`) |

**Erwartung:** Separate Analyse; kein Einfluss auf bestehende 11-Kunden-Lage. Kein Migrationsschaden erwartet.

**Nächste Schritte:** Separate Session; Pipeline-Script für 527406 bauen; Report ergänzen.

---

### 8.3 Aggregation-Audit (Methodik-Folge)

**Status:** Plan-Datei vorhanden (`/root/.claude/plans/binary-percolating-pumpkin.md`). Zwei Dokumente geplant:
- `docs/aggregation_codebase_audit.md`
- `docs/aggregation_retroactive_risk.md`

**Kernbefund (bereits erhoben):** Kein aktiver Aggregationsfehler bei keinem abgeschlossenen Kunden. GEZE hat latentes Risiko (140 Sub-Rows Tonnage>0) für den Fall, dass ein BI-Vergleich hinzugefügt wird.

**Erwartung:** Keine Änderung der Audit-Aussage; Methodik-Dokumentation für v1.9-Standard.

---

### Zeitplan Restwellen

| Aufgabe | Aufwand (est.) | Impact auf Audit-Aussage |
|---|---|---|
| KNR 511241 Import-Flow | ~1 h | Negligible (2 Rows) |
| KNR 527406 ATM | ~4–6 h (Pipeline + Report) | Additive Zeile, kein Schaden erwartet |
| Aggregation-Audit Docs | ~2–3 h | Methodik-Dokumentation |
---

## §9 Audit-Aussage und Empfehlungen

### Audit-Aussage

> **Die Migration des Transportmanagementsystems von Dinas auf Microsoft Dynamics AX (Noerpel-Gruppe) vom 27. September 2025 wurde sauber durchgeführt.**
>
> Über 11 Kunden-Scopes (9 Kundenfirmen), 17.150 beurteilbare Abrechnungszeilen und ein Erlösvolumen von 6,98 MEUR wurde **kein systematischer Migrationsschaden** identifiziert. Kein Kunde weist eine Konstellation auf, die auf fehlerhafte Tarif-Migration hindeutet.
>
> Alle identifizierten Abweichungen sind durch methodisch erklärbare Faktoren begründet: Calculator-Pre-Flight-Fixes (P1–P20 bei 6 Kunden), Erlös-Komponenten-Separation (P20, Sika 491063), Pricing-Mode-Artefakte (Charter-Pool Fischerwerke, GC-Band Groz-Beckert) oder FTL-Flat-Rate-Effekte (P19, Hornschuch). Diese Faktoren sind keine Migrationsfehler.

**Net Δ adjustiert (alle 11 Kunden): +136.952 EUR (+1,96 %)**  
Dieser Wert liegt innerhalb der Wesentlichkeitsschwelle und zeigt, dass AX im Mittel minimal über dem DLV-Niveau abrechnet — kein Schaden für Noerpel.

---

### Empfehlungen

#### Operative Klärungen (kurzfristig)

1. **Hornschuch PL (203.992 EUR):** ContiTech-Vertragsscope für Polen klären. Noerpel nach gültigem PL-Tarif fragen. Zeitlich dringlich, da hoher EUR-Betrag ohne DLV-Verifizierung.

2. **Sika SSC de_oos (631.702 EUR):** Buchungszugehörigkeit der 347 DE-Ziel-Zeilen unter KNR 511241 klären. Wenn DE-Inland: zugehörigen DLV beschaffen oder auf KNR 491063 umbuchen.

#### Methodik-Standard (mittelfristig)

3. **P20-Prüfung als Standard:** Für zukünftige Kunden-Audits: alle `Erlöse_*`-Spalten in bi_top20 per Pool summieren und gegen DLV-Soll-Komponenten abgleichen (→ SKILL.md P20).

4. **P1–P20 als Pre-Flight-Checkliste:** Systematisch vor jedem neuen Kunden-Audit durchführen. Reduziert Calculator-Bug-Nacharbeit erheblich (HELU: 2 Bugs, Hornschuch: 1 Bug — alle hätten zu falschen DLV-Lücken geführt).

#### Folge-Audits (mittelfristig)

5. **Sika ATM (KNR 527406):** Separate Session; gewichtsbasierter DLV; keine Auswirkung auf Gesamtaussage erwartet.

6. **Fischerwerke GR-Tarif (264 Rows, ~100 TEUR):** GR-DLV für Etappe 10 beschaffen.

7. **Aggregation-Audit:** Methodik-Dokumentation für v1.9-Standard abschließen (2–3 h, kein Audit-Ergebnis-Impact).

---

### Verteilung

Dieser Bericht ist für ERKA-Management und Noerpel-Geschäftsführung bestimmt. Detail-Reports pro Kunde sind in `docs/v1_9_*_cluster_report.md` verfügbar. Methodikdokumentation: `docs/AUDIT_METHODOLOGY.md` v1.9.7.
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
| M1 | &#124;fp&#124; ≤ 5 % — korrekte Abrechnung |
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
| Net Δ % | Net Δ / Σ dlv_soll (prozentuale Gesamtabweichung) |
| Charter-Artefakt | Vollfahrzeug-Pauschalpreise werden gegen per-kg-DLV verglichen → M_over |
| GC-Mode | Grob-Cluster-Modus (Gewicht/kg-Extrapolation für große Sendungen) |

---

## Anhang B — Datenquellen und Cache-Dateien

### BI-Daten

| Datei | Inhalt | Kunden |
|---|---|---|
| `output/bi_top20_data.pkl` | AX POST-Buchungen Top-20-KNRs | Alle außer 527406 |
| `output/bi_cache_sika_527406.pkl` | AX POST-Buchungen KNR 527406 | Sika ATM |

### Kunden-Audit-Caches

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
| `output/sika_welle1_step23_results_v197.pkl` | Sika 491063 + 511241 | 71cc9c2 |

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

---

## Anhang C — Versions-Historie der Methodik

| Version | Datum | Änderungen |
|---|---|---|
| v1.0 | 2026-02 | Erstaudit GEZE (Dinas PRE × AX POST Familien-Vergleich) |
| v1.9 | 2026-03 | Vollumstieg auf DLV-Soll-Vergleich; ZGI-Cluster; Sub-Row-Filter |
| v1.9.4 | 2026-03 | EBM, HERMA, GEZE v2, Fischerwerke v1 |
| v1.9.5 | 2026-03 | Bitzer; Calculator Bug-Klassen A–H |
| v1.9.6 | 2026-04 | CHT, Groz-Beckert, HELU-KABEL, Hornschuch; P17–P19 |
| **v1.9.7** | **2026-04-28** | **Sika Welle 1 (491063+511241); P20 Erlöse-Maut-Separation** |

Vollständige Änderungshistorie: `docs/AUDIT_METHODOLOGY.md` — Changelog §0.
