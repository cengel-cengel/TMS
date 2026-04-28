# Operative Klärungsbedarfe — Konsolidiertes Memo v1.0
**ERKA Rechnungsprüfung / Noerpel-Gruppe**  
Stand: 2026-04-28 | Erstellt: Claude Code (Anthropic)

---

## §1 Einleitung

Dieses Dokument fasst alle im Rahmen des TMS-Migrations-Audits (Dinas → AX, 27.09.2025) identifizierten operativen Klärungsbedarfe zusammen.

**Wichtig:** Die nachstehenden Punkte sind **keine Migrationsbefunde**. Sie beschreiben bestehende Vertrags- oder Tarif-Lücken, die während der Audit-Analyse sichtbar wurden. Die Gesamtaussage des Audits — kein systematischer Migrationsschaden — bleibt unberührt.

Adressat: ERKA-Operativ-Team (Rechnungsprüfung, Carrier-Management).  
Audit-Kontext: `docs/FINAL_AUDIT_REPORT_v1_1.md` (§7 Operative Klärungsbedarfe).

---

## §2 Überblick

| Punkt | Kunde | Volumen (EUR) | Rows | Priorität | Status |
|---|---|---:|---:|---|---|
| C.1 | Hornschuch AG | 203.992 | 726 | Hoch | Offen |
| C.2 | Sika Supply Center AG | 631.702 | 347 | Hoch | Offen |
| C.3 | Fischerwerke GmbH | 102.052 | 264 | Mittel | Offen |
| C.4 | HERMA GmbH | 61.917 | 93 | Mittel | Offen |
| C.5 | Bitzer SE | 33.970 | 67 | Mittel | Offen |
| C.6 | CHT Germany GmbH | 38.776 | 102 | Niedrig | Offen |
| C.7 | Bitzer SE | 445 | 7 | Niedrig | Offen |
| **Σ** | | **1.072.854** | **1.606** | | |

**Quellen:** Alle Volumen- und Row-Zahlen aus `output/*_step23_results_*.pkl` oder `docs/operative_followups/`.  
**Priorität Hoch:** C.1 + C.2 zusammen 835.694 EUR (78 % des Gesamtvolumens).

---

## §3 C.1 — Hornschuch AG: PL-Sendungen ohne verifizierbaren Tarif

**Priorität: Hoch | KNR: 490085 | Carrier: Noerpel (ContiTech-Rahmen)**

| Merkmal | Wert |
|---|---|
| Rows | 726 |
| Σ Erlöse Fracht | 203.992 EUR |
| Zeitraum | Oktober 2025 – März 2026 |
| Status | DLV-Lücke — kein Soll-Tarif berechenbar |
| Cache | `output/hornschuch_step23_results_v196.pkl` → `no_dlv` |

### Befund

726 PL-Sendungen werden in AX unter KNR 490085 mit positivem `Erlöse Fracht` gebucht. Das ERKA-DLV (ContiTech-Rahmenvertrag) enthält eine PL-Zonenstruktur mit 99 PLZ-Gruppen, aber **keine Freight-Raten** — alle PL-Zellen sind leer. Ein DLV-Soll-Vergleich ist nicht möglich. Tarifgruppe in Calculator: `hornschuch_pl_na` (explizit als nicht-nominiert markiert).

### Top-10-Empfänger PL (nach Erlösen)

| Empfänger | Rows | Σ ef (EUR) |
|---|---:|---:|
| Lumatech | 39 | 32.773 |
| Aluplast sp. z o.o. | 40 | 24.142 |
| Salamander | 45 | 17.948 |
| VEKA Polska Sp. z o.o. | 34 | 14.553 |
| Rehau Sp.z.o.o. | 32 | 8.376 |
| Uslugi i Produkcja Export-Import | 21 | 7.686 |
| Deceuninck Sp. z o.o. | 27 | 6.675 |
| XPO1 / Amazon Poland | 42 | 6.443 |
| Askol-Svatava Koletzko | 24 | 6.228 |
| Centrum Logistyczne Leroy Merlin | 19 | 6.225 |

