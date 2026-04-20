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
- `pre_dlv` — vor DLV-Gültigkeitsbeginn (kein aktives DLV; kein Calculator-Check)
- `pre_dlv_2026` — Leistungsdatum vor 01.01.2026 bei Kunden, deren ältestes
  verfügbares DLV erst 2026 beginnt (z. B. CHT: DLV-Start 2026-01-01). Diese
  Zeilen sind nicht unbeurteilbar — sie benötigen ein 2025-DLV, das ggf. noch
  nicht extrahiert/gepflegt ist. fp-Werte zeigen systematischen Versatz vs.
  2026-DLV, der als DLV-Version-Gap zu dokumentieren ist, nicht als Abweichung.
- `in_dlv` / `in_dlv_2025` / `in_dlv_2026` — innerhalb eines Gültigkeitsfensters
- `in_dlv_2025_fallback` — Datum nach DLV-Ablauf, aber kein Nachfolge-DLV
  vorhanden; 2025-DLV bleibt aktiv (z. B. GEZE: kein 2026-DLV)
- `post_dlv` — nach DLV-Ablauf mit Nachfolge-DLV (Fallback explizit deaktiviert)

Calculator-Checks laufen **ausschließlich** auf `in_dlv`-Zeilen. `pre_dlv_2026`-
Zeilen werden im Report mit Versatz-Kennzeichnung ausgewiesen (kein Calculator-
Befund, aber Indikator für fehlendes 2025-DLV).

---

## §2 DLV-Tarif-Formate

### §2.0 Standard-Formeln (ab v1.5)

#### Diesel-Regel (methodikweit verbindlich)

**Diesel ist IMMER eine separate Komponente** — sie erscheint in den BI-Daten als
eigene Spalte `Erlöse Diesel` und fließt **nie** in `floater_pct` ein.

```
# Fracht-Abweichung:
floater_pct  = (Erlöse_Fracht − basispreis) / basispreis

# Diesel-Abweichung (separat):
diesel_delta = Erlöse_Diesel − diesel_soll
# diesel_soll = 0, wenn DLV keinen Diesel-Satz modelliert
# diesel_soll = calculierter Satz, wenn DLV Dieselfloater enthält
```

Diese Trennung verhindert, dass variable Dieselzuschläge als Muster-A-Treffer
fehlinterpretiert werden (vgl. §3 Begründung, PL-Zeilen März 2026).

#### Zwei-Fall-Regel für weitere Komponenten (Maut, Surcharges, Währung)

| Fall | Bedingung | Behandlung |
|---|---|---|
| **A — unbundled** | Komponente im Calculator als eigener Wert UND BI-Spalte zuverlässig gefüllt | Eigenes Delta: `komponente_delta = Erlöse_X − soll_X` |
| **B — all_in** | Komponente im Calculator inkludiert (z. B. Maut in basispreis) ODER BI-Spalte leer/unzuverlässig | In `floater_pct` enthalten; Komponentenliste dokumentieren |

**Pflichtfelder pro Kunden-Block:**

| Feld | Werte | Bedeutung |
|---|---|---|
| `pricing_mode` | `unbundled` \| `all_in` \| `hybrid` | Dominant angewendete Behandlung |
| `all_in_components` | Liste | Welche Komponenten in `floater_pct` eingebettet sind |

Beim Modus `hybrid` gilt `unbundled` für die aufgeführten Einzelkomponenten und
`all_in` für den Rest.

---

### Fischerwerke (Stellplatz-basiert)
- Lookup-Tabelle: Anzahl Stellplätze → Flat-Rate per Sendung
- Per-Route-Dateien (eine Datei pro Abrechnungsrelation)
- Quelle: `Fischerwerke/DLVs & Tarife/`
- `pricing_mode: all_in` — kein separates Maut/Diesel im DLV modelliert
- `all_in_components: [maut, diesel]`

### EBM-Papst (Palletspace-Matrix, LDM-basiert)
- Breite Matrix: Zeile = Route (PLZ-Key), Spalte = Stellplätze 1–33 + FTL
- Zwei Sheets pro DLV-Datei: `Tariffs_DE_EU` (Frachtpreis) + `Toll_DE_EU` (Maut)
- Datenquelle: **Abrechnungsstrecken** `EBM.xlsx` (nicht BI-Daten) — Spalten:
  `betrag` (Fracht + Floater, kein Diesel), `toll` (DLV-Maut)
- `pricing_mode: hybrid` — Maut unbundled (aus `Toll_DE_EU`); Diesel fehlt in
  Abrechnungsstrecken-Quelle (kein `Erlöse_Diesel`-Äquivalent), muss retroaktiv
  geprüft werden (→ §7 EBM-Diesel-Retroaktiv)
