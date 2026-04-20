# TMS Billing Audit — Methodik-Referenz

**Projekt:** Migration Dinas → AX (ERP-Wechsel)
**Scope:** Billing-Accuracy-Audit für Kundentarife (Etappe 9a.x)
**Stand:** 2026-04-20

---

## §1 Grundprinzip

Jede Abrechnungszeile aus den **Abrechnungsstrecken** (AX-System) wird gegen den
**kundengerichteten DLV-Tarif** geprüft — nicht gegen den Einkaufstarif des
Unterfrachtführers (z. B. Kern). Ziel: Nachweis von Über- oder Unterfakturierung
gegenüber der vertraglich vereinbarten Offerte.

Die Prüfung ist **phasen-bewusst**: Jede Zeile wird einem Zeitfenster zugeordnet:
- `pre_dlv` — vor DLV-Gültigkeitsbeginn
- `in_dlv` / `in_dlv_2025` / `in_dlv_2026` — innerhalb eines Gültigkeitsfensters
- `post_dlv` — nach DLV-Ablauf

Calculator-Checks laufen **ausschließlich** auf `in_dlv`-Zeilen.

---

## §2 DLV-Tarif-Formate

### Fischerwerke (Stellplatz-basiert)
- Lookup-Tabelle: Anzahl Stellplätze → Flat-Rate per Sendung
- Per-Route-Dateien (eine Datei pro Abrechnungsrelation)
- Quelle: `Fischerwerke/DLVs & Tarife/`

### EBM-Papst (Palletspace-Matrix, LDM-basiert)
- Breite Matrix: Zeile = Route (PLZ-Key), Spalte = Stellplätze 1–33 + FTL
- Zwei Sheets pro DLV-Datei: `Tariffs_DE_EU` (Frachtpreis) + `Toll_DE_EU` (Maut)
- Abrechnung: `betrag = tariff[route][n_stpl] × (1 + floater) + toll[route][n_stpl]`
- Quelle: `EBM-Papst, Mulfingen/`

### Route-Key-Extraktion (EBM)
- **IE/GB** (Eircode-Länder): 3-stelliger Alpha-Code — `'IE-A92 FY90'` → `'A92'`
- **PLZ-Länder** (PL/SK/SI/HR/EE): Vollständiger PLZ-String — `'PL-03-236'` → `'PL-03-236'`
- **Merged-Einträge**: Pipe-separated → nimm erstes — `'EE-75301|EE-75306'` → `'EE-75301'`

### GEZE GmbH (Gewichts-basiert, EUR/100 kg, Maut inkludiert)

**DLV-Struktur:** Sheet "Exporttarife" — Country-Blocks mit Zonen-Zeilen.
Pro Zone: Minimum-Betrag + Gewichtsbänder (bis 300 kg, bis 500 kg, … bis 3.000 kg)
mit Rate EUR/100 kg. Länder: PT, GB, IE, IT, FR, AT, ES, CH.
Gültig: 2025-01-01 – 2025-12-31 (kein separates 2026-DLV; 2025-Fallback bleibt aktiv).

**Abrechnungsformel:**
```
billing_kg  = max(100, ceil(tonnage_kg / 100) * 100)
basispreis  = max(minimum_zone, rate_per_100kg × billing_kg / 100)   # EUR
chf_amount  = basispreis × chf_floater_fraction                       # EUR, nur CH
Erlöse_Fracht_soll = basispreis + chf_amount
```

**Maut:** In `basispreis` inkludiert → `toll = 0` in der floater_pct-Formel.
**Diesel:** Nicht im DLV modelliert — erscheint als separate Spalte `Erlöse Diesel`
in den BI-Daten und fließt nicht in `floater_pct` ein.

**floater_pct für GEZE:**
```
floater_pct = Erlöse_Fracht / basispreis - 1
# non-CH: floater_pct ≈ Diesel-Floater (variabel, monatlich)
# CH:     floater_pct ≈ CHF-Floater-Fraktion + ggf. Diesel-Floater
```

**CHF-Floater (nur Empfänger Land = CH):**
Der CHF/EUR-Wechselkurs zum Sendungsdatum dient als **Lookup-Key** in die
Prozentband-Tabelle (`Schweiz_Währungszuschlag_Geze.xlsx` bzw. Sheet
"CH-Währungsfloater" im DLV). Die Tabelle gibt eine EUR-Prozent-Fraktion auf
`basispreis` zurück — kein Währungsumtausch, alles in EUR.