### Hypothesen

- **A (wahrscheinlich):** PL nicht in der Noerpel/ContiTech-Nominierung enthalten. Noerpel bedient PL über eigenes Netz zu eigenen Raten — kein DLV mit ERKA.
- **B:** PL-Tarif in separater DLV-Datei (nicht in der ERKA-Übergabe enthalten).
- **C:** PL-Sendungen werden über ContiTech-Framework fakturiert; DLV fehlt.

### Empfehlung

1. Noerpel fragen: Welche Tarif-Basis gilt für PL-Ziele unter dem ContiTech-Rahmenvertrag?
2. Falls Tarif vorhanden: DLV-Datei anfordern und PL-Calculator ergänzen.
3. Falls keine Nominierung: PL-Sendungen als dauerhaft OOS dokumentieren und ggf. separate PL-DLV-Verhandlung einleiten.

**Zeitdringlichkeit: Hoch** — 203.992 EUR / 726 Rows ohne jede Soll-Überprüfung.

### Verweis

`docs/v1_9_6_hornschuch_cluster_report.md` — §PL-DLV-Lücke

---

## §4 C.2 — Sika Supply Center AG: de_oos-Buchungszugehörigkeit

**Priorität: Hoch | KNR: 511241 | Carrier: Noerpel**

| Merkmal | Wert |
|---|---|
| Rows | 347 |
| Σ Erlöse Fracht | 631.702 EUR |
| Zeitraum | Oktober 2025 – März 2026 |
| Status | OOS — Buchungsfrage ungeklärt |
| Cache | `output/sika_welle1_step23_results_v197.pkl` → `scope_511` |

### Befund

Unter KNR 511241 (SIKA Supply Center AG, Export-DLV) sind 347 Sendungen mit **Empfänger DE** gebucht. Das Export-DLV (KNR 511241) gilt nach Vertragslogik nur für Sendungen mit Ursprung DE → EU-Ausland. DE-Inland-Sendungen sind im Export-DLV nicht abgedeckt.

**Abgrenzung vom auditierten Import-Flow:**  
Der in Welle 2 auditierte Import-Flow (346 Rows, ES/IT → DE-70499, `sika_import.py`) ist ein separater Scope und wurde mit eigenem Calculator und DLV korrekt auditiert (Net Δ P20-adj +9.915 EUR — kein Schaden). Die hier aufgeführten 347 de_oos-Rows sind davon verschieden: es handelt sich um Sendungen mit DE-Empfänger, die inhaltlich Inlandslieferungen darstellen, aber unter der SSC-Exportkunden-KNR gebucht wurden.

### Buchungsfrage

**Option A:** Die 347 Rows sind korrekt unter KNR 511241 — dann wird ein separates DE-Inland-DLV für KNR 511241 benötigt.  
**Option B:** Die Rows gehören unter KNR 491063 (Sika Deutschland GmbH) — dann ist eine Umbuchung erforderlich.  
**Option C:** Die Rows sind physische Importlieferungen (IT/ES → DE) die fälschlicherweise ohne Versender-Land-Kennzeichnung gebucht wurden — dann Verknüpfung mit Import-Flow-DLV prüfen.

### Empfehlung

1. Noerpel-Buchhaltung klären: Welche AX-Kostenstelle gilt für SSC-DE-Inlandslieferungen?
2. Buchungshistorie der 347 Rows prüfen (Versender-Land der AX-Buchungen).
3. Nach Klärung: entweder passendes DLV zuordnen oder Umbuchung durchführen.

**Zeitdringlichkeit: Hoch** — 631.702 EUR außerhalb jeder Soll-Überprüfung.

### Verweis

`docs/v1_9_7_sika_welle1_cluster_report.md` — §8.1 de_oos-Block  
`docs/FINAL_AUDIT_REPORT_v1_1.md` — §7.2

---

## §5 C.3 — Fischerwerke GmbH: GR-Sendungen ohne Karton-Tarif

**Priorität: Mittel | KNR: 409480 | Carrier: Noerpel**