- Abrechnungsformel (Abrechnungsstrecken):
```
floater_pct = (betrag − toll) / tariff − 1
# toll aus DLV-Matrix; tariff aus DLV-Matrix
# Diesel: Abrechnungsstrecken-Quelle hat keine separate Diesel-Spalte
#         → falls Diesel in betrag eingebettet: floater_pct enthält Diesel-Anteil
#         → falls Diesel nicht verrechnet: floater_pct = reiner Floater
```
- `all_in_components: [diesel]` — bis Retroaktiv-Check (§7) bestätigt ob diesel=0

### Route-Key-Extraktion (EBM)
- **IE/GB** (Eircode-Länder): 3-stelliger Alpha-Code — `'IE-A92 FY90'` → `'A92'`
- **PLZ-Länder** (PL/SK/SI/HR/EE): Vollständiger PLZ-String — `'PL-03-236'` → `'PL-03-236'`
- **Merged-Einträge**: Pipe-separated → nimm erstes — `'EE-75301|EE-75306'` → `'EE-75301'`

### GEZE GmbH (Gewichts-basiert, EUR/100 kg, Maut all_in)
- `pricing_mode: hybrid`
- `all_in_components: [maut]` — Maut in `basispreis` inkludiert, kein separates `Erlöse_Maut`
- Diesel: Fall A unbundled — `Erlöse_Diesel` in BI-Daten vorhanden; `diesel_soll = 0`
  (DLV modelliert keinen Diesel-Satz); `diesel_delta = Erlöse_Diesel − 0`
- CHF-Floater: Fall B all_in — in `Erlöse_Fracht` eingebettet; via Reverse-Engineer
  auf CHF-Band-Tabelle gemappt

**DLV-Struktur:** Sheet "Exporttarife" — Country-Blocks mit Zonen-Zeilen.
Pro Zone: Minimum-Betrag + Gewichtsbänder (bis 300 kg, bis 500 kg, … bis 3.000 kg)
mit Rate EUR/100 kg. Länder: PT, GB, IE, IT, FR, AT, ES, CH.
Gültig: 2025-01-01 – 2025-12-31 (kein separates 2026-DLV; 2025-Fallback bleibt aktiv).

**Abrechnungsformel:**
```
billing_kg   = max(100, ceil(tonnage_kg / 100) * 100)
basispreis   = max(minimum_zone, rate_per_100kg × billing_kg / 100)   # EUR, Maut inkl.
chf_amount   = basispreis × chf_floater_fraction                       # EUR, nur CH
fracht_soll  = basispreis + chf_amount

floater_pct  = (Erlöse_Fracht − basispreis) / basispreis
# non-CH: floater_pct ≈ CHF-Neutralband (≈0) + variabler Diesel-Floater
# CH:     floater_pct ≈ CHF-Floater-Fraktion (Diesel separat in Erlöse_Diesel)
diesel_delta = Erlöse_Diesel − 0     # diesel_soll=0, DLV hat keinen Diesel-Block
```

**CHF-Floater (nur Empfänger Land = CH):**
Der CHF/EUR-Wechselkurs zum Sendungsdatum dient als **Lookup-Key** in die
Prozentband-Tabelle (Sheet "CH-Währungsfloater" im DLV). Die Tabelle gibt eine
EUR-Prozent-Fraktion auf `basispreis` zurück — kein Währungsumtausch, alles in EUR.

Bandbreite: **CHF/EUR 1,021 – 0,88** in 14 Stufen;
Stückgut (≤ 3.000 kg): 0 % – 9,18 %; Komplett (> 3.000 kg): separates Staffel.

**Reverse-Engineer-Ansatz für 9b.3:** `floater_pct` aus Billing-Daten berechnen →
CHF-Bandtabelle rückwärts → konsistente Bandeinordnung. 9b.3-Ergebnis: 51/95
CH-Gruppen im Neutralband, 3 aktive Bänder, 41 Diesel-Überlagerung.

**Zone-Lookup:** Länderspezifische PLZ-Präfix-Tabellen im Calculator (`geze.py`);
IE = immer Zone 1; GB = Postcode-Area (WS/B/CV… → Zone 1, G/EH… → Zone 3, BT → Zone 4).

### CHT Germany GmbH (Gewichts-basiert, Dual-Mode, Maut unbundled)
- `pricing_mode: hybrid`
- Maut: Fall A unbundled — 0,56 EUR/100 kg (DE-Maut 0,50 + AT-Maut 0,06)
  aus Calculator; `Erlöse_Maut` in BI-Daten vorhanden (empirisch zu prüfen)
- Diesel: `Erlöse_Diesel` laut Calculator-Code = 0 in BI-Daten; Diesel via
  separaten Sonder-Dieselfloater (nicht im DLV modelliert) → `diesel_delta = 0`
- `all_in_components: []` — keine Komponente all_in (außer Diesel=0)

**DLV-Struktur:** Sheet "Ex- und Import Italien" — 8 Zonen, 2 Preismodi.
Gültig: 2026-01-01 – 2026-12-31. Herkunft: DE-72072 Tübingen.
Länder in Scope: IT (cht.py), weitere (AT/BE/ES/GR via dlv_tariffs.py).