Bandbreite im aktuellen CHF-Sheet: **CHF/EUR 1,021 – 0,88** in 14 Stufen;
Stückgut (≤ 3.000 kg): 0 % – 9,18 %; Komplett (> 3.000 kg): 0 % – separates
Staffel (Forward-Fill für Lücken in der Komplett-Spalte).

**Reverse-Engineer-Ansatz für 9b.3** (kein externer CHF/EUR-Kursdatensatz
erforderlich): `floater_pct` aus Billing-Daten berechnen → CHF-Bandtabelle
rückwärts durchlaufen → konsistente Bandeinordnung als Verifikation.

**Zone-Lookup:** Länderspezifische PLZ-Präfix-Tabellen im Calculator
(`geze.py`); IE = immer Zone 1; GB = Postcode-Area (WS/B/CV… → Zone 1,
G/EH… → Zone 3, BT → Zone 4).

---

## §2a Positions-Level vs Sendungs-Level

### Hintergrund

Die **Abrechnungsstrecken**-Daten aus dem AX-System liefern je nach Datenquelle und
Kundenkonfiguration entweder:
- **Positions-Level:** Eine Zeile pro Auftragsposition (Auftragsnummer). Mehrere
  Positionen können zur selben Sendung (Ausgangsbordero) gehören.
- **Sendungs-Level:** Eine Zeile pro Sendung. Tonnage und Betrag sind bereits
  sendungsseitig aggregiert.

Der Unterschied ist **nicht sofort sichtbar** — beide Formate haben die gleichen
Spaltennamen. Erkennbar erst beim Quervergleich: mehrere Auftragsnummern auf
gleicher Rechnungsnummer/Ausgangsbordero → Positions-Level.

### GEZE-Befund (9b.3)

GEZE BI-Daten sind **Positions-Level**: 3.120 beurteilbare Positionen entsprechen
1.098 Gruppen nach Aggregation auf `Rechnungsnummer × Empfänger Land × PLZ-norm`.
Extremfall GB: 591 Positionen auf 8 Gruppen (Ø 74 Positionen/Gruppe, 2 eindeutige
Ausgangsbordero). Auf Positions-Ebene wäre `floater_pct` stark verzerrt
(Einzelminimumgebühren dominieren → fp ≈ −0,996).

### Aggregations-Key-Hierarchie

| Priorität | Key | Verwendbar wenn |
|---|---|---|
| 1 | `Ausgangsbordero` | Vorhanden und eindeutig pro Sendung |
| 2 | `Mastersendungs-Key` (RN × Land × PLZ-norm) | Ausgangsbordero fehlt oder dünn besetzt |
| 3 | `Position-Level mit Caveat` | Keine Aggregation möglich; fp-Werte als "unvalidiert" kennzeichnen |

**Aktuell (9b.3):** Aggregations-Key = Mastersendungs-Key (Rechnungsnummer ×
Empfänger Land × PLZ-norm), da `Ausgangsbordero` in den GEZE BI-Daten nicht
konsistent befüllt ist.

### Konsequenzen für Muster-A / Muster-B

- **floater_pct** und daraus abgeleitetes **Muster-A** sind nur auf
  **Sendungs-Ebene** belastbar. Auf Positions-Ebene (ohne Aggregation) sind alle
  fp-Werte als **unvalidiert** zu markieren.
- **Muster-B** (delta_raw < −10 EUR) reagiert empfindlich auf die
  Aggregationsebene: Eine große Sendung mit 50 Positionen, die korrekt
  abgerechnet wurde, kann auf Positions-Ebene 49× als Muster-B erscheinen
  (Einzelposition << DLV-Minimum der aggregierten Sendung).
- **Aggregationsartefakt-Flag:** Muster-B-Kandidaten mit `n_pos > 5` und
  `fp > 0` auf Gruppenebene sind als "Aggregationsartefakt — Sendungs-Aggregation
  erforderlich" zu kennzeichnen und **nicht** als bestätigte Unterfakturierung
  zu werten.

### Pflichtfelder (ab v1.4)