| Merkmal | Wert |
|---|---|
| Rows | 264 |
| Σ Erlöse Fracht | 102.052 EUR |
| Zeitraum | Oktober 2025 – März 2026 |
| Status | Calculator-Fehler — Karton-Pricing nicht implementiert |
| Cache | `output/fischerwerke_step23_results_v196.pkl` → `errors` (GR-Fehler) |

### Befund

264 GR-Sendungen für Fischerwerke erzeugen einen `LookupError` im Calculator. Der bestehende `FischerwerkeCalculator` ist für Stellplatz-basierte EU-Export-Tarife ausgelegt. Für GR verwendet Noerpel eine **Karton-basierte Pricing-Basis** (EUR/Karton), die eine abweichende Calculator-Architektur erfordert.

| GR in Pool | GR in rdf (beurteilbar) | GR Fehler | GR Fehler ef |
|---:|---:|---:|---:|
| 489 | 214 | 264 | 102.052 EUR |

Die 214 beurteilbaren GR-Rows (75.521 EUR) wurden bereits im Hauptaudit verarbeitet (über bestehende Stellplatz-Tarifgruppen mit dem nächstgültigen Tarif). Die 264 Fehler-Rows haben keinen Calculator-Match.

### Empfehlung

1. **Kurzfristig:** GR-Karton-DLV von Noerpel / ERKA anfordern.
2. **Mittelfristig:** Separaten `FischerwerkeGRCalculator` (Karton-Basis) implementieren — ca. 2–3 Stunden Entwicklungsaufwand. Analog CHT-GR (C.6).
3. **Falls GR dauerhaft im Scope:** GR-Audit als Etappe 10 einplanen.

### Verweis

`docs/v1_9_6_fischerwerke_cluster_report.md`  
`docs/FINAL_AUDIT_REPORT_v1_1.md` — §7.6

---

## §6 C.4 — HERMA GmbH: GB-Postcode-Areas ohne DLV-Abdeckung

**Priorität: Mittel | KNR: 423650 | Carrier: Noerpel**

| Merkmal | Wert |
|---|---|
| Rows | 93 |
| Σ Erlöse Fracht | 61.917 EUR |
| Zeitraum | Oktober 2025 – März 2026 |
| Status | DLV-Lücke — 10 GB Area-Codes fehlen im DLV |
| Cache | `docs/operative_followups/herma_gb_zones.md` |

### Befund

10 britische Postcode-Areas sind im HERMA DLV-Workbook (2026 Haftmaterial) nicht eingetragen. Der Calculator kann für diese Areas keinen Tarif berechnen (`LookupError`). Die Areas sind alle in England/Wales und entsprechen Industriestandorten (Textilmaschinen, Logistikzentren).

### Fehlende GB Postcode-Areas

| Area-Code | Ort | Rows | Σ ef (EUR) |
|---|---|---:|---:|
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

### Empfehlung

1. ERKA-Anfrage an HERMA / Noerpel: Welche Tarifzone gilt für die 10 fehlenden GB Postcode-Areas?
2. DLV-Ergänzung durch Noerpel anfordern.
3. Nach Klärung: Calculator-Update; GR-Audit für betroffene Areas nachziehen.

### Verweis

`docs/operative_followups/herma_gb_zones.md` — vollständige Analyse inkl. ERKA-Anfrageschema  
`docs/v1_9_6_herma_cluster_report.md`

---

## §7 C.5 — Bitzer SE: DE-Inbound-Sendungen ohne Importtarif

**Priorität: Mittel | KNR: 406345 | Carrier: Noerpel**

| Merkmal | Wert |
|---|---|
| Rows | 67 |
| Σ Erlöse Fracht | 33.970 EUR |
| Zeitraum | Oktober 2025 – März 2026 |
| Status | OOS — kein Importtarif im DLV hinterlegt |
| Cache | `output/bitzer_step23_results_v196_postfix.pkl` → `df_res`, `land == "DE"` |

### Befund