**Dual-Mode-Umschaltpunkt: 1.000 kg (Aktual-Gewicht, nicht Billing-Gewicht)**
```
if actual_kg ≤ 1000:   # per-Sendung (Pauschalpreis je Gewichtsband)
    basispreis = band.rates[zone]
else:                   # per-100-kg
    billing_kg = max(100, ceil(actual_kg / 100) * 100)
    basispreis = rate_per_100kg × billing_kg / 100
maut_soll = 0.56 × billing_kg / 100                   # EUR

floater_pct  = (Erlöse_Fracht − basispreis) / basispreis
maut_delta   = Erlöse_Maut − maut_soll
diesel_delta = Erlöse_Diesel − 0
```

**Zone-Lookup (IT):** Erste 2 Stellen der 5-stelligen IT-PLZ → Zone 1–8.
Override: PLZ-Präfix 238/239 → Zone 1 (vor generischem Präfix 23 → Zone 4 geprüft).

**Sonder-PLZ (all_in_special):** PLZ 20052 (Arcor Monza) und 20098 (Sesto Ulteriano)
→ eigene DLV-Datei; immer per-100-kg mit Mindestgebühr 55,46 EUR/Sendung.

**CHT Diesel/Maut-Vereinbarung per Land (B-Check 9c.0, empirisch):**

| Land | `diesel_mode` | `maut_mode` | Erlöse_Diesel >0 | Erlöse_Maut >0 |
|---|---|---|---|---|
| IT | `not_contracted` | `unbundled` | 0/158 (0 %) | 157/158 (99 %) |
| AT | `not_contracted` | `unbundled` | 0/36 (0 %) | 34/36 (94 %) |
| ES | `not_contracted` | `unbundled` | 0/114 (0 %) | 111/114 (97 %) |
| DE | `not_contracted` | `unbundled` | 0/11 (0 %) | 3/11 (27 %) |
| BE | `contracted` | `unbundled` | 256/258 (99 %) | 256/258 (99 %) |
| GR | `contracted` | `unbundled` | 102/102 (100 %) | 102/102 (100 %) |

Maut ist kunden-weit Fall A (unbundled) bei CHT — `Erlöse_Maut` zuverlässig gefüllt
für alle relevanten Länder. Maut-Delta für IT (9c.0): mean=−0,29 EUR, p50=0,000.

**9c.0 IT fp-Befund (pre_dlv_2026-Diagnose):**

| Cluster | n | fp-Bereich | Datum | Interpretation |
|---|---|---|---|---|
| fp ≈ 0,000 | 64 | ±0,001 | Jan–Mär 2026 | In-DLV exakter Match |
| fp ≈ −0,020 | 80 | −0,022 bis −0,018 | Okt–Dez 2025 | `pre_dlv_2026`: 2025-Raten ~2 % günstiger |
| fp ≈ +0,070 | 0 | — | — | Kein Muster-A bei CHT |

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
- **Aggregationsartefakt-Flag (streng):** Muster-B-Kandidaten mit `n_pos > 5`
  und `fp > 0` auf Gruppenebene sind als "Aggregationsartefakt — Sendungs-
  Aggregation erforderlich" zu kennzeichnen und **nicht** als bestätigte
  Unterfakturierung zu werten. (GEZE 9b.3: GB/WS13 8SY, n_pos=27, fp=−0,395)
- **Aggregationsartefakt-Flag (weich):** Muster-B-Kandidaten mit
  `n_pos > 20 AND |delta_raw| < positions_min_fee × n_pos` sind als
  "Aggregation-Minimalgebühren-Verdacht — manuelle Sendungs-Disaggregation
  empfohlen" zu markieren. Hintergrund: Wenn eine Gruppe aus 30 kleinen
  Positionen besteht, von denen jede einzeln die DLV-Mindestgebühr ausgelöst
  hätte, ist der aggregierte Soll-Basispreis systematisch zu niedrig. Erst wenn
  `delta_raw_per_sendung > delta_raw_per_positions` kann auf echte
  Unterfakturierung geschlossen werden. Anwendungsfall: HERMA/Hornschuch-
  Rollouts mit vielen kleinen Positionen je Rechnungsempfänger.

### Pflichtfelder (ab v1.4)

| Feld | Werte | Bedeutung |
|---|---|---|
| `aggregation_level` | `sendung` \| `position` | Ebene der Billing-Kalkulation |
| `aggregation_key_source` | `bordero` \| `mastersendung` \| `position_group` \| `none` | Welcher Key für die Aggregation verwendet wurde |

Diese Felder sind in den Lane-Summary-CSVs ab 9b.3 implizit vorhanden
(9b.3 verwendet `mastersendung`-Key) und werden ab 9b.4 explizit ausgewiesen.

### Diesel/Maut-Modus pro (Kunde, Land) (ab v1.6)

Diesel und Maut sind **nicht kunden-global**, sondern **landen-spezifisch** vereinbart.
Innerhalb eines Landes gilt: entweder immer verrechnet (`contracted`) oder nie (`not_contracted`).