| Feld | Werte | Bedeutung |
|---|---|---|
| `aggregation_level` | `sendung` \| `position` | Ebene der Billing-Kalkulation |
| `aggregation_key_source` | `bordero` \| `mastersendung` \| `position_group` \| `none` | Welcher Key für die Aggregation verwendet wurde |

Diese Felder sind in den Lane-Summary-CSVs ab 9b.3 implizit vorhanden
(9b.3 verwendet `mastersendung`-Key) und werden ab 9b.4 explizit ausgewiesen.

---

## §3 Muster-A-Erkennung

### Definition
Muster-A = **Fester ERKA-Indexaufschlag** von exakt 7,00 % auf den DLV-Basistarif
(nicht Teil des DLV, sondern separates Rider-Dokument / Email-Vereinbarung).

### Erkennungsformel
```
floater_pct = (betrag - toll) / tariff - 1
muster_a    = abs(floater_pct - 0.07) < 0.0015
```

**Begründung für floater_pct-Basis (nicht Ratio-Basis):**

Die nahe liegende Alternative — `ratio = betrag / (tariff + toll)` mit Fenster
`[1.0645, 1.0755]` — ist **zu breit** und erzeugt Falsch-Positive:
- PL-Zeilen März 2026 haben einen variablen Diesel-Floater von ~8,1 %
- Deren Ratio fällt ebenfalls in das Fenster, obwohl es sich um regulären
  Dieselzuschlag (kein ERKA-Indexaufschlag) handelt
- Der floater_pct-Ansatz trennt sauber: 7,00 % ± 0,15 % = ERKA-Indexaufschlag;
  8,1 % = normaler Dieselzuschlag

**Kreuzvalidierung:** Alle 50 bestätigten Muster-A-Zeilen liegen im Januar 2026
und stammen aus 5 Lanes (IE/PL/EE/SK/HR) — konsistent mit einem systemweiten
Aktivierungsdatum.

### Kundenbelegte Muster-A-Funde (Stand 9b.0)

| Kunde | KNR | Aktivierungsmonat | n Zeilen | Lanes |
|---|---|---|---|---|
| Fischerwerke | 409480 | März 2026 | ~31 | IT-Padova, IT-Copiano, FR, GB |
| EBM-Papst | 410844 | Januar 2026 | 50 | IE, PL, EE, SK, HR |
| GEZE GmbH | 406035 | offen (9b.3) | — | alle Lanes zu prüfen |

Unterschiedliche Aktivierungszeitpunkte pro Kunde deuten auf kundenspezifische
Vereinbarungen hin — gleicher Mechanismus, unterschiedliches Roll-out-Datum.

**Muster-A-Check in 9b.3:** Binning-Fenster `abs(floater_pct - 0.07) < 0.00005`
(enger als Standard 0,0015, da Diesel-Floater bei GEZE als separate Spalte
erkennbar ist und kein Falsch-Positiv-Risiko besteht). Fund → dritter Kunde
bestätigt Meta-Erkenntnis. Kein Fund → GEZE als Gegenbeleg ebenso dokumentieren.

---

## §4 Muster-B-Erkennung

### Definition
Muster-B = **Echte Unterfakturierung** — abgerechneter Betrag liegt deutlich
unterhalb des DLV-Erwartungswerts (tariff + toll) ohne erklärendes Floater-Muster.

### Erkennungsformel
```
delta_raw = betrag - (tariff + toll)
muster_b  = delta_raw < -10.0          # EUR
```

Der Schwellwert −10 EUR filtert Rundungsartefakte heraus.

### Bestätigte Muster-B-Funde (Stand 9a.4.2)

| Kunde | Lane | Datum | n_stpl | Betrag | Erwartet | Delta |
|---|---|---|---|---|---|---|
| EBM-Papst | EE-Lehmja | 2025-12-08 | 2 | 159,60 € | 260,00 € | −100,40 € |

Hypothese: Abrechnung erfolgte auf Basis von Stellplatz 1 statt Stellplatz 2
(159,60 € ≈ tariff[EE-75301][1] × 1.064).

---

## §5 Billing-Dimension-Ermittlung

### §5.0 Pflichtfeld `tonnage_source` und Audit-Schwelle

Jede beurteilte Zeile muss ein Pflichtfeld `tonnage_source` (bzw. allgemein
`billing_dim_source`) führen, das dokumentiert, woher die Billing-Dimension
(Tonnage, Stellplätze, LDM) stammt:

| Wert | Bedeutung |
|---|---|
| `direct` | Wert direkt aus Abrechnungsstrecken-Spalte, plausibel (>0) |
| `ldm_fallback` | Tonnage=0, Wert aus LDM abgeleitet (EBM-Konvention) |
| `unbeurteilbar` | Tonnage=0 UND LDM=0 → keine Billing-Basis vorhanden |

**20 %-Audit-Schwelle:** Wenn `unbeurteilbar`-Anteil > 20 % der Core-Zeilen,
ist der Befund mit einem Gate-Hinweis zu versehen. Der Befund ist **nicht gesperrt**
— die beurteilbaren Zeilen werden normal ausgewertet — aber der Report muss die
Lücke explizit ausweisen.

**GEZE 9b.2 Befund:** 1.109/4.349 Zeilen (25,5 %) haben Tonnage=0 und LDM=0.
Alle sind `unbeurteilbar`. Gate-1-Hinweis ist aktiv; 3.120 Zeilen (71,7 %) bleiben
für 9b.3 beurteilbar. Ursache der Tonnage=0-Zeilen ist unklar (möglicherweise
Positions-Aggregationsartefakt im AX-Export); Klärung bei ERKA/IT offen.

### Direkt aus Abrechnungsstrecken
Bevorzugte Quelle: Spalte `Abrechnungsstellplätze` (integer) bzw. `Tonnage (eff.)`.

### §5a LDM-Fallback bei NaN-Stpl

**Hintergrund:** In den EBM-Abrechnungsstrecken haben 165/397 Zeilen (41,6 %) den
Wert `NaN` in `Abrechnungsstellplätze`. Diese Zeilen haben aber gültige
`Abrechnungslademeter`-Werte. Ohne Fallback wären sie `unbeurteilbar`.

**Formel:**
```python
if pd.isna(stpl) and not math.isnan(ldm):
    n_stpl = max(1, math.ceil(ldm / 0.4))
n_stpl = max(1, min(n_stpl, 33))   # auf DLV-Maximum kappen
```

**Umrechnungsregel:** 1 Stellplatz = 0,4 LDM (EBM-Papst DLV-Konvention).

**Effekt:** Unbeurteilbar-Zeilen sinken von 208 → 58 (−75 %).

**Betroffene Routen (EBM 9a.4.2):**

| Route | NaN-Stpl / gesamt | LDM-Beispiel | abgeleiteter Stpl |
|---|---|---|---|
| Warszawa (Białołęka) | 74 / 82 | 13,6 | 34 → cap 33 |
| Senica | 40 / 47 | variabel | 1–33 |
| Buje | 16 / 23 | variabel | 1–33 |
| Lehmja | 3 / 23 | variabel | 1–33 |
| Logatec | 2 / 3 | variabel | 1–33 |

**Hinweis:** Diese Formel ist auf alle LDM-basierten DLV-Kunden übertragbar (z. B.
künftige HERMA-, CHT-Analyse), sofern die Konvention 1 Stpl = 0,4 LDM gilt.

---

## §6 DLV-Versions-Fallback

Bei Zeilen im Zeitfenster `in_dlv_2025` (10.10.2025 – 28.02.2026) wird zuerst das
DLV vom 10.10.2025 geprüft. Falls die Route dort nicht vorhanden ist (z. B. GB,
F92/Rathmullan), wird auf das aktuellste verfügbare DLV (`fallback_latest`) zurück-
gegriffen. Zeilen ohne jede DLV-Abdeckung erhalten `dlv_fallback = 'no_dlv'` und
fließen nicht in Calculator-Checks ein.

---

## §6a Sanity-Gates für Calculator-Binnentests

Ein Calculator gilt erst dann als **validiert**, wenn alle fünf Gates bestanden sind:

| Gate | Prüfung | Fehlermodus |
|---|---|---|
| 1 | Mindest-Abdeckung: ≥ 2 Fälle pro Land/Zone-Kombination | Blind Spots in Zonen-Lookup |
| 2 | Minimum-Floor: mind. 1 Fall, der durch das Minimum gedeckelt wird | Minimum-Logik nie aktiviert |
| 3 | Rate-Bereich: mind. 1 Fall mit rate×billing_kg > minimum | Rate-Berechnung nie aktiv |
| 4 | Gewichtsband-Grenze: mind. 1 Fall exakt auf einer Band-Grenze (z. B. billing_kg=300) | Off-by-one in Band-Lookup |
| 5 | **Bedingte Komponenten nicht-null**: Alle optionalen Surcharges/Floater/Währungen müssen in mind. 1 Testfall einen Wert > 0 liefern | Stille Nullen durch Parser-Bug |

**Gate 5 — Hintergrund (Präzedenzfall GEZE 9b.1):**

Etappe 5e validierte den GEZE-Calculator mit 6/6 grünen Tests. Der CHF-Floater
schien zu funktionieren. Tatsächlich las `_parse_chf_floater` Spalten 0–3 statt
der korrekten 2–5, lieferte eine leere Tabelle, und `chf_amount` war immer 0.
Die 6 Testfälle enthielten einen CH-Fall mit Rate 1.065 — der fällt in das
Null-Prozent-Band (≥ 1.021), sodass auch mit korrektem Parser `chf_amount=0`
erwartet worden wäre. Grüner Test, falscher Grund.

**Konsequenz für künftige Calculator-Validierungen:**

| Calculator | Bedingte Komponente | Gate-5-Testanforderung |
|---|---|---|
| GEZE | CHF-Floater | mind. 1 CH-Fall mit CHF/EUR < 1.021 (nicht-null Band) |
| HERMA | VL-Aufschlag (Vorlauf) | mind. 1 Fall mit VL > 0 |
| HELU | Country-Fallback | mind. 1 Fall, der Fallback auslöst |
| CHT | Zonen-Lookup (Spanien, Italien) | mind. 1 Fall je Zone-Lookup-Pfad |
| Hornschuch | Formel-Varianten | mind. 1 Fall je Formelzweig |

---

## §7 Altzahl-Validierung und Retroaktiv-Liste

### EBM-Papst — Revision 9a.1.b

Bekannte Altzahl aus Vorgänger-Analyse 9a.1.b: **−18.517 EUR** (scheinbare Unter-
fakturierung EBM gesamt).

Ursache des Artefakts:
1. IE Eircode-PLZ-Matching-Lücke → viele Zeilen als `no_dlv` geführt → fehlende
   Delta-Einträge → negative Gesamtsumme
2. Kein Floater-Treatment → Erwartet > Ist auf allen Zeilen mit positivem Floater

Korrekte Gesamt-Delta (9a.4.2, 339 beurteilbare Zeilen): **+41.283 EUR** — alle
positiv, erklärt durch Floater-Aufschlag auf DLV-Tarif. Keine systematische
Unterfakturierung auf Lane-Ebene außer Muster-B (1 Zeile, −100,40 EUR).

### GEZE — Retroaktiv-Eintrag 5e (Commit 23d6a1a)

**Status: Funktional invalide, obwohl Tests grün.**

Commit 23d6a1a ("Etappe 5e: GEZE calculator, 6/6 within 2%") wurde im
CHF-Parser-Bug-State freigegeben. Die 6 Validierungssendungen enthielten einen
CH-Fall (PLZ 5436, CHF-Rate 1.065), der zufällig in das Null-Prozent-Band fällt.
Kein Testfall prüfte einen nicht-null CHF-Floater.

**Post-9b.1-Prüfung erforderlich:**
- Waren die 6 Validierungssendungen aus 5e allesamt non-CH oder im Null-Band?
  → Wenn ja: keine echte Drift in den 5e-Zahlen, nur stille Null für CH.
  → Wenn nein: 5e-Ergebnisse für CH-Zeilen nach unten verzerrt (chf_amount fehlte).
- Die 9b.3-Analyse wird zeigen, ob AX-Abrechnungszeilen für CH einen
  floater_pct > 0 aufweisen — das ist der indirekte Nachweis, dass ERKA
  den CHF-Floater korrekt berechnet hat (und 5e ihn nur nicht prüfte).

**Empfehlung:** 5e-Commit nicht rückwirkend ändern; stattdessen 9b.1-Fix
(dd3d558) als Nachfolge-Commit dokumentieren. Keine Zahlen aus 5e zitieren,
bis 9b.3 den CH-Floater im AX-Betrag bestätigt hat.