67 Sendungen mit **Empfänger DE** (Bitzer-Werke Rottenburg/Ergenzingen, Althengstett, Gäufelden, Schkeuditz) werden unter KNR 406345 gebucht. Der `BitzerCalculator` ist ausschließlich für EU-Export (Ursprung DE → EU-Ausland) implementiert. Ein Importtarif (Ursprung Ausland → DE) fehlt.

### Herkunftsverteilung der 67 DE-Inbound-Rows

| Versender Land | Rows | Σ ef (EUR) |
|---|---:|---:|
| IT | 52 | 29.750 |
| FR | 6 | 1.109 |
| ES | 1 | 688 |
| DE | 1 | 520 |
| BE | 1 | 470 |
| CH | 2 | 445 |
| Weitere | 4 | 988 |

Hauptlieferanten aus IT (Bitzer-Lieferanten nach Rottenburg/Ergenzingen) dominieren.

### Empfehlung

1. Prüfen, ob ein DE-Inbound-DLV (Importtarif für Noerpel-Sendungen nach DE) existiert.
2. Falls ja: DLV-Datei anfordern und separaten Importtarif-Calculator implementieren.
3. Falls nein: 67 Rows als dauerhaft OOS dokumentieren (Importabwicklung außerhalb Noerpel-Rahmen).

### Verweis

`docs/v1_9_6_bitzer_cluster_report.md`  
`docs/FINAL_AUDIT_REPORT_v1_1.md` — §7.4

---

## §8 C.6 — CHT Germany GmbH: GR-Sendungen Calculator nicht implementiert

**Priorität: Niedrig | KNR: 486073 | Carrier: Noerpel**

| Merkmal | Wert |
|---|---|
| Rows | 102 |
| Σ Erlöse Fracht | 38.776 EUR |
| Zeitraum | Oktober 2025 – März 2026 |
| Status | Calculator-Fehler — `CHTGreeceCalculator.calculate()` nicht implementiert |
| Cache | `output/cht_step23_results_v196.pkl` → `errors` |

### Befund

102 GR-Sendungen für CHT Germany werfen einen `AttributeError`: `'CHTGreeceCalculator' object has no attribute 'calculate'`. Die `CHTGreeceCalculator`-Klasse existiert bereits als Stub (Klassen-Gerüst vorhanden), aber die `calculate()`-Methode wurde nicht implementiert. GR-Sendungen für CHT werden über einen anderen Preismechanismus abgewickelt als die BE/IT/ES/AT-Sendungen.

Die 4 CHT-Länder-Scopes (BE, IT, ES, AT) sind vollständig auditiert (554 Rows, 97,3 % M1, kein Schaden). GR ist ein separater Teilscope ohne aktiven Vergleich.

### Empfehlung

1. CHT-GR-DLV von ERKA anfordern (Tarif-Grundlage klären).
2. `CHTGreeceCalculator.calculate()` implementieren — vermutlich analog `CHTGermanyCalculator` (Gewichts-/LDM-Basis), ca. 2–3 Stunden.
3. Nach Implementierung: CHT-GR-Audit als Mini-Etappe anhängen.

### Verweis

`docs/v1_9_6_cht_cluster_report.md`

---

## §9 C.7 — Bitzer SE: FR-PLZ-92xxx Zonenzuordnung fehlt

**Priorität: Niedrig | KNR: 406345 | Carrier: Noerpel**

| Merkmal | Wert |
|---|---|
| Rows | 7 |
| Σ Erlöse Fracht | 445 EUR |
| Zeitraum | Oktober 2025 – März 2026 |
| Status | DLV-Lücke — PLZ-Prefix 92 nicht in FR-Zonentabelle |
| Cache | `output/bitzer_step23_results_v196_postfix.pkl` → `df_res`, `land=="FR" & plz.str.startswith("92")` |

### Befund

7 Sendungen nach PLZ 92000 (Nanterre, Hauts-de-Seine / Île-de-France) erzeugen einen `LookupError`: PLZ-Prefix `92` ist in der FR-Zonentabelle des Bitzer-DLV nicht eingetragen. Die abgerechneten Erlöse (87 EUR / 58 EUR / 33,50 EUR) entsprechen Zone-4-Raten — AX rechnet bereits mit Zone 4 ab.