**Regel:**
```
diesel_mode(kunde, land) ∈ {"contracted", "not_contracted"}
maut_mode(kunde, land)   ∈ {"unbundled", "all_in"}
```

**Sanity-Check:**
- `diesel_mode = "contracted"` UND `Erlöse_Diesel = 0` in > 5 % der Zeilen
  → Flag `"diesel_expected_missing"` — manuelle Prüfung (Storno? Korrekturbuchung?)
- `diesel_mode = "not_contracted"` UND `Erlöse_Diesel > 0` in > 0 Zeilen
  → Flag `"diesel_unexpected"` — mögliche Falschbuchung

**Einzelfall-all_in-Ausnahme:** Innerhalb eines `(kunde, land)` mit
`diesel_mode = "contracted"` können einzelne Zeilen `Erlöse_Diesel = 0`
**und** `Erlöse_Maut = 0` aufweisen, während `Erlöse_Fracht` dem Gesamtbetrag
vergleichbarer Zeilen entspricht. Diese Zeilen erhalten das Flag
`pricing_mode: all_in_exception` — kein Datenfehler, sondern Buchungsformat-
Ausnahme (Fracht+Diesel+Maut in einem einzigen Fracht-Betrag gebündelt).

Schwelle: ≤ 1 % der Zeilen im `(kunde, land)`-Scope → Einzelfall-Ausnahme.
Bei > 1 %: keine Ausnahme mehr, sondern Hinweis auf strukturelle Änderung →
`diesel_mode` für diese Kombination neu evaluieren.

**Präzedenzfall CHT (9c.0 B-Check):** BE PE PLZ 8550 (0,78 % von 258 BE-Zeilen)
hat Diesel=0 und Maut=0 bei `Erlöse_Fracht = 167,91` ≈ Split-Gesamtbetrag
vergleichbarer Zeilen (PLZ 8560: 146,96+14,64+6,38 = 167,98). Flag
`all_in_exception` gesetzt.

**Präzedenzfall CHT (9c.0 B-Check):** BE und GR haben Diesel vereinbart (Erlöse_Diesel
immer > 0); IT, AT, ES, DE nicht (immer = 0). 2 BE-Zeilen ohne Diesel (von 258) →
Flag `"diesel_expected_missing"`, Einzelfall-Abweichungen (Storno/Korrektur), kein Blocker.

---

## §3 Muster-A-Erkennung

### Definition
Muster-A = **Fester ERKA-Indexaufschlag** von exakt 7,00 % auf den DLV-Basistarif
(nicht Teil des DLV, sondern separates Rider-Dokument / Email-Vereinbarung).

### Erkennungsformel
```
# Standard (BI-Daten, ab v1.5):
floater_pct = (Erlöse_Fracht − basispreis) / basispreis
muster_a    = abs(floater_pct - 0.07) < 0.0015

# EBM-Sonder-Block (Abrechnungsstrecken-Quelle, kein Erlöse_Fracht):
floater_pct = (betrag − toll) / tariff − 1
# betrag = Fracht+Floater; toll = DLV-Maut; tariff = DLV-Tarif
# Retroaktiv offen: ob Diesel in betrag eingebettet (→ §7 EBM-Diesel)
```

**Begründung für floater_pct-Basis (nicht Ratio-Basis):**

Die nahe liegende Alternative — `ratio = Erlöse_Fracht / basispreis` mit Fenster
`[1.0645, 1.0755]` — ist **zu breit** und erzeugt Falsch-Positive:
- PL-Zeilen März 2026 haben einen variablen Diesel-Floater von ~8,1 %
- Deren Ratio fällt ebenfalls in das Fenster, obwohl es sich um regulären
  Dieselzuschlag (kein ERKA-Indexaufschlag) handelt
- Der floater_pct-Ansatz (`Erlöse_Fracht − basispreis`) trennt sauber: Diesel
  ist in §2.0 aus `floater_pct` herausdefiniert; 7,00 % ± 0,15 % = ERKA-
  Indexaufschlag; Diesel-Floater erscheint ausschließlich in `diesel_delta`

**Kreuzvalidierung:** Alle 50 bestätigten Muster-A-Zeilen liegen im Januar 2026
und stammen aus 5 Lanes (IE/PL/EE/SK/HR) — konsistent mit einem systemweiten
Aktivierungsdatum.

### Kundenbelegte Muster-A-Funde (Stand 9b.0)

| Kunde | KNR | Aktivierungsmonat | n Zeilen | Lanes |
|---|---|---|---|---|
| Fischerwerke | 409480 | März 2026 | ~31 | IT-Padova, IT-Copiano, FR, GB |
| EBM-Papst | 410844 | Januar 2026 | 50 | IE, PL, EE, SK, HR |
| GEZE GmbH | 406035 | nicht nachweisbar (9b.3) | 0 | kein Treffer in POST-Daten |
| CHT Germany | 486073 | offen (9c.3) | — | alle Lanes zu prüfen |