**9b.3-Ergebnis:** 54/95 CH-Gruppen zeigen Band-Match (51 × Neutralband
1.021–1.075 → chf_amount=0; 3 × aktive Bänder < 1.021 → CHF-Floater aktiv).
41 CH-Gruppen ohne Band-Match: Diesel-Überlagerung oder multiperiodische Batches.
→ Bestätigt: ERKA hat CHF-Floater korrekt in `Erlöse Fracht` eingerechnet;
5e-Commit-Bug hatte keine Auswirkung auf die tatsächliche Abrechnung (ERKA
rechnete korrekt), nur auf die Validator-Prüfung.

### EBM-Papst und Fischerwerke — Retroaktiv-Prüfung Aggregationsebene (post-9b.3)

**Offene Frage:** Wurden EBM Muster-A-Treffer (50 Zeilen, Jan 2026) und Fischerwerke
Muster-A-Treffer (~31 Zeilen, März 2026) auf Positions- oder Sendungs-Ebene berechnet?

**EBM 9a.4.2-Analyse (Commit c4bcad9):**
- Eingabedaten: Abrechnungsstrecken `EBM.xlsx`, eine Zeile pro Eintrag
- Aggregations-Key: `Nach Ort` (Ortsname) → DLV-Route-Key
- Muster-A-Check: direkt auf Zeilen-Level (nicht aggregiert)
- Risiko: Falls EBM-Daten Positions-Level sind, könnten die 50 Muster-A-Treffer
  auf denselben 10–15 Sendungen basieren (Zahl des Findings wäre identisch, aber
  fp-Statistik wäre sendungsseitig robuster darzustellen)

**Fischerwerke (Muster-A ~31 Zeilen, März 2026):** Aggregationsebene noch nicht
dokumentiert; Risiko analog EBM.

**Prüfschema:**
1. Zähle eindeutige `Ausgangsbordero` in den EBM/Fischerwerke Muster-A-Zeilen
2. Wenn `n_unique_bordero << n_zeilen`: Positions-Level → retroaktiv auf
   Sendungs-Ebene aggregieren, Muster-A und delta_sum neu berechnen
3. Wenn `n_unique_bordero ≈ n_zeilen`: Sendungs-Level → kein Retroaktiv-Bedarf

**Wichtig:** Das Muster-A-Zählkriterium (`abs(fp − 0.07) < 0.0015`) ist auf
Positions-Ebene identisch anwendbar, sofern der 7 %-Floater sendungseinheitlich
aufgeschlagen wird (alle Positionen derselben Sendung haben denselben Floater).
In diesem Fall ändert Sendungs-Aggregation die Anzahl Treffer nicht, nur die
Granularität der delta_sum-Darstellung.

**Status:** Offen. Prüfung in Etappe 9c.x (EBM Retroaktiv) oder als separater
Retroaktiv-Commit vor Abschluss-Report.

---

## Changelog

| Version | Datum | Etappe | Änderung |
|---|---|---|---|
| 1.0 | 2026-04-20 | 9a.4.2 | Initiale Erstellung; §3 floater_pct-Basis für Muster-A; §5a LDM-Fallback |
| 1.1 | 2026-04-20 | 9b.0 | §2 GEZE-Block: Maut-inklusiv, CHF-Floater als EUR-Surcharge, Reverse-Engineer-Ansatz; §3 GEZE-Zeile + engeres Muster-A-Binning für 9b.3 |
| 1.2 | 2026-04-20 | 9b.1 | §6a Sanity-Gate 5 (bedingte Komponenten nicht-null); §7 Retroaktiv-Eintrag GEZE 5e (23d6a1a im Parser-Bug-State freigegeben) |
| 1.3 | 2026-04-20 | 9b.2 | §5.0 tonnage_source-Pflichtfeld + 20%-Audit-Schwelle; GEZE-Befund 25,5% Tonnage=0 dokumentiert |
| 1.4 | 2026-04-20 | 9b.3 | §2a Positions-Level vs Sendungs-Level: Aggregations-Key-Hierarchie, Muster-B-Aggregationsartefakt-Flag, Pflichtfelder aggregation_level/key_source; §7 EBM+Fischerwerke Retroaktiv-Aggregationsebene-Prüfung; §7 GEZE 9b.3-Ergebnis (CHF-Band-Match) |