**Aus BI-Daten implizit abgeleitete Zone: Zone 4** (Bestätigung durch ERKA erforderlich).

### Analyse

PLZ-Prefix 92 (Hauts-de-Seine) liegt im Großraum Paris. Benachbarte Präfixe im DLV:
- 91 (Essonne) → Zone 4
- 93 (Seine-Saint-Denis) → nicht im DLV
- 94 (Val-de-Marne) → nicht im DLV
- 95 (Val-d'Oise) → Zone 4

Naheliegend: 92, 93, 94 ebenfalls Zone 4 (Île-de-France komplett). Klärung empfohlen, da die AX-Abrechnung bereits Zone 4 anwendet.

### Empfehlung

ERKA-Anfrage an Noerpel: Bestätigung Zone für PLZ-Präfixe 92, 93, 94 (Île-de-France). Calculator-Update nach Bestätigung (5 Minuten). Materiell marginal (445 EUR Gesamtvolumen).

### Verweis

`docs/operative_followups/bitzer_fr_92000_zone.md` — vollständige Analyse inkl. Zone-4-Nachweis  
`docs/operative_followups/bitzer_fr_13400_aubagne_tarifwahl.md` — verwandter FR-Zonenbefund

---

## §10 Prioritäten-Empfehlung

### Hoch (sofortiger Handlungsbedarf)

| Punkt | Kunde | Volumen | Handlung |
|---|---|---:|---|
| C.1 | Hornschuch AG PL | 203.992 EUR | Noerpel nach PL-Tarifbasis fragen |
| C.2 | Sika SSC de_oos | 631.702 EUR | KNR-Buchungszugehörigkeit klären |
| **Σ Hoch** | | **835.694 EUR** | |

Beide Punkte haben kein DLV-Soll und können damit nicht auf korrekte Abrechnung überprüft werden. Zeitdringlichkeit durch Volumen gegeben.

### Mittel (innerhalb 4–8 Wochen)

| Punkt | Kunde | Volumen | Handlung |
|---|---|---:|---|
| C.3 | Fischerwerke GR | 102.052 EUR | GR-Karton-DLV anfordern; Calculator-Bau |
| C.4 | HERMA GB | 61.917 EUR | 10 fehlende Area-Codes beim DLV-Halter klären |
| C.5 | Bitzer DE-Inbound | 33.970 EUR | Importtarif-Existenz prüfen |
| **Σ Mittel** | | **197.939 EUR** | |

### Niedrig (opportunistisch, bei Kapazität)

| Punkt | Kunde | Volumen | Handlung |
|---|---|---:|---|
| C.6 | CHT GR | 38.776 EUR | Calculator-Stub zu vollständiger Implementierung ausbauen |
| C.7 | Bitzer FR-92000 | 445 EUR | Zone-4-Bestätigung; 5-Min-Fix |
| **Σ Niedrig** | | **39.221 EUR** | |

---

## §11 Status-Tracking

| Datum | Punkt | Status | ERKA-Owner | Notiz |
|---|---|---|---|---|
| 2026-04-28 | C.1 Hornschuch PL | Offen | — | Identifiziert im Audit v1.9.6 |
| 2026-04-28 | C.2 Sika SSC de_oos | Offen | — | Identifiziert im Audit v1.9.7 |
| 2026-04-28 | C.3 Fischerwerke GR | Offen | — | Calculator-Stub vorhanden |
| 2026-04-28 | C.4 HERMA GB | Offen | — | Memo erstellt 2026-04-27 |
| 2026-04-28 | C.5 Bitzer DE-Inbound | Offen | — | Identifiziert im Audit v1.9.6 |
| 2026-04-28 | C.6 CHT GR | Offen | — | Calculator-Stub vorhanden |
| 2026-04-28 | C.7 Bitzer FR-92000 | Offen | — | Memo erstellt 2026-04-27 |

*Diese Tabelle ist für manuelle Fortschritts-Updates vorgesehen.*