Unterschiedliche Aktivierungszeitpunkte pro Kunde deuten auf kundenspezifische
Vereinbarungen hin — gleicher Mechanismus, unterschiedliches Roll-out-Datum.
GEZE zeigt keinen Muster-A-Befund in POST-Daten (mögliches Roll-out nach April 2026
oder keine ERKA-Vereinbarung).

---

## §3a Sonder-PLZ-Aufschlag (ab v1.7.1)

### Definition

Ein **Sonder-PLZ-Aufschlag** ist ein PLZ-spezifischer Festaufschlag auf den
DLV-Basispreis, der **nicht im DLV-Dokument ausgewiesen** ist. Er erscheint als
konsistenter positiver `fp`-Wert bei ≥ 2 Positionen derselben PLZ, während andere
PLZs desselben Kunden/Landes keinen oder geringen fp zeigen.

**Abgrenzung zu Muster-A:**

| Merkmal | Muster-A | Sonder-PLZ-Aufschlag |
|---|---|---|
| Granularität | Kunden-/Lane-übergreifend | PLZ-spezifisch |
| Wert | exakt +7,00 % ± 0,15 % | variabel +6–8 % (beobachtet) |
| Ursache | ERKA-Indexvereinbarung | Thermo-/Sondergebiets-/Gefahrgut-Zuschlag |
| Erkennung | abs(fp − 0.07) < 0.0015 | ≥ 2 Pos. derselben PLZ, abs(fp − fp_plz) < 0.005 |

### Erkennungsregel

```python
# Pro (Kunde, Land, PLZ): wenn ≥ 2 Positionen mit fp-Konsistenz
plz_fp_mean = mean(fp für Positionen mit dieser PLZ)
plz_fp_std  = std(fp für Positionen mit dieser PLZ)
if plz_fp_std < 0.005 and abs(plz_fp_mean) > 0.03 and n >= 2:
    flag = "sonder_plz_aufschlag"
```

Positionen mit `sonder_plz_aufschlag` werden als **§8 (Klärungsfrage)** markiert,
nicht als bestätigte Billing-Abweichung. Hypothese: Thermozuschlag,
Gefahrgut-Handling oder PLZ-gebundener Sondertarif, der im DLV-Basispreis
fehlt — mögliche Calculator-Lücke.

**Retroaktiv-Check bei HELU/HERMA/Hornschuch:** PLZ-Cluster mit fp > 0.03 und
Std < 0.005 prüfen. Falls gefunden: §8-Eintrag analog zu den CHT-Fällen.

### Bekannte Sonder-PLZ-Fälle (Stand 9c.2a)

| Kunde | Land | PLZ | fp | n | Hypothese |
|---|---|---|---|---|---|
| CHT | IT | 20098 | +0,061 | 3 | Thermozuschlag Sesto Ulteriano / Milan |
| CHT | BE | 8540 | +0,063 | 1 | Thermozuschlag Kortrijk-West / Westflandern |
| CHT | BE | 8560 | +0,063 | 1 | Thermozuschlag Kortrijk-West / Westflandern |
| CHT | BE | 8400 | +0,064 | 1 | Thermozuschlag Kortrijk-West / Westflandern |

Alle drei BE-PLZ liegen im Großraum Kortrijk (Westflandern) und zeigen
konsistent +6,3–6,4 %. Zusammen mit IT/20098 (+6,1 %) deutet das auf
einen **Thermo-/Sondergebietszuschlag von 75 EUR** hin, der auf den
DLV-Basispreis prozentual skaliert wirkt, aber im DLV-Dokument nicht
aufgeführt ist.

**Sonderfall 924248/PLZ 7700 (+18,7 %, 1 Position):** Abweichend von den
+6 %-Fällen — zu hoch für Sonder-PLZ-Aufschlag, zu konsistent für Rauschen.
Mögliche FTL-/Gefahrgut-/Priority-Sondertarifebene. Im 9c.4-Report als
eigenständige Prioritäts-§8-Position, nicht mit Sonder-PLZ-Fällen zusammengeführt.

### AX-Raten-Präzision (Hinweis ab v1.7.1)

AX speichert DLV-Tarifsätze möglicherweise mit reduzierter Dezimalstellenpräzision
(2dp statt 4dp des DLV-Dokuments). Dieses Muster wurde für CHT/BE bestätigt, für
CHT/IT nicht (IT-Raten in AX: volle 4dp-Präzision). Konsequenz:

- **Pro Land validieren:** Integration-Test zeigt, ob AX-Raten 2dp oder 4dp haben.
  Indikation: Systematisches fp ≈ −0,0002 (nicht zufällig) bei `exact_dlv`-RNs.
- **Calculator anpassen:** Wenn AX 2dp speichert, Calculator-Raten auf 2dp runden
  (damit ±0,01-EUR-Kriterium anwendbar bleibt).
- **§8-Dokumentation:** "AX speichert <Land>-Tarifsätze mit 2 Dezimalstellen;
  DLV notiert 4dp. Calculator folgt AX-Präzision. KLÄRUNGSFRAGE: 2dp vertragskonform?"
- **Retroaktiv-Prüfung:** Für alle weiteren CHT-Länder (AT/ES/GR) und Welle-3-
  Kunden im Integration-Test prüfen, ob AX-Präzision 2dp oder 4dp.

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
| CHT | Dual-Mode-Umschalt + Maut | mind. 1 Fall per-Sendung + 1 Fall per-100kg + 1 Fall mit Maut-Delta ≠ 0 |
| Hornschuch | Formel-Varianten | mind. 1 Fall je Formelzweig |

---

## §6b RN-Level-Faktor-Detection (Gate 6, ab v1.7)

### Motivation

In einigen Kunden-Ländern (erstmals CHT/BE, 9c.2a) weichen die tatsächlichen
Erlöse_Fracht-Werte systematisch vom 2026-DLV ab — aber nicht über alle Zeilen
gleichmäßig, sondern **pro Rechnungsnummer (RN) konsistent**. Das heißt: innerhalb
eines RN haben alle Positionen denselben relativen Abstand zum berechneten
Basispreis. Ursache: unbekannter Mechanismus auf Rechnungsebene (möglicherweise
eine quartalsbezogene Frachtraten-Anpassung, die in AX je Invoice-Batch
unterschiedlich eingestellt wurde).

Dieses Muster ist **kein Calculator-Bug** und **kein Muster-A-Treffer** — es ist ein
strukturelles Billing-Artefakt, das vor der Pass-Rate-Berechnung identifiziert und
separat ausgewiesen werden muss.

### Abgrenzung zu anderen Mustern

| Muster | Granularität | Wert | Richtung | Bedeutung |
|---|---|---|---|---|
| Muster-A | Lane-übergreifend | exakt +7,00 % ± 0,15 % | positiv | ERKA-Indexaufschlag |
| RN-Level-Faktor | pro RN | beliebig (beobachtet: −0,7 % bis +3,0 %) | positiv oder negativ | Unbekannter RN-Mechanismus |
| Rundungsartefakt | pro Position | < 0,01 EUR absolut | beliebig | Dezimalstellen-Differenz |
| Aggregationsartefakt | pro Gruppe | fp > 0 bei n_pos > 5 | positiv | Sendungs-Ebene fehlt |

### Classifier-Logik (Gate 6)

Vor der Pass-Rate-Berechnung wird **pro RN** geprüft:

```python
rn_factor = median(erloes_fracht / basispreis)   # ≈ 1 + fp
rn_std    = std(erloes_fracht / basispreis)

if rn_std < 0.0005:                        # alle Positionen im RN gleichmäßig
    if abs(rn_factor - 1.0) < 0.0005:     # Faktor ≈ 1 → exaktes DLV
        flag = "exact_dlv"                 # → zählt in Pass-Rate
    else:
        flag = "rn_level_adjustment"       # → aus Pass-Rate exkludiert
else:                                      # heterogene Abweichungen im RN
    flag = None                            # → per-Position ±0.01 EUR Check
```

**Pass-Kriterium (Gate 6):** ≥ 90 % der Positionen mit `flag is None` oder
`flag == "exact_dlv"` haben `|Erlöse_Fracht − basispreis| ≤ 0,01 EUR`.

Positionen mit `flag == "rn_level_adjustment"` werden:
1. **Aus dem Pass-Rate-Zähler exkludiert** (weder Zähler noch Nenner)
2. **Im §8-Abschnitt des Kunden-Reports gelistet** (pro RN: Faktor, n, delta_sum)
3. **Nicht als Unterfakturierung gewertet**, solange keine Kontext-Information
   (z. B. ein abweichendes Sonder-DLV) vorliegt

### §8-Listenformat für RN-Level-Adjustment-Fälle

```
RN <xxx>: rn_factor=<f>, n=<n>, delta_sum=<EUR>
  → Faktor <f-1:+.2%> auf alle <n> Positionen
  → Hypothese: [quarterly_fracht_adjustment | AX_config_drift | andere]
  → Priorität: [hoch (|f-1| > 2%) | mittel | niedrig]
```

**CHT/BE 9c.2a Befund:**

| RN | rn_factor | n | delta_sum | Prio |
|---|---|---|---|---|
| 924081 | 1.0295 | 11 | +49,8 EUR | hoch (Overbilling) |
| 924248 | 1.0290 | 13 | +60,0 EUR | hoch (Overbilling) |
| 924069 | 0.9931 | 16 | −20,6 EUR | niedrig (Underbilling) |
| 924102 | 1.0050 | 7 | +7,6 EUR | mittel |
| 924234 | 1.0042 | 14 | +6,9 EUR | mittel |
| 924132 | gemischt | 20 | variabel | §8 pos-Level |

### Retroaktiv-Anwendung auf Welle-1/2 Kunden

Gate 6 muss **retroaktiv** auf alle abgeschlossenen Calculator-Tests angewendet
werden, sobald der zugehörige Kunden-Report erstellt wird. Indikation für
RN-Level-Adjustments:
- `rn_std < 0.0005` in mehr als 20 % der RNs im Testset
- Systematische fp-Cluster in der Verteilung (Bimodalität oder Multimodalität)

GEZE (9b.3): Muster-A-Treffer: 0. Aggregationsartefakt-Flags gesetzt für GB.
→ Kein RN-Level-Adjustment erkannt. Gate 6 retroaktiv: bestanden.

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

### EBM-Papst — Retroaktiv-Check Diesel-Einbettung (post-v1.5)

**Offene Frage:** Ist Diesel in den EBM-Abrechnungsstrecken-`betrag`-Werten
eingebettet, oder wurde für EBM kein Diesel-Floater verrechnet?

**Kontext:** Die EBM-9a.4.2-Analyse verwendete Abrechnungsstrecken (`EBM.xlsx`)
mit Spalten `betrag` und `toll` — keine separate Diesel-Spalte. Die
`floater_pct = (betrag − toll) / tariff − 1`-Interpretation kann daher zwei
verschiedene Dinge bedeuten:

| Szenario | Bedeutung von floater_pct | Muster-A-Interpretation |
|---|---|---|
| **Diesel = 0** (EBM hat keinen Diesel-Floater) | Reiner ERKA-/Vertragsfloater | Muster-A-Treffer sind valide; 7 % = ERKA-Aufschlag |
| **Diesel in betrag** (EBM-Diesel in `betrag` eingebettet) | ERKA-Floater + Diesel | Muster-A-Treffer könnten Diesel+Floater-Kombination sein |

**Schärfung durch CHT-B-Check (v1.6):** Die diesel_mode-Regel besagt: Diesel ist
pro (Kunde, Land) vereinbart — entweder immer oder nie. EBM-Prüfschema daher:

**Prüfschema:**
1. EBM BI-Daten (bi_top20_data.pkl, KNR 410844): `Erlöse_Diesel` per Land abfragen
   - Wenn für alle EBM-Länder `Erlöse_Diesel = 0`: EBM hat **keinen Diesel-Floater**
     → diesel_mode = `"not_contracted"` für alle EBM-Länder → floater_pct ist reiner
     Vertragsfloater → Muster-A-Narrative (7 % = ERKA-Aufschlag) bleibt valide
   - Wenn für einige Länder `Erlöse_Diesel > 0`: EBM hat Diesel für jene Länder
     → die Abrechnungsstrecken-`betrag`-Spalte enthält ggf. keinen Diesel (eigene
     Spalte im BI-System, nicht in Streckenabrechnung) → betrag = Tariff + Floater
     (Diesel separat im BI, nicht im `betrag`)
2. Cross-Check: `floater_pct = (betrag − toll) / tariff − 1` für EBM-Zeilen vor
   Jan 2026 (vor Muster-A-Aktivierungsdatum): Wenn Ratio ≈ 0,000 → kein Floater
   vor Jan 2026 → 7 % exakt im Jan 2026 = struktureller Switch = ERKA bestätigt

**Konsequenzbaum:**
- `Erlöse_Diesel = 0` für alle EBM-Länder in BI + fp ≈ 0 vor Jan 2026 → Muster-A valide
- `Erlöse_Diesel > 0` für EBM-Länder, `betrag` ohne Diesel + fp ≈ 0 vor Jan 2026 → Muster-A valide
- fp ≈ konstant vor Jan 2026 (nicht Null) → Diesel in `betrag` oder anderer Floater vorher

**Status:** Offen. Hohe Priorität. Prüfung in Etappe 9c.x als eigenständiger Retroaktiv-Commit.

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

### Welle-3-Kunden — Retroaktiv-Prüfung RN-Level-Faktor (post-9c.2a, v1.7)

**Hintergrund:** Das in CHT/BE (9c.2a) entdeckte RN-Level-Adjustment-Muster
(konsistente per-RN Faktoren ≠ 1.0 bei rn_std < 0.0005) kann potenziell auch
bei Welle-3-Kunden auftreten. Insbesondere bei Kunden mit:
- Quarterly-Floater-Mechanismen (ähnlich CHT BE-Dieselfloater)
- Kundenspezifischen Preisanpassungs-Vereinbarungen
- AX-Invoice-Batch-Konfigurationen, die pro Periode leicht variieren

**Pflicht-Prüfschema für Welle-3-Integration-Tests (HELU, HERMA, Hornschuch u.a.):**

Vor Pass-Rate-Berechnung jedes neuen Calculator-Tests:
1. Berechne pro RN: `rn_factor = median(erloes_fracht / basispreis)`, `rn_std`
2. Falls `rn_std < 0.0005 AND |rn_factor − 1| > 0.001`:
   → RN als `rn_level_adjustment` flaggen, §6b-Classifier aktivieren
3. Falls ≥ 3 RNs im Testset mit `rn_level_adjustment`:
   → Muster-Report: welche Faktoren, welche Periodizität, Richtung
   → Im Kunden-Report §8 ausweisen; nicht als Calculator-Bug werten

**Besondere Aufmerksamkeit bei Sonder-PLZ-Konsistenz:**
Analog zum CHT-IT-Befund (PLZ 20098: +6,1 % in 3 Zeilen, Calculator-Coverage-Frage)
sollten bei HELU/HERMA/Hornschuch ähnliche Sonder-PLZ-Muster (z. B. Industriegebiete
mit Thermozuschlag oder PLZ-gebundene Sondertarife) gesondert auf fp-Konsistenz
geprüft werden. Falls ≥ 2 Zeilen mit identischer PLZ konsistent fp ≠ 0 zeigen →
§8-Flag "Sonder-PLZ-Muster", manuelle Klärung ob Calculator-Lücke oder DLV-Sondertarif.

**Status:** Offen. Wird bei erstem Welle-3-Integration-Test aktiviert.

---

## Changelog

| Version | Datum | Etappe | Änderung |
|---|---|---|---|
| 1.0 | 2026-04-20 | 9a.4.2 | Initiale Erstellung; §3 floater_pct-Basis für Muster-A; §5a LDM-Fallback |
| 1.1 | 2026-04-20 | 9b.0 | §2 GEZE-Block: Maut-inklusiv, CHF-Floater als EUR-Surcharge, Reverse-Engineer-Ansatz; §3 GEZE-Zeile + engeres Muster-A-Binning für 9b.3 |
| 1.2 | 2026-04-20 | 9b.1 | §6a Sanity-Gate 5 (bedingte Komponenten nicht-null); §7 Retroaktiv-Eintrag GEZE 5e (23d6a1a im Parser-Bug-State freigegeben) |
| 1.3 | 2026-04-20 | 9b.2 | §5.0 tonnage_source-Pflichtfeld + 20%-Audit-Schwelle; GEZE-Befund 25,5% Tonnage=0 dokumentiert |
| 1.4 | 2026-04-20 | 9b.3 | §2a Positions-Level vs Sendungs-Level: Aggregations-Key-Hierarchie, Muster-B-Aggregationsartefakt-Flag, Pflichtfelder aggregation_level/key_source; §7 EBM+Fischerwerke Retroaktiv-Aggregationsebene-Prüfung; §7 GEZE 9b.3-Ergebnis (CHF-Band-Match) |
| 1.5 | 2026-04-20 | 9c.0 | §2.0 Standard-Formeln: Diesel-always-separate, Zwei-Fall-Regel (unbundled/all_in), Pflichtfelder pricing_mode + all_in_components; §2 Kunden-Blöcke realigned (Fischerwerke/EBM/GEZE) + CHT-Block neu; §3 Muster-A-Formel auf neue Notation + EBM-Sonder-Block; §3 Kundentabelle GEZE+CHT aktualisiert; §7 EBM-Diesel-Retroaktiv-Check (Szenario Diesel=0 vs Diesel-in-betrag) |
| 1.6 | 2026-04-20 | 9c.0 | §1 pre_dlv_2026-Phase + in_dlv_2025_fallback präzisiert; §2 CHT Diesel/Maut-Tabelle per Land (B-Check empirisch) + 9c.0 IT fp-Befund; §2a diesel_mode/maut_mode pro (Kunde, Land) mit Sanity-Check-Regel; CHT-Präzedenzfall BE/GR contracted vs IT/AT/ES not_contracted |
| 1.6.1 | 2026-04-20 | 9c.0 | §2a Einzelfall-all_in-Ausnahme: Diesel=0+Maut=0 bei Fracht≈split_sum → all_in_exception-Flag; Schwelle ≤1%; CHT-BE-Präzedenzfall PLZ 8550/3600 |
| 1.7 | 2026-04-20 | 9c.2a | §6b neu: RN-Level-Faktor-Detection (Gate 6); Classifier-Logik (rn_std<0.0005, rn_factor); §8-Listenformat für RN-Adjustment-Fälle; CHT/BE 9c.2a Befundtabelle; GEZE retroaktiv Gate-6-bestanden; §7 Welle-3-Retroaktiv-Pflichtprüfschema RN-Level-Faktor + Sonder-PLZ-Konsistenz |
| 1.7.1 | 2026-04-20 | 9c.2a | §3a neu: Sonder-PLZ-Aufschlag — Definition, Abgrenzung zu Muster-A, Detection-Regel (plz_fp_std<0.005, abs(fp_mean)>0.03, n≥2), Known-Cases-Tabelle (CHT/IT/20098 +6.1%, CHT/BE/8540+8560+8400 +6.3-6.4% Kortrijk West), PRIORITY-§8-Eintrag 924248/7700 (+18.7%); AX-Raten-Präzisions-Hinweis: IT=4dp, BE=2dp, Pflicht-per-Land-Validierung |
